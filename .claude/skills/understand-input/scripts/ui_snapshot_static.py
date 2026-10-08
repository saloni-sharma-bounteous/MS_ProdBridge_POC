#!/usr/bin/env python3
"""Turn HTML files into UI snapshots without a browser (standard library only).

A snapshot lists one screen's headings, controls (links, buttons, inputs, selects, textareas), forms, tables,
scripts, inline event handlers, fetch/XHR calls and script-driven navigation, each with its source line and a
Playwright locator. It is the same format ui_capture.py produces from a live page, so the same tools treat
them alike.

Limits: it reads the HTML as written. Screens that build their markup with JavaScript (innerHTML, createElement)
are flagged rendered_by_script: true because their real controls are only visible in a live capture.
Input values are never recorded.

Usage: python3 ui_snapshot_static.py --input <file.html|folder> --out <dir>
Python 3.8+, standard library only.
"""
import argparse
import json
import os
import re
import sys
from html.parser import HTMLParser

VOID = {"input", "br", "img", "hr", "meta", "link", "area", "base", "col", "embed", "source", "track", "wbr"}
TEXT_TAGS = {"a", "button", "label", "h1", "h2", "h3", "th", "option", "summary", "legend", "title", "td"}
IMPLICIT_ROLE = {"a": "link", "button": "button", "select": "combobox", "textarea": "textbox", "table": "table", "form": "form"}
INPUT_ROLE = {"checkbox": "checkbox", "radio": "radio", "submit": "button", "button": "button", "reset": "button", "range": "slider"}
SECRETISH = re.compile(r"(?i)(token|secret|password|passwd|apikey|api_key|auth)")


def slug(rel):
    return re.sub(r"[^a-z0-9]+", "-", os.path.splitext(rel)[0].lower()).strip("-") or "screen"


def pyq(s):
    return json.dumps(s)


class Parser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.title = ""
        self.headings, self.elements, self.forms, self.tables, self.scripts, self.inline_scripts = [], [], [], [], [], []
        self.labels_for = {}
        self.stack = []        # open elements that collect text: [tag, element-or-None, text-list]
        self.form_stack = []
        self.label_stack = []
        self.cur_script = None
        self.cur_table = None
        self.select_depth = 0

    def attrs(self, attrs):
        return {k: (v if v is not None else "") for k, v in attrs}

    def handle_starttag(self, tag, attrs):
        a = self.attrs(attrs)
        line = self.getpos()[0]
        if tag == "script":
            if a.get("src"):
                self.scripts.append(a["src"])
            self.cur_script = {"line": line, "text": []}
            return
        if tag == "form":
            f = {"id": "form-%d" % (len(self.forms) + 1), "dom_id": a.get("id", ""), "action": a.get("action", ""),
                 "method": (a.get("method") or "").lower(), "fields": [], "submit": [], "line": line}
            self.forms.append(f)
            self.form_stack.append(f)
        if tag == "table":
            self.cur_table = {"id": "table-%d" % (len(self.tables) + 1), "headers": [], "line": line}
            self.tables.append(self.cur_table)
        handlers = {k: v[:80] for k, v in a.items() if k.startswith("on") and v}
        el = None
        if tag in ("a", "button", "select", "textarea", "input") or ("role" in a and a["role"] in ("button", "link", "tab")) or handlers or "data-testid" in a:
            if tag == "input" and a.get("type", "text").lower() == "hidden":
                el = None
            else:
                typ = a.get("type", "text" if tag == "input" else "").lower() if tag in ("input", "button") else ""
                if tag == "button" and not typ:
                    typ = "submit" if self.form_stack else "button"
                kind = {"a": "link", "button": "button", "select": "select", "textarea": "textarea"}.get(tag)
                if tag == "input":
                    kind = "button" if typ in ("submit", "button", "reset") else ("checkbox" if typ == "checkbox" else "radio" if typ == "radio" else "input")
                kind = kind or ("button" if a.get("role") == "button" else "link" if a.get("role") == "link" else "control")
                role = a.get("role") or (INPUT_ROLE.get(typ, "textbox") if tag == "input" else IMPLICIT_ROLE.get(tag, ""))
                el = {"kind": kind, "tag": tag, "role": role, "type": typ, "id": a.get("id", ""), "name_attr": a.get("name", ""),
                      "placeholder": a.get("placeholder", ""), "aria_label": a.get("aria-label", ""), "title": a.get("title", ""),
                      "href": a.get("href", ""), "testid": a.get("data-testid", ""), "required": "required" in a,
                      "disabled": "disabled" in a, "pattern": a.get("pattern", ""), "min": a.get("min", ""), "max": a.get("max", ""),
                      "maxlength": a.get("maxlength", ""), "handlers": handlers, "form": self.form_stack[-1]["id"] if self.form_stack else "",
                      "text": "", "label": "", "line": line, "options": []}
                if tag == "select":
                    el["options"] = []
                if self.label_stack and tag in ("input", "select", "textarea"):
                    el["_wrap_label"] = self.label_stack[-1]
                self.elements.append(el)
        if tag == "select":
            self.select_depth += 1
        if tag == "label":
            lab = {"for": a.get("for", ""), "text": []}
            self.label_stack.append(lab)
        if tag in TEXT_TAGS or (tag in ("a", "button") and True):
            self.stack.append([tag, el if tag in ("a", "button") else None, [], a])
        if tag == "option" and self.elements and self.elements[-1]["tag"] == "select":
            pass
        if tag in VOID and tag != "input":
            return

    def handle_endtag(self, tag):
        if tag == "script":
            if self.cur_script is not None:
                txt = "".join(self.cur_script["text"])
                if txt.strip():
                    self.inline_scripts.append({"line": self.cur_script["line"], "text": txt})
            self.cur_script = None
            return
        if tag == "select" and self.select_depth:
            self.select_depth -= 1
        if tag == "form" and self.form_stack:
            self.form_stack.pop()
        if tag == "label" and self.label_stack:
            lab = self.label_stack.pop()
            if lab["for"]:
                self.labels_for[lab["for"]] = " ".join("".join(lab["text"]).split())
            lab["done"] = " ".join("".join(lab["text"]).split())
        if tag == "table":
            self.cur_table = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                t, el, text, a = self.stack.pop(i)
                s = " ".join("".join(text).split())
                if t == "title":
                    self.title = s
                elif t in ("h1", "h2", "h3") and s:
                    self.headings.append({"level": int(t[1]), "text": s})
                elif t == "th" and self.cur_table is not None and s:
                    self.cur_table["headers"].append(s)
                elif t == "option" and s:
                    for e in reversed(self.elements):
                        if e["tag"] == "select":
                            e["options"].append(s)
                            break
                elif el is not None:
                    el["text"] = s
                break

    def handle_data(self, data):
        if self.cur_script is not None:
            self.cur_script["text"].append(data)
            return
        for s in self.stack:
            s[2].append(data)
        if not self.select_depth:
            for lab in self.label_stack:
                lab["text"].append(data)


def locator(el, label):
    if el["testid"]:
        return "page.get_by_test_id(%s)" % pyq(el["testid"])
    name = el["aria_label"] or el["text"] or el["title"]
    if el["kind"] in ("button", "link") and name:
        return "page.get_by_role(%s, name=%s)" % (pyq(el["role"] or el["kind"]), pyq(name[:60]))
    if el["kind"] in ("input", "select", "textarea", "checkbox", "radio"):
        if label:
            return "page.get_by_label(%s)" % pyq(label[:60])
        if el["placeholder"]:
            return "page.get_by_placeholder(%s)" % pyq(el["placeholder"])
    if el["id"]:
        return "page.locator(%s)" % pyq("#" + el["id"])
    if el["name_attr"]:
        return "page.locator(%s)" % pyq("[name=%s]" % pyq(el["name_attr"]))
    if name:
        return "page.get_by_text(%s)" % pyq(name[:60])
    return "page.locator(%s)" % pyq(el["tag"])


def build_snapshot(rel, text, root):
    p = Parser()
    p.feed(text)
    p.close()
    script_text = "\n".join(s["text"] for s in p.inline_scripts)
    for src in p.scripts:
        if not re.match(r"https?://|//", src):
            f = os.path.normpath(os.path.join(root, os.path.dirname(rel), src.split("?")[0]))
            if os.path.isfile(f):
                script_text += "\n" + open(f, encoding="utf-8", errors="replace").read()
    dynamic = bool(re.search(r"\binnerHTML\b|createElement\(|appendChild\(|insertAdjacentHTML|\.html\(", script_text))
    els = []
    for i, e in enumerate(p.elements):
        label = e.pop("_wrap_label", None)
        label_text = (p.labels_for.get(e["id"]) if e["id"] else "") or (" ".join("".join(label["text"]).split()) if label else "")
        e["label"] = label_text
        e["name"] = e["aria_label"] or label_text or e["text"] or e["placeholder"] or e["title"] or e["name_attr"] or e["id"]
        e["locator"] = locator(e, label_text)
        e["visible"] = True
        e["eid"] = "e%d" % (i + 1)
        els.append(e)
    for f in p.forms:
        f["fields"] = [e["eid"] for e in els if e["form"] == f["id"] and e["kind"] in ("input", "select", "textarea", "checkbox", "radio")]
        f["submit"] = [e["eid"] for e in els if e["form"] == f["id"] and e["kind"] == "button" and e["type"] == "submit"]
    fetches = []
    for m in re.finditer(r"""fetch\(\s*([`"'])(.*?)\1""", script_text):
        fetches.append({"method": "GET", "url": re.sub(r"\$\{[^}]*\}", "{x}", m.group(2))})
    for m in re.finditer(r"""\.open\(\s*["'](GET|POST|PUT|DELETE|PATCH)["']\s*,\s*["']([^"']+)["']""", script_text):
        fetches.append({"method": m.group(1), "url": m.group(2)})
    for f in fetches:
        f["url"] = re.sub(r"([?&](?:[^=&]*(?:token|key|secret|password|auth)[^=&]*)=)[^&]*", r"\1<redacted>", f["url"], flags=re.I)
    nav = sorted({m.group(1) for m in re.finditer(r"""location(?:\.href)?\s*=\s*["']([^"'#?]+\.html?)["']""", script_text)})
    storage = sorted({m.group(2) for m in re.finditer(r"""(localStorage|sessionStorage)\.(?:get|set)Item\(\s*["']([^"']+)["']""", script_text)})
    return {"id": slug(rel), "source": rel, "url": "", "title": p.title, "viewport": None, "screenshot": "",
            "headings": p.headings, "elements": els, "forms": p.forms, "tables": p.tables, "scripts": p.scripts,
            "inline_script_count": len(p.inline_scripts), "rendered_by_script": dynamic,
            "script_navigation": nav, "network": [dict(f, status=None, trigger="static") for f in fetches],
            "browser_storage_keys": storage, "console_errors": [], "mode": "static"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True, help="an .html file or a folder containing .html files")
    ap.add_argument("--out", required=True, help="folder for <screen>.snapshot.json files")
    a = ap.parse_args()
    inp = os.path.abspath(a.input)
    files = []
    if os.path.isfile(inp):
        root = os.path.dirname(inp)
        files = [os.path.basename(inp)]
    elif os.path.isdir(inp):
        root = inp
        for dp, dn, fn in os.walk(inp):
            dn[:] = sorted(d for d in dn if d not in {"node_modules", ".git", "dist", "build", "handoff"})
            for f in sorted(fn):
                if f.lower().endswith((".html", ".htm")):
                    files.append(os.path.relpath(os.path.join(dp, f), inp).replace(os.sep, "/"))
    else:
        print("ERROR: input not found: " + inp, file=sys.stderr)
        return 2
    if not files:
        print("ERROR: no .html files found in " + inp, file=sys.stderr)
        return 2
    os.makedirs(a.out, exist_ok=True)
    n_el = 0
    for rel in files:
        snap = build_snapshot(rel, open(os.path.join(root, rel), encoding="utf-8", errors="replace").read(), root)
        n_el += len(snap["elements"])
        json.dump(snap, open(os.path.join(a.out, snap["id"] + ".snapshot.json"), "w", encoding="utf-8"), indent=1)
    print("static snapshots: %d screens, %d controls -> %s" % (len(files), n_el, a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
