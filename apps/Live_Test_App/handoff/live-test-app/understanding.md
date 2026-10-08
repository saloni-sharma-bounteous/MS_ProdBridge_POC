# Understanding: KYC Onboarding Desk (Live_Test_App, server-rendered Python)

Source: `apps/Live_Test_App/ui.py` (one file, about 330 lines, Python standard library only). Live at http://localhost:8000 (`/health` returns ok, `/login` returns 200). Behaviour below is read from the source; it was not captured with a browser (Playwright browsers are not installed) and no forms were submitted. `inventory.json` is almost empty because the script does not recognise a Python http.server app, so the file was read directly.

IMPORTANT: `handoff/` already holds understanding, spec, stories, Jira import state and a data model for a DIFFERENT app, `apps/html-kyc-onboarding-desk` (static HTML, different rules). Those were not overwritten. This work is in `handoff/live-test-app/`.

## 1. Purpose
A small web app where an onboarding analyst reviews customer KYC applications: capture details, verify documents, run a sanctions screen, see a risk score, then approve, escalate or reject. The docstring says it is "a small web app to test agents against", so it is a test fixture as much as a POC (inferred: the real business intent may be REQ-0044).

## 2. Users and roles
One hard-coded user, "analyst" (`ui.py:15`). No roles, no per-user identity; every signed-in user can do everything. Credentials are in source and in the docstring (value not copied here).

## 3. Screens and flows
- `/login` sign in. `/queue` review queue with status filter (All, Pending, Escalated, Approved, Rejected). `/new` new application form. `/app/{id}` detail: applicant, risk, documents, screening, decision, audit log. `/health`, `/api/applications` (JSON of all records), `/api/reset` (POST, restores seed data), `/logout`.
Main journey:
1. Sign in. 2. New application (validated). 3. Open case. 4. Mark the three documents verified. 5. Run screening. 6. Approve, or Escalate/Reject with a reason. 7. Closed cases are read-only; audit log shows each step.

## 4. Data
In-memory dict `APPS` only; lost on restart (`ui.py:23,26`). Fields: id, name, dob, nationality, id_type, id_number, email, occupation, funds, pep, docs (3 booleans), screening (None/Clear/Hit), status (Pending/Escalated/Approved/Rejected), reason, log (list of text lines). Five fictional seed applicants. Sessions are an in-memory set. No database, no files.

## 5. Business rules
- Required fields: name, dob, nationality, id_number, email, occupation [ui.py:189-196].
- Age at least 18, computed as days/365 (approximate) [ui.py:197-203]. DOB format YYYY-MM-DD [ui.py:197-205].
- Email needs "@" and a dot after it [ui.py:206]. ID number at least 5 chars [ui.py:208].
- Documents: Photo ID, Proof of address, Source of funds [ui.py:16].
- Risk score starts at 10; PEP +40; high-risk nationality +35 (iran, north korea, syria, myanmar, afghanistan); risky occupation +20 (casino owner, crypto trader, arms dealer); source of funds Gift/Unknown +15 [ui.py:50-59]. Bands: Low under 30, Medium 30-59, High 60 and over [ui.py:60].
- Screening: exact case-insensitive name match against 3 fictional names = Hit, else Clear [ui.py:333; list at ui.py:21].
- Approve requires: all docs verified, screening run, screening not Hit, and if High band then status must already be Escalated [ui.py:210-235].
- Reject and Escalate require a reason [ui.py:215]. Approved/Rejected cases are closed; Escalated can still be approved [ui.py:211].
- Every action appends a timestamped audit line.

## 6. Integrations
None. Sanctions list is a hard-coded set; no external service.

## 7. Security observations
- Single shared hard-coded credential, plaintext comparison, no lockout, no SSO.
- Session cookie is HttpOnly but has no Secure or SameSite flag; no CSRF tokens on any POST (state changes by form post, and `/logout` is a GET).
- `/api/reset` is a POST that wipes data and is reachable WITHOUT sign-in (checked before the session test, `ui.py:296`).
- `/api/applications` exposes full PII (DOB, ID number, email) to any signed-in user; no masking, no encryption, no retention.
- Audit log is mutable in-memory text, has no actor, and views are not logged.
- No maker-checker: the creator can approve their own case; the "reason" for approval is not required.
- Server binds to 127.0.0.1, plain HTTP, no rate limiting.
- Bug (inferred): an `/app/<id>` URL whose id does not exist falls through to 404, fine; `max(APPS)` in create would raise if APPS were ever empty.
- Expired ID documents are not checked, and PEP is a manual checkbox.

## 8. Stated intent vs built (REQ-0044 in `requirements/`, applicability to this app is an assumption)
- Met/partial: age 18 check, name screening blocks approval, PEP raises score, approve/reject/escalate with reason, queue, audit log.
- Different: risk points and band cut-offs differ from BR-4/BR-5 (+3/+2 scale, bands 0-2/3-5/6+); approval authority is not by role (BR-6); residence and monthly volume not captured.
- Missing: SSO and roles, maker-checker, expired ID, ad-hoc screening page, reports and CSV export, ID upload, periodic review, encryption/masking, 5-year retention, daily screening list refresh.

## 9. Open questions
1. Is this app the real production target, or is `html-kyc-onboarding-desk` (already specced, stories already in Jira as MSPOC-1..33)? Should this replace, extend, or be a separate project?
2. Which business rules are authoritative: this app's scoring (10/+40/+35/+20/+15, bands 30/60) or REQ-0044 (BR-4/BR-5)?
3. Is the Hit/Clear screening to be replaced by a real provider? Which one, and exact or fuzzy matching?
4. Which roles and approval authorities are needed, and is maker-checker required?
5. Should High-risk cases need an Escalated step by someone other than the analyst?
6. Data: retention, masking, encryption, where it will be hosted, and SSO provider.
7. Should `/api/reset` and `/api/applications` exist in production? (Recommend no.)
8. Is the high-risk country list for nationality only, or also residence?

Note: line references were re-checked only for key items (21, 50-60, 189, 210, 215, 296, 313, 333); others are approximate.
