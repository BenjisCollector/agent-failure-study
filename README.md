# Agent Failure Study

**Measure how your AI coding agent's tool calls fail, using your own Claude Code logs.**

When an agent loses time, it is usually not one dramatic mistake. It is hundreds of small
tool failures: a file read that was too big, a browser click on a tab that no longer exists,
an edit to a file it never read. This repository is a small, reproducible way to count them,
sort them into causes, and see which tools and habits are worth fixing first.

It runs entirely on your machine. Nothing is uploaded.

## Run it on your own logs

```bash
python3 mine.py --since 2026-07-07 --until 2026-10-22   # writes results/summary.json
python3 report.py                                        # rewrites the Results section below
python3 test_mine.py                                     # proves the counting and the redaction
```

`mine.py` reads `~/.claude/projects/**/*.jsonl` by default (`--root` to point elsewhere).
No dependencies beyond the Python standard library.

## How it counts

- **A failure is whatever the harness itself marked `is_error: true`.** Each failing
  `tool_result` is joined back to its `tool_use` by id, so it is attributed to the right tool.
  Pattern matching is only used to *categorise* failures, never to decide what counts as one.
- **Categories are an ordered list of patterns, first match wins.** They live at the top of
  `mine.py`, so you can read, dispute and change them.
- **Guardrails are separated from faults.** A hook that blocks a write, the auto-mode
  classifier denying an action, or a concurrency cap is flagged as an error by the harness,
  but it is a policy decision working as intended. These go to `harness_policy_block`.

## Privacy

The output is aggregates only, designed so the results can be published safely:

- no file names, project folders or raw messages are ever written;
- MCP tools are collapsed to `browser:<tool>` or `mcp (other)`, so the output does not
  reveal which private servers or connectors you have installed;
- error text is reduced to redacted signatures (paths, files, emails, URLs, ids, handles,
  numbers and the operator's name are replaced) and a signature is kept only if it
  occurs at least 5 times;
- signatures are quoted only for categories whose text the tool or harness writes. Shell
  output, tracebacks and anything unclassified are counted but never quoted, because they
  can contain anything.

## Results

<!-- RESULTS:START -->
Window **2026-07-07 to 2026-10-22**, one operator's Claude Code transcripts.

| | |
|---|---|
| Sessions | 1,906 |
| Tool calls | 88,521 |
| Hard failures (`is_error: true`) | 3,329 |
| **Failure rate** | **3.76%** |

### Failure taxonomy

| Category | Count | Share |
|---|---:|---:|
| unclassified | 716 | 21.5% |
| nonzero_exit | 684 | 20.5% |
| harness_policy_block | 312 | 9.4% |
| syntax_runtime | 271 | 8.1% |
| file_not_found | 253 | 7.6% |
| timeout | 238 | 7.1% |
| missing_precondition | 160 | 4.8% |
| network_auth | 141 | 4.2% |
| stale_edit_context | 122 | 3.7% |
| browser_focus_lost | 121 | 3.6% |
| invalid_tool_input | 110 | 3.3% |
| context_budget_exceeded | 98 | 2.9% |
| permission_denied | 39 | 1.2% |
| command_not_found | 37 | 1.1% |
| test_build_fail | 15 | 0.5% |
| disk_full | 12 | 0.4% |

### Failure rate by tool (tools with 200+ calls)

| Tool | Failures / calls | Rate |
|---|---:|---:|
| `browser:find` | 120 / 632 | 18.99% |
| `browser:file_upload` | 19 / 231 | 8.23% |
| `browser:navigate` | 90 / 1,132 | 7.95% |
| `browser:browser_batch` | 372 / 5,501 | 6.76% |
| `browser:get_page_text` | 26 / 422 | 6.16% |
| `Edit` | 191 / 3,334 | 5.73% |
| `browser:javascript_tool` | 209 / 3,816 | 5.48% |
| `browser:computer` | 213 / 4,462 | 4.77% |
| `mcp (other)` | 53 / 1,239 | 4.28% |
| `Bash` | 1,487 / 40,527 | 3.67% |
| `browser:tabs_create_mcp` | 6 / 205 | 2.93% |
| `WebFetch` | 63 / 2,679 | 2.35% |
| `Agent` | 49 / 2,135 | 2.3% |
| `Write` | 53 / 2,319 | 2.29% |
| `browser:read_page` | 7 / 401 | 1.75% |
| `Read` | 203 / 13,048 | 1.56% |
| `SendUserFile` | 6 / 470 | 1.28% |
| `Skill` | 3 / 261 | 1.15% |
| `browser:tabs_context_mcp` | 3 / 408 | 0.74% |
| `WebSearch` | 14 / 2,073 | 0.68% |
| `SendMessage` | 1 / 608 | 0.16% |
| `ToolSearch` | 0 / 864 | 0.0% |

### Most common redacted error signatures

**context_budget_exceeded**
```
   70  File content (N.NKB) exceeds maximum allowed size (NKB). Use offset and limit parameters t
```
**harness_policy_block**
```
   45  BLOCKED by HOOK (user-defined hook message removed)
   42  PreToolUse hook did not respond before its timeout (host client may be unreachable). The t
   37  Concurrent subagent limit reached. You can run N subagents at once. Do not retry. If the u
   26  Permission for this action was denied by the Claude Code auto mode classifier. Reason: Blo
   12  Blocked: sleep N followed by: cat PATH To wait for a condition, use Monitor with an until-
```
**file_not_found**
```
   49  File does not exist. Note: your current working directory is PATH
   17  Exit code N Traceback (most recent call last): File " ", line N, in FileNotFoundError: [Er
    8  Exit code N ls: PATH No such file or directory
    7  File does not exist. Note: your current working directory is PATH Did you mean FILE?
    6  The MCP server returned HTTP N for this tool call. Server error detail: Invalid JSON paylo
```
**permission_denied**
```
   30  The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it 
```
**stale_edit_context**
```
   95  File has not been read yet. Read it first before writing to it.
   17  File has been modified since read, either by the user or by a linter. Read it again before
```
**timeout**
```
   45  Exit code N Command timed out after Nm Ns
   33  computer timed out after Ns. The Browser pane may be stuck (modal dialog, navigation hang,
   32  Failed to execute JavaScript: CDP sendCommand "Runtime.evaluate" timed out after Nms on ta
   12  timeout of Nms exceeded
   10  computer timed out after Ns. The Browser pane is currently hidden. The pane may be stuck (
```
**disk_full**
```
    9  ENOSPC: no space left on device, open 'PATH'
```
**invalid_tool_input**
```
   14  MCP error -N: Input validation error: Invalid arguments for tool computer: [ { "origin": "
   13  MCP error -N: Input validation error: Invalid arguments for tool computer: [ { "expected":
   13  InputValidationError: Read was called with input that could not be parsed as JSON. You sen
   11  MCP error -N: Input validation error: Invalid arguments for tool navigate: [ { "expected":
    7  InputValidationError: WebSearch was called with input that could not be parsed as JSON. Yo
```
**missing_precondition**
```
   61  no read_page tree cached; call read_page first
   45  Tab ID is not in Claude's tab group for this session. Tools can only target tabs inside th
   20  Tab ID no longer exists. Call tabs_context_mcp to get current tabs.
   16  No site is open in this tab. Use `navigate` first.
    7  ref map not initialized; call read_page first
```
**command_not_found**
```
    8  Exit code N Traceback (most recent call last): File " ", line N, in ModuleNotFoundError: N
    5  Exit code N (eval):N: command not found: timeout
```
**network_auth**
```
   23  navigation to URL was denied or failed
    9  Error: net::ERR_FAILED
```
**browser_focus_lost**
```
   28  Failed to execute JavaScript: Cannot access a chrome-extension:PATH URL of different exten
   26  Error capturing screenshot: Cannot access a chrome-extension:PATH URL of different extensi
   13  actions[N] (computer:left_click) failed: Error clicking: Cannot access a chrome-extension:
    8  Error clicking: Cannot access a chrome-extension:PATH URL of different extension
    7  actions[N] (computer:screenshot) failed: Error capturing screenshot: Cannot access a chrom
```
<!-- RESULTS:END -->

## What the numbers say

- **Browser automation is the least reliable class of tool** in this window, several times
  the failure rate of reading and writing files. Much of that is hidden state: the agent
  acts on a page tree, tab or element that is not there any more (`missing_precondition`),
  or the browser loses focus to another window (`browser_focus_lost`). A tool whose call
  can fail on state the agent cannot see should either establish that state itself or
  expose it through a cheap query.
- **A meaningful share of "failures" are guardrails, not faults.** Any agent failure rate
  that does not separate policy blocks from tool errors overstates how unreliable the
  tools are.
- **Reading a file that is too large is a real but small category.** It is cheap to prevent
  by checking size before reading.

## Limitations

- `is_error` measures tool-level failure, not task-level success. A session with no tool
  errors can still produce the wrong answer.
- One operator, one harness configuration, one window. The rates describe this tool mix,
  not the tools in general.
- About two fifths of failures cannot be categorised from their message alone
  (`nonzero_exit` and `unclassified`). Better categories need more context than the
  error text.
- Claude Code prunes old transcripts, so the window is limited to what is still on disk.

## Correction

An earlier version of this repository (September 2026) reported figures from a run that
could not be reproduced from the published code, and they were withdrawn on 23 October
2026. Every number on this page is now produced by `mine.py` and written by `report.py`.

## License

MIT
