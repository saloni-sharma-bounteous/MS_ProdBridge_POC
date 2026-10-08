#!/usr/bin/env python3
"""Export graph.json to a plain-language report, a Mermaid overview, GraphML, and a self-contained HTML viewer.

Outputs (written next to graph.json unless --out-dir is given):
  GRAPH_REPORT.md   what the codebase is made of, where the risk concentrates, suggested questions
  graph.mmd         Mermaid flowchart of the communities (paste into any Markdown that renders Mermaid)
  graph.graphml     import into Gephi, yEd or Neo4j tooling
  graph.html        offline interactive viewer (no external scripts); node text is inserted as text, never as HTML

Usage: python3 graph_export.py --graph <dir>/graph.json [--out-dir <dir>] [--max-nodes 300]
Python 3.8+, standard library only.
"""
import argparse
import json
import math
import os
import sys
from xml.sax.saxutils import escape

PALETTE = {"ui": "#378ADD", "api": "#D85A30", "service": "#7F77DD", "data": "#1D9E75", "config": "#BA7517",
           "integration": "#D4537E", "core": "#888780", "test": "#639922", "external": "#B4B2A9", "": "#B4B2A9"}


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def short(n, k=60):
    return n if len(n) <= k else n[:k - 1] + "..."


def report(g):
    N = {n["id"]: n for n in g["nodes"]}
    a, st = g["analysis"], g["stats"]
    L = ["# Code graph report: %s" % g["root_name"], "",
         "%d nodes and %d links from %d files. Link confidence: %s." % (
             st["nodes"], st["links"], st["files"], ", ".join("%s %d" % (k, v) for k, v in sorted(st["by_confidence"].items()))),
         "EXTRACTED links are stated in the source. INFERRED links are resolved by name or type to one target. AMBIGUOUS links have several candidates; check them before relying on them.", "",
         "## Shape", "", "| Node type | Count |", "|---|---|"]
    L += ["| %s | %d |" % (k, v) for k, v in sorted(st["by_node_type"].items())]
    L += ["", "| Layer | Nodes |", "|---|---|"] + ["| %s | %d |" % (k, v) for k, v in a["layers"].items()]
    L += ["", "## Communities (groups that change together)", "", "| ID | Name | Size | Top members |", "|---|---|---|---|"]
    for c in g["communities"][:12]:
        L.append("| %s | %s | %d | %s |" % (c["id"], c.get("label") or c["name"], c["size"], ", ".join(N[m]["name"] for m in c["top_members"][:3])))
    L += ["", "## Hubs (what everything flows through)", ""]
    L += ["- `%s` (%s), degree %d, %s:%s" % (h["name"], N[h["id"]]["type"], h["degree"], N[h["id"]]["file"], N[h["id"]]["line"]) for h in a["hubs"]] or ["- none"]
    L += ["", "## Entry points", ""] + ["- `%s`" % e[5:] for e in a["entry_points"]] or ["- none found"]
    eps = [n for n in g["nodes"] if n["type"] == "endpoint"]
    if eps:
        L += ["", "## Endpoints and routes", ""] + ["- `%s` (%s:%s)" % (n["name"], n["file"], n["line"]) for n in eps]
    stores = [n for n in g["nodes"] if n["type"] == "datastore"]
    if stores:
        L += ["", "## Data stores and who touches them", "", "| Store | Kind | Reads | Writes | Tags |", "|---|---|---|---|---|"]
        for s in stores:
            r = sum(1 for l in g["links"] if l["target"] == s["id"] and l["type"] == "reads")
            w = sum(1 for l in g["links"] if l["target"] == s["id"] and l["type"] in ("writes", "maps_to"))
            L.append("| %s | %s | %d | %d | %s |" % (s["name"], s["kind"], r, w, ", ".join(s["tags"])))
    ext = [n for n in g["nodes"] if n["type"] == "external" and n["kind"] in ("http", "cdn-script")]
    if ext:
        L += ["", "## External hosts", ""] + ["- `%s` (%s)" % (n["name"], n["kind"]) for n in ext]
    L += ["", "## Things worth a closer look", ""]
    if a["import_cycles"]:
        L += ["Import cycles (files that depend on each other):"] + ["- " + " <-> ".join(x[5:] for x in c) for c in a["import_cycles"]]
    else:
        L += ["No import cycles found."]
    if a["similar_lists"]:
        L += ["", "Similar lists in different files (possible duplicated business rules):"]
        for s in a["similar_lists"]:
            diff = ""
            if s["kind"] == "overlapping":
                diff = " (only in first: %s; only in second: %s)" % (", ".join(s["only_in_first"]) or "-", ", ".join(s["only_in_second"]) or "-")
            L.append("- %s: `%s` and `%s`%s" % (s["kind"], s["first"], s["second"], diff))
    if a["duplicate_names"]:
        L += ["", "Names defined in more than one file:"] + ["- `%s` (%s): %s" % (d["name"], d["type"], ", ".join(i.split(":", 1)[1] for i in d["ids"])) for d in a["duplicate_names"]]
    if a["orphan_files"]:
        L += ["", "Files nothing connects to (dead code or unused assets?):"] + ["- `%s`" % o[5:] for o in a["orphan_files"]]
    if a["surprising_links"]:
        L += ["", "Surprising connections (links between otherwise separate communities):"]
        L += ["- `%s` -> `%s` (%s, %s) at %s" % (N[s["source"]]["name"], N[s["target"]]["name"], s["type"], s["confidence"], s["evidence"]) for s in a["surprising_links"]]
    amb = [l for l in g["links"] if l["confidence"] == "AMBIGUOUS"]
    if amb:
        L += ["", "Ambiguous links to verify (%d):" % len(amb)] + ["- `%s` -> `%s` (%s) at %s" % (N[l["source"]]["name"], N[l["target"]]["name"], l["type"], l["evidence"]) for l in amb[:10]]
    if g.get("concepts"):
        L += ["", "## Concepts (added by review)", ""]
        for c in g["concepts"]:
            L += ["### %s" % c["name"], c["description"], "Nodes: " + ", ".join("`%s`" % N[i]["name"] for i in c["nodes"] if i in N), ""]
    if g.get("tours"):
        L += ["## Guided tours", ""]
        for t in g["tours"]:
            L += ["### %s" % t["title"]] + ["%d. `%s`: %s" % (i + 1, N[s["node"]]["name"], s["why"]) for i, s in enumerate(t["steps"]) if s["node"] in N] + [""]
    L += ["", "## Suggested questions", ""]
    if a["hubs"]:
        L.append("- What breaks if `%s` changes? (`graph_query.py impact`)" % a["hubs"][0]["name"])
    for s in stores[:2]:
        L.append("- Which code reads and writes `%s`, and who is allowed to?" % s["name"])
    if a["similar_lists"] or a["duplicate_names"]:
        L.append("- Are the duplicated lists or functions meant to be the same rule? Which one is right?")
    if amb:
        L.append("- Which of the ambiguous links is the real call?")
    L.append("- Which communities should become separate services or modules?")
    return "\n".join(L) + "\n"


def mermaid(g):
    comm = {c["id"]: c for c in g["communities"][:14]}
    cnt = {}
    N = {n["id"]: n for n in g["nodes"]}
    for l in g["links"]:
        if l["type"] == "contains":
            continue
        a, b = N[l["source"]].get("community"), N[l["target"]].get("community")
        if a in comm and b in comm and a != b:
            cnt[(a, b)] = cnt.get((a, b), 0) + 1
    L = ["flowchart LR"]
    for cid, c in comm.items():
        label = (c.get("label") or c["name"]).replace('"', "'")
        L.append('  %s["%s (%d)"]' % (cid, short(label, 40), c["size"]))
    for (a, b), n in sorted(cnt.items(), key=lambda x: -x[1])[:30]:
        L.append("  %s -->|%d| %s" % (a, n, b))
    return "\n".join(L) + "\n"


def graphml(g):
    keys = ["type", "name", "file", "line", "layer", "community", "degree", "summary"]
    L = ['<?xml version="1.0" encoding="UTF-8"?>', '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">']
    for k in keys:
        L.append('  <key id="n_%s" for="node" attr.name="%s" attr.type="string"/>' % (k, k))
    for k in ("type", "confidence", "evidence"):
        L.append('  <key id="e_%s" for="edge" attr.name="%s" attr.type="string"/>' % (k, k))
    L.append('  <graph id="G" edgedefault="directed">')
    for n in g["nodes"]:
        L.append('    <node id="%s">' % escape(n["id"], {'"': "&quot;"}))
        for k in keys:
            L.append('      <data key="n_%s">%s</data>' % (k, escape(str(n.get(k, "")))))
        L.append("    </node>")
    for i, l in enumerate(g["links"]):
        L.append('    <edge id="e%d" source="%s" target="%s">' % (i, escape(l["source"], {'"': "&quot;"}), escape(l["target"], {'"': "&quot;"})))
        for k in ("type", "confidence", "evidence"):
            L.append('      <data key="e_%s">%s</data>' % (k, escape(str(l[k]))))
        L.append("    </edge>")
    L += ["  </graph>", "</graphml>"]
    return "\n".join(L) + "\n"


def layout(nodes, communities, max_nodes):
    core = [n for n in nodes if n["type"] in ("file", "class", "function", "endpoint", "datastore")]
    core.sort(key=lambda n: (-n["degree"], n["id"]))
    keep = core[:max_nodes]
    by = {}
    for n in keep:
        by.setdefault(n.get("community", "c0"), []).append(n)
    W, H = 1000, 720
    cx, cy = W / 2.0, H / 2.0
    order = [c["id"] for c in communities if c["id"] in by]
    R = min(W, H) * 0.34 if len(order) > 1 else 0
    pos = {}
    for i, cid in enumerate(order):
        ang = 2 * math.pi * i / max(1, len(order))
        ox, oy = cx + R * math.cos(ang), cy + R * math.sin(ang)
        members = sorted(by[cid], key=lambda n: (-n["degree"], n["id"]))
        for j, n in enumerate(members):
            if j == 0:
                pos[n["id"]] = (ox, oy)
                continue
            ring = 1 + (j - 1) // 8
            k = (j - 1) % 8
            a2 = 2 * math.pi * k / min(8, len(members) - 1 - 8 * (ring - 1)) + ring
            rr = 34 * ring
            pos[n["id"]] = (ox + rr * math.cos(a2), oy + rr * math.sin(a2))
    return keep, pos, (W, H)


def html(g, max_nodes):
    keep, pos, (W, H) = layout(g["nodes"], g["communities"], max_nodes)
    ids = {n["id"] for n in keep}
    nodes = [{"id": n["id"], "name": n["name"], "type": n["type"], "kind": n.get("kind", ""), "layer": n["layer"] or "core",
              "file": n["file"], "line": n["line"], "community": n.get("community", ""), "degree": n["degree"],
              "summary": n.get("summary", ""), "tags": n["tags"], "x": round(pos[n["id"]][0], 1), "y": round(pos[n["id"]][1], 1)} for n in keep]
    links = [{"s": l["source"], "t": l["target"], "type": l["type"], "conf": l["confidence"], "ev": l["evidence"]}
             for l in g["links"] if l["type"] != "contains" and l["source"] in ids and l["target"] in ids]
    data = json.dumps({"root": g["root_name"], "nodes": nodes, "links": links, "palette": PALETTE,
                       "total_nodes": len(g["nodes"]), "shown": len(nodes)}).replace("<", "\\u003c")
    return HTML_TEMPLATE.replace("__DATA__", data).replace("__W__", str(W)).replace("__H__", str(H))


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Code graph</title>
<style>
body{margin:0;font:14px/1.5 system-ui,sans-serif;color:#222;background:#fff}
header{padding:10px 16px;border-bottom:1px solid #ddd;display:flex;gap:16px;align-items:center;flex-wrap:wrap}
input[type=search]{padding:6px 8px;border:1px solid #bbb;border-radius:6px;min-width:220px}
main{display:flex;gap:0}
svg{flex:1;min-width:0;background:#fafafa}
aside{width:300px;border-left:1px solid #ddd;padding:12px;overflow:auto;max-height:760px}
.leg span{display:inline-block;margin-right:10px}.leg i{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:4px}
.dim{opacity:.12}code{background:#eee;padding:0 3px;border-radius:3px}
</style></head><body>
<header><strong id="title"></strong><input id="q" type="search" placeholder="Search nodes"><span class="leg" id="leg"></span><span id="count"></span></header>
<main><svg id="g" viewBox="0 0 __W__ __H__" role="img" aria-label="Code graph"></svg><aside id="d"><p>Click a node.</p></aside></main>
<script>
var D=__DATA__;
var NS="http://www.w3.org/2000/svg",svg=document.getElementById("g"),byId={},adj={};
D.nodes.forEach(function(n){byId[n.id]=n;adj[n.id]=[]});
D.links.forEach(function(l){adj[l.s].push(l);adj[l.t].push(l)});
document.getElementById("title").textContent="Code graph: "+D.root;
document.getElementById("count").textContent="showing "+D.shown+" of "+D.total_nodes+" nodes";
var legEl=document.getElementById("leg");
Object.keys(D.palette).filter(function(k){return k&&D.nodes.some(function(n){return n.layer===k})}).forEach(function(k){
 var s=document.createElement("span"),i=document.createElement("i");i.style.background=D.palette[k];s.appendChild(i);s.appendChild(document.createTextNode(k));legEl.appendChild(s)});
function mk(t,a){var e=document.createElementNS(NS,t);for(var k in a)e.setAttribute(k,a[k]);return e}
var lg=mk("g",{}),ng=mk("g",{}),linkEls=[],nodeEls={};
D.links.forEach(function(l){var a=byId[l.s],b=byId[l.t];
 var e=mk("line",{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:"#888","stroke-width":l.conf==="EXTRACTED"?0.8:0.8,"stroke-opacity":0.45});
 if(l.conf!=="EXTRACTED")e.setAttribute("stroke-dasharray","3 3");lg.appendChild(e);linkEls.push(e)});
D.nodes.forEach(function(n){
 var r=4+Math.min(10,Math.sqrt(n.degree)*1.8);
 var e=mk("circle",{cx:n.x,cy:n.y,r:r,fill:D.palette[n.layer]||"#888780",stroke:"#fff","stroke-width":1,style:"cursor:pointer"});
 var t=mk("title",{});t.textContent=n.name+" ("+n.type+")";e.appendChild(t);
 e.addEventListener("click",function(){select(n.id)});ng.appendChild(e);nodeEls[n.id]=e;
 if(n.degree>=6){var tx=mk("text",{x:n.x+r+2,y:n.y+4,"font-size":11,fill:"#333"});tx.textContent=n.name;ng.appendChild(tx)}});
svg.appendChild(lg);svg.appendChild(ng);
function row(parent,label,value){var p=document.createElement("p");var b=document.createElement("strong");b.textContent=label+" ";p.appendChild(b);p.appendChild(document.createTextNode(value));parent.appendChild(p)}
function select(id){var n=byId[id],d=document.getElementById("d");d.textContent="";
 var h=document.createElement("h3");h.textContent=n.name;d.appendChild(h);
 row(d,"Type",n.type+(n.kind?" ("+n.kind+")":""));row(d,"Layer",n.layer);row(d,"Where",n.file+(n.line?":"+n.line:""));row(d,"Community",n.community);row(d,"Degree",String(n.degree));
 if(n.tags.length)row(d,"Tags",n.tags.join(", "));if(n.summary)row(d,"Summary",n.summary);
 var ul=document.createElement("ul");adj[id].forEach(function(l){var o=l.s===id?byId[l.t]:byId[l.s];var li=document.createElement("li");
  li.textContent=(l.s===id?"-> ":"<- ")+l.type+" ["+l.conf+"] "+o.name;ul.appendChild(li)});d.appendChild(ul);
 var keep={};keep[id]=1;adj[id].forEach(function(l){keep[l.s]=1;keep[l.t]=1});
 D.nodes.forEach(function(m){nodeEls[m.id].setAttribute("class",keep[m.id]?"":"dim")});
 D.links.forEach(function(l,i){linkEls[i].setAttribute("class",(l.s===id||l.t===id)?"":"dim")})}
document.getElementById("q").addEventListener("input",function(ev){var q=ev.target.value.toLowerCase();
 D.nodes.forEach(function(n){var hit=!q||n.name.toLowerCase().indexOf(q)>=0||n.file.toLowerCase().indexOf(q)>=0;nodeEls[n.id].setAttribute("class",hit?"":"dim")});
 linkEls.forEach(function(e){e.setAttribute("class",q?"dim":"")})});
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--graph", required=True)
    ap.add_argument("--out-dir")
    ap.add_argument("--max-nodes", type=int, default=300)
    a = ap.parse_args()
    try:
        g = load(a.graph)
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    out = a.out_dir or os.path.dirname(os.path.abspath(a.graph))
    os.makedirs(out, exist_ok=True)
    for name, text in (("GRAPH_REPORT.md", report(g)), ("graph.mmd", mermaid(g)), ("graph.graphml", graphml(g)),
                       ("graph.html", html(g, a.max_nodes))):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            f.write(text)
    print("exported GRAPH_REPORT.md, graph.mmd, graph.graphml, graph.html -> %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
