#!/usr/bin/env python3
"""KYC Onboarding Desk - a small web app to test agents against.

Standard library only. Data lives in memory (restart or POST /api/reset to restore seed data).

Run:   python kyc_app.py            -> http://localhost:8000
Login: analyst / analyst123
"""
import html
import json
import secrets
import sys
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

USER, PASSWORD = "analyst", "analyst123"
DOCS = ["Photo ID", "Proof of address", "Source of funds"]
HIGH_RISK_COUNTRIES = {"iran", "north korea", "syria", "myanmar", "afghanistan"}
RISKY_JOBS = {"casino owner", "crypto trader", "arms dealer"}
SANCTIONS = {"viktor draven", "imran qasser", "elena marek"}  # fictional watchlist
SESSIONS = set()
APPS = {}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def seed():
    APPS.clear()
    rows = [
        ("Amara Okafor", "1990-04-12", "Nigeria", "Passport", "A1234567", "amara@example.com", "Teacher", "Salary", False),
        ("Viktor Draven", "1985-11-02", "Cyprus", "Passport", "P9988776", "viktor@example.com", "Consultant", "Savings", False),
        ("Lena Hoffmann", "1978-07-23", "Germany", "National ID", "D5566778", "lena@example.com", "Government minister", "Salary", True),
        ("Daniel Reyes", "1992-01-30", "Spain", "Driving licence", "R1122334", "daniel@example.com", "Engineer", "Salary", False),
        ("Sofia Marchetti", "1988-09-15", "Italy", "Passport", "Y7766554", "sofia@example.com", "Crypto trader", "Gift", False),
    ]
    for i, r in enumerate(rows, 1):
        APPS[i] = {
            "id": i, "name": r[0], "dob": r[1], "nationality": r[2], "id_type": r[3], "id_number": r[4],
            "email": r[5], "occupation": r[6], "funds": r[7], "pep": r[8],
            "docs": {d: False for d in DOCS}, "screening": None, "status": "Pending", "reason": "",
            "log": [f"{now()} Application received"],
        }
    APPS[4]["docs"] = {d: True for d in DOCS}
    APPS[4]["screening"] = "Clear"


def risk(a):
    score, why = 10, ["Base score"]
    if a["pep"]:
        score += 40; why.append("Politically exposed person (+40)")
    if a["nationality"].strip().lower() in HIGH_RISK_COUNTRIES:
        score += 35; why.append("High-risk country (+35)")
    if a["occupation"].strip().lower() in RISKY_JOBS:
        score += 20; why.append("High-risk occupation (+20)")
    if a["funds"] in ("Gift", "Unknown"):
        score += 15; why.append("Unverified source of funds (+15)")
    band = "Low" if score < 30 else "Medium" if score < 60 else "High"
    return score, band, why


# ---------- HTML ----------
CSS = """
:root{--bg:#eceee9;--ink:#1c2826;--mut:#5d6b68;--line:#cfd5d0;--pane:#fbfbf9;--acc:#0e5a58;--amb:#a96a12;--red:#a53a2c;--grn:#2d6a3e}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Segoe UI",system-ui,sans-serif}
header{background:var(--ink);color:#f2f4f1;display:flex;align-items:center;gap:28px;padding:0 28px;height:54px}
header b{font-size:17px;letter-spacing:.2px}header a{color:#cfd9d5;text-decoration:none}header a:hover{color:#fff}
header .sp{flex:1}main{max-width:1000px;margin:28px auto;padding:0 20px}
h1{font-size:26px;margin:0 0 4px}h2{font-size:17px;margin:0 0 10px}.sub{color:var(--mut);margin:0 0 20px}
.pane{background:var(--pane);border:1px solid var(--line);border-radius:6px;padding:18px 20px;margin-bottom:18px}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:10px 8px;border-bottom:1px solid var(--line)}
th{color:var(--mut);font-weight:600;font-size:13px}tr:last-child td{border-bottom:0}
a{color:var(--acc)}.chip{display:inline-block;padding:1px 10px;border-radius:99px;font-size:13px;border:1px solid currentColor}
.Pending{color:var(--mut)}.Escalated{color:var(--amb)}.Approved{color:var(--grn)}.Rejected{color:var(--red)}
.Low{color:var(--grn)}.Medium{color:var(--amb)}.High{color:var(--red)}.Hit{color:var(--red)}.Clear{color:var(--grn)}
label{display:block;font-weight:600;margin:12px 0 4px}input,select,textarea{width:100%;padding:8px 10px;border:1px solid #aab3ae;border-radius:4px;font:inherit;background:#fff}
input[type=checkbox]{width:auto;margin-right:8px}.chk{font-weight:400;display:flex;align-items:center}
button{font:inherit;padding:8px 16px;border-radius:4px;border:1px solid var(--acc);background:var(--acc);color:#fff;cursor:pointer}
button.alt{background:transparent;color:var(--acc)}button.bad{background:var(--red);border-color:var(--red)}button.warn{background:var(--amb);border-color:var(--amb)}
button:focus-visible,input:focus-visible,select:focus-visible,textarea:focus-visible,a:focus-visible{outline:3px solid #6fb3ae;outline-offset:2px}
.msg{padding:10px 14px;border-radius:4px;margin-bottom:16px;border:1px solid}.ok{background:#e6f1e8;border-color:var(--grn)}.err{background:#f6e4e0;border-color:var(--red)}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}@media(max-width:760px){.cols{grid-template-columns:1fr}}
dl{display:grid;grid-template-columns:140px 1fr;gap:6px 12px;margin:0}dt{color:var(--mut)}dd{margin:0}
.row{display:flex;gap:10px;align-items:center;justify-content:space-between;padding:6px 0}.acts{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
ul.log{margin:0;padding-left:18px;color:var(--mut);font-size:14px}.login{max-width:360px;margin:80px auto}
"""


def esc(x):
    return html.escape(str(x))


def page(title, body, logged_in=True, msg=None, kind="ok"):
    nav = ""
    if logged_in:
        nav = ('<a href="/queue" data-testid="nav-queue">Queue</a><a href="/new" data-testid="nav-new">New application</a>'
               '<span class="sp"></span><a href="/logout" data-testid="nav-logout">Sign out</a>')
    flash = f'<div class="msg {kind}" role="status" data-testid="message">{esc(msg)}</div>' if msg else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)} - KYC Onboarding Desk</title><style>{CSS}</style></head><body>'
            f'<header><b>KYC Onboarding Desk</b>{nav}</header><main>{flash}{body}</main></body></html>')


def chip(text, cls=None):
    return f'<span class="chip {esc(cls or text)}">{esc(text)}</span>'


def login_page(error=None):
    body = ('<div class="pane login"><h1>Sign in</h1><p class="sub">Use the analyst account to review applications.</p>'
            '<form method="post" action="/login"><label for="u">Username</label><input id="u" name="username" data-testid="username" autocomplete="username">'
            '<label for="p">Password</label><input id="p" name="password" type="password" data-testid="password" autocomplete="current-password">'
            '<div class="acts"><button type="submit" data-testid="login-submit">Sign in</button></div></form></div>')
    return page("Sign in", body, logged_in=False, msg=error, kind="err")


def queue_page(status, msg=None, kind="ok"):
    items = [a for a in APPS.values() if status in ("", "All") or a["status"] == status]
    opts = "".join(f'<option{" selected" if s == status else ""}>{s}</option>' for s in ["All", "Pending", "Escalated", "Approved", "Rejected"])
    rows = "".join(
        f'<tr data-testid="row-{a["id"]}"><td>#{a["id"]}</td><td><a href="/app/{a["id"]}" data-testid="open-{a["id"]}">{esc(a["name"])}</a></td>'
        f'<td>{esc(a["nationality"])}</td><td>{chip(risk(a)[1])}</td><td>{chip(a["status"])}</td></tr>' for a in items
    ) or '<tr><td colspan="5" data-testid="empty">No applications match this filter. Choose All to see everything.</td></tr>'
    body = (f'<h1>Review queue</h1><p class="sub" data-testid="count">{len(items)} application(s)</p>'
            f'<div class="pane"><form method="get" action="/queue" class="row"><label for="s" style="margin:0">Status</label>'
            f'<select id="s" name="status" data-testid="status-filter" style="max-width:200px">{opts}</select>'
            f'<button class="alt" type="submit" data-testid="filter-apply">Apply filter</button></form></div>'
            f'<div class="pane"><table data-testid="queue-table"><tr><th>ID</th><th>Applicant</th><th>Nationality</th><th>Risk</th><th>Status</th></tr>{rows}</table></div>')
    return page("Queue", body, msg=msg, kind=kind)


def new_page(v=None, errors=None):
    v = v or {}
    err = "".join(f"<li>{esc(e)}</li>" for e in errors or [])
    flash = f'<div class="msg err" role="alert" data-testid="form-errors"><ul style="margin:0;padding-left:18px">{err}</ul></div>' if err else ""

    def f(name, label, typ="text", ph=""):
        return (f'<label for="{name}">{label}</label><input id="{name}" name="{name}" type="{typ}" placeholder="{ph}" '
                f'value="{esc(v.get(name, ""))}" data-testid="{name}">')

    def sel(name, label, options):
        o = "".join(f'<option{" selected" if v.get(name) == x else ""}>{x}</option>' for x in options)
        return f'<label for="{name}">{label}</label><select id="{name}" name="{name}" data-testid="{name}">{o}</select>'

    body = (f'<h1>New application</h1><p class="sub">Capture the applicant details. All fields except the PEP box are required.</p>{flash}'
            '<form method="post" action="/new" class="pane">'
            + f("name", "Full name") + f("dob", "Date of birth", "date") + f("nationality", "Nationality", ph="e.g. Germany")
            + sel("id_type", "ID type", ["Passport", "National ID", "Driving licence"]) + f("id_number", "ID number")
            + f("email", "Email", "email") + f("occupation", "Occupation")
            + sel("funds", "Source of funds", ["Salary", "Savings", "Business income", "Gift", "Unknown"])
            + f'<label class="chk"><input type="checkbox" name="pep" value="1" data-testid="pep"{" checked" if v.get("pep") else ""}>Applicant is a politically exposed person</label>'
            '<div class="acts"><button type="submit" data-testid="submit-application">Submit application</button></div></form>')
    return page("New application", body)


def detail_page(a, msg=None, kind="ok"):
    score, band, why = risk(a)
    docs = "".join(
        f'<form method="post" action="/app/{a["id"]}/doc" class="row" data-testid="doc-{i}"><span>{d} {chip("Verified" if ok else "Missing", "Clear" if ok else "Pending")}</span>'
        f'<input type="hidden" name="doc" value="{d}"><button class="alt" type="submit" data-testid="toggle-doc-{i}">{"Mark missing" if ok else "Mark verified"}</button></form>'
        for i, (d, ok) in enumerate(a["docs"].items()))
    scr = a["screening"]
    scr_html = chip(scr) if scr else '<span class="Pending">Not run</span>'
    final = a["status"] in ("Approved", "Rejected")
    decide = (f'<p data-testid="final-note">This case is closed ({esc(a["status"])}).</p>' if final else
              f'<form method="post" action="/app/{a["id"]}/decide"><label for="reason">Reason (required to reject or escalate)</label>'
              f'<textarea id="reason" name="reason" rows="3" data-testid="reason"></textarea><div class="acts">'
              f'<button name="action" value="approve" data-testid="approve">Approve</button>'
              f'<button name="action" value="escalate" class="warn" data-testid="escalate">Escalate</button>'
              f'<button name="action" value="reject" class="bad" data-testid="reject">Reject</button></div></form>')
    body = (f'<p><a href="/queue">Back to queue</a></p><h1 data-testid="applicant-name">{esc(a["name"])}</h1>'
            f'<p class="sub">Application #{a["id"]} &middot; <span data-testid="status">{chip(a["status"])}</span></p>'
            f'<div class="cols"><div class="pane"><h2>Applicant</h2><dl><dt>Date of birth</dt><dd>{esc(a["dob"])}</dd><dt>Nationality</dt><dd>{esc(a["nationality"])}</dd>'
            f'<dt>ID</dt><dd>{esc(a["id_type"])} {esc(a["id_number"])}</dd><dt>Email</dt><dd>{esc(a["email"])}</dd><dt>Occupation</dt><dd>{esc(a["occupation"])}</dd>'
            f'<dt>Source of funds</dt><dd>{esc(a["funds"])}</dd><dt>PEP</dt><dd>{"Yes" if a["pep"] else "No"}</dd></dl></div>'
            f'<div class="pane"><h2>Risk</h2><p><span data-testid="risk-band">{chip(band)}</span> score <span data-testid="risk-score">{score}</span></p>'
            f'<ul style="margin:0;padding-left:18px;color:var(--mut)">{"".join(f"<li>{esc(w)}</li>" for w in why)}</ul></div></div>'
            f'<div class="cols"><div class="pane"><h2>Documents</h2>{docs}</div>'
            f'<div class="pane"><h2>Sanctions screening</h2><p data-testid="screening">{scr_html}</p>'
            f'<form method="post" action="/app/{a["id"]}/screen"><button class="alt" type="submit" data-testid="run-screening">Run screening</button></form></div></div>'
            f'<div class="pane"><h2>Decision</h2>{decide}'
            f'{"<p data-testid=reason-shown>Reason: " + esc(a["reason"]) + "</p>" if a["reason"] else ""}</div>'
            f'<div class="pane"><h2>Audit log</h2><ul class="log" data-testid="audit-log">{"".join(f"<li>{esc(x)}</li>" for x in reversed(a["log"]))}</ul></div>')
    return page(a["name"], body, msg=msg, kind=kind)


# ---------- logic ----------
def validate(f):
    e = []
    for k, label in [("name", "Full name"), ("dob", "Date of birth"), ("nationality", "Nationality"),
                     ("id_number", "ID number"), ("email", "Email"), ("occupation", "Occupation")]:
        if not f.get(k, "").strip():
            e.append(f"{label} is required.")
    if f.get("dob", "").strip():
        try:
            d = datetime.strptime(f["dob"], "%Y-%m-%d").date()
            age = (date.today() - d).days // 365
            if age < 18:
                e.append("Applicant must be at least 18 years old.")
        except ValueError:
            e.append("Date of birth must be a valid date (YYYY-MM-DD).")
    if f.get("email", "").strip() and ("@" not in f["email"] or "." not in f["email"].split("@")[-1]):
        e.append("Email must be a valid address, like name@example.com.")
    if f.get("id_number", "").strip() and len(f["id_number"].strip()) < 5:
        e.append("ID number must be at least 5 characters.")
    return e


def decide(a, action, reason):
    """Returns (ok, message)."""
    if a["status"] in ("Approved", "Rejected"):
        return False, "This case is already closed."
    if action in ("reject", "escalate") and not reason:
        return False, f"Enter a reason before you {action}."
    if action == "approve":
        if not all(a["docs"].values()):
            return False, "Verify all three documents before approving."
        if a["screening"] is None:
            return False, "Run sanctions screening before approving."
        if a["screening"] == "Hit":
            return False, "Sanctions hit: this application cannot be approved."
        if risk(a)[1] == "High" and a["status"] != "Escalated":
            return False, "High-risk applications must be escalated before approval."
        a["status"] = "Approved"
    elif action == "reject":
        a["status"], a["reason"] = "Rejected", reason
    elif action == "escalate":
        a["status"], a["reason"] = "Escalated", reason
    else:
        return False, "Unknown action."
    a["log"].append(f"{now()} Case {a['status'].lower()}" + (f": {reason}" if reason else ""))
    return True, f"Application {a['status'].lower()}."


# ---------- server ----------
class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    def sid(self):
        for part in self.headers.get("Cookie", "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "sid" and v in SESSIONS:
                return v

    def send(self, body, code=200, ctype="text/html; charset=utf-8", cookie=None):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, to, cookie=None):
        self.send_response(303)
        self.send_header("Location", to)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def form(self):
        n = int(self.headers.get("Content-Length") or 0)
        return {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode()).items()}

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        if u.path == "/health":
            return self.send(json.dumps({"status": "ok"}), ctype="application/json")
        if u.path == "/login":
            return self.send(login_page())
        if u.path == "/logout":
            SESSIONS.discard(self.sid())
            return self.redirect("/login", "sid=; Max-Age=0; Path=/")
        if not self.sid():
            return self.redirect("/login")
        if u.path == "/":
            return self.redirect("/queue")
        if u.path == "/queue":
            return self.send(queue_page(q.get("status", "All"), q.get("msg"), q.get("kind", "ok")))
        if u.path == "/new":
            return self.send(new_page())
        if u.path == "/api/applications":
            return self.send(json.dumps([{**a, "risk": risk(a)[1]} for a in APPS.values()]), ctype="application/json")
        if u.path.startswith("/app/"):
            a = APPS.get(int(u.path.split("/")[2])) if u.path.split("/")[2].isdigit() else None
            if a:
                return self.send(detail_page(a, q.get("msg"), q.get("kind", "ok")))
        self.send(page("Not found", '<h1>Page not found</h1><p><a href="/queue">Go to the queue</a></p>'), 404)

    def do_POST(self):
        u = urlparse(self.path)
        if u.path == "/api/reset":
            seed()
            return self.send(json.dumps({"reset": True}), ctype="application/json")
        f = self.form()
        if u.path == "/login":
            if f.get("username") == USER and f.get("password") == PASSWORD:
                s = secrets.token_hex(16)
                SESSIONS.add(s)
                return self.redirect("/queue", f"sid={s}; Path=/; HttpOnly")
            return self.send(login_page("Username or password is incorrect."), 401)
        if not self.sid():
            return self.redirect("/login")
        if u.path == "/new":
            f["pep"] = bool(f.get("pep"))
            errors = validate(f)
            if errors:
                return self.send(new_page(f, errors), 400)
            nid = max(APPS) + 1
            APPS[nid] = {
                "id": nid, "name": f["name"].strip(), "dob": f["dob"], "nationality": f["nationality"].strip(),
                "id_type": f.get("id_type", "Passport"), "id_number": f["id_number"].strip(), "email": f["email"].strip(),
                "occupation": f["occupation"].strip(), "funds": f.get("funds", "Salary"), "pep": f["pep"],
                "docs": {d: False for d in DOCS}, "screening": None, "status": "Pending", "reason": "",
                "log": [f"{now()} Application received"],
            }
            return self.redirect(f"/app/{nid}?msg={quote('Application created.')}")
        parts = u.path.split("/")
        if len(parts) == 4 and parts[1] == "app" and parts[2].isdigit() and int(parts[2]) in APPS:
            a, act = APPS[int(parts[2])], parts[3]
            back = f"/app/{a['id']}"
            if a["status"] in ("Approved", "Rejected") and act != "decide":
                return self.redirect(f"{back}?kind=err&msg={quote('This case is closed.')}")
            if act == "doc" and f.get("doc") in a["docs"]:
                a["docs"][f["doc"]] = not a["docs"][f["doc"]]
                a["log"].append(f"{now()} {f['doc']} marked {'verified' if a['docs'][f['doc']] else 'missing'}")
                return self.redirect(f"{back}?msg={quote(f['doc'] + ' updated.')}")
            if act == "screen":
                a["screening"] = "Hit" if a["name"].strip().lower() in SANCTIONS else "Clear"
                a["log"].append(f"{now()} Sanctions screening: {a['screening']}")
                return self.redirect(f"{back}?msg={quote('Screening result: ' + a['screening'])}")
            if act == "decide":
                ok, m = decide(a, f.get("action", ""), f.get("reason", "").strip())
                return self.redirect(f"{back}?kind={'ok' if ok else 'err'}&msg={quote(m)}")
        self.send(page("Not found", "<h1>Page not found</h1>"), 404)


if __name__ == "__main__":
    seed()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"KYC Onboarding Desk running at http://localhost:{port}  (login: {USER} / {PASSWORD})")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()