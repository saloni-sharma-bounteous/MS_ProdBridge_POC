# Spec: KYC Onboarding Desk (Live_Test_App)

Status: DRAFT for review. Source: handoff/live-test-app/understanding.md. Rules marked "as built" are taken from the prototype and are not yet confirmed as the intended production rules (see Section 9).

## 1. Scope
A production web application for onboarding analysts to review customer KYC applications: capture applicant details, verify documents, screen against sanctions, see a risk score and band, and approve, escalate or reject with an audit trail.

Out of scope: periodic review tasks, ID document upload, reports and CSV export, ad-hoc screening page, and changes to apps/html-kyc-onboarding-desk and its Jira stories (MSPOC-1 to MSPOC-33). Any of these can be added if the owner decides so (Q-003, Q-008).

## 2. Actors
- Analyst: signs in, creates applications, verifies documents, runs screening, approves, escalates or rejects (authority limits pending Q-002).
- Other roles (for example senior analyst, compliance officer, admin): not defined in the prototype; to be decided in Q-002.

## 3. Functional requirements
- **FR-001** A user signs in with an individual identity; an unauthenticated user can reach only the sign-in page and the health check.
- **FR-002** A signed-in user can sign out; the session ends and the user returns to sign-in.
- **FR-003** A user can view the review queue and filter by status (All, Pending, Escalated, Approved, Rejected); the queue shows the count, and each row shows ID, applicant, nationality, risk band and status. An empty filter shows a message.
- **FR-004** A user can create an application with full name, date of birth, nationality, ID type (Passport, National ID, Driving licence), ID number, email, occupation, source of funds (Salary, Savings, Business income, Gift, Unknown) and a PEP flag; the system validates per BR-001 to BR-004 and shows every error at once, keeping the entered values.
- **FR-005** A new application starts as Pending with all three documents unverified, screening not run, and an audit entry "Application received".
- **FR-006** A user can open a case and see applicant details, risk score with the reasons for it, documents, screening result, decision and audit log.
- **FR-007** A user can toggle each of the three documents (Photo ID, Proof of address, Source of funds) between Verified and Missing on an open case.
- **FR-008** A user can run sanctions screening on an open case; the result is Clear or Hit and is recorded.
- **FR-009** A user can approve, escalate or reject an open case, subject to BR-006 to BR-009; the system shows a clear message when an action is refused.
- **FR-010** Approved and Rejected cases are closed and read-only; no document, screening or decision change is accepted.
- **FR-011** Every create, document change, screening and decision is written to the audit log with time and the acting user.
- **FR-012** An unknown case number shows a "not found" page with a link to the queue.

## 4. Business rules
- **BR-001** Required: full name, date of birth, nationality, ID number, email, occupation. ID type and source of funds must be one of the listed values. (as built)
- **BR-002** Applicant must be 18 or older on the day of submission, calculated by calendar date (the prototype uses days/365, which is approximate; correct to exact age). Date format YYYY-MM-DD. Whether exactly 18 passes: yes, 18 is allowed.
- **BR-003** Email must contain "@" and a dot after it. ID number must be at least 5 characters after trimming. (as built)
- **BR-004** Expired ID documents are not accepted (from REQ-0044 BR-1). Expiry date is not captured by the prototype; see Q-009.
- **BR-005** Risk score (as built, pending Q-002): start at 10; add 40 if PEP; add 35 if nationality is one of Iran, North Korea, Syria, Myanmar, Afghanistan (case-insensitive); add 20 if occupation is Casino owner, Crypto trader or Arms dealer; add 15 if source of funds is Gift or Unknown. Band: Low below 30, Medium 30 to 59, High 60 and above. The same band definition is used on every screen.
- **BR-006** Reject and escalate require a non-empty reason.
- **BR-007** Approve requires: all three documents Verified; screening has been run; screening result is not Hit.
- **BR-008** A High-risk case can be approved only after it has been Escalated. (as built; who may approve is Q-002)
- **BR-009** Screening is a case-insensitive exact match of the full name (as built). A Hit blocks approval and must be reported to Compliance (REQ-0044 BR-2; mechanism in Q-004).
- **BR-010** Maker-checker: whether the creator may approve their own case is undecided (Q-002). The prototype allows it.

## 5. Data
- **DM-001** Application: id, name, date of birth, nationality, ID type, ID number, email, occupation, source of funds, PEP flag, status (Pending, Escalated, Approved, Rejected), decision reason, created time, created by. Owner: onboarding team. Retention: Q-005.
- **DM-002** Document check: application, document name (Photo ID, Proof of address, Source of funds), verified flag, who and when.
- **DM-003** Screening result: application, result (Clear, Hit), list version and provider, who and when. History is kept, not overwritten.
- **DM-004** Audit entry: application, time, actor, action, detail. Append-only.
- **DM-005** User and role: identity, role, active flag (shape depends on Q-002 and Q-005).
- **DM-006** Personal data: name, date of birth, ID number and email are personal data and are protected per NF-002.

## 6. Screens
- **UI-001** Sign-in: username and password (or SSO per Q-005); shows a clear error on failure.
- **UI-002** Review queue: filter and table per FR-003; visible to all signed-in roles.
- **UI-003** New application: form per FR-004 with inline error list.
- **UI-004** Case detail: panels for applicant, risk, documents, screening, decision, audit log.
- **UI-005** Not found and error pages with a way back.

## 7. Integrations
- **IN-001** Sanctions screening provider: sends applicant name (and possibly date of birth and nationality); returns Clear or Hit. If the provider fails, screening shows an error, no result is recorded, and approval stays blocked. Provider and matching style: Q-004.
- **IN-002** Identity provider for sign-in: Q-005.

## 8. Non-functional
- **NF-001** Access: every page and data endpoint except sign-in and health requires authentication; permissions are enforced on the server.
- **NF-002** Personal data (ID number, date of birth) is encrypted at rest and masked on screen and in any export except for roles named in Q-005.
- **NF-003** All state-changing requests are protected against cross-site request forgery; sign-out is not a GET; session cookies are HttpOnly, Secure and SameSite.
- **NF-004** No credentials in source code or logs; secrets come from configuration.
- **NF-005** The data reset and bulk-list endpoints of the prototype are not present in production (Q-006).
- **NF-006** Data is stored in a durable database, not memory; the audit log cannot be edited or deleted by users.
- **NF-007** Pages are usable by keyboard and screen reader (labels on all inputs, visible focus, status messages announced). Target level WCAG 2.2 AA.
- **NF-008** Health endpoint for monitoring; performance and availability targets: Q-005.

## 9. Open questions
- **Q-001** Confirm Live_Test_App is the production target and stays separate from html-kyc-onboarding-desk. (Reported by coordinator as confirmed by Saloni Sharma; owner: Saloni Sharma)
- **Q-002** Which risk scoring and band rules are authoritative: this app's (BR-005) or REQ-0044 BR-4/BR-5 (points of 3/2/1, bands 0-2, 3-5, 6+)? Which roles exist, who may approve each band, and is maker-checker required? (owner: business owner, Compliance)
- **Q-003** Is the prototype's scope complete, or are REQ-0044 items such as reports, ID upload, periodic review and ad-hoc screening required? (owner: business owner)
- **Q-004** Which sanctions provider, exact or fuzzy matching, list refresh frequency, and how is a Hit reported to Compliance? (owner: Compliance)
- **Q-005** Data protection and platform: retention period, who may see unmasked data, encryption approach, hosting, SSO provider, availability and performance targets. (owner: tech lead, security)
- **Q-006** Confirm that the reset endpoint and the all-applications JSON endpoint are removed in production. Recommendation: remove both. (owner: business owner, tech lead)
- **Q-007** Should an approval also require a reason or note? The prototype does not. (owner: business owner)
- **Q-008** Is PEP determined by the analyst's checkbox only, or by a PEP list check? (owner: Compliance)
- **Q-009** Should ID type, issue and expiry date be captured so BR-004 can be enforced? Which high-risk country list applies, and to nationality only or also residence? (owner: Compliance)
