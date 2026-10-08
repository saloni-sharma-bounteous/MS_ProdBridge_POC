# Modeling rules

## Identity and keys
- Surrogate primary key `id uuid default gen_random_uuid()` on every entity unless the key is genuinely natural and immutable (a reference code).
- Natural identifiers (employee number, tax id) are separate columns with a `unique` constraint.
- Composite uniqueness that the business states ("one balance per employee, type and year") is a `unique` list, not application code.

## Types
| Need | Type |
|---|---|
| Money, rates, quantities that drive decisions | `numeric(p,s)`; never float, real or double |
| Calendar day | `date` |
| Moment in time | `timestamptz` (names end `_at`) |
| Calendar date (names end `_date`) | `date` |
| Short text with a known maximum | `varchar(n)` |
| Long free text | `text` |
| Code from a closed list | `enum:<name>` (stored as varchar with a CHECK) |
| Structured payload | `jsonb`, only for audit before and after states or genuinely schemaless data |
| Flag | `boolean`, named `is_`, `has_`, `needs_`, `can_` |

## Constraints
- NOT NULL by default; make a column nullable only when absence has a business meaning, and say what it means in the description.
- Foreign keys for every relationship. `on_delete`: `restrict` for business records, `cascade` only for pure children (approval steps of a request), `set null` only on nullable columns.
- CHECK constraints for rules the database can enforce (date order, value ranges, "address only for parental leave").
- Unique constraints and foreign key columns get indexes automatically from the generator; add indexes for the filters and joins the screens and reports need.

## Classification and protection
- Levels: Restricted, Confidential, Internal, Public (Restricted: identifiers, financial and health data; Confidential: business data; Internal; Public).
- Personal identifiers, health and HR details, payment and account numbers, credentials and full case records are Restricted. Names and contact details are at least Confidential.
- Protection: `encrypted_at_rest` (application-level or column encryption), `tokenized`, `hashed` (one-way, for secrets), or `none` with a `protection_note` naming the compensating control (for example database-level encryption plus restricted access).
- Entity classification equals its most sensitive attribute. The checker enforces this.

## Audit and history
- `audit: true` adds `created_at`, `created_by`, `updated_at`, `updated_by`, `version`. Do not declare those columns yourself.
- A separate `audit_log` entity records who did what to which row and when, with before and after state. It is append-only: the service writes it, and no role can update or delete it.
- Decisions (approvals, rejections) are rows, not overwritten columns, so the history survives.

## Retention
Put the retention rule in the entity `retention` field in the business's words ("6 years after employment ends"). If the business has not decided, write "TBD: ask <owner>" and list it as an open question.

## Reference data
Limits, allowances, thresholds and lookup values are entities with an owner, not constants in code. Mark them `reference_data: true`, audit them, and give them a stable natural key.

## Multi-tenancy and access
Mark entities with per-user or per-role visibility `rls: true`. The service skill designs the policies; this model only records that row-level security must be on.
