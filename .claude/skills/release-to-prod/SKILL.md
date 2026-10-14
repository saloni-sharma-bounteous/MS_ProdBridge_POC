---
name: release-to-prod
description: Take a QA-approved service to production safely - release-readiness gate, rollback plan, named human approvals, deployment through the team's pipeline, and post-release verification. Use after release-to-qa passes, when asked "release to production", "is it ready for prod", "go-live checklist".
---

# Release to production

Production is a person's decision. This skill prepares the evidence and the plan; a named approver authorises; the team's pipeline deploys.

## 1. Readiness gate (every line must be yes; otherwise stop and name what blocks)

- QA report shows every acceptance criterion passed or explicitly accepted by the business owner, with a QA sign-off name.
- No open Critical or High defects or security findings.
- Same image/artifact that passed QA is being promoted (same digest), not rebuilt.
- Database migrations are versioned Flyway scripts, tested on a copy of production-shaped (anonymised) data, and backwards-compatible with the previous release where a rollback is needed.
- Secrets come from the production secret store; none in code, image or config files.
- Service is private behind TLS, authenticates every endpoint, logs without personal data, has health checks, metrics and alerts.
- Backups exist and a restore has been tried at least once.
- Data protection: personal data classified, access limited, retention defined.
- Dependencies scanned; no known critical vulnerabilities.

## 2. Release plan (`handoff/release-plan.md`)

What is released (version, digest, migrations), when and by whom, order of steps, expected downtime, how success is checked, **rollback steps** (including what happens to migrated data), who is on call, and communication to users.

## 3. Approvals

Ask the person to name: the business approver, the technical approver, and the change ticket. They record these; you do not fill them in or approve on anyone's behalf. If any is missing, stop.

## 4. Deploy

Use the organisation's pipeline (and its change process). If you are asked to run commands yourself, state each step and its effect, get a yes for that step, run it, and log time, action and result in `handoff/release-log.md`. Stop on the first error; do not retry destructive actions or widen permissions to get past a denial. Never create long-lived credentials.

## 5. Verify

Health green, migration applied, smoke test of the main flow with a non-destructive test account, error rate and latency normal, alerts quiet. Report what was and was not verified. If the checks fail, roll back per the plan and say so.

## Rules

- Never deploy without the readiness gate and named approvals.
- No secrets in files, chat or logs.
- Everything cloud-specific (services, limits, prices) is taken from the provider's current documentation or the team's runbook, not from memory; if you cannot check, list it as an open item.

## Output

`<handoff>/release-plan.md`, `<handoff>/release-log.md`.

## Self-learning

At the end of every run, reflect on what went wrong or was slow, what the user corrected, and what was missing or unclear in this skill. If you find a concrete improvement, do not edit this skill on your own. Instead:

1. Propose it as a short list. For each item give the section affected, the exact change, and the reason (what it prevents next run).
2. Ask the user to approve, edit, or reject each item.
3. Apply only the approved items to this `SKILL.md` (or its scripts, templates or references), keeping edits small. Tell the user what changed.
4. If nothing needs changing, say so in one line. Never record secrets, personal data or one-off project details as lessons.
