# Team coding standards (house defaults)

Edit this file to match the team. Keep IDs stable so reviews can cite them. MUST = blocks merge. SHOULD = fix unless there is a stated reason.

## Security (SEC)
- **TS-SEC-01** MUST: every endpoint requires authentication; every state change is authorised on the server by role and ownership.
- **TS-SEC-02** MUST: no secret, token, password or personal data in code, tests, fixtures or logs. Secrets come from the environment.
- **TS-SEC-03** MUST: never take identity, owner, status, price or limits from the request body when the server can determine them.
- **TS-SEC-04** MUST: validate all external input on the server; use parameterised queries only.
- **TS-SEC-05** SHOULD: responses omit Restricted personal data unless the spec allows it.

## Correctness and errors (COR)
- **TS-COR-01** MUST: business rules match the spec, including inclusive/exclusive limits.
- **TS-COR-02** MUST: no catch block that swallows an error; log with context or rethrow.
- **TS-COR-03** MUST: outbound calls have timeouts; retries are bounded and idempotent.
- **TS-COR-04** SHOULD: errors returned to clients are RFC 9457 problems with no stack traces.
- **TS-COR-05** SHOULD: state changes are audited (who, what, when).

## Design (DES)
- **TS-DES-01** SHOULD: constructor injection only; no field injection.
- **TS-DES-02** SHOULD: controllers hold no business logic; services own rules; repositories own queries.
- **TS-DES-03** SHOULD: functions do one thing and fit on a screen; avoid more than 4 parameters.
- **TS-DES-04** SHOULD: no duplicated rules; one source of truth per rule.
- **TS-DES-05** SHOULD: names say what things are; no abbreviations the team does not use.
- **TS-DES-06** SHOULD: no dead code, commented-out code or unexplained TODOs.

## Data (DAT)
- **TS-DAT-01** MUST: schema changes go through versioned migrations (Flyway); never edit an applied migration.
- **TS-DAT-02** SHOULD: transactions wrap one business operation; no remote calls inside long transactions.
- **TS-DAT-03** SHOULD: no N+1 queries; list endpoints are paged.

## Testing (TST)
- **TS-TST-01** MUST: every spec rule has a test, including negative and boundary cases.
- **TS-TST-02** MUST: tests are deterministic (no sleeps, real clocks or shared state).
- **TS-TST-03** SHOULD: never skip, loosen or delete a failing test to get green.
- **TS-TST-04** SHOULD: test names describe behaviour (given/when/then).

## Operability and process (OPS)
- **TS-OPS-01** SHOULD: structured logs with correlation ids; no `System.out`.
- **TS-OPS-02** SHOULD: configuration is externalised; same artifact runs in every environment.
- **TS-OPS-03** SHOULD: containers run as non-root; health checks present.
- **TS-OPS-04** SHOULD: public behaviour changes are documented (README, API docs, changelog).
- **TS-OPS-05** SHOULD: PRs are small and focused, with a description linking the story or spec ID.
