#!/usr/bin/env python3
"""Write the Results section of README.md from results/summary.json, so every number in
the README is produced by mine.py and cannot drift from it."""
import json, re

s = json.load(open("results/summary.json"))
w = s["window"]
out = [f"Window **{w['since']} to {w['until']}**, one operator's Claude Code transcripts.", "",
       "| | |", "|---|---|",
       f"| Sessions | {s['sessions']:,} |",
       f"| Tool calls | {s['tool_calls']:,} |",
       f"| Hard failures (`is_error: true`) | {s['hard_failures']:,} |",
       f"| **Failure rate** | **{s['failure_rate_pct']}%** |", "",
       "### Failure taxonomy", "", "| Category | Count | Share |", "|---|---:|---:|"]
out += [f"| {t['category']} | {t['count']:,} | {t['share_pct']}% |" for t in s["taxonomy"]]
out += ["", f"### Failure rate by tool (tools with 200+ calls)", "",
        "| Tool | Failures / calls | Rate |", "|---|---:|---:|"]
out += [f"| `{t['tool']}` | {t['failures']:,} / {t['calls']:,} | {t['rate_pct']}% |" for t in s["per_tool"]]
out += ["", "### Most common redacted error signatures", ""]
for cat, sigs in s["top_signatures"].items():
    if sigs:
        out.append(f"**{cat}**")
        out.append("```")
        out += [f"{n:5d}  {sig}" for sig, n in sigs]
        out.append("```")

readme = open("README.md").read()
block = "<!-- RESULTS:START -->\n" + "\n".join(out) + "\n<!-- RESULTS:END -->"
readme = re.sub(r"<!-- RESULTS:START -->.*<!-- RESULTS:END -->", lambda _: block, readme, flags=re.S)
open("README.md", "w").write(readme)
print("README results section regenerated")
