# KYC Onboarding Desk

A small, browser-only web app for onboarding customers under Know Your Customer (KYC) rules. Staff sign in, create a customer case, and the app screens the name against sanctions and PEP lists and scores the risk. A reviewer then approves, rejects or escalates the case.

It is a proof of concept: plain HTML, CSS and JavaScript, with no build step, server or database.

## Running it

1. Open `login.html` in a browser, or serve the folder:
   ```
   python -m http.server 8000
   ```
   then visit `http://localhost:8000/login.html`.
2. Sign in with one of the test users (see `js/auth.js`).
3. Three sample cases are created the first time the queue loads.

The only network dependency is jQuery, loaded from a CDN on the Reports page.

## Screens

| Page | Purpose |
|------|---------|
| `login.html` | Sign in |
| `index.html` | Review queue with stats (total, awaiting decision, high risk, blocked) |
| `new-case.html` | Onboard a new customer: validate, screen, score, save |
| `case.html` | Case detail, risk, next review date and the approve / reject / escalate decision |
| `screening.html` | Check any name against the sanctions and PEP lists |
| `reports.html` | Case table filtered by rating, with CSV export |
| `old-dashboard.html` | Legacy page, admin-only link, not in use |

## How a case flows

1. The analyst fills in the new customer form. Name, date of birth and ID details are required, the customer must be 18 or older, and the ID must not be expired.
2. The name is screened. A sanctions match sets the status to `blocked`. A PEP match sets the PEP flag.
3. Risk is scored and rated Low, Medium or High.
4. Low is approved automatically. Medium and High become `pending_review`.
5. A reviewer opens the case and approves, rejects or escalates it with a note.

Case statuses: `pending_review`, `approved`, `rejected`, `escalated`, `blocked`.

## Risk scoring

Points are added for:

- High-risk nationality or country of residence (+3 each)
- Politically exposed person (+3)
- Cash-intensive occupation: casino, money service, car dealer, jewellery (+2)
- Monthly volume over 50,000 (+2), or over 10,000 (+1)
- Source of funds "other" or "unknown" (+2)
- Not met face to face (+1)

In `js/risk.js`, a score of 6 or more is High and 3 or more is Medium. Next review is due in 1 year (High), 2 years (Medium) or 3 years (Low).

## Roles

| Role | Can approve |
|------|-------------|
| `analyst` | Creates cases; cannot approve on the case page |
| `senior_analyst` | Cases not rated High |
| `compliance_officer` | All cases |
| `admin` | All cases; also sees the Legacy link |

## Project layout

```
index.html, login.html, new-case.html, case.html,
screening.html, reports.html, old-dashboard.html
css/style.css        shared styles
js/auth.js           users, login, session
js/store.js          case storage in localStorage (key: kyc_cases)
js/risk.js           risk scoring
js/screening.js      sanctions and PEP name matching
js/nav.js            top navigation
```

Data is kept in the browser: cases in `localStorage`, the signed-in user in `sessionStorage`. Clearing site data resets the app.

## Known issues

This is a proof of concept and not safe for real use as it stands.

- **Two scoring copies.** `case.html` has its own rules (High at 7+, Medium at 4+, and RU and VE counted as high-risk), which differ from `js/risk.js`. The same case can show different ratings on different pages.
- **Quick approve.** The button on the queue approves a pending case with no role or risk check.
- **Credentials.** Users and passwords are hard-coded in plain text in `js/auth.js` (a TODO mentions SSO), and the login page shows test logins.
- **Personal data.** The report and CSV export include date of birth and ID numbers. Case data is in unencrypted localStorage.
- **Screening.** The sanctions and PEP lists are a few hard-coded names matched by substring.
- **Legacy page.** `old-dashboard.html` has commented-out code with a sandbox API key. Remove it.
- **Unused code.** `approverFor()` in `js/risk.js` is not called by any page.

## Mindmap

A visual map of the app is in `../../mindmap/kyc-desk/mindmap.html`.
