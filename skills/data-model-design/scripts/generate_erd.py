#!/usr/bin/env python3
"""Generate a Mermaid erDiagram from data-model.json (paste into any Markdown that renders Mermaid).

Usage: python3 generate_erd.py --model data-model.json --out erd.mmd
Python 3.8+, standard library only.
"""
import argparse
import json
import re
import sys


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    try:
        m = json.load(open(a.model, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    L = ["erDiagram"]
    for e in m["entities"]:
        fkcols = {c for fk in e.get("foreign_keys", []) for c in fk["columns"]}
        uq = {c for u in e.get("unique", []) if len(u) == 1 for c in u}
        L.append("  %s {" % e["name"])
        for c in e["attributes"]:
            t = re.sub(r"[(),:]", "_", c["type"]).strip("_")
            marks = ["PK"] if c.get("primary_key") else []
            if c["name"] in fkcols:
                marks.append("FK")
            if c["name"] in uq:
                marks.append("UK")
            L.append("    %s %s %s" % (t, c["name"], ",".join(marks)) if marks else "    %s %s" % (t, c["name"]))
        L.append("  }")
    for e in m["entities"]:
        cols = {c["name"]: c for c in e["attributes"]}
        for fk in e.get("foreign_keys", []):
            opt = any(cols[c]["nullable"] for c in fk["columns"] if c in cols)
            L.append('  %s %s--o{ %s : "%s"' % (fk["references_entity"], "|o" if opt else "||", e["name"], "_".join(fk["columns"])))
    text = "\n".join(L) + "\n"
    if a.out:
        open(a.out, "w", encoding="utf-8").write(text)
        print("ERD -> " + a.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
