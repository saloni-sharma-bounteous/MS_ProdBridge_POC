#!/usr/bin/env python3
"""Check a graph.json for structural integrity and, optionally, that its evidence points at real code.

Checks: schema; unique node ids; every link ends exist; evidence looks like path:line; with --root, evidence
files exist and line numbers are inside the file; every node with a file/line points inside that file;
concept and tour references exist. Warnings: hubs without a summary, no tour, many AMBIGUOUS links.

Usage: python3 graph_check.py --graph graph.json [--root <code-dir>]
Exit: 0 clean, 1 errors, 2 usage/IO error.   Python 3.8+, standard library only.
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from validate_json import validate  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--root")
    a = ap.parse_args()
    try:
        g = json.load(open(a.graph, encoding="utf-8"))
        schema = json.load(open(os.path.join(HERE, "..", "assets", "graph.schema.json"), encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    errs = ["schema: " + x for x in validate(g, schema)][:20]
    warns = []
    if not errs:
        ids = [n["id"] for n in g["nodes"]]
        if len(ids) != len(set(ids)):
            errs.append("duplicate node ids")
        S = set(ids)
        cache = {}

        def nlines(rel):
            if rel not in cache:
                p = os.path.join(a.root, rel)
                cache[rel] = len(open(p, encoding="utf-8", errors="replace").read().splitlines()) if os.path.isfile(p) else None
            return cache[rel]
        for l in g["links"]:
            if l["source"] not in S or l["target"] not in S:
                errs.append("link %s -> %s has a missing end" % (l["source"], l["target"]))
            ev = l["evidence"]
            if ev and not re.match(r"^[^\s:]+(?::\d+)?$", ev):
                errs.append("bad evidence %r on %s -> %s" % (ev, l["source"], l["target"]))
            elif ev and a.root:
                m = re.match(r"^([^:]+)(?::(\d+))?$", ev)
                if os.path.isdir(os.path.join(a.root, m.group(1))):
                    continue
                n = nlines(m.group(1))
                if n is None:
                    errs.append("evidence file missing: " + m.group(1))
                elif m.group(2) and int(m.group(2)) > n + 1:
                    errs.append("evidence line %s beyond end of %s (%d lines)" % (m.group(2), m.group(1), n))
        if a.root:
            for n in g["nodes"]:
                if n["file"] and n["type"] != "module":
                    k = nlines(n["file"])
                    if k is None:
                        errs.append("node %s points at a missing file" % n["id"])
                    elif n["line"] > k + 1:
                        errs.append("node %s line %d beyond end of file" % (n["id"], n["line"]))
        for c in g["concepts"]:
            for x in c["nodes"]:
                if x not in S:
                    errs.append("concept %s references unknown node %s" % (c["id"], x))
        for t in g["tours"]:
            for s in t["steps"]:
                if s["node"] not in S:
                    errs.append("tour %r references unknown node %s" % (t["title"], s["node"]))
        N = {n["id"]: n for n in g["nodes"]}
        bare = [h["name"] for h in g["analysis"]["hubs"][:5] if not N[h["id"]]["summary"]]
        if bare:
            warns.append("top hubs have no summary yet: " + ", ".join(bare))
        if not g["tours"]:
            warns.append("no guided tour yet")
        amb = sum(1 for l in g["links"] if l["confidence"] == "AMBIGUOUS")
        if g["links"] and amb / float(len(g["links"])) > 0.1:
            warns.append("%d AMBIGUOUS links (over 10%%): resolve or mark in the report" % amb)
    print("graph check: %d errors, %d warnings" % (len(errs), len(warns)))
    for e in errs:
        print("  ERROR " + e)
    for w in warns:
        print("  warn  " + w)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
