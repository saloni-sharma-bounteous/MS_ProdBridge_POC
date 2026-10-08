#!/usr/bin/env python3
"""Ask questions of a graph.json without re-reading the code.

  search TERM                 nodes whose name or file contains TERM
  node REF                    details and every link in and out
  neighbors REF [--depth N]   what REF is connected to (default depth 1)
  path A B                    shortest chain of links between two nodes
  impact REF [--depth N]      everything that depends on REF, directly or through others (ripple effect)
  deps REF [--depth N]        everything REF depends on
  datastore REF               who reads and writes a table, storage key or file
  hubs                        most connected nodes
REF is a node id, an exact name, or a unique part of a name. Add --json for machine-readable output.

Usage: python3 graph_query.py --graph graph.json <command> [args]
Exit: 0 ok, 1 not found or ambiguous reference, 2 usage/IO error.   Python 3.8+, standard library only.
"""
import argparse
import json
import sys
from collections import deque

DEP_TYPES = {"calls", "uses", "imports", "extends", "implements", "reads", "writes", "exposes", "manages", "maps_to",
             "references", "loads", "fetches", "depends_on"}
RANK = {"EXTRACTED": 0, "INFERRED": 1, "AMBIGUOUS": 2}


def resolve(N, ref):
    if ref in N:
        return ref
    low = ref.lower()
    exact = [k for k, n in N.items() if n["name"].lower() == low and n["type"] != "module"]
    if len(exact) == 1:
        return exact[0]
    cand = exact or [k for k, n in N.items() if (low in n["name"].lower() or low in k.lower()) and n["type"] != "module"]
    if len(cand) == 1:
        return cand[0]
    if not cand:
        raise SystemExit("not found: %s" % ref)
    cand.sort(key=lambda k: (-N[k]["degree"], k))
    raise SystemExit("ambiguous %r, candidates:\n  %s" % (ref, "\n  ".join(cand[:8])))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--depth", type=int, default=None)
    ap.add_argument("cmd", choices=["search", "node", "neighbors", "path", "impact", "deps", "datastore", "hubs"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    try:
        g = json.load(open(a.graph, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    N = {n["id"]: n for n in g["nodes"]}
    out, inn, und = {}, {}, {}
    for l in g["links"]:
        if l["type"] == "contains":
            continue
        out.setdefault(l["source"], []).append(l)
        inn.setdefault(l["target"], []).append(l)
        und.setdefault(l["source"], []).append((l["target"], l))
        und.setdefault(l["target"], []).append((l["source"], l))

    def show(k):
        n = N[k]
        return "%s [%s] %s%s" % (n["name"], n["type"], n["file"], (":%d" % n["line"]) if n["line"] else "")

    def emit(obj, lines):
        print(json.dumps(obj, indent=1) if a.json else "\n".join(lines))
    try:
        if a.cmd == "hubs":
            hs = g["analysis"]["hubs"]
            emit(hs, ["%2d  %s" % (h["degree"], show(h["id"])) for h in hs])
        elif a.cmd == "search":
            t = " ".join(a.args).lower()
            r = [k for k, n in N.items() if t in n["name"].lower() or t in n["file"].lower()]
            r.sort(key=lambda k: (-N[k]["degree"], k))
            emit(r[:40], ["%s  (%s)" % (show(k), k) for k in r[:40]] or ["no match"])
        elif a.cmd == "node":
            k = resolve(N, a.args[0])
            n = N[k]
            lines = ["%s" % show(k), "id: %s" % k, "layer: %s  community: %s  degree: %d" % (n["layer"], n.get("community", ""), n["degree"])]
            if n["tags"]:
                lines.append("tags: " + ", ".join(n["tags"]))
            if n["summary"]:
                lines.append("summary: " + n["summary"])
            lines += ["  -> %s [%s] %s  at %s" % (l["type"], l["confidence"], N[l["target"]]["name"], l["evidence"]) for l in out.get(k, [])]
            lines += ["  <- %s [%s] %s  at %s" % (l["type"], l["confidence"], N[l["source"]]["name"], l["evidence"]) for l in inn.get(k, [])]
            emit({"node": n, "out": out.get(k, []), "in": inn.get(k, [])}, lines)
        elif a.cmd in ("neighbors", "impact", "deps"):
            k = resolve(N, a.args[0])
            depth = a.depth or (1 if a.cmd == "neighbors" else 3)
            seen, q, rows = {k: 0}, deque([(k, 0, "EXTRACTED")]), []
            while q:
                cur, d, worst = q.popleft()
                if d >= depth:
                    continue
                if a.cmd == "neighbors":
                    nxt = [(o, l) for o, l in und.get(cur, [])]
                elif a.cmd == "impact":
                    nxt = [(l["source"], l) for l in inn.get(cur, []) if l["type"] in DEP_TYPES]
                else:
                    nxt = [(l["target"], l) for l in out.get(cur, []) if l["type"] in DEP_TYPES]
                for o, l in sorted(nxt, key=lambda x: x[0]):
                    if o in seen:
                        continue
                    w = l["confidence"] if RANK[l["confidence"]] > RANK[worst] else worst
                    seen[o] = d + 1
                    rows.append((d + 1, o, l["type"], w))
                    q.append((o, d + 1, w))
            title = {"neighbors": "connected to", "impact": "depends on (would be affected by a change to)", "deps": "is depended on by this node"}[a.cmd]
            lines = ["%s: %s %s" % (show(k), len(rows), title)]
            lines += ["  depth %d  %s  via %s, weakest link %s" % (d, show(o), t, w) for d, o, t, w in rows]
            emit([{"depth": d, "node": o, "via": t, "weakest": w} for d, o, t, w in rows], lines)
        elif a.cmd == "path":
            s, t = resolve(N, a.args[0]), resolve(N, a.args[1])
            prev, q = {s: None}, deque([s])
            while q:
                cur = q.popleft()
                if cur == t:
                    break
                for o, l in sorted(und.get(cur, []), key=lambda x: x[0]):
                    if o not in prev:
                        prev[o] = (cur, l)
                        q.append(o)
            if t not in prev:
                print("no path between %s and %s" % (show(s), show(t)))
                return 1
            chain, cur = [], t
            while prev[cur]:
                p, l = prev[cur]
                chain.append((p, cur, l))
                cur = p
            chain.reverse()
            emit([{"from": p, "to": c, "type": l["type"], "confidence": l["confidence"]} for p, c, l in chain],
                 ["%s  --%s [%s]-->  %s" % (N[p]["name"], l["type"], l["confidence"], N[c]["name"]) for p, c, l in chain])
        elif a.cmd == "datastore":
            k = resolve(N, a.args[0])
            rows = list(inn.get(k, []))
            extra = []
            for l in inn.get(k, []):
                if l["type"] == "maps_to":
                    for m in inn.get(l["source"], []):
                        if m["type"] == "manages":
                            for u in inn.get(m["source"], []):
                                if u["type"] in ("uses", "calls") and u["source"] != m["source"]:
                                    extra.append((u, "through repository %s" % N[m["source"]]["name"]))
            lines = ["%s: %d direct links in" % (show(k), len(rows))]
            lines += ["  %-9s %s  at %s" % (l["type"], show(l["source"]), l["evidence"]) for l in rows]
            if extra:
                lines.append("  and %d users of the repository that manages the mapped entity:" % len(extra))
                lines += ["  %-9s %s  (%s) at %s" % (u["type"], show(u["source"]), via, u["evidence"]) for u, via in extra]
            emit({"direct": rows, "through_repository": [u for u, _ in extra]}, lines)
    except SystemExit as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
