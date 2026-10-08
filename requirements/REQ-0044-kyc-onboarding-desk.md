# REQ-0044: Customer KYC Onboarding Desk

**Requested by:** Retail Onboarding and Financial Crime Compliance
**Date:** 2025-02-10

## Problem
Onboarding analysts capture customer details in a shared spreadsheet. Risk ratings differ between
analysts, sanctions checks are done by hand, and compliance cannot show who approved a high-risk customer.

## Users
Analyst, Senior Analyst, Compliance Officer, Admin.

## Business rules
| ID | Rule |
|----|------|
| BR-1 | Customers must be 18 or older. Expired ID documents are not accepted. |
| BR-2 | Customer name is screened against the sanctions list; a match blocks onboarding and is reported to Compliance. |
| BR-3 | A PEP match sets the PEP flag and raises the risk score. |
| BR-4 | Risk score: high-risk nationality +3, high-risk residence +3, PEP +3, cash-intensive occupation +2, monthly volume over 50,000 +2 (over 10,000 +1), source of funds other/unknown +2, non face-to-face +1. |
| BR-5 | Rating: score 0-2 Low, 3-5 Medium, 6 or more High. One definition used everywhere. |
| BR-6 | Approval: Low by analyst (automatic), Medium by Senior Analyst, High by Compliance Officer after enhanced due diligence. |
| BR-7 | Periodic review: High every 1 year, Medium every 2 years, Low every 3 years. |
| BR-8 | Maker-checker: the person who created a case cannot approve it. |

## Functional requirements
- FR-1 Sign in with bank SSO and role-based access.
- FR-2 Capture customer and ID details; run screening and risk scoring on submit.
- FR-3 Queue of cases awaiting decision with status.
- FR-4 Case page with decision (approve, reject, escalate) and a mandatory decision note.
- FR-5 Ad-hoc name screening.
- FR-6 Report of cases filtered by rating, exportable.
- FR-7 Upload and store a copy of the ID document.
- FR-8 Audit log of every view, change and decision.
- FR-9 Automatic task to the analyst when a periodic review falls due.

## Non-functional requirements
- NFR-1 ID numbers and dates of birth are personal data: encrypted at rest, masked on screen and in exports except for Compliance.
- NFR-2 Screening list must come from the bank's approved provider and be refreshed daily.
- NFR-3 Records retained 5 years after the relationship ends.
