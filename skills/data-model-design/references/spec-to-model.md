# From specification to model

## Reading the spec
| Spec shows | Model gets |
|---|---|
| `DM-nnn` entity or field list | entity and attributes, one for one |
| Status values ("pending, approved, rejected") | an enum with those values; a `status` attribute with a default |
| Business rule with a threshold or limit | a reference-data entity if it can change; a CHECK if it is invariant |
| "Needs two approvals" / "manager and HR" | an approval entity with one row per step and a unique constraint per role |
| A quirk: "approver name is free text" | a foreign key to the person entity in the target |
| A quirk: "amount kept as a float" | `numeric(p,s)` and a note in the description |
| Data kept in browser storage | a server-side entity; the migration plan notes the browser keys |
| "Who decided and when" | `decided_by`, `decided_at`, or better an approval row |
| Requirement without an implementation (retention, masking, audit) | the field or entity the requirement implies, with its `REQ-... ` reference |

## Referencing
Every entity, attribute and check can list `spec_refs`: spec statement ids (`BR-004`) or requirement references (`REQ-0100 BR-2`). The checker verifies spec ids exist when you pass `--spec-dir`. An entity with no reference is a design decision; say why in its description.

## Coverage
After the first draft, compare the list of `DM-nnn` statements to the references. A statement nobody references is either missing from the model or intentionally dropped; decide which and record it.

## Questions to ask the owner
1. What is the retention period for each Restricted entity?
2. Who may see each Restricted attribute, and in what form (full, masked, none)?
3. Which values can each status take, and who may move it from one to the next?
4. Which numbers must be exact, and to how many decimals?
5. Which lists are policy (owned by someone) rather than code?
6. What must be kept for evidence if a record is changed or deleted?
