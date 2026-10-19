---
name: skill-step-check
description: Find out why a skill gives inconsistent results by splitting it into steps and measuring which step varies. Use when a skill "sometimes works", results differ between runs, or before trusting a skill for unattended work. Complements `claude plugin eval` suites (which score whole outcomes).
---

# Check a skill step by step

1. **Map the steps.** Read the skill and write a numbered step list into `<skill>/evals/steps.md`. Tag each step: **deterministic** (code/script could do it identically every time), **probabilistic** (needs model judgment), **human** (needs the user).
2. **Run with saved steps.** Run the skill on one fixed, realistic input three times. Have each step write its output to `<skill>/evals/runs/<run>/<step>.md` (or json). No real side effects: no pushes, mails, deploys, no paid API quota; use dry-run modes or mock the external call.
3. **Compare.** For each step, diff the three outputs. Report per step: stable / varies (how) / wrong. The first step that varies is where to fix.
4. **Fix by type.** Deterministic step that varies -> move it into a script. Probabilistic step that varies too much -> narrower instruction, an example, or a check after it. Human step skipped -> make it an explicit stop.
5. **Lock it in.** Turn the fixed step into an eval case (`evals/<case>/prompt.md` + grader) so `claude plugin eval` catches a regression. Delete `evals/runs/` afterwards.
