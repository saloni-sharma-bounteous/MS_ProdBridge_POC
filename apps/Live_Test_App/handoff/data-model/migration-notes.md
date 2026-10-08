# Migration notes: KYC Onboarding Desk

The prototype has no database. Data lives only in the browser (`localStorage["kyc_cases"]`, `sessionStorage["user"]`). There is nothing server-side to migrate; this lists what changes and what is open.

## What changes from the prototype
| Prototype | Target | Note |
|---|---|---|
| `kyc_cases[]` in localStorage | `customer`, `identity_document`, `onboarding_case` | Browser data is per-user and not authoritative. Do not import it. The three seeded sample cases are test data only. |
| `id` `KYC-` + 5 random digits | `id uuid` | Random ids can collide. If a readable case number is wanted, add a database sequence. |
| `fullName`, `dob`, `idNumber` in plain text | encrypted at rest | Prototype console logging and unescaped CSV export are not carried over. |
| `monthlyVolume` as a JS number | `numeric(14,2)` | |
| `rating` strings `High/Medium/Low` | enum `low/medium/high` | Lower-case codes. |
| `score`, `rating` re-computed in three places | `risk_assessment` rows with `rule_set_id` | The case page's own rules (High >=7, RU/VE) are dropped. |
| `decisionNote`, `decidedBy`, `decidedAt` on the case | `case_decision` rows | History is kept; the prototype overwrote it. |
| `screening` object | `screening_check` | |
| `nextReview` calculated on the case page | `periodic_review` row | |
| Hard-coded users and passwords (`auth.js`) | `app_user` keyed by identity provider subject | No passwords stored. Role mapping per Q-007. |
| Risk lists and points hard-coded in `risk.js` | `risk_rule_set` and `risk_rule_list_item`, seeded as version 1 | Prototype values, unconfirmed. |
| Approver matrix (`approverFor`, unused) | `risk_rule_set.approver_role_*` | Unconfirmed (Q-003). |

## Backfill
No existing server data, so no backfill. Reference data (rule set v1) loads in `V5__reference_data.sql` with audit actor `flyway`; confirm the values with the compliance owner before production.

## Proposed answers (no owner has confirmed any of these)
| Question | Proposed answer |
|---|---|
| Q-011 retention | 5 years after the relationship ends (REQ-0044 NFR-3); decisions and audit rows never edited or deleted in that time; users deactivated, not deleted |
| Q-001 rule set | Scoring-module values (High 6+, Medium 3+, six countries), matching REQ-0044 BR-5; the case page's second rule set is dropped |
| Q-002 auto-approve Low | No: every case gets a human decision (`auto_approve_low = false`). REQ-0044 BR-6 says automatic, so this conflicts and needs the owner |
| Q-003 approval matrix | Enforced on the server; four-eyes required |
| Q-004 review cycle | Stored as a `periodic_review` row (1, 2 and 3 years) |
| Q-008 formats | Country codes are two capital letters; volume not negative (database checks) |
| Q-010 masking | ID number and date of birth unmasked only for compliance_officer (REQ-0044 NFR-1); masked for others and in exports |

Still open and not modelled: Q-005, Q-006, Q-007, Q-009, Q-012, Q-013.

## Design choices to confirm with the owner
1. A customer can have several cases and documents. The spec does not say so. There is no rule for matching a returning customer to an existing record, so uniqueness is not enforced.
2. The current rating is the latest `risk_assessment` row; screens need a join or a view (add as a new migration).
3. `decision_action` includes `release` as a placeholder for blocked cases (Q-005).
4. Four-eyes (BR-010) is not a database check; the service enforces and tests it.
5. No ID document scan is stored (out of scope in the spec; REQ-0044 FR-7 would add it).
6. Currency is USD only (Q-013). `audit_log` is a design decision based on REQ-0044 FR-8 and NF-003.
7. Retention is "5 years" for every entity until compliance and legal confirm (Q-011).

## Tool notes
- `model_check.py` accepts spec ids with prefixes OV, FN, BR, DM, IN, UI, AU, NF and QK, but this spec uses `FR-` and `Q-`. Those ids appear in descriptions, not `spec_refs`.
- The SQL was generated, not executed. Run it on a scratch PostgreSQL before relying on it.
- Row-level security is enabled in `V4`; policies are added as a new versioned script with the service.
