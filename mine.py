#!/usr/bin/env python3
"""Measure how an AI coding agent's tool calls fail, from your own Claude Code transcripts.

Everything runs locally. The output is aggregates only: no file names, no project
folders, no raw messages. Error text is reduced to redacted signatures, and a signature
is only kept if it occurs at least MIN_SIGNATURE_COUNT times.

  python3 mine.py --since 2026-07-07 --until 2026-10-22
  python3 mine.py --root /path/to/transcripts --out results/summary.json
"""
import argparse, collections, getpass, glob, json, os, re

MIN_SIGNATURE_COUNT = 5
PER_TOOL_MIN_CALLS = 200

# Ordered: first match wins. Patterns only ever classify calls the harness already
# flagged with is_error; they never decide what counts as a failure.
TAXONOMY = [
    ("context_budget_exceeded", r"exceeds maximum allowed (size|tokens)|prompt is too long|context (window|length) exceeded"),
    # Guardrails doing their job (hooks, auto-mode classifier, sleep blocks, concurrency caps).
    # The harness flags these is_error, but they are policy decisions, not tool faults.
    ("harness_policy_block",    r"BLOCKED by|Blocked: sleep|denied by the Claude Code auto mode classifier|"
                                r"hook did not respond|PreToolUse hook|Concurrent subagent limit"),
    ("browser_focus_lost",      r"Cannot access a chrome-extension"),
    ("missing_precondition",    r"call read_page first|ref map not initialized|use `?navigate`? first|requires a prior screenshot|"
                                r"no longer exists\. call|ref is stale|no site is open|not in Claude's tab group"),
    ("permission_denied",       r"permission (denied|to use)|requested permissions|user (denied|doesn't want)|not allowed"),
    ("file_not_found",          r"no such file|does not exist|ENOENT|file not found|cannot find"),
    ("stale_edit_context",      r"has (not )?been (read|modified)|string not found|old_string|not unique|must read"),
    ("command_not_found",       r"command not found|not recognized|is not installed|No module named"),
    ("timeout",                 r"timed? ?out|deadline exceeded|ETIMEDOUT"),
    ("disk_full",               r"ENOSPC|no space left on device"),
    ("network_auth",            r"\b(401|403|429|502|503)\b|unauthorized|forbidden|rate limit|ECONNREFUSED|connection refused|"
                                r"navigation to .{0,40}(denied|failed)|net::ERR_"),
    ("syntax_runtime",          r"Traceback|SyntaxError|TypeError|ValueError|KeyError|AttributeError|NameError|panicked"),
    ("invalid_tool_input",      r"InputValidationError|invalid (input|argument|parameter)|validation (failed|error)|required (property|parameter)"),
    ("nonzero_exit",            r"^Exit code \d+"),
]
TAXONOMY = [(name, re.compile(rx, re.I)) for name, rx in TAXONOMY]
# Case-sensitive on purpose: the old case-insensitive "FAIL" pattern swallowed every "failed".
TEST_BUILD = re.compile(r"\bFAILED\b|\bFAIL\b|AssertionError|[Bb]uild failed|[Cc]ompilation error|\b\d+ (tests? )?failed\b")

# Signatures are only published for categories whose text the tool or harness writes.
# Free-form output (shell commands, tracebacks, anything unclassified) can contain private
# content, so those categories are counted but never quoted.
QUOTABLE = {"context_budget_exceeded", "harness_policy_block", "browser_focus_lost", "missing_precondition",
            "permission_denied", "file_not_found", "stale_edit_context", "command_not_found", "timeout",
            "disk_full", "network_auth", "invalid_tool_input", "test_build_fail"}
SECRETISH = re.compile(r"api[_-]?key|token|secret|password|bearer|\bsk-|gsk_", re.I)


def _names():
    """Operator names to redact: the OS login plus AFS_REDACT_NAMES (comma separated).
    Kept out of the code on purpose so no real name is ever published with it."""
    names = [getpass.getuser()] + os.environ.get("AFS_REDACT_NAMES", "").split(",")
    names = sorted({n.strip() for n in names if len(n.strip()) >= 3}, key=len, reverse=True)
    return re.compile(r"(?i)\b(" + "|".join(map(re.escape, names)) + r")\w*('s)?") if names else None


NAMES = _names()


def tool_label(name):
    """Built-in tools keep their name. MCP tools are collapsed so the output never
    reveals which private servers or connectors the operator has installed."""
    if not name.startswith("mcp__"):
        return name
    server, _, tool = name[5:].partition("__")
    return f"browser:{tool}" if re.search(r"browser|chrome", server, re.I) else "mcp (other)"


def classify(text):
    for name, rx in TAXONOMY:
        if name == "nonzero_exit" and TEST_BUILD.search(text):
            return "test_build_fail"
        if rx.search(text):
            return name
    return "test_build_fail" if TEST_BUILD.search(text) else "unclassified"


def redact(text):
    s = re.sub(r"<[^>]+>", " ", text)
    if re.search(r"BLOCKED by", s):
        return "BLOCKED by HOOK (user-defined hook message removed)"
    s = re.sub(r"@\w[\w.]*", "@HANDLE", s)
    s = NAMES.sub("USER", s) if NAMES else s
    s = re.sub(r"https?://\S+", "URL", s)
    s = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "EMAIL", s)
    s = re.sub(r"(~|/|[A-Za-z]:\\)[^\s'\"`)]+", "PATH", s)
    s = re.sub(r"\b[\w.-]+\.(xlsx|docx|pptx|pdf|csv|json|py|ts|tsx|js|md|html|txt|png|jpg|mp4)\b", "FILE", s, flags=re.I)
    s = re.sub(r"\b[0-9a-f-]{8,}\b", "ID", s, flags=re.I)
    s = re.sub(r"\d+", "N", s)
    return re.sub(r"\s+", " ", s).strip()[:90]


def _text(body):
    if isinstance(body, list):
        body = " ".join(b.get("text", "") for b in body if isinstance(b, dict))
    return body if isinstance(body, str) else ""


def mine(paths, since=None, until=None):
    calls, fails = collections.Counter(), collections.Counter()
    cats, sigs = collections.Counter(), collections.defaultdict(collections.Counter)
    sessions = 0
    for fp in paths:
        id2tool, active = {}, False
        try:
            fh = open(fp, errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                day = (rec.get("timestamp") or "")[:10]
                if (since or until) and (not day or (since and day < since) or (until and day > until)):
                    continue
                content = (rec.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for blk in content:
                    if not isinstance(blk, dict):
                        continue
                    if blk.get("type") == "tool_use":
                        label = tool_label(blk.get("name", "?"))
                        calls[label] += 1
                        active = True
                        if blk.get("id"):
                            id2tool[blk["id"]] = label
                    elif blk.get("type") == "tool_result" and blk.get("is_error") is True:
                        label = id2tool.get(blk.get("tool_use_id"), "unknown")
                        fails[label] += 1
                        text = _text(blk.get("content"))[:600]
                        cat = classify(text)
                        cats[cat] += 1
                        sig = redact(text)
                        if sig and cat in QUOTABLE and not SECRETISH.search(sig):
                            sigs[cat][sig] += 1
        sessions += active

    total_calls, total_fails = sum(calls.values()), sum(fails.values())
    return {
        "window": {"since": since, "until": until},
        "sessions": sessions,
        "tool_calls": total_calls,
        "hard_failures": total_fails,
        "failure_rate_pct": round(100 * total_fails / total_calls, 2) if total_calls else 0.0,
        "taxonomy": [{"category": c, "count": n, "share_pct": round(100 * n / total_fails, 1)}
                     for c, n in cats.most_common()] if total_fails else [],
        "per_tool": sorted(({"tool": t, "calls": calls[t], "failures": fails.get(t, 0),
                             "rate_pct": round(100 * fails.get(t, 0) / calls[t], 2)}
                            for t in calls if calls[t] >= PER_TOOL_MIN_CALLS),
                           key=lambda r: -r["rate_pct"]),
        "top_signatures": {c: [[s, n] for s, n in sigs[c].most_common(5) if n >= MIN_SIGNATURE_COUNT]
                           for c in cats},
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--since"), ap.add_argument("--until")
    ap.add_argument("--out", default="results/summary.json")
    a = ap.parse_args()
    files = glob.glob(os.path.join(a.root, "**", "*.jsonl"), recursive=True)
    summary = mine(files, a.since, a.until)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(summary, open(a.out, "w"), indent=2)
    print(f"{summary['tool_calls']:,} tool calls, {summary['hard_failures']:,} hard failures "
          f"({summary['failure_rate_pct']}%) across {summary['sessions']:,} sessions -> {a.out}")
