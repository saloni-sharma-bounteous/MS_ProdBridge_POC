# Understanding: KYC Onboarding Desk (HTML POC)

Source: `apps/html-kyc-onboarding-desk` (static multi-page, 7 HTML, 5 JS, 1 CSS, about 430 LOC; no backend). Evidence: `handoff/inventory.json`, `handoff/ui/*.snapshot.json` (static, no browser capture), and a direct read of every file. Not run live; behaviour is read from code.

## 1. Purpose
A browser-only tool for compliance staff to onboard customers (KYC). An analyst enters customer details, the app screens the name against sanctions/PEP lists, scores risk, and either auto-approves, blocks, or queues the case for a senior analyst or compliance officer to decide.

## 2. Users and roles
Hard-coded users in `js/auth.js:2-7`: analyst, senior_analyst, compliance_officer, admin.
- All roles: view queue, create cases, screen names, view reports, sign out.
- senior_analyst: may approve unless the case is High risk. compliance_officer and admin: may approve anything (`case.html:48`).
- admin only: sees "Legacy" nav link (`nav.js:8`).
- Everyone can Reject and Escalate pending cases (`case.html:66-67`).

## 3. Screens and flows
- `login.html` sign-in. `index.html` review queue with stats and Quick approve. `new-case.html` onboarding form. `case.html?id=` case detail and decision. `screening.html` ad-hoc name check. `reports.html` filterable table and CSV export. `old-dashboard.html` legacy stub ("do not use", only commented-out code).

Main journey:
1. Sign in. 2. New customer: fill form (name, DOB, nationality, residence, ID, occupation, source of funds, monthly volume, PEP, face-to-face). 3. Validation, screening, scoring, status set. 4. Redirect to case page. 5. If pending/escalated, a permitted user Approves, Rejects or Escalates with a note (browser prompt). 6. Queue and Reports reflect the result.

## 4. Data
No database. All in browser storage:
- `localStorage["kyc_cases"]`: array of cases (`store.js:1`). Fields: id (`KYC-` plus random 5 digits), fullName, dob, nationality, residenceCountry, idType, idNumber, idExpiry, occupation, sourceOfFunds, monthlyVolume, isPEP, faceToFace, score, rating, status, screening, createdBy, createdAt, decisionNote, decidedBy, decidedAt.
- `sessionStorage["user"]`: {name, role}.
- Statuses seen: approved, pending_review, escalated, rejected, blocked.
- Three seeded sample cases (`store.js:28-41`), including a PEP.
- Contains personal data (name, DOB, ID number) stored in plain text.

## 5. Business rules
Risk score (`js/risk.js:4-15`): nationality in high-risk list +3; residence in list +3; PEP +3; cash-intensive occupation +2; monthly volume >50,000 +2, else >10,000 +1; source of funds other/unknown +2; not face to face +1.
- High-risk countries `risk.js:1`: IR, KP, SY, MM, AF, YE. Cash-intensive `risk.js:2`: casino, money_service, car_dealer, jewellery.
- Rating `risk.js:17-21`: High >=6, Medium >=3, else Low.
- Approver by rating `risk.js:23-27`: High compliance_officer, Medium senior_analyst, Low analyst. Defined but never used.
- Onboarding validation `new-case.html:41-45`: name, DOB, ID number, expiry required; age >= 18 (365.25-day years); ID not expired.
- Screening `screening.js:1-11`: case-insensitive substring match against 5 sanctions names and 3 PEP names. PEP match forces isPEP = true (`new-case.html:56`).
- Initial status `new-case.html:61-63`: sanctions match = blocked; Low = approved automatically; otherwise pending_review.
- Next review date `case.html:30-34`: High 1 year, Medium 2, Low 3.
- Approval permission `case.html:48` (see roles).

Inconsistencies found (important):
- `case.html:16-28` recalculates risk with different rules: country list adds RU and VE; thresholds High >=7, Medium >=4. So the same case can get different ratings on the case page (own rules), the queue (stored value) and reports (re-scored with risk.js). The case page decides approval permission from its own rating. Example (inferred from arithmetic): a Venezuelan national scores +3 on the case page but 0 in risk.js.
- Seed KYC-10003 stores score 8; risk.js gives PEP 3 + other source 2 + volume 1 + not face to face 1 = 7 (inferred), so seed data does not match either rule set exactly. KYC-10002 (5) matches risk.js.
- Queue stats count `rating === "High"` from stored data; `blocked` is counted but blocked cases cannot be actioned.
- Queue "Quick approve" (`index.html:20-24`) approves any pending_review case with no role check, no note, no risk check; it can approve Medium/High cases, bypassing the approval matrix.
- Reject and Escalate have no role check; escalated cases may be re-approved by anyone with approve permission; no four-eyes rule (creator can approve own case, inferred).

## 6. Integrations
None active. jQuery 3.6.0 loaded from `code.jquery.com` on reports.html (CDN dependency). `old-dashboard.html` has commented-out calls to a sandbox screening provider API (`sandbox.screening-provider.example.com/v2`) with an API key header; this is legacy and not executed.

## 7. Security observations
- Authentication is client-side only: user list with plaintext passwords in `js/auth.js:2-7` (secrets exist; values not reproduced here). The login page also displays test credentials (`login.html:12`). A TODO says to replace with SSO.
- Authorisation is client-side only and bypassable via browser storage/console; `requireLogin` only checks sessionStorage.
- `old-dashboard.html` contains a commented-out API token (sample-looking, but still a secret-like value in source). No role check on the page itself (only the nav link is hidden).
- Stored XSS risk: names, notes and other fields are inserted via innerHTML without escaping (`case.html:51-63`, `index.html:35-39`, `reports.html:28-29`, `screening.html:20`); decision note from `prompt()` is rendered raw.
- Personal data (DOB, ID numbers) in localStorage, in console logs (`store.js:12`), and in CSV export without role restriction or audit; CSV export has no escaping (comma/formula injection).
- No audit trail of who did what beyond the last decision; case IDs are random (collision possible).
- Sanctions/PEP matching is a hard-coded 8-name list with substring matching (misses spelling variants, false positives); not a real screening source.

## 8. Stated intent vs built
No requirement document was supplied. Not applicable.

## 9. Open questions
1. Which risk rules are correct: `risk.js` (High >=6, Medium >=3, 6 countries) or `case.html` (High >=7, Medium >=4, plus RU and VE)? Who owns the country list and its updates?
2. Should Low-risk cases still be auto-approved with no human review? Is this allowed by policy?
3. Is "Quick approve" intended? Should it exist, and for which roles/ratings?
4. Should the approval matrix (`approverFor`) be enforced (Medium needs senior analyst, High needs compliance officer)? What about Reject/Escalate permissions and four-eyes (creator cannot approve)?
5. What happens to blocked (sanctions) cases: who can review, release or report them (e.g. suspicious activity reporting)?
6. Which real sanctions/PEP provider is to be used (the legacy page hints at one), and what match logic (fuzzy, DOB, aliases)?
7. Identity provider for production (SSO is mentioned in a TODO): which one, and how are roles assigned?
8. Is "Legacy" dashboard to be dropped? (assumed yes, inferred)
9. Retention, deletion and audit requirements for customer data; reporting and CSV export permissions; which fields are required.
10. Review cycle: is "next review due" (1/2/3 years) to be stored and trigger re-reviews or notifications? Is document upload (ID scans) expected? Not in POC.
11. Country, currency (USD assumed) and multi-jurisdiction scope.
12. Expired-ID rule is checked at onboarding only; should a case be re-checked later?

## Not verified
App was not run in a browser and no live capture or screenshots were taken (static snapshot only). The exposed sample token was not tested. CSS not reviewed. Seed score comparisons are arithmetic from reading the code. The Python inventory and static snapshot scripts ran (inventory validated against schema); understand-anything was skipped as the app is small (13 files).
