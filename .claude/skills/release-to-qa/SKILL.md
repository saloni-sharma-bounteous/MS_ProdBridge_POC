---
name: release-to-qa
description: Deploy a built service to QA and prove it meets the approved acceptance criteria: build and test, container image, migrations, Playwright tests per criterion, and a QA report with sign-off. Use after implementation, or when asked to "move to QA" or "write Playwright tests for the stories".
---

# Release to QA

Goal: evidence that what was built matches what the business approved, in an environment that is not production.

## Entry checks (stop and report if any fail)

- Stories in `handoff/stories.json` are approved and implemented.
- `mvn -B verify` passes on the service (unit and Testcontainers tests). Do not skip or loosen tests to get green.
- `java-spring-service`'s checker (`scripts/java_check.py`) reports no errors.
- Flyway migrations are present and apply cleanly to an empty database.
- No secrets in code, config or the image. Settings come from the environment.

## Steps

1. **Package**: build the image from the service's Dockerfile (non-root, health endpoint). Tag with the version or commit, never `latest`.
2. **Deploy to QA** with the team's pipeline or the commands they give you. Settings and secrets come from the QA environment's store; never type credentials into the chat. Run migrations as a pipeline or task step, not from a person's laptop. If you do not know how QA is deployed, ask; do not guess an account, host or network.
3. **Smoke check**: health endpoint is up, migrations applied, a protected endpoint returns 401 without a token.
4. **Write Playwright tests from the acceptance criteria.** One test per criterion, named with its story id (for example `test_S004_ac2_...`) so the trace is obvious. Use role/label/test-id locators, Playwright's waiting assertions (no `sleep`), synthetic data, and an assertion that would fail if the rule were broken. Include the refusal and boundary cases. Criteria the UI cannot show (audit rows, server-enforced limits) are tested at the API or database level in the service project; say which.
5. **Run** against the QA URL (`pytest --base-url https://<qa-host> tests/` or `npx playwright test`). Use a saved browser state for protected environments; tests never type real passwords.
6. **Report** `handoff/qa-report.md`: a table of every story and criterion, its test, and result (pass / fail / not automated with reason); failures with owner; what was not checked. A failing accessibility or security test is a finding to fix, not a test to delete.
7. **Gate**: the QA lead signs off, and the business owner confirms the acceptance criteria are met. Only a person records sign-off.

## Rules

- QA data is synthetic. No production data in QA.
- Never change a test to match a bug; check it against the approved criterion first.
- Report honestly what is not automated.

## Output

`<repo>/tests/` (Playwright tests) and `<handoff>/qa-report.md`.
