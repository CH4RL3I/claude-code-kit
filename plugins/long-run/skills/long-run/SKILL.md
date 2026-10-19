---
name: long-run
description: Use for long unattended or multi-hour runs (big builds, audits, migrations) so progress survives context compaction. Creates and maintains a STATE.md in the working directory.
---

# Long run: STATE.md

At the start of a long run, create `STATE.md` in the project root (or `.claude/STATE.md`) with these sections:

```
# STATE
## Status        (done / in progress / blocked, with commit or branch)
## Tests         (what ran, result, how to rerun)
## Findings      (facts learned, with file or command evidence)
## Dead ends     (what failed and why, so it is not retried)
## Next step     (one concrete action)
```

Rules:
- Update it after every milestone, failed attempt, and before long waits, not only at the end. Keep it under about 3,000 characters; compress old entries.
- Facts only. Mark guesses as guesses.
- Do not commit it unless asked.
- The hooks `state-before-compact` (PreCompact, records a snapshot) and `state-after-compact` (SessionStart "compact", injects STATE.md after compaction) ship with this plugin and rely on this file. A PreCompact hook cannot instruct the model, so keep the file current yourself.
- After a compaction, treat STATE.md as the source of truth over the summary; if they disagree, check the repo and fix the file.
