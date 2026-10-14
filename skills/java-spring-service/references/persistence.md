# Persistence

## Schema comes from the data model
The database schema is owned by Flyway migrations, generated from `data-model.json` by the `data-model-design` skill (`generate_ddl.py --flyway-dir src/main/resources/db/migration --version 1 --description init`). Hibernate only validates (`spring.jpa.hibernate.ddl-auto=validate`); it never creates or alters tables. Later changes are new `V<n>__description.sql` files, never edits to applied ones.

Migration discipline: forward-only; expand then contract for anything destructive (add new, backfill, switch reads, remove old in a later release); every migration is tested by starting the application against a real PostgreSQL (the generated `ApplicationTests` does this).

## Mapping
- UUID primary keys with `@GeneratedValue(strategy = GenerationType.UUID)`.
- Foreign keys are mapped as scalar columns (`UUID employeeId`) by default. Add `@ManyToOne(fetch = FetchType.LAZY)` only where a use case needs the association, and fetch with a join query or an entity graph to avoid N+1 queries.
- Enums stored as lowercase strings through an `AttributeConverter` (generated), matching the database CHECK constraint and the API values.
- `numeric(p,s)` maps to `BigDecimal` with `precision` and `scale` on `@Column`; JSON columns map to `String` with `@JdbcTypeCode(SqlTypes.JSON)`.
- Audited entities extend `AuditedEntity` (created and updated by and at, `@Version` for optimistic locking). A conflicting update surfaces as `OptimisticLockingFailureException`, which the error handler maps to 409.
- `equals` and `hashCode` use the identifier; entities are not Lombok `@Data`.
- Keep `spring.jpa.open-in-view=false`; load what the use case needs inside the service transaction.

## Queries
- Derived queries for simple filters; `@Query` with named parameters for the rest. Never build SQL or JPQL by string concatenation with user input.
- Every list query is paged or bounded. Index what the screens filter and join on.
- Reads use `@Transactional(readOnly = true)`.

## Audit trail
Business changes write an `audit_log` row in the same transaction through `AuditTrail.record(...)`. The table is append-only: no update or delete path in the application, and the database role used by the service has no UPDATE or DELETE grant on it. Keep Restricted values out of `action` text; before and after states live in the encrypted `jsonb` columns.

## Row-level security
If the data model sets `rls: true`, the migration enables it. Write policies as a separate migration per role, and decide how the identity reaches the database (a per-transaction setting such as `set_config('app.user', ..., true)` read by the policies, or separate database roles). Test with two users.

## Connection and pool
HikariCP defaults are a start; size the pool for the database, not the thread count, especially with virtual threads. Credentials come from the environment. Use TLS to the database in every non-local environment.
