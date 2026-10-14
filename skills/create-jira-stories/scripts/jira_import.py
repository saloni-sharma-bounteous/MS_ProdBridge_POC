#!/usr/bin/env python3
"""Create a Jira Scrum board, epics and stories from backlog.json.

Standard library only. Targets Jira Cloud (REST API v3 + Agile API).

Works for any app handoff: point it at that app's backlog.json (the file produced by
the hardening-backlog skill, with "app" and "epics" keys).

Usage (dry run is the default; nothing is sent to Jira):
    python jira_import.py apps/<app>/handoff/backlog.json

Credentials come from the environment of the active virtual env. Missing JIRA_* values
are also read from a .env file in the current directory, beside the backlog, or at the
root of the active virtual env's parent folder. Real environment variables take priority.

Create everything:
    set JIRA_BASE_URL=https://yourorg.atlassian.net
    set JIRA_EMAIL=you@example.com
    set JIRA_API_TOKEN=<token from id.atlassian.com/manage-profile/security/api-tokens>
    python jira_import.py apps/<app>/handoff/backlog.json --project KYC --apply

Options:
    --project KEY       Jira project key (required with --apply). Must already exist
                        unless --create-project is given.
    --create-project    Create a company-managed Scrum project (needs Jira admin).
                        Uses --project-name and the lead's account id (looked up from
                        JIRA_EMAIL's account). Without --project, a key is derived from
                        the app name (word initials, e.g. "KYC Onboarding Desk" -> KOD)
                        and the run stops if that key already exists in Jira.
    --board-name NAME   Board name (default: "<app> hardening").
    --state FILE        Idempotency map of backlog id -> Jira key
                        (default: jira_import_state.json next to the backlog file, so
                        each app keeps its own). Re-running skips items
                        already created, so a failed run can be resumed.

Field mapping:
    epic            -> Epic, summary "E-01 <title>", description = goal
    story           -> Story (or --story-type), parent = epic
    priority        -> P0 Highest, P1 High, P2 Medium (override with --priority-map)
    labels          -> story labels + type, severity, effort (e.g. "effort-L"), controls, findings
    acceptance      -> bullet list in the description under "Acceptance criteria"
    depends_on      -> issue link "Blocks" (the dependency blocks this story)

Notes:
    * Effort is stored as a label (effort-S/M/L) because story points are a custom field
      whose id differs per site.
    * The board needs a saved filter; the script creates one on the project
      ("<KEY> hardening backlog") and then a Scrum board on that filter.
"""
import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
import ssl
ctx = ssl.create_default_context()
ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT

DEFAULT_PRIORITY = {"P0": "Highest", "P1": "High", "P2": "Medium"}


class Jira:
    def __init__(self, base, email, token):
        self.base = base.rstrip("/")
        cred = base64.b64encode(f"{email}:{token}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {cred}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def call(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            raise SystemExit(f"Jira {method} {path} failed: HTTP {e.code}\n{detail}")


# ---- Atlassian Document Format helpers ----
def p(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def bullets(items):
    return {
        "type": "bulletList",
        "content": [{"type": "listItem", "content": [p(i)]} for i in items],
    }


def heading(text):
    return {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": text}]}


def adf(*blocks):
    return {"type": "doc", "version": 1, "content": [b for b in blocks if b]}


def story_description(s):
    blocks = [p(s["description"])]
    meta = []
    if s.get("severity"):
        meta.append(f"Severity: {s['severity']}")
    if s.get("effort"):
        meta.append(f"Effort: {s['effort']}")
    if s.get("control_ids"):
        meta.append("Controls: " + ", ".join(s["control_ids"]))
    if s.get("finding_ids"):
        meta.append("Findings: " + ", ".join(s["finding_ids"]))
    if s.get("requirement_refs"):
        meta.append("Requirements: " + ", ".join(s["requirement_refs"]))
    if s.get("depends_on"):
        meta.append("Depends on: " + ", ".join(s["depends_on"]))
    if meta:
        blocks += [heading("Traceability"), bullets(meta)]
    if s.get("acceptance_criteria"):
        blocks += [heading("Acceptance criteria"), bullets(s["acceptance_criteria"])]
    return adf(*blocks)


def clean_label(x):
    return "".join(c if c.isalnum() or c in "-_." else "-" for c in x)


def story_labels(s):
    labels = list(s.get("labels", []))
    labels += [s.get("type"), s.get("severity") and f"severity-{s['severity']}",
               s.get("effort") and f"effort-{s['effort']}"]
    labels += s.get("control_ids", []) + s.get("finding_ids", [])
    seen, out = set(), []
    for l in labels:
        if l and (l := clean_label(l)) not in seen:
            seen.add(l)
            out.append(l)
    return out


def load_state(path):
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(path, state):
    path.write_text(json.dumps(state, indent=2))


def derive_key(app_name):
    """Jira project key from the app name: word initials, else leading letters (2-10 A-Z)."""
    words = re.findall(r"[A-Za-z]+", app_name)
    key = "".join(w[0] for w in words).upper() if len(words) >= 2 else "".join(words).upper()[:5]
    return (key[:10] if len(key) >= 2 else (key + "PRJ"))[:10]


def load_dotenv(*dirs):
    """Fill missing JIRA_* variables from the first .env found. Real environment wins."""
    for d in dirs:
        f = Path(d) / ".env"
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.removeprefix("export ").strip()
            if k.startswith("JIRA_"):
                os.environ.setdefault(k, v.strip().strip("\"'"))
        return f


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually call Jira (default: dry run)")
    ap.add_argument("--project", help="Jira project key")
    ap.add_argument("--project-name", help="name when using --create-project")
    ap.add_argument("--create-project", action="store_true")
    ap.add_argument("--board-name")
    ap.add_argument("backlog", help="path to the app's backlog.json")
    ap.add_argument("--state", help="state file (default: jira_import_state.json beside the backlog)")
    ap.add_argument("--epic-type", default="Epic")
    ap.add_argument("--story-type", default="Story")
    ap.add_argument("--link-type", default="Blocks", help="issue link type for depends_on")
    ap.add_argument("--priority-map", default="", help="e.g. P0=Highest,P1=High,P2=Medium")
    ap.add_argument("--no-priority", action="store_true", help="do not set priority (if screen lacks the field)")
    a = ap.parse_args()

    backlog_path = Path(a.backlog).resolve()
    backlog = json.loads(backlog_path.read_text(encoding="utf-8"))
    for k in ("app", "epics"):
        if k not in backlog:
            sys.exit(f"{backlog_path} is not a backlog file: missing '{k}'")
    pmap = dict(DEFAULT_PRIORITY)
    for pair in filter(None, a.priority_map.split(",")):
        k, v = pair.split("=")
        pmap[k.strip()] = v.strip()

    app_name = backlog["app"]["name"]
    board_name = a.board_name or f"{app_name} hardening"
    epics = backlog["epics"]
    n_stories = sum(len(e["stories"]) for e in epics)

    if not a.apply:
        print(f"DRY RUN: board '{board_name}', {len(epics)} epics, {n_stories} stories\n")
        for e in epics:
            print(f"[Epic] {e['id']} {e['title']}")
            for s in e["stories"]:
                dep = f"  (blocked by {', '.join(s['depends_on'])})" if s.get("depends_on") else ""
                print(f"   [Story] {s['id']} {s['priority']}/{pmap.get(s['priority'])} "
                      f"{s['title']}{dep}")
        print("\nRe-run with --apply and JIRA_* environment variables to create them.")
        return

    load_dotenv(Path.cwd(), backlog_path.parent, Path(sys.prefix).parent)
    for v in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        if not os.environ.get(v):
            sys.exit(f"Missing {v}: set it in the active virtual env or a .env file")
    jira = Jira(os.environ["JIRA_BASE_URL"], os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"])
    state_path = Path(a.state) if a.state else backlog_path.parent / "jira_import_state.json"
    state = load_state(state_path)
    if a.project:
        key = a.project.upper()
    elif a.create_project:
        key = state.get("project") or derive_key(app_name)
        print(f"No --project given; using key {key}")
    else:
        sys.exit("--project is required with --apply (or pass --create-project to derive a key)")

    me = jira.call("GET", "/rest/api/3/myself")
    print(f"Authenticated as {me.get('displayName')}")

    # ---- project ----
    if a.create_project:
        if "project" not in state:
            if not a.project:
                try:
                    jira.call("GET", f"/rest/api/3/project/{key}")
                except SystemExit:
                    pass  # not found: the derived key is free
                else:
                    sys.exit(f"Derived key {key} already exists in Jira; pass --project with a different key")
            res = jira.call("POST", "/rest/api/3/project", {
                "key": key,
                "name": a.project_name or f"{app_name} hardening",
                "projectTypeKey": "software",
                "projectTemplateKey": "com.pyxis.greenhopper.jira:gh-simplified-scrum-classic",
                "leadAccountId": me["accountId"],
                "assigneeType": "UNASSIGNED",
            })
            state["project"] = res["key"]
            save_state(state_path, state)
            print(f"Created project {res['key']}")
    jira.call("GET", f"/rest/api/3/project/{key}")  # fail early if missing

    # ---- epics and stories ----
    def create(kind, backlog_id, fields):
        if backlog_id in state:
            print(f"  skip {backlog_id} (already {state[backlog_id]})")
            return state[backlog_id]
        res = jira.call("POST", "/rest/api/3/issue", {"fields": fields})
        state[backlog_id] = res["key"]
        save_state(state_path, state)
        print(f"  created {kind} {backlog_id} -> {res['key']}")
        return res["key"]

    for e in epics:
        epic_key = create("epic", e["id"], {
            "project": {"key": key},
            "issuetype": {"name": a.epic_type},
            "summary": f"{e['id']} {e['title']}",
            "description": adf(p(e.get("goal", e["title"]))),
        })
        for s in e["stories"]:
            fields = {
                "project": {"key": key},
                "issuetype": {"name": a.story_type},
                "summary": f"{s['id']} {s['title']}"[:255],
                "description": story_description(s),
                "labels": story_labels(s),
                "parent": {"key": epic_key},
            }
            if not a.no_priority:
                fields["priority"] = {"name": pmap[s["priority"]]}
            create("story", s["id"], fields)

    # ---- dependency links ----
    for e in epics:
        for s in e["stories"]:
            for dep in s.get("depends_on", []):
                link_id = f"link:{dep}->{s['id']}"
                if link_id in state:
                    continue
                jira.call("POST", "/rest/api/3/issueLink", {
                    "type": {"name": a.link_type},
                    "inwardIssue": {"key": state[s["id"]]},    # "is blocked by"
                    "outwardIssue": {"key": state[dep]},       # "blocks"
                })
                state[link_id] = True
                save_state(state_path, state)
                print(f"  linked {dep} blocks {s['id']}")

    # ---- filter + scrum board ----
    if "filter" not in state:
        f = jira.call("POST", "/rest/api/3/filter", {
            "name": f"{key} hardening backlog",
            "jql": f"project = {key} ORDER BY Rank ASC",
            "description": f"Backlog for {app_name}, imported from backlog.json",
        })
        state["filter"] = f["id"]
        save_state(state_path, state)
    if "board" not in state:
        b = jira.call("POST", "/rest/agile/1.0/board", {
            "name": board_name,
            "type": "scrum",
            "filterId": int(state["filter"]),
            "location": {"type": "project", "projectKeyOrId": key},
        })
        state["board"] = b["id"]
        save_state(state_path, state)
        print(f"Created board '{board_name}' (id {b['id']})")

    base = os.environ["JIRA_BASE_URL"].rstrip("/")
    print(f"\nDone. Board: {base}/jira/software/projects/{key}/boards/{state['board']}")
    print(f"State saved to {state_path} (re-run is safe; created items are skipped).")


if __name__ == "__main__":
    main()
