#!/usr/bin/env python3
"""Capture a running UI with Playwright: screenshots, controls, forms, links, network calls (read-only crawl).

Input is a URL, an .html file, or a folder of static files (served locally on a random port). The crawl follows
same-origin links breadth-first and writes, per screen, a screenshot and a snapshot in the same format as
ui_snapshot_static.py.

Safety: it never types into fields, never submits forms, skips links whose text or address looks destructive
(logout, delete, remove, pay, ...) and records network calls without request bodies, headers or token values.
For pages behind a login, sign in yourself once and pass the saved browser state (see references/playwright-capture.md);
this script never accepts a password. Screenshots may show personal data: capture synthetic data only.

Scripted states: --states states.json is a list like
  [{"name": "employee", "steps": [{"action": "fill", "locator": "#name", "value": "Test User"},
                                  {"action": "select", "locator": "#role", "value": "employee"},
                                  {"action": "click", "locator": "text=Enter"}]}]
Each state is loaded fresh, the steps run, and the screen is captured as <screen>@<state>. Actions: fill, select,
check, click, wait (milliseconds). Use synthetic values only: steps that fill a field whose locator or value looks
like a password, token or secret are refused.

Requires: pip install playwright && playwright install chromium   (not needed for static snapshots)
Usage:
  python3 ui_capture.py --url https://pilot.example.test/ --out handoff/ui [--max-pages 25] [--storage-state state.json]
  python3 ui_capture.py --input prototype/ --out handoff/ui
  python3 ui_capture.py --check            # is Playwright installed and can it start a browser?
Exit: 0 ok, 2 usage error, 3 Playwright missing or the browser cannot start.
"""
import argparse
import functools
import http.server
import json
import os
import re
import socketserver
import sys
import threading
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ui_snapshot_static import locator, slug  # noqa: E402

DESTRUCTIVE = re.compile(r"(?i)(log\s?out|sign\s?out|delete|remove|destroy|cancel account|pay|purchase|buy|approve|reject|submit|send|confirm|reset|unsubscribe)")
SAFE_CLICK = re.compile(r"(?i)^(open|view|show|details|more|menu|filter|search|expand|next|previous|tab|overview|settings)\b")
SECRET_KEY = re.compile(r"(?i)(token|key|secret|password|passwd|auth|session|signature|code)")


def redact_url(u):
    p = urlparse(u)
    q = [(k, "<redacted>" if SECRET_KEY.search(k) else v) for k, v in parse_qsl(p.query, keep_blank_values=True)]
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q, safe="<>"), ""))


def serve(directory):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    handler.log_message = lambda *a, **k: None
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.TCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/" % srv.server_address[1]


def screen_id(url, base):
    p = urlparse(url)
    path = p.path.rstrip("/") or "index"
    s = slug(path.lstrip("/")) or "index"
    if p.fragment and p.fragment.startswith("/"):
        s += "-" + slug(p.fragment)
    return s or "index"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url")
    ap.add_argument("--input", help="an .html file or a folder to serve locally")
    ap.add_argument("--out")
    ap.add_argument("--max-pages", type=int, default=25)
    ap.add_argument("--viewport", default="1280x800")
    ap.add_argument("--storage-state", help="saved browser state for pages behind a login (made with playwright codegen --save-storage)")
    ap.add_argument("--states", help="JSON file describing scripted UI states (see above)")
    ap.add_argument("--click-safe", action="store_true", help="also click buttons whose text looks harmless (open, view, filter, next, ...)")
    ap.add_argument("--timeout", type=int, default=15000)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--channel", help="use an installed browser instead of Playwright's download: chrome or msedge (useful behind a proxy)")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is not installed. Install it with:\n  pip install playwright\n  playwright install chromium\n"
              "Or use ui_snapshot_static.py for plain HTML files (no browser needed).", file=sys.stderr)
        return 3
    if a.check:
        try:
            with sync_playwright() as pw:
                b = pw.chromium.launch(headless=True, channel=a.channel)
                b.close()
            print("Playwright and Chromium are ready.")
            return 0
        except Exception as exc:  # noqa: BLE001
            print("Playwright is installed but the browser cannot start: %s\nRun: playwright install chromium" % exc, file=sys.stderr)
            return 3
    if not a.out or not (a.url or a.input):
        print("ERROR: give --out and either --url or --input", file=sys.stderr)
        return 2
    js = open(os.path.join(HERE, "..", "assets", "snapshot.js"), encoding="utf-8").read()
    srv, start = None, a.url
    if a.input:
        path = os.path.abspath(a.input)
        if os.path.isfile(path):
            srv, base = serve(os.path.dirname(path))
            start = base + os.path.basename(path)
        elif os.path.isdir(path):
            srv, base = serve(path)
            pages = sorted(f for f in os.listdir(path) if f.lower().endswith((".html", ".htm")))
            start = base + ("index.html" if os.path.exists(os.path.join(path, "index.html")) else (pages[0] if pages else ""))
        else:
            print("ERROR: input not found", file=sys.stderr)
            return 2
    w, h = [int(x) for x in a.viewport.split("x")]
    shots = os.path.join(a.out, "screens")
    os.makedirs(shots, exist_ok=True)
    origin = urlparse(start).netloc
    seen, queue, count = set(), [start], 0
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, channel=a.channel)
            ctx = browser.new_context(viewport={"width": w, "height": h}, storage_state=a.storage_state) if a.storage_state else browser.new_context(viewport={"width": w, "height": h})
            page = ctx.new_page()
            page.set_default_timeout(a.timeout)
            net, errors = [], []
            page.on("response", lambda r: net.append({"method": r.request.method, "url": redact_url(r.url), "status": r.status, "type": r.request.resource_type})
                    if r.request.resource_type in ("xhr", "fetch") else None)
            page.on("pageerror", lambda e: errors.append(str(e)[:200]))
            page.on("console", lambda m: errors.append(m.text[:200]) if m.type == "error" else None)
            def snapshot(page, sid, state=""):
                snap = page.evaluate(js)
                png = os.path.join("screens", sid + ".png")
                page.screenshot(path=os.path.join(a.out, png), full_page=True)
                for i, e in enumerate(snap["elements"]):
                    e["eid"] = "e%d" % (i + 1)
                    e["name"] = e["aria_label"] or e["label"] or e["text"] or e["placeholder"] or e["title"] or e["name_attr"] or e["id"]
                    e["locator"] = locator(e, e["label"])
                for f in snap["forms"]:
                    f["fields"] = [e["eid"] for e in snap["elements"] if e["form"] == f["id"] and e["kind"] in ("input", "select", "textarea", "checkbox", "radio")]
                    f["submit"] = [e["eid"] for e in snap["elements"] if e["form"] == f["id"] and e["kind"] == "button" and e["type"] == "submit"]
                snap.update({"id": sid, "state": state, "source": "", "url": redact_url(page.url), "viewport": {"width": w, "height": h}, "screenshot": png.replace(os.sep, "/"),
                             "inline_script_count": 0, "rendered_by_script": False, "script_navigation": [], "browser_storage_keys": [],
                             "network": [dict(n, trigger="load" if not state else "state:" + state) for n in net], "console_errors": list(errors), "mode": "live"})
                return snap

            if a.states:
                for st in json.load(open(a.states, encoding="utf-8")):
                    sctx = browser.new_context(viewport={"width": w, "height": h}, storage_state=a.storage_state) if a.storage_state else browser.new_context(viewport={"width": w, "height": h})
                    sp = sctx.new_page()
                    sp.set_default_timeout(a.timeout)
                    net2, err2 = [], []
                    sp.on("response", lambda r, n=net2: n.append({"method": r.request.method, "url": redact_url(r.url), "status": r.status, "type": r.request.resource_type})
                          if r.request.resource_type in ("xhr", "fetch") else None)
                    sp.goto(st.get("start") or start, wait_until="load")
                    ok = True
                    for step in st["steps"]:
                        act, loc, val = step["action"], step.get("locator", ""), step.get("value", "")
                        is_pw = False
                        if act == "fill":
                            try:
                                is_pw = (sp.locator(loc).first.get_attribute("type") or "").lower() == "password"
                            except Exception:  # noqa: BLE001
                                is_pw = False
                        if act in ("fill", "select") and (is_pw or SECRET_KEY.search(loc) or SECRET_KEY.search(str(val)) or re.search(r"(?i)pass", loc)):
                            print("state %s: refused step on a secret-looking field (%s); use --storage-state instead" % (st["name"], loc), file=sys.stderr)
                            ok = False
                            break
                        if act == "fill":
                            sp.locator(loc).fill(val)
                        elif act == "select":
                            sp.locator(loc).select_option(val)
                        elif act == "check":
                            sp.locator(loc).check()
                        elif act == "click":
                            sp.locator(loc).click()
                        elif act == "wait":
                            sp.wait_for_timeout(int(val or 300))
                    if ok:
                        sp.wait_for_timeout(300)
                        net_save, err_save = net, errors
                        net, errors = net2, err2
                        snap = snapshot(sp, "%s@%s" % (screen_id(sp.url, start), st["name"]), st["name"])
                        net, errors = net_save, err_save
                        snap["state_steps"] = [{"action": x["action"], "locator": x.get("locator", ""), "value": ("<value>" if x["action"] in ("fill", "select") else "")} for x in st["steps"]]
                        json.dump(snap, open(os.path.join(a.out, snap["id"].replace("@", "__") + ".snapshot.json"), "w", encoding="utf-8"), indent=1)
                        count += 1
                    sctx.close()
            while queue and count < a.max_pages:
                url = queue.pop(0)
                key = url.split("#")[0] if "#/" not in url else url
                if key in seen:
                    continue
                seen.add(key)
                del net[:]
                del errors[:]
                try:
                    page.goto(url, wait_until="load")
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:  # noqa: BLE001
                        pass
                except Exception as exc:  # noqa: BLE001
                    print("could not load %s: %s" % (redact_url(url), str(exc)[:120]), file=sys.stderr)
                    continue
                snap = snapshot(page, screen_id(page.url, start))
                sid = snap["id"]
                if a.click_safe:
                    for e in snap["elements"]:
                        if e["kind"] == "button" and e["visible"] and SAFE_CLICK.match(e["name"] or "") and not DESTRUCTIVE.search(e["name"] or "") and e["type"] != "submit":
                            before = page.url
                            del net[:]
                            try:
                                page.get_by_role("button", name=e["name"]).first.click(timeout=3000)
                                page.wait_for_timeout(500)
                            except Exception:  # noqa: BLE001
                                continue
                            e["click_result"] = {"url_changed": page.url != before, "to": redact_url(page.url), "network": [dict(n) for n in net]}
                            if page.url != before:
                                page.goto(before)
                json.dump(snap, open(os.path.join(a.out, sid + ".snapshot.json"), "w", encoding="utf-8"), indent=1)
                count += 1
                for e in snap["elements"]:
                    if e["kind"] == "link" and e["href"] and not e["href"].startswith(("mailto:", "tel:", "javascript:")) and not DESTRUCTIVE.search(e["name"] or e["href"]):
                        target = urljoin(page.url, e["href"])
                        if urlparse(target).netloc == origin and target not in queue:
                            queue.append(target)
            browser.close()
    finally:
        if srv:
            srv.shutdown()
    print("live capture: %d screens, screenshots in %s" % (count, shots))
    return 0


if __name__ == "__main__":
    sys.exit(main())
