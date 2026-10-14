# Production readiness checklist

"Auto" means `java_check.py` or a generated test checks it; "Manual" means a reviewer confirms it.

## Build and platform
- [ ] Spring Boot 4.x parent, current patch, Java version agreed (Auto: JV-001)
- [ ] Modular starters only, no Jackson 2, no classic bridge (Auto: JV-002, JV-003)
- [ ] Dependencies scanned in CI; lockfile or pinned versions (Manual)

## Security
- [ ] Resource server with the organisation's identity provider; no local credentials (Manual, Auto: JV-009)
- [ ] `@EnableMethodSecurity`, `@PreAuthorize` on every state-changing endpoint, ownership checks in queries (Auto: JV-017, JV-026; Manual)
- [ ] No `permitAll` on anything but health and info; CORS lists exact origins (Auto: JV-013, JV-017)
- [ ] No secrets in repository, config or image (Auto: JV-009)
- [ ] Actuator limited; no stack traces or SQL in responses (Auto: JV-010; handler)

## Data
- [ ] Schema from reviewed Flyway migrations; Hibernate set to validate (Auto: JV-007, JV-020)
- [ ] Money as BigDecimal and numeric (Auto: JV-014)
- [ ] Restricted fields omitted from default responses, protected at rest as the model says (Manual)
- [ ] Optimistic locking on audited entities; audit rows for every state change (Test)
- [ ] Retention implemented or scheduled with an owner (Manual)

## API
- [ ] DTOs only, validated; list endpoints paged and bounded (Auto: JV-011, JV-012; Manual)
- [ ] Problem responses for every error path (Test)
- [ ] API versioned; contract documented (Manual)

## Quality
- [ ] Every spec business rule has an enabled test (Auto note: JV-025 lists disabled stubs)
- [ ] Negative tests for each control (Manual)
- [ ] Real PostgreSQL in tests (Auto: JV-018)
- [ ] Architecture tests pass (Test)
- [ ] No field injection, no console printing, no empty catch (Auto: JV-005, JV-006, JV-016)

## Operations
- [ ] Health probes, metrics, traces, structured logs without personal data (Auto: JV-010, JV-023; Manual)
- [ ] Timeouts and bounded retries on outbound calls (Manual)
- [ ] Non-root container, pinned base image (Auto: JV-019)
- [ ] Runbook, owner, recovery objectives recorded (Manual)
