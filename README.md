# claude-code-kit

Small, tested plugins for [Claude Code](https://docs.claude.com/en/docs/claude-code), extracted from one person's daily setup. Plain Python 3 (standard library only), no network except an optional local Ollama.

## Why these exist

Long agentic sessions fail in boring, repeatable ways:

- A coordinating session paraphrases what you asked when it briefs a subagent, and the paraphrase drifts. (**owner-words**)
- Builders grade their own homework; a green test may not check anything. (**holdouts**)
- Worktrees pile up on disk after the work is pushed. (**worktree-cleanup**)
- The memory index you carefully wrote is not looked at when it matters. (**prompt-router**)
- An MCP server quietly needs a login or has crashed, and you find out mid-task. (**mcp-health**)
- Context compaction eats the state of a multi-hour run. (**long-run**)
- Design work starts from adjectives instead of real references. (**references-first**)
- A skill "sometimes works" and nobody knows which step varies. (**skill-step-check**)

Every hook is defensive: on any error it exits 0 and stays silent, so it can never break a session.

## Install

```
/plugin marketplace add CH4RL3I/claude-code-kit
/plugin install owner-words@claude-code-kit
/plugin install holdouts@claude-code-kit
/plugin install worktree-cleanup@claude-code-kit
/plugin install prompt-router@claude-code-kit
/plugin install mcp-health@claude-code-kit
/plugin install long-run@claude-code-kit
/plugin install references-first@claude-code-kit
/plugin install skill-step-check@claude-code-kit
```

Install only what you want; the plugins are independent. Hooks need `python3` on your PATH. Run the test suite with `python3 -m unittest discover -s tests`.

---

## owner-words

**What.** A `PreToolUse` hook on `Agent` and `SendMessage`. It prefixes the brief with your latest message, verbatim:

```
FROM THE USER, word for word: "<your message>"
Brief written by Claude (the coordinating session), not by the user. The words above are context for who decided what; your task is only this brief:

<the brief>
```

**Why.** A subagent otherwise sees only the model's paraphrase of your request. With your actual words attached it can tell what you decided from what the coordinator assumed.

**Config.** `OWNER_WORDS_NAME` sets the name in the marker (`OWNER_WORDS_NAME=Alice` gives `FROM ALICE, word for word:`). Default: `the user`.

**Limits.**
- Skips tool results, meta entries, system reminders, and context-compaction summaries when looking for "your last words".
- When replying to a peer session via `SendMessage` (a `<cross-session-message` arrived after you last spoke) it adds nothing, because your last words belong to another task.
- Secret-looking strings (API keys, tokens, PEM blocks, `op://` references) are replaced by `[redacted]`; messages over 2000 characters are cut. This is a heuristic, not a guarantee.
- It reads the session transcript file (`transcript_path`) from the hook payload.

## holdouts

**What.** A full build route with hidden acceptance tests: size the work, write 3-8 user-level scenarios with the plan, build in parallel slices, then let a separate `holdout-validator` agent use the real app and run scenarios the builders never saw. Includes mutation checks ("tests with teeth") and a regression gate. Ships a skill (`holdouts`), an agent (`holdouts:holdout-validator`), a `holdout` CLI (added to PATH by the plugin) and a guard hook.

**Why.** Builders tend to grade their own homework. Hidden scenarios plus a validator that behaves like a user catch what unit tests written by the builder do not.

**Use.**
```
holdout add <project> <slug> < scenarios.md   # stored in ~/.holdouts/<project>/<slug>.md, mode 700/600
holdout ls [project]
holdout path <project> <slug>
```
Then invoke the `holdouts` skill and follow its route. The validator returns PASS/FAIL/BLOCKED per scenario with evidence.

**Config.** `HOLDOUTS_DIR` moves the storage directory (the guard then protects that path too).

**Limits.**
- The guard (`PreToolUse` on `Read|Grep|Glob|Bash|Edit|Write|MultiEdit|NotebookEdit`) denies every subagent except `holdout-validator` access to the literal `.holdouts` (or `HOLDOUTS_DIR`) and the `holdout` CLI. The main session is not restricted. It is a speed bump for honest agents, not a sandbox.
- The validator is read-only on code except for the temporary, restored mutation in the teeth check, and relies on Playwright MCP (web) or XcodeBuildMCP (iOS) when present; otherwise curl.
- Optional: the skill suggests an independent second-model code review (for example Codex) after validation; nothing depends on it.

## worktree-cleanup

**What.** Removes git worktrees that are safe to remove. Runs as a hook after a Bash command containing `git push` (`PostToolUse`) and at `SessionEnd`, as a detached background process.

**Why.** Agent workflows create many worktrees; once the branch is pushed the folder is just clutter.

**What counts as safe.** All of: not the main checkout, not locked, `git status --porcelain` empty (no untracked files either), commits are on the remote (branch fully pushed to its upstream, or HEAD contained in a remote branch), and no process has its working directory inside it. Only the folder goes (`git worktree remove`, never `--force`); the branch stays.

**Config.** Nothing is scanned until you say where your repos live:
- `WORKTREE_CLEANUP_ROOTS=/path/a:/path/b`, or
- `~/.config/worktree-cleanup/roots.txt`, one directory per line (`#` comments).

Each root is scanned one and two levels deep for directories containing a `.git` directory. Run it by hand with `python3 plugins/worktree-cleanup/scripts/worktree-cleanup`: no arguments = dry run, `--really` = remove. Removals are logged to `~/.cache/worktree-cleanup/cleanup.log`.

**Limits.** Needs `git` and `lsof`. Repositories whose `.git` is a file (worktrees, submodules) are not treated as scan targets. No fetch is performed: "pushed" is judged against the remote-tracking refs you already have.

## prompt-router

**What.** A `UserPromptSubmit` hook. Before the model answers, it matches your prompt against the one-line entries of your `MEMORY.md` index and injects the top 3 (file name plus hook text, max 600 characters), so the model knows which memory file to open.

**Why.** An index nobody consults does nothing. This makes the lookup mechanical and cheap, with no model call.

**Which memory file.** Auto-detected per Claude project: `<config dir>/projects/<cwd with non-alphanumerics replaced by "-">/memory/MEMORY.md`, trying each parent directory of the working directory. Index lines are expected as `- [Title](file.md) - one-line hook`. Set `PROMPT_ROUTER_MEMORY=/path/MEMORY.md` to pin one file.

**Ranking.** Keyword scoring (IDF weighted, light stemming, English and German stop words). Optional semantic ranking with a local embedding model through Ollama (`ollama pull embeddinggemma`); it talks to 127.0.0.1 only, caches vectors per index line, rebuilds in the background, and silently falls back to keywords if the server is slow or down.

**Config (environment).**

| Variable | Meaning |
|---|---|
| `PROMPT_ROUTER_OFF` | any value turns the hook off |
| `PROMPT_ROUTER_MEMORY` | explicit index path |
| `PROMPT_ROUTER_NAMES` | comma-separated project or tool names that count extra when matched (or one per line in `~/.config/prompt-router/names.txt`) |
| `PROMPT_ROUTER_EMBED=0` | keyword ranking only |
| `PROMPT_ROUTER_OLLAMA`, `PROMPT_ROUTER_MODEL`, `PROMPT_ROUTER_CACHE` | Ollama URL, embedding model, cache file |

**Limits.** Skips prompts under 25 characters, prompts starting with `/` or `!`, and subagent prompts. It only ever reads the index, never the memory files, and skips index lines that look like they contain a secret. Matching is lexical or embedding-based, so expect misses and the occasional irrelevant hit; the injected text is a hint, not an instruction. It does no session routing; if you want to route prompts across tmux sessions, see [cct](https://github.com/CH4RL3I/cct).

## mcp-health

**What.** A `mcp-health` command (the plugin's `bin/` is added to PATH) that runs `claude mcp list` and prints every MCP server as `ok`, `needs login` or `broken`; exit code 1 if anything needs attention. `mcp-health --notify` stays silent unless something is wrong, then sends a desktop notification (`terminal-notifier`, `osascript` or `notify-send`), for use from cron or launchd.

**Why.** Remote MCP servers lose their login and local ones crash without telling you until the tool call fails.

**Config.**
- Ignore list: one server name per line in `~/.config/mcp-health/ignore.txt` (or `MCP_HEALTH_IGNORE`). Ignored servers are still listed, marked `(ignored)`, but never alarm.
- Optional shared proxy check, if you run one local proxy that fronts several servers: `MCP_HEALTH_PROXY_PORT=8765` checks that the port accepts connections; add `MCP_HEALTH_PROXY_LOG=<file>` to also flag more than 3 restarts in the last hour, counting lines containing `MCP_HEALTH_PROXY_RESTART_MARKER`.
- `MCP_HEALTH_HOME` moves the log directory (default `~/.cache/mcp-health`).

**Limits.** Parses the human-readable output of `claude mcp list`, so a future format change can break it (it then says so and exits 2). `claude mcp list` itself can take a while with many servers.

## long-run

**What.** A skill that has Claude keep a `STATE.md` (Status, Tests, Findings, Dead ends, Next step) during long unattended runs, plus two hooks: `PreCompact` records a snapshot, and `SessionStart` (matcher `compact`) re-injects `STATE.md` (max 4000 characters) after compaction, with a warning if it was not refreshed before the compaction.

**Why.** Compaction summaries lose detail, especially dead ends. A file the model maintains itself survives.

**Config.** `LONG_RUN_BLOCK_ONCE=1` makes the first compaction of a session be blocked while `STATE.md` is older than 10 minutes, with a reason telling the model to update it. Off by default because blocking an automatic compaction that is recovering from a context-limit error fails that request. `LONG_RUN_STATE_DIR` moves the snapshot directory.

**Limits.** A `PreCompact` hook cannot inject instructions into the model; it can only block. So the default is a snapshot and a warning afterwards. Looks for `STATE.md` or `.claude/STATE.md` in the session's working directory only.

## references-first

**What.** A skill for anything visual (site, app screen, deck, logo, animation): ask three questions, collect 4-6 live references with screenshots and measurements, show them, wait for approval, write the agreed direction into the plan, then build and compare against the main reference.

**Why.** Models converge on generic design when they start from words.

**Limits.** It stops and asks, so it is not for small tweaks on an established design. It uses a browser tool (for example Playwright MCP) to open references.

## skill-step-check

**What.** A skill that debugs an inconsistent skill: map it into steps tagged deterministic, probabilistic or human; run it three times on one fixed input saving each step's output; diff per step; fix the first step that varies by type; lock the fix in as an eval case for `claude plugin eval`.

**Why.** "It sometimes works" is not actionable; "step 3 varies" is.

**Limits.** It costs three real runs of the skill; use dry-run modes so no pushes, mails or paid calls happen.

---

## License

MIT, see [LICENSE](LICENSE).
