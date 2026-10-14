#!/usr/bin/env python3
"""Apply reviewer enrichment (summaries, community labels, concepts, guided tours) to graph.json and check it.

Enrichment lives in its own file so it survives a rebuild of the graph:
  {
    "summaries": {"<node id>": "one or two sentences, what it does and why it matters"},
    "community_labels": {"c0": "Short human name"},
    "concepts": [{"id": "concept:approval", "name": "Approval workflow", "description": "...", "nodes": ["<node id>", ...]}],
    "tours": [{"title": "How a request becomes an approval", "steps": [{"node": "<node id>", "why": "..."}]}]
  }
Rules (errors): every node id must exist, summaries are at most 400 characters, no secret-looking values,
concepts need a description of at least 20 characters and at least one node, tours at least two steps.
Stale references (nodes that no longer exist after a rebuild) are reported and skipped, not applied.

Usage: python3 graph_enrich.py --graph graph.json --enrichment enrichment.json
Exit: 0 ok, 1 problems found (nothing is written), 2 usage/IO error.   Python 3.8+, standard library only.
"""
import argparse
import json
import re
import sys

SECRET = re.compile(r"eyJ[\w.\-]{10,}|\b(?:cb|sk|pk|scr|rk)_(?:live|test)_[\w\-]{6,}|(?i:password|passwd|pwd|pin|secret|token)\s*[:=]\s*[\"'][^\"']{3,}[\"']")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--enrichment", required=True)
    a = ap.parse_args()
    try:
        g = json.load(open(a.graph, encoding="utf-8"))
        e = json.load(open(a.enrichment, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    N = {n["id"]: n for n in g["nodes"]}
    C = {c["id"]: c for c in g["communities"]}
    errs, stale = [], []
    for nid, text in e.get("summaries", {}).items():
        if nid not in N:
            stale.append(nid)
        elif len(text) > 400:
            errs.append("summary for %s is %d characters (max 400)" % (nid, len(text)))
        elif SECRET.search(text):
            errs.append("summary for %s looks like it contains a secret value" % nid)
    for cid in e.get("community_labels", {}):
        if cid not in C:
            stale.append(cid)
    seen = set()
    for c in e.get("concepts", []):
        if not str(c.get("id", "")).startswith("concept:"):
            errs.append("concept id must start with 'concept:': %r" % c.get("id"))
        if c.get("id") in seen:
            errs.append("duplicate concept id %s" % c.get("id"))
        seen.add(c.get("id"))
        if len(c.get("description", "")) < 20:
            errs.append("concept %s needs a description of at least 20 characters" % c.get("id"))
        if SECRET.search(c.get("description", "")):
            errs.append("concept %s looks like it contains a secret value" % c.get("id"))
        good = [n for n in c.get("nodes", []) if n in N]
        stale += [n for n in c.get("nodes", []) if n not in N]
        if not good:
            errs.append("concept %s has no existing nodes" % c.get("id"))
    for t in e.get("tours", []):
        steps = [s for s in t.get("steps", []) if s.get("node") in N]
        stale += [s.get("node") for s in t.get("steps", []) if s.get("node") not in N]
        if len(steps) < 2:
            errs.append("tour %r needs at least two existing steps" % t.get("title"))
        for s in steps:
            if len(s.get("why", "")) < 10:
                errs.append("tour %r step %s needs a reason" % (t.get("title"), s["node"]))
    if errs:
        print("enrichment rejected (%d problems), graph not changed" % len(errs))
        for x in errs:
            print("  ERROR " + x)
        return 1
    for nid, text in e.get("summaries", {}).items():
        if nid in N:
            N[nid]["summary"] = text
    for cid, label in e.get("community_labels", {}).items():
        if cid in C:
            C[cid]["label"] = label
    g["concepts"] = [dict(c, nodes=[n for n in c["nodes"] if n in N]) for c in e.get("concepts", [])]
    g["tours"] = [dict(t, steps=[s for s in t["steps"] if s["node"] in N]) for t in e.get("tours", [])]
    json.dump(g, open(a.graph, "w", encoding="utf-8"), indent=1)
    print("enrichment applied: %d summaries, %d labels, %d concepts, %d tours%s" % (
        len([n for n in e.get("summaries", {}) if n in N]), len(e.get("community_labels", {})), len(g["concepts"]), len(g["tours"]),
        (" | %d stale references skipped: %s" % (len(stale), ", ".join(sorted(set(stale))[:5]))) if stale else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
