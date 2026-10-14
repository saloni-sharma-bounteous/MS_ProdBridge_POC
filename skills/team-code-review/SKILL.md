---
name: team-code-review
description: Review a diff, PR, branch or folder against the team's written coding standards and general best practices, and report findings by severity with the standard each one breaks. Use when asked to review code, check a PR against our standards, or before release-to-qa.
---

# Team code review

Goal: a review a tech lead would sign. Every finding cites the standard it breaks, says why it matters, and shows the fix. Style opinions that no standard backs are left out.

## Inputs

1. The target: a PR number, branch, commit range, folder or the working-tree diff. If none is given, review the working-tree diff against `main`.
2. The standards, in this order of authority:
   1. `standards/` or `CODING_STANDARDS.md` in the repo, if present (the team's own rules win).
   2. `references/team-standards.md` in this skill (house defaults; edit it to match the team).
   3. `references/best-practices.md` (language-neutral good practice, used to fill gaps).
   Read the first one that exists in full, then the others for gaps. If two disagree, the higher one wins and you say so.
3. The spec (`handoff/spec.md`) and stories, if they exist, to check that business rules are implemented rather than guessed.

## Steps

1. **Scope the change.** List changed files and group them (API, domain, persistence, config, tests, build). Read each changed file in full, not just the hunks, plus the callers of any changed public method. Skip generated code, lockfiles and vendored files; say that you skipped them.
2. **Run what exists.** Build, tests, linters and `java_check.py` (from `java-spring-service`) if the project has them. Report failures as findings; do not run anything that deploys or needs secrets. If a tool cannot run here, say so.
3. **Review in this order**, stopping to note a finding as soon as you see it:
   1. Correctness and spec fit: wrong logic, boundary errors, missing cases, rules invented or ignored.
   2. Security: authorisation on the server, input validation, injection, secrets, personal data in logs or responses.
   3. Data and errors: transactions, migrations, null handling, swallowed exceptions, retries and timeouts.
   4. Tests: does each changed behaviour have a test, including negative and boundary cases? Are tests deterministic?
   5. Design: layering, duplication, naming, size of functions and classes, needless cleverness.
   6. Operability: logging, metrics, config, backwards compatibility, docs.
4. **Verify each finding** before reporting it: re-read the code, confirm the failure scenario is reachable, and drop it if it is not. Say "possible" and what you could not check where you are unsure.
5. **Report** using the format below.

## Report format

```
# Code review: <target>
Verdict: APPROVE | APPROVE WITH COMMENTS | REQUEST CHANGES
Reviewed: <files, commit range>. Not reviewed: <skipped and why>.
Checks run: <build/test/lint results, or "none run: reason">.

## Must fix (blocks merge)
1. <file:line> <one-sentence problem>
   Standard: <ID or section, e.g. TS-SEC-03>
   Why: <concrete failure>
   Fix: <short code or description>

## Should fix
## Consider
## Good practice noticed   (one or two lines; reinforce what to keep)
## Open questions for the author
```

Severity: **Must fix** = bug, security hole, data loss, broken standard marked MUST, or missing test for a spec rule. **Should fix** = breaks a SHOULD standard or hurts maintainability. **Consider** = optional improvement. REQUEST CHANGES if any Must fix remains.

## Rules

- No finding without a file and line and a named standard (or "best practice: <name>" when the team standards are silent).
- Be specific and brief; one finding per issue; group repeats ("same pattern in 6 places: ...").
- Do not edit code unless asked. If asked to fix, fix only the listed findings and re-run the checks.
- Never print secret values or personal data found in the code; point to the location.
- Do not invent standards. If the team's rule is unclear, put it in Open questions.
- Judge the change, not the author. Prefer "this will..." over "you should have...".

## Output

The report in the chat, and `handoff/code-review.md` if a handoff folder exists. Gate: the author fixes Must-fix items and a reviewer re-runs this skill on the new diff before merge.

## Self-learning

At the end of every run, reflect on what went wrong or was slow, what the user corrected, and what was missing or unclear in this skill. If you find a concrete improvement, do not edit this skill on your own. Instead:

1. Propose it as a short list. For each item give the section affected, the exact change, and the reason (what it prevents next run).
2. Ask the user to approve, edit, or reject each item.
3. Apply only the approved items to this `SKILL.md` (or its scripts, templates or references), keeping edits small. Tell the user what changed.
4. If nothing needs changing, say so in one line. Never record secrets, personal data or one-off project details as lessons.
