# KYC Onboarding Desk: design brief

Platform: web desktop, 1440 x 900 frames, 240 px sidebar, 8 pt rhythm. Source: REQ-0044 and `apps/html-kyc-onboarding-desk`.

## Who and why
Onboarding analysts, senior analysts and compliance officers decide whether a new customer can be onboarded. The job: **get a customer from "details captured" to a defensible, audited decision, without the risk rating ever being ambiguous.**

## Principles
1. **Decide in one glance.** Rating, score and who must approve sit at the top of every case. No hunting.
2. **Never hide risk, never leak data.** Risk is always label plus icon plus number. ID numbers and dates of birth are masked unless the viewer is Compliance (NFR-1).
3. **The system explains the rules.** Disabled actions say why ("You created this case", "High risk needs a Compliance Officer"). One rating definition everywhere (BR-5).

## Core flow
1. Sign in with bank SSO (role comes from the directory).
2. Review queue: see what needs a decision, filter by status.
3. New customer: capture details and ID copy; checks run on submit.
4. Screening and score result: Low auto-approves, Medium/High go to the queue, a sanctions match blocks.
5. Case page: read risk factors, screening, history; write a note; approve, reject or escalate.
6. Screening (ad hoc) and Reports (filter, export) support the above.

## Screens
01 Sign in / 02 Review queue / 03 New customer / 04 Case detail / 05 Case detail dark (error state) / 06 Name screening / 07 Reports / 08 Queue states.

## States
- Queue: loading skeleton, empty ("All clear"), error with retry, filter with no results.
- New customer: field errors (under 18, expired ID), submitting, blocked by sanctions.
- Case: approve disabled (maker-checker, wrong role), missing decision note error, decided (read-only with audit trail), blocked.
- Screening: clear, PEP match, sanctions match, list stale (older than 24 h).
- Reports: no results, export masked notice.

## Visual direction
- **Accent:** deep teal `#0E6B72`. Calm and financial, distinct from default blue; passes 4.5:1 on white. Dark mode `#4FC3CB`.
- **Mood:** calm, precise, accountable.
- **Type:** system stack falling back to Inter, iOS-style scale from `design-system.css`; tabular figures for case ids and money.
- **Rating colours** are status only: Low = good, Medium = warn, High = bad, always with a label.
- **Rich moment:** the risk meter on the case page, a 0-12 scale with Low / Medium / High bands and the factor-by-factor breakdown from BR-4.

## Motion notes
- Risk meter fills left to right, 450 ms, ease-out, once on load.
- Live score on New customer ticks up/down 200 ms as factors change.
- Row hover tint 120 ms; sheet/modal for confirm: 250 ms ease-out in, 200 ms ease-in out.
- Reduce Motion: crossfade only.

## Assumptions and open questions
- Live risk preview on the new-customer form is a design addition; the requirement only says "on submit". Confirm with Compliance.
- Pagination vs. infinite scroll for the queue: assumed paginated, 25 rows.
- "Reveal" of masked data for Compliance is logged to the audit log (FR-8); confirm wording.
- Admin screens (users, screening provider status) are out of scope here.
