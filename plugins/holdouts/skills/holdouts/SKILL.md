---
name: holdouts
description: "Full build route with hidden acceptance tests: route by size, write holdout scenarios with the plan, parallel builders on vertical slices, a validator that uses the app like a user and runs holdouts the builders never saw, then code review and an intent check. Use for holdouts, hidden acceptance tests, validate like a user, full build route, or building a larger feature with AI agents."
---

# Holdouts

Builders tend to grade their own homework. Holdouts are user-level acceptance scenarios written with the plan and kept from the builders; a separate validator runs them against the real app. Bounded, no adversarial loops.

## 1. Route by size first

| Size | Route |
|---|---|
| Small (one area, clear spec, easily reversible) | Fast: one builder + validator. No plan review, no holdout file; the validator gets the acceptance criteria and uses the app. |
| Big or brownfield (several slices, shared state, money/auth/data) | Full: plan the user approves, holdouts, parallel slices, validator, independent code review, the user checks intent. |

When unsure, ask the user one question: small or big? Choosing models per role is up to you; this skill does not decide it. If you have a plan-hardening step (for example an independent second-model review of the plan), run it inside step 1; this skill sits around it, not instead of it.

## 2. Full route

1. **Plan.** Goal, observable acceptance criteria, vertical slices (each slice ships user-visible behavior end to end, with owned files so parallel builders do not collide). The user approves.
2. **Holdouts, written with the plan.** 3-8 concrete user-level scenarios, Given/When/Then, real data, exact screens/flows/endpoints. Cover the happy path, one failure path, one permission/role edge, and one thing the plan does not obviously mention. Store with the script, never in the repo or a worktree, never in a builder prompt:
   ```
   holdout add <project> <feature-slug> <<'EOF'
   # Scenario 1: <title>
   Given ... When ... Then ...
   EOF
   holdout ls <project>      # list
   holdout path <project> <feature-slug>
   ```
   Files land in `~/.holdouts/<project>/<slug>.md` (dir mode 700). The guard hook `holdout-guard` blocks every subagent except `holdout-validator` from touching `.holdouts`; the main session may.
3. **Build.** Parallel builders, one per slice, each gets the plan and its slice only. Builders never get holdouts, their path, or hints about their content. Builders run their own tests; that is not validation.
4. **Validate.** Spawn the `holdout-validator` agent with project, slug, how to reach the app, test accounts. Tools by platform: Playwright MCP for web, XcodeBuildMCP or idb simulator for iOS, curl for APIs. Start the app fresh and check the running build is the new one (PID/mtime) before validating. Also run the mutation check and regression gate of section 3.
5. **Fail loop (max 2 rounds).** The validator returns, per scenario, PASS/FAIL/BLOCKED with evidence: screenshot path, log excerpt, exact failing step, expected vs actual. On FAIL send the builder the failure evidence (steps, expected, actual, screenshot), not the scenario file. Rebuild, re-validate. After 2 rounds with failures, stop and ask the user. No further ping-pong.
6. **Code review last**, only after validation passes: an independent reviewer (`/code-review`, or a second model such as Codex if you use one). Fix findings, re-run the failing scenarios only if the fix touches their path.
7. **Intent check for the user.** A short list (max 7 lines): what was built, what the validator proved, what it could not check, anything the plan decided that they should confirm, and what to click first. The user checks intent; agents already checked behavior.

## 3. Tests with teeth

Reason: a green check does not necessarily check anything. Green proves nothing until the check has been seen red.
- **Mutation check.** Every NEW automated test written for the feature must be proven able to fail. The validator (or the builder before handover) temporarily breaks the covered code (invert a condition, return a wrong value, comment out the call), runs the test, confirms RED, restores that one file (`git stash` / `git checkout -- <file>`, never touching unrelated changes), confirms GREEN. A test that stays green under mutation is "no teeth": FAIL for its scenario. Record command + result for each.
- **Regression gate.** Before "done", run the project's full existing suite (real command from package.json/Makefile/README, e.g. `npm test`, `pnpm -w test`). Any red is FAIL with evidence; a suite that ran zero tests counts as not run.

## 4. Quality gates (every build)
- A test must fail first; never trust one you have not seen red.
- Never simulate the failure you are fixing; reproduce it for real.
- Fix root causes, not append-only patches on top: when a value, rule or position is wrong, change it where it is defined; never add a later step that overrides it ("move it here, then there"). Before handover, `git diff` must show the original line changed, not a compensating addition elsewhere; if a patch-on-top is unavoidable, say why in the report.
- Bug report (steps, expected, actual) before the fix.
- No "done" without evidence: command output, screenshot, response excerpt.
- Full suite green and mutation evidence recorded before handover.

## 5. Validator output contract

```
### S<n> <title>: PASS | FAIL | BLOCKED
Steps run / Expected / Actual / Evidence
...
EXTRA: <exploratory findings>
TEETH: <new test> mutated <file:change> -> RED, restored -> GREEN | no teeth
SUITE: <command> -> <pass/fail counts>
VERDICT: PASS | FAIL (n of m)
```
A PASS without evidence counts as not run. The validator is read-only on code.

## Notes
- Holdouts are for acceptance, not unit tests. Keep them few and user-level.
- After a clean run, keep the file; reuse it as regression scenarios for the next change to that feature.
- The guard hook ships with this plugin (PreToolUse on `Read|Grep|Glob|Bash|Edit|Write|MultiEdit|NotebookEdit`). It is a speed bump for honest agents (it matches the literal `.holdouts` and the `holdout` CLI), not a sandbox. Scenarios live in `~/.holdouts` unless `HOLDOUTS_DIR` is set.
- Spawn the validator as `holdouts:holdout-validator` (plugin agents are namespaced).
