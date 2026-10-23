"""Proves the counting and the redaction on a synthetic transcript. Run: python3 test_mine.py"""
import json, os, tempfile
os.environ["AFS_REDACT_NAMES"] = "Alice"   # must be set before mine is imported
from mine import mine, redact, tool_label


def rec(day, *blocks):
    return json.dumps({"timestamp": f"{day}T10:00:00Z", "message": {"content": list(blocks)}})


def use(i, name):
    return {"type": "tool_use", "id": i, "name": name}


def res(i, err, text):
    return {"type": "tool_result", "tool_use_id": i, "is_error": err, "content": text}


lines = [
    rec("2026-08-01", use("a", "Read"), use("b", "Bash"), use("c", "mcp__claude-in-chrome__navigate"),
        use("d", "mcp__acme-private__render"), use("e", "Edit")),
    rec("2026-08-01", res("a", True, "File content (900KB) exceeds maximum allowed size (256KB)"),
        res("b", False, "ok"), res("c", True, "No site is open in this tab. Use `navigate` first."),
        res("d", True, "ENOENT: no such file /Users/someone/Client-Secret-Project/x.xlsx")),
    rec("2026-01-01", use("z", "Bash")),  # outside the window
]

with tempfile.TemporaryDirectory() as d:
    p = os.path.join(d, "s.jsonl")
    open(p, "w").write("\n".join(lines))
    s = mine([p], since="2026-07-01", until="2026-10-31")

assert s["tool_calls"] == 5 and s["hard_failures"] == 3 and s["sessions"] == 1, s
cats = {t["category"]: t["count"] for t in s["taxonomy"]}
assert cats == {"context_budget_exceeded": 1, "missing_precondition": 1, "file_not_found": 1}, cats
assert tool_label("mcp__acme-private__render") == "mcp (other)"          # private server name hidden
assert tool_label("mcp__claude-in-chrome__navigate") == "browser:navigate"
r = redact("ENOENT: no such file /Users/someone/Client-Secret-Project/x.xlsx me@x.com")
assert "someone" not in r and "Client" not in r and "x.com" not in r, r
assert "Client-Secret" not in json.dumps(s)                               # nothing identifying in output
from mine import classify
assert classify("navigation to https://x was denied or failed") == "network_auth"
assert classify("Failed to execute JavaScript: Cannot access a chrome-extension:// URL") == "browser_focus_lost"
assert classify("BLOCKED by vault-guard. Vault is Alice's own writing") == "harness_policy_block"
assert classify("Exit code 1\n2 tests FAILED") == "test_build_fail"
assert classify("Exit code 2") == "nonzero_exit"
r2 = redact("BLOCKED by vault-guard. Vault/Notes is Alice's own writing")
assert "vault-guard" not in r2 and "Alice" not in r2, r2
assert "Alice" not in redact("cannot open /tmp/x for alice")
assert redact("ping @somecreator now") == "ping @HANDLE now"
assert "Vault" not in redact("BLOCKED by vault-guard. Vault/Notes is private")
print("test_mine ok")
