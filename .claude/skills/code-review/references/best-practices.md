# Language-neutral best practices

Use to fill gaps where team standards are silent. Cite as "best practice: <name>".

- **Fail fast**: validate at the boundary, reject bad input with a clear error.
- **Least privilege**: code, services and users get only the access they need.
- **Single responsibility**: a unit has one reason to change.
- **DRY, but not at any cost**: remove duplicated rules; tolerate duplicated shapes that may diverge.
- **Make illegal states unrepresentable**: use enums, types and constraints over free strings and flags.
- **Immutability by default**: mutate only where needed.
- **Explicit over implicit**: no hidden global state, magic values or surprising side effects. Name constants.
- **Handle the unhappy path**: null, empty, duplicate, concurrent, timeout, partial failure.
- **Idempotency**: operations that may be retried must be safe to repeat.
- **Time and money**: inject clocks; use decimal types for money; store UTC.
- **Concurrency**: shared mutable state needs a stated protection; prefer optimistic locking for edits.
- **Observability**: log events with context, never secrets; expose metrics for what operators will ask.
- **Backward compatibility**: additive API and schema changes first; deprecate before removing.
- **Dependencies**: justify each new one; check licence, maintenance and known vulnerabilities.
- **Readability**: code is read more than written; comments explain why, not what.
- **Tests**: test behaviour, not implementation; one reason to fail per test; keep them fast.
- **Performance**: measure before optimising; avoid unbounded queries, loops over remote calls and loading whole tables.
- **Accessibility and i18n** (UI): labels, keyboard use, contrast, no hard-coded strings or date formats.
