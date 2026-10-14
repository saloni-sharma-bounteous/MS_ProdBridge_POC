#!/usr/bin/env python3
"""Validate mindmap.json and write a self-contained mindmap.html next to it.

Usage: python build_mindmap.py mindmap/mindmap.json [output.html]
"""
import json
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "mindmap_template.html"


def validate(d):
    errs = []
    if not d.get("title"):
        errs.append("Missing 'title'.")
    branches = d.get("branches")
    if not isinstance(branches, list) or not branches:
        return errs + ["'branches' must be a non-empty list."]
    if len(branches) > 8:
        errs.append(f"{len(branches)} branches is too many to read; merge them down to 8 or fewer.")
    ids = set()
    for i, b in enumerate(branches):
        if not b.get("name"):
            errs.append(f"Branch {i} has no name.")
        kids = b.get("children") or []
        if len(kids) > 8:
            errs.append(f"Branch '{b.get('name')}' has {len(kids)} components; split it (max 8).")
        for c in kids:
            if not c.get("name"):
                errs.append(f"A component in '{b.get('name')}' has no name.")
            cid = c.get("id")
            if cid:
                if cid in ids:
                    errs.append(f"Duplicate id '{cid}'.")
                ids.add(cid)
    for l in d.get("links") or []:
        for end in ("from", "to"):
            if l.get(end) not in ids:
                errs.append(f"Link {l.get('from')} -> {l.get('to')}: unknown id '{l.get(end)}' in '{end}'.")
    return errs


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    src = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else src.with_name("mindmap.html")
    data = json.loads(src.read_text(encoding="utf-8-sig"))
    errs = validate(data)
    if errs:
        print("Fix these problems in the JSON, then run again:")
        for e in errs:
            print(" -", e)
        sys.exit(1)
    root = src.resolve().parent.parent  # mindmap/ sits directly under the project root
    base = data.get("previewBase")
    for b in data["branches"]:
        for c in b.get("children") or []:
            target = c.get("preview") or (c.get("path") if str(c.get("path", "")).lower().endswith((".html", ".htm")) else "")
            if target and not target.lower().startswith(("http://", "https://")) and base in (None, "../"):
                if not (root / target).is_file():
                    print(f"Warning: preview file not found for '{c.get('name')}': {root / target}")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/null", payload)
    out.write_text(html, encoding="utf-8")
    n = sum(len(b.get("children") or []) for b in data["branches"])
    print(f"Wrote {out} ({len(data['branches'])} branches, {n} components, {len(data.get('links') or [])} links)")


if __name__ == "__main__":
    main()
