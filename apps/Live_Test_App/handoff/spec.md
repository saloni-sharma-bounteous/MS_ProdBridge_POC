# Spec: KYC Onboarding Desk (DRAFT, not approved)

Status: draft from handoff/understanding.md. No business owner has been named or has confirmed anything. Rules marked "(prototype value)" are taken from the POC and are unconfirmed.

## 1. Scope
A web application for compliance staff of a financial firm to onboard customers: capture customer details, screen the name against sanctions and PEP sources, calculate a risk rating, route the case to the right approver, record the decision, and report on cases. Replaces a browser-only prototype with a server-backed, authenticated, audited service.

Out of scope: customer-facing self-service, ID document upload and verification, transaction monitoring, suspicious activity report filing, the legacy dashboard page, mobile apps.

## 2. Actors
- Analyst: creates cases, runs name screening, views cases and reports.
- Senior analyst: all analyst actions; decides Medium-risk cases.
- Compliance officer: all senior analyst actions; decides High-risk cases.
- Admin: manages user access (scope to be confirmed, see Q-009).

## 3. Functional requirements
- **FR-001** A user signs in through the organisation's identity provider; unauthenticated users cannot reach any screen or data.
- **FR-002** An analyst or higher can create a case with: full name, date of birth, nationality, country of residence, ID type, ID number, ID expiry, occupation, source of funds, expected monthly volume (USD), PEP declaration, face-to-face flag.
- **FR-003** On creation the system rejects the case with a clear message if a required field is missing, the customer is under 18, or the ID is expired.
- **FR-004** On creation the system screens the customer name against sanctions and PEP sources and stores the result with the case.
- **FR-005** If screening flags the customer as a PEP, the system marks the case as PEP regardless of the declaration.
- **FR-006** The system calculates a risk score and rating for each case and stores them with the rule version used.
- **FR-007** A sanctions match sets the case to blocked; blocked cases cannot be approved (handling per Q-005).
- **FR-008** Cases not blocked are routed to the approver role for their rating (BR-004), unless Q-002 allows automatic approval of Low risk.
- **FR-009** A permitted approver can approve, reject or escalate a pending case and must enter a decision note.
- **FR-010** The system enforces decision permissions on the server, not only in the screen.
- **FR-011** The review queue lists cases with status and rating and shows counts of total, awaiting decision, High risk and blocked cases.
- **FR-012** A user can run an ad-hoc name screening without creating a case.
- **FR-013** An authorised user can view a report of cases filtered by rating and export it to CSV (who may export: Q-010).
- **FR-014** The case page shows the stored rating, score and next review due date; the rating shown is the same everywhere in the app.
- **FR-015** On any error the user sees a plain message and the failed action changes no data.

## 4. Business rules
- **BR-001** (prototype value, unconfirmed, see Q-001) Risk score is the sum of: nationality in the high-risk country list +3; residence country in the list +3; PEP +3; occupation casino, money_service, car_dealer or jewellery +2; monthly volume above 50,000 +2, otherwise above 10,000 +1 (limits exclusive); source of funds other or unknown +2; not met face to face +1.
- **BR-002** (prototype value, unconfirmed, see Q-001) High-risk country list: IR, KP, SY, MM, AF, YE. The list must be maintained by a named owner, not in code (Q-001).
- **BR-003** (prototype value, unconfirmed, see Q-001) Rating: High at score 6 or more; Medium at 3 to 5; Low at 0 to 2.
- **BR-004** (prototype value, unconfirmed, see Q-003) Approver by rating: High needs compliance officer; Medium needs senior analyst or higher; Low needs analyst or higher.
- **BR-005** Customer must be at least 18 years old on the day of creation (date-based calculation, not 365.25-day approximation).
- **BR-006** ID expiry date must be today or later at creation (inclusive); confirm in Q-012.
- **BR-007** (prototype value, unconfirmed, see Q-004) Next review due: High 1 year, Medium 2 years, Low 3 years from the decision date.
- **BR-008** Case statuses: pending_review, approved, rejected, escalated, blocked. Only pending_review and escalated cases accept decisions.
- **BR-009** Every status change records who, when and the note.
- **BR-010** A user cannot decide a case they created (four-eyes), subject to Q-003.
- **BR-011** Screening compares names to the sanctions and PEP sources using the matching method set in Q-006; the prototype's exact-substring match on 8 names is not the target.

## 5. Data
- **DM-001** Customer case: id, full name, date of birth, nationality, residence country, ID type, ID number, ID expiry, occupation, source of funds, monthly volume, PEP flag, face-to-face flag, score, rating, rule version, status, screening result, next review date, created by and at, current decision (decider, note, time). Personal data classified confidential; ID number and date of birth protected at rest. Retention: Q-011.
- **DM-002** Decision/audit event: case id, action, old and new status, actor, timestamp, note; append-only.
- **DM-003** Screening record: case id or ad-hoc, name searched, source version, result, time, user.
- **DM-004** Risk rule configuration: country list, points, thresholds, version, effective date, changed by.
- **DM-005** User and role assignment (from the identity provider; mapping per Q-007).

## 6. Screens
- **UI-001** Sign-in via identity provider; all users.
- **UI-002** Review queue: stats and case table; all roles; no approve shortcut that skips BR-004 (Q-003).
- **UI-003** New customer form with validation messages; analyst and above.
- **UI-004** Case detail: customer data, risk, screening result, decision history; decision buttons only for permitted roles.
- **UI-005** Name screening: ad-hoc check; all roles.
- **UI-006** Reports: filter and CSV export; roles per Q-010.
- **UI-007** Free text shown to users is escaped so entered data cannot run as code.

## 7. Integrations
- **IN-001** Identity provider (SSO); provider and role mapping unknown (Q-007). On failure users cannot sign in; no local fallback accounts.
- **IN-002** Sanctions and PEP screening provider (Q-006). On failure case creation is held with a visible "screening unavailable" state; it must never be treated as "no match".

## 8. Non-functional
- **NF-001** No credentials or tokens in source code or screens; secrets from a secret store.
- **NF-002** Authorisation enforced server-side on every request; role checks tested.
- **NF-003** Personal data encrypted in transit and at rest; not written to logs; CSV exports are escaped against formula injection and audited.
- **NF-004** Audit trail per DM-002 retained per Q-011.
- **NF-005** Targets (proposed, unconfirmed): page response under 2 seconds for 95 percent of requests; availability during business hours per Q-013.
- **NF-006** Keyboard accessible and WCAG 2.1 AA (proposed).

## 9. Open questions
All unresolved. No owner has answered; owners below are proposed roles only.
- **Q-001** Which risk rule set is correct: the scoring module (High 6 or more, Medium 3 or more, 6 countries) or the case page's own copy (High 7 or more, Medium 4 or more, also RU and VE)? The prototype shows different ratings in different places. Who owns the country list and points? (owner: compliance owner, unnamed). BLOCKS BR-001 to BR-003.
- **Q-002** May Low-risk cases be approved automatically with no human review? (owner: compliance owner)
- **Q-003** The queue's "Quick approve" lets any user approve a pending case with no role, risk or note check, bypassing the approval matrix. Should it exist at all, for whom? Should the approval matrix be enforced, who may reject or escalate, and is four-eyes required? (owner: compliance owner). BLOCKS FR-009, FR-010, BR-004, BR-010.
- **Q-004** Is the review cycle 1, 2, 3 years to be stored and trigger reminders? (owner: compliance owner)
- **Q-005** What happens to blocked sanctions cases: who reviews, releases or reports them? (owner: compliance officer)
- **Q-006** Which screening provider and matching logic (fuzzy, aliases, date of birth)? (owner: tech lead and compliance)
- **Q-007** Which identity provider, and how are roles assigned? (owner: tech lead)
- **Q-008** Which fields are required and validated (formats of ID numbers, country codes)? (owner: business owner)
- **Q-009** What may the admin role do beyond the analyst roles? (owner: business owner)
- **Q-010** Who may view and export reports containing ID numbers and dates of birth? (owner: compliance owner)
- **Q-011** Retention, deletion and audit retention periods for customer data. (owner: compliance and legal)
- **Q-012** Is ID expiry on the creation day acceptable, and must ID validity be re-checked later? (owner: compliance owner)
- **Q-013** Supported jurisdictions, currency (USD assumed), expected users and volumes, availability target. (owner: business owner)
- **Q-014** Should the legacy dashboard be dropped? (assumed yes) (owner: business owner)
