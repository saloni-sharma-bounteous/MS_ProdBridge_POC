#!/usr/bin/env python3
"""Build a code knowledge graph (nodes and links) from a codebase, offline and deterministically.

Reads source only. Never runs code, never touches the network, never stores literal secret values
(only names, paths, table names, hosts). Languages: Java, TypeScript/JavaScript (incl. React), HTML,
SQL, Python, plus config/build files (properties, yml, pom.xml, package.json).

Every link carries a confidence tag:
  EXTRACTED  stated directly in the source (import, extends, annotation, route, table, containment)
  INFERRED   resolved by name or type heuristics to exactly one target (most calls)
  AMBIGUOUS  several possible targets (one link per candidate, at most 3)

Usage:
    python3 graph_build.py --root <code-dir> --out <dir>/graph.json
Python 3.8+, standard library only.
"""
import argparse
import datetime
import json
import os
import re
import sys

IGNORE_DIRS = {"node_modules", ".git", "dist", "build", "target", ".next", "coverage", "handoff", "__pycache__",
               ".venv", "venv", ".idea", ".vscode", ".gradle", ".mvn", "graph-out", "out", ".turbo", ".cache"}
LANG = {".java": "java", ".ts": "js", ".tsx": "js", ".js": "js", ".jsx": "js", ".mjs": "js", ".cjs": "js",
        ".html": "html", ".htm": "html", ".sql": "sql", ".py": "py", ".yml": "config", ".yaml": "config",
        ".properties": "config", ".toml": "config", ".gradle": "config", ".xml": "config"}
MAX_BYTES = 1000000
CONF_RANK = {"EXTRACTED": 0, "INFERRED": 1, "AMBIGUOUS": 2}
JAVA_KW = {"if", "for", "while", "switch", "catch", "synchronized", "return", "new", "else", "try", "throw", "super",
           "this", "assert", "do", "case", "instanceof", "yield"}
COMMON_NAMES = {"main", "render", "init", "get", "set", "handle", "toString", "equals", "hashCode", "run", "setup",
                "constructor", "build", "create", "update", "delete", "test", "show", "load", "save", "apply"}
SECRET_VALUE = re.compile(r"eyJ[\w.\-]{10,}|\b(?:cb|sk|pk|scr|rk)_(?:live|test)_[\w\-]{6,}")
STEREO = {"RestController": "api", "Controller": "api", "Service": "service", "Repository": "data", "Entity": "data",
          "Configuration": "config", "SpringBootApplication": "config", "ConfigurationProperties": "config",
          "Component": "core", "ControllerAdvice": "api", "RestControllerAdvice": "api"}


def lineno(text, idx):
    return text.count("\n", 0, idx) + 1


def mask(text, keep_strings=False, java=False):
    """Blank comments (and string contents unless keep_strings) while preserving offsets and newlines."""
    out = list(text)
    n, i = len(text), 0

    def blank(a, b):
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "
    while i < n:
        c = text[i]
        nx = text[i + 1] if i + 1 < n else ""
        if c == "/" and nx == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif c == "/" and nx == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            blank(i, j)
            i = j
        elif java and text.startswith('"""', i):
            j = text.find('"""', i + 3)
            j = n if j < 0 else j + 3
            if not keep_strings:
                blank(i + 3, max(i + 3, j - 3))
            i = j
        elif c in "\"'`":
            j = i + 1
            while j < n and text[j] != c:
                if text[j] == "\\":
                    j += 1
                elif text[j] == "\n" and c != "`":
                    break
                j += 1
            if not keep_strings:
                blank(i + 1, min(j, n))
            i = j + 1
        else:
            i += 1
    return "".join(out)


def match_brace(code, i):
    depth, n = 0, len(code)
    while i < n:
        if code[i] == "{":
            depth += 1
        elif code[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return n - 1


def skeleton(code, start, end):
    """Keep only member-level text (depth 1) plus the braces of member bodies; hide everything deeper."""
    out, depth = [], 0
    for i in range(start, end + 1):
        c = code[i]
        if c == "\n":
            out.append(c)
            continue
        if c == "{":
            depth += 1
            out.append("{" if depth == 2 else " ")
        elif c == "}":
            out.append("}" if depth == 2 else " ")
            depth -= 1
        else:
            out.append(c if depth == 1 else " ")
    return "".join(out)


def simple_type(t):
    t = re.sub(r"<[^<>]*>", "", t)
    t = re.sub(r"<[^<>]*>", "", t).replace("[]", "").replace("...", "").strip()
    return t.split(".")[-1] if t else ""


def split_params(p):
    parts, depth, cur = [], 0, []
    for ch in p:
        if ch in "<(":
            depth += 1
        elif ch in ">)":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def parse_params(p):
    out = []
    for part in split_params(p):
        part = re.sub(r"@\w+(?:\((?:[^()]|\([^()]*\))*\))?", " ", part)
        part = re.sub(r"\bfinal\b", " ", part).strip()
        toks = part.split()
        if len(toks) >= 2:
            out.append((simple_type(" ".join(toks[:-1])), toks[-1]))
    return out


class Graph:
    def __init__(self):
        self.nodes = {}
        self.links = {}

    def node(self, nid, ntype, name, file="", line=0, lang="", kind="", tags=None, layer=None, **extra):
        n = self.nodes.get(nid)
        if n is None:
            n = {"id": nid, "type": ntype, "name": name, "file": file, "line": line, "lang": lang, "kind": kind,
                 "layer": layer or "", "tags": sorted(set(tags or [])), "summary": ""}
            n.update(extra)
            self.nodes[nid] = n
        else:
            for t in (tags or []):
                if t not in n["tags"]:
                    n["tags"] = sorted(n["tags"] + [t])
            if layer and not n["layer"]:
                n["layer"] = layer
        return n

    def link(self, src, dst, ltype, conf, evidence=""):
        if src == dst or src not in self.nodes or dst not in self.nodes:
            return
        key = (src, dst, ltype)
        cur = self.links.get(key)
        if cur is None or CONF_RANK[conf] < CONF_RANK[cur["confidence"]]:
            self.links[key] = {"source": src, "target": dst, "type": ltype, "confidence": conf, "evidence": evidence}


def layer_for(rel, ntype, ann=(), ext=""):
    p = rel.lower()
    if re.search(r"(^|/)(test|tests|__tests__|spec)(/|$)|\.test\.|\.spec\.|test\.java$", p):
        return "test"
    a = set(ann)
    if a & {"RestController", "Controller", "ControllerAdvice", "RestControllerAdvice"} or ntype == "endpoint" or \
            re.search(r"/controller|/api/|/routes?/", p):
        return "api"
    if a & {"Repository", "Entity"} or ntype == "datastore" or re.search(r"/repositor|/dao/|/entit|/model|/store|/migrations?/|\.sql$", p):
        return "data"
    if "Service" in a or re.search(r"/service|/usecase|/domain", p):
        return "service"
    if a & {"Configuration", "SpringBootApplication", "ConfigurationProperties"} or \
            re.search(r"/config|application[-\w]*\.(yml|yaml|properties)$|pom\.xml$|package\.json$|\.gradle$", p):
        return "config"
    if re.search(r"/integration|/client|/adapter|/gateway|/lib/api", p):
        return "integration"
    if ext in (".html", ".htm", ".tsx", ".jsx") or re.search(r"/pages?/|/components?/|/views?/|/ui/|\.css$", p):
        return "ui"
    return "core"


# ----------------------------------------------------------------------------------------------
class Extractor:
    def __init__(self, root):
        self.root = root
        self.g = Graph()
        self.files = {}            # rel -> text
        self.pending_calls = []    # dicts for pass 2
        self.java_fqn = {}         # fqn -> class id
        self.classes_by_name = {}  # simple name -> [class ids]
        self.class_info = {}       # class id -> dict(file, name, methods{name:id}, fields{var:type}, extends[], implements[])
        self.funcs_by_name = {}    # name -> [fn ids]
        self.file_funcs = {}       # rel -> {name: fn id}
        self.js_bindings = {}      # rel -> {local: (target_rel_or_None, imported_name, ext_pkg)}
        self.const_str = {}
        self.pages_scripts = {}    # html rel -> [script rels]
        self.skipped = []

    # ---- files ----
    def load(self):
        for dp, dn, fn in os.walk(self.root):
            dn[:] = sorted(d for d in dn if d not in IGNORE_DIRS)
            for f in sorted(fn):
                p = os.path.join(dp, f)
                rel = os.path.relpath(p, self.root).replace(os.sep, "/")
                ext = os.path.splitext(f)[1].lower()
                if f == "package.json" or f == "pom.xml" or ext in LANG:
                    try:
                        raw = open(p, "rb").read()
                    except OSError:
                        continue
                    if len(raw) > MAX_BYTES or b"\x00" in raw:
                        self.skipped.append(rel)
                        continue
                    self.files[rel] = raw.decode("utf-8", "replace")
        for rel, t in self.files.items():
            if rel.endswith((".js", ".ts", ".tsx", ".jsx", ".html", ".htm")):
                for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*[\"']([^\"']*)[\"']", t):
                    self.const_str.setdefault(m.group(1), m.group(2))

    def add_file(self, rel):
        ext = os.path.splitext(rel)[1].lower()
        lang = LANG.get(ext, "config")
        text = self.files[rel]
        self.g.node("file:" + rel, "file", os.path.basename(rel), rel, 1, lang,
                    layer=layer_for(rel, "file", ext=ext), lines=text.count("\n") + 1)
        d = os.path.dirname(rel) or "."
        mid = "module:" + d
        self.g.node(mid, "module", d, d, 0, "", layer="")
        self.g.link(mid, "file:" + rel, "contains", "EXTRACTED", rel)
        parent = os.path.dirname(d) if d != "." else None
        if d != "." and parent is not None:
            pid = "module:" + (parent or ".")
            self.g.node(pid, "module", parent or ".", parent or ".", 0, "")
            self.g.link(pid, mid, "contains", "EXTRACTED", d)

    def enclosing(self, rel, offset, ranges):
        best = None
        for s, e, fid in ranges:
            if s <= offset <= e and (best is None or e - s < best[1] - best[0]):
                best = (s, e, fid)
        return best[2] if best else "file:" + rel

    # ---- Java ----
    def parse_java(self, rel):
        text = self.files[rel]
        code = mask(text, java=True)
        g = self.g
        fid = "file:" + rel
        pkg = re.search(r"\bpackage\s+([\w.]+)\s*;", code)
        pkg = pkg.group(1) if pkg else ""
        imports = [m.group(1) for m in re.finditer(r"\bimport\s+(?:static\s+)?([\w.]+?)(?:\.\*)?\s*;", code)]
        classes = []
        for m in re.finditer(r"(?:^|[\s;}{)])(?:(?:public|protected|private|abstract|final|static|sealed|non-sealed|strictfp)\s+)*"
                             r"(class|interface|enum|record|@interface)\s+(\w+)", code):
            br = code.find("{", m.end())
            if br < 0:
                continue
            end = match_brace(code, br)
            classes.append((m.start(2) - len(m.group(1)) - 1, m.group(1), m.group(2), m.end(), br, end))
        for start, kw, name, hend, br, end in classes:
            owner = None
            for s2, k2, n2, h2, b2, e2 in classes:
                if b2 < br and e2 >= end and (owner is None or b2 > owner[4]):
                    owner = (s2, k2, n2, h2, b2, e2)
            cid = "class:%s#%s" % (rel, (owner[2] + "." if owner else "") + name)
            seg_start = max(code.rfind(";", 0, start), code.rfind("}", 0, start), code.rfind("{", 0, start)) + 1
            ann = re.findall(r"@(\w+)", text[seg_start:start + 1 + len(kw)])
            hdr = re.sub(r"<[^<>]*>", "", re.sub(r"<[^<>]*>", "", code[hend:br]))
            ext_m = re.search(r"\bextends\s+([\w.,\s]+?)(?=\bimplements\b|\bpermits\b|$)", hdr)
            impl_m = re.search(r"\bimplements\s+([\w.,\s]+?)(?=\bpermits\b|$)", hdr)
            extends = [x.strip().split(".")[-1] for x in (ext_m.group(1).split(",") if ext_m else []) if x.strip()]
            implements = [x.strip().split(".")[-1] for x in (impl_m.group(1).split(",") if impl_m else []) if x.strip()]
            raw_hdr = code[hend:br]
            repo = re.search(r"\bextends\s+(?:[\w.]*\.)?(?:Jpa|Crud|PagingAndSorting|ListCrud|ListPagingAndSorting)?Repository\s*<\s*(\w+)", raw_hdr)
            kind = {"class": "class", "interface": "interface", "enum": "enum", "record": "record", "@interface": "annotation"}[kw]
            stereo = [a for a in ann if a in STEREO]
            if repo:
                stereo.append("Repository")
            layer = layer_for(rel, "class", stereo)
            for a in ann:
                if a in STEREO and STEREO[a] != "core":
                    layer = STEREO[a] if layer == "core" else layer
            n = g.node(cid, "class", name, rel, lineno(text, start + len(kw) + 1), "java", kind=kind, tags=["@" + a for a in ann if a in STEREO] + (["spring-data-repository"] if repo else []), layer=layer)
            g.link(fid, cid, "contains", "EXTRACTED", "%s:%d" % (rel, n["line"]))
            if owner:
                g.link("class:%s#%s" % (rel, owner[2]), cid, "contains", "EXTRACTED", rel)
            full = (pkg + "." if pkg else "") + (owner[2] + "." if owner else "") + name
            self.java_fqn[full] = cid
            self.classes_by_name.setdefault(name, []).append(cid)
            info = {"file": rel, "name": name, "methods": {}, "fields": {}, "extends": extends, "implements": implements, "pkg": pkg, "imports": imports, "repo_entity": repo.group(1) if repo else None}
            self.class_info[cid] = info
            # record components
            if kw == "record":
                po = code.find("(", hend - 1, br)
                if po >= 0:
                    depth, k = 0, po
                    while k < br:
                        depth += (code[k] == "(") - (code[k] == ")")
                        if depth == 0:
                            break
                        k += 1
                    for t, v in parse_params(code[po + 1:k]):
                        info["fields"][v] = t
            # entity / table
            if "Entity" in ann:
                tm = re.search(r"@Table\s*\(([^)]*)\)", text[seg_start:start + 1 + len(kw)])
                tname = None
                if tm:
                    nm = re.search(r"name\s*=\s*\"([^\"]+)\"", tm.group(1))
                    tname = nm.group(1) if nm else None
                tname = tname or re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
                tid = "datastore:table:" + tname
                g.node(tid, "datastore", tname, "", 0, "sql", kind="table", layer="data")
                g.link(cid, tid, "maps_to", "EXTRACTED", "%s:%d" % (rel, n["line"]))
            # members
            sk = skeleton(code, br, end)
            ctor_re = re.compile(r"(?:public|protected|private)?\s*%s\s*\(((?:[^()]|\([^()]*\))*)\)\s*(?:throws[\w.,\s]+)?\{" % re.escape(name))
            for fm in re.finditer(r"(?m)^[ \t]*(?:@\w+(?:\([^)]*\))?\s+)*(?:(?:private|protected|public|static|final|volatile|transient)\s+)*([A-Z][\w.]*(?:<[^;=(){}]*?>)?(?:\[\])?)\s+(\w+)\s*(?:=|;)", sk):
                info["fields"][fm.group(2)] = simple_type(fm.group(1))
            for cm in ctor_re.finditer(sk):
                for t, v in parse_params(cm.group(1)):
                    info["fields"].setdefault(v, t)
            cls_prefix = ""
            ctext_start = seg_start
            cls_ann_txt = text[ctext_start:start + 1 + len(kw)]
            pm = re.search(r"@RequestMapping\s*\(([^)]*)\)", cls_ann_txt)
            if pm:
                s = re.search(r"\"([^\"]*)\"", pm.group(1))
                cls_prefix = s.group(1) if s else ""
            for mm in re.finditer(r"(?<![\w.])((?:(?:public|protected|private|static|final|abstract|synchronized|default|native|strictfp)\s+)*)(?:<[^<>;{}()]*>\s+)?([\w.\[\]]+(?:<[^;{}()]*?>)?(?:\[\])*)\s+(\w+)\s*\(((?:[^()]|\([^()]*\))*)\)\s*(?:throws\s+[\w.,\s]+)?\s*([{;])", sk):
                mname, rtype = mm.group(3), mm.group(2)
                if mname in JAVA_KW or rtype in JAVA_KW or rtype in ("new", "return", "throw", "else"):
                    continue
                mstart = mm.start(3)
                mid = "fn:%s#%s.%s" % (rel, (owner[2] + "." if owner else "") + name, mname)
                if mid in g.nodes:
                    mid += "/%d" % lineno(text, mstart)
                mline = lineno(text, mstart)
                if mm.group(5) == "{":
                    _b0 = br + mm.end() - 1
                    _b1 = match_brace(code, _b0)
                    if re.fullmatch(r"\{\s*(?:return\s+(?:this\.)?\w+\s*;|(?:this\.)?\w+\s*=\s*\w+\s*;|return\s+getClass\(\)\.hashCode\(\)\s*;)\s*\}", code[_b0:_b1 + 1].strip()):
                        continue
                bnd = max(sk.rfind(";", 0, mm.start()), sk.rfind("}", 0, mm.start()), sk.rfind("{", 0, mm.start())) + 1
                # sk is offset-aligned with code starting at br
                seg_txt = text[br + bnd:br + mm.start()]
                anns = re.findall(r"@(\w+)", seg_txt)
                g.node(mid, "function", mname, rel, mline, "java", kind="method", layer=layer, owner=cid)
                g.link(cid, mid, "contains", "EXTRACTED", "%s:%d" % (rel, mline))
                info["methods"].setdefault(mname, mid)
                types = dict(info["fields"])
                for t, v in parse_params(mm.group(4)):
                    types[v] = t
                body = ""
                if mm.group(5) == "{":
                    bopen = br + mm.end() - 1
                    bclose = match_brace(code, bopen)
                    body = code[bopen:bclose + 1]
                    for lm in re.finditer(r"\b([A-Z]\w*(?:<[^<>;]*>)?)\s+(\w+)\s*(?:=|;|:)", body):
                        types.setdefault(lm.group(2), simple_type(lm.group(1)))
                self.pending_calls.append({"lang": "java", "from": mid, "file": rel, "cls": cid, "body": body, "types": types,
                                           "line0": lineno(text, br + mm.end() - 1)})
                for am in re.finditer(r"@(Get|Post|Put|Delete|Patch|Request)Mapping\s*(?:\(([^)]*)\))?", seg_txt):
                    args = am.group(2) or ""
                    s = re.search(r"\"([^\"]*)\"", args)
                    path = (cls_prefix.rstrip("/") + "/" + (s.group(1).lstrip("/") if s else "")).rstrip("/") or "/"
                    if not path.startswith("/"):
                        path = "/" + path
                    verb = am.group(1).upper()
                    if verb == "REQUEST":
                        vm = re.search(r"RequestMethod\.(\w+)", args)
                        verb = vm.group(1) if vm else "ANY"
                    eid = "endpoint:%s %s@%s" % (verb, path, rel)
                    g.node(eid, "endpoint", "%s %s" % (verb, path), rel, mline, "java", kind="rest", layer="api")
                    g.link(cid, eid, "exposes", "EXTRACTED", "%s:%d" % (rel, mline))
                    g.link(eid, mid, "exposes", "EXTRACTED", "%s:%d" % (rel, mline))
                    self.pending_calls.append({"lang": "none", "endpoint": eid})
        return pkg, imports

    # ---- JS / TS ----
    def parse_js(self, rel, text, base_line=0, owner_file=None):
        owner_file = owner_file or rel
        g = self.g
        fid = "file:" + owner_file
        code = mask(text, keep_strings=False)
        scode = mask(text, keep_strings=True)
        ext = os.path.splitext(owner_file)[1].lower()
        bind = self.js_bindings.setdefault(owner_file, {})
        for m in re.finditer(r"import\s+(?:type\s+)?([^;'\"]*?)\s*from\s*[\"']([^\"']+)[\"']|import\s*[\"']([^\"']+)[\"']|export\s+[^;'\"]*?from\s*[\"']([^\"']+)[\"']|require\(\s*[\"']([^\"']+)[\"']\s*\)", scode):
            spec = m.group(2) or m.group(3) or m.group(4) or m.group(5)
            clause = m.group(1) or ""
            tgt = self.resolve_js(owner_file, spec)
            line = base_line + lineno(text, m.start())
            if tgt:
                g.link(fid, "file:" + tgt, "imports", "EXTRACTED", "%s:%d" % (owner_file, line))
            else:
                pk = spec if spec.startswith(".") else ("/".join(spec.split("/")[:2]) if spec.startswith("@") else spec.split("/")[0])
                if not spec.startswith("."):
                    g.node("external:" + pk, "external", pk, "", 0, "", kind="package", layer="external")
                    g.link(fid, "external:" + pk, "imports", "EXTRACTED", "%s:%d" % (owner_file, line))
            for dm in re.finditer(r"(?:^|,)\s*([A-Za-z_$][\w$]*)\s*(?:,|$|(?=\{))", clause.split("{")[0]):
                bind[dm.group(1)] = (tgt, "default", None if tgt else spec)
            bm = re.search(r"\{([^}]*)\}", clause)
            if bm:
                for part in bm.group(1).split(","):
                    part = part.strip()
                    if not part:
                        continue
                    seg = re.split(r"\s+as\s+", part)
                    bind[seg[-1].strip()] = (tgt, seg[0].replace("type ", "").strip(), None if tgt else spec)
            nm = re.search(r"\*\s+as\s+(\w+)", clause)
            if nm:
                bind[nm.group(1)] = (tgt, "*", None if tgt else spec)
        ranges = []
        decl_re = [
            re.compile(r"(?:^|[\s;}])(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\("),
            re.compile(r"(?:^|[\s;}])(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*(?::[^=;]+)?=\s*(?:async\s*)?(?:function\b|\([^)]*\)\s*(?::[^=]+)?=>|[A-Za-z_$][\w$]*\s*=>)"),
        ]
        for rx in decl_re:
            for m in rx.finditer(code):
                name = m.group(1)
                if name in JAVA_KW or name in ("if", "for", "while", "switch", "catch", "function"):
                    continue
                s = m.start(1)
                br = None
                if rx is decl_re[0]:
                    po, depth = m.end() - 1, 0
                    k = po
                    while k < len(code):
                        depth += (code[k] == "(") - (code[k] == ")")
                        if depth == 0:
                            break
                        k += 1
                    br = code.find("{", k)
                if br is None:
                    arrow = code.find("=>", m.start())
                    nxt = code[arrow + 2:arrow + 40].lstrip()
                    if nxt.startswith("{"):
                        br = arrow + 2 + (len(code[arrow + 2:arrow + 40]) - len(nxt))
                if br is not None and br >= 0:
                    e = match_brace(code, br)
                else:
                    e = code.find(";", m.end())
                    e = len(code) - 1 if e < 0 else e
                fidn = "fn:%s#%s" % (owner_file, name)
                if fidn in g.nodes:
                    continue
                kind = "component" if name[:1].isupper() and ext in (".tsx", ".jsx") else "function"
                g.node(fidn, "function", name, owner_file, base_line + lineno(text, s), "js", kind=kind, layer=layer_for(owner_file, "function", ext=ext))
                g.link(fid, fidn, "contains", "EXTRACTED", "%s:%d" % (owner_file, base_line + lineno(text, s)))
                ranges.append((s, e, fidn))
                self.file_funcs.setdefault(owner_file, {})[name] = fidn
                self.funcs_by_name.setdefault(name, []).append(fidn)
        for m in re.finditer(r"(?:^|[\s;}])(?:export\s+)?(?:default\s+)?class\s+([A-Za-z_$][\w$]*)(?:\s+extends\s+([\w$.]+))?", code):
            cid = "class:%s#%s" % (owner_file, m.group(1))
            br = code.find("{", m.end())
            g.node(cid, "class", m.group(1), owner_file, base_line + lineno(text, m.start(1)), "js", kind="class", layer=layer_for(owner_file, "class", ext=ext))
            g.link(fid, cid, "contains", "EXTRACTED", owner_file)
            self.classes_by_name.setdefault(m.group(1), []).append(cid)
            if m.group(2):
                self.pending_calls.append({"lang": "extends", "from": cid, "name": m.group(2).split(".")[-1], "file": owner_file})
        for m in re.finditer(r"export\s+default\s+(?:function\s+)?([A-Za-z_$][\w$]*)", code):
            bind.setdefault("__default__", (None, m.group(1), None))
        # routes
        starts = [m.start() for m in re.finditer(r"<Route\b", scode)]
        for k, s in enumerate(starts):
            e = starts[k + 1] if k + 1 < len(starts) else len(scode)
            cut = scode.find("</Routes>", s)
            e = min(e, cut) if cut != -1 else e
            win = scode[s:e]
            pm = re.search(r"path=\"([^\"]+)\"", win)
            comps = [c for c in re.findall(r"<([A-Z]\w*)", win) if c != "Route"]
            eid = "endpoint:ROUTE %s@%s" % (pm.group(1) if pm else "(layout)", owner_file)
            g.node(eid, "endpoint", "ROUTE " + (pm.group(1) if pm else "(layout)"), owner_file, base_line + lineno(text, s), "js", kind="route", layer="ui")
            g.link(fid, eid, "contains", "EXTRACTED", owner_file)
            for c in comps:
                self.pending_calls.append({"lang": "routecomp", "endpoint": eid, "name": c, "file": owner_file, "line": base_line + lineno(text, s)})
        # data access, fetch, storage, env, calls, jsx
        fn_ranges = ranges
        for m in re.finditer(r"\.from\(\s*[\"'](\w+)[\"']\s*\)", scode):
            tail = scode[m.end():m.end() + 400]
            op = re.search(r"\.(select|insert|update|delete|upsert)\s*\(", tail)
            tid = "datastore:table:" + m.group(1)
            g.node(tid, "datastore", m.group(1), "", 0, "sql", kind="table", layer="data")
            who = self.enclosing(owner_file, m.start(), fn_ranges)
            ln = base_line + lineno(text, m.start())
            g.link(who, tid, "writes" if op and op.group(1) != "select" else "reads", "EXTRACTED", "%s:%d" % (owner_file, ln))
        for m in re.finditer(r"fetch\(\s*([`\"'])(https?://[^`\"'$?]+)", scode):
            host = re.sub(r"^https?://", "", m.group(2)).split("/")[0]
            g.node("external:" + host, "external", host, "", 0, "", kind="http", layer="external")
            who = self.enclosing(owner_file, m.start(), fn_ranges)
            g.link(who, "external:" + host, "fetches", "EXTRACTED", "%s:%d" % (owner_file, base_line + lineno(text, m.start())))
        for m in re.finditer(r"(localStorage|sessionStorage)\.(getItem|setItem|removeItem)\(\s*([^,)]*)", scode):
            k = m.group(3).strip()
            key = k.strip("\"'`") if k[:1] in "\"'`" else self.const_str.get(k, "<dynamic:%s>" % k)
            sid = "datastore:storage:%s:%s" % (m.group(1), key)
            g.node(sid, "datastore", key, "", 0, "", kind="browser-storage", layer="data")
            who = self.enclosing(owner_file, m.start(), fn_ranges)
            g.link(who, sid, "reads" if m.group(2) == "getItem" else "writes", "EXTRACTED", "%s:%d" % (owner_file, base_line + lineno(text, m.start())))
        for m in re.finditer(r"import\.meta\.env\.(\w+)|process\.env\.(\w+)", scode):
            name = m.group(1) or m.group(2)
            g.node("config:env:" + name, "config", name, "", 0, "", kind="env-var", layer="config")
            who = self.enclosing(owner_file, m.start(), fn_ranges)
            g.link(who, "config:env:" + name, "uses", "EXTRACTED", "%s:%d" % (owner_file, base_line + lineno(text, m.start())))
        for m in re.finditer(r"(?<![\w$.])([A-Za-z_$][\w$]*)\s*\(", code):
            nm = m.group(1)
            if nm in JAVA_KW or nm in ("function", "import", "require", "fetch", "catch", "async", "await", "typeof"):
                continue
            who = self.enclosing(owner_file, m.start(), fn_ranges)
            if who.startswith("fn:") and who.endswith("#" + nm):
                continue
            self.pending_calls.append({"lang": "jscall", "from": who, "name": nm, "file": owner_file, "line": base_line + lineno(text, m.start())})
        if ext in (".tsx", ".jsx", ".html", ".htm", ".js"):
            for m in re.finditer(r"<([A-Z][\w]*)\b", code):
                who = self.enclosing(owner_file, m.start(), fn_ranges)
                self.pending_calls.append({"lang": "jsx", "from": who, "name": m.group(1), "file": owner_file, "line": base_line + lineno(text, m.start())})

    def resolve_js(self, from_file, spec):
        if spec.startswith("@/"):
            base = "src/" + spec[2:]
        elif spec.startswith("."):
            base = os.path.normpath(os.path.join(os.path.dirname(from_file), spec)).replace(os.sep, "/")
        else:
            return None
        for suffix in ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", "/index.ts", "/index.tsx", "/index.js"):
            if base + suffix in self.files:
                return base + suffix
        return None

    # ---- HTML ----
    def parse_html(self, rel):
        text = self.files[rel]
        g = self.g
        fid = "file:" + rel
        scripts = []
        for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", text, re.I | re.S):
            attrs, body = m.group(1), m.group(2)
            src = re.search(r"\bsrc=[\"']([^\"']+)[\"']", attrs)
            if src:
                s = src.group(1)
                if re.match(r"https?://|//", s):
                    host = re.sub(r"^(https?:)?//", "", s).split("/")[0]
                    g.node("external:" + host, "external", host, "", 0, "", kind="cdn-script", layer="external")
                    g.link(fid, "external:" + host, "loads", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
                else:
                    tgt = os.path.normpath(os.path.join(os.path.dirname(rel), s.split("?")[0])).replace(os.sep, "/")
                    if tgt in self.files:
                        g.link(fid, "file:" + tgt, "loads", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
                        scripts.append(tgt)
            elif body.strip():
                self.parse_js(rel, body, base_line=lineno(text, m.start(2)) - 1, owner_file=rel)
        for m in re.finditer(r"<link\b([^>]*)>", text, re.I):
            if re.search(r"rel=[\"']stylesheet[\"']", m.group(1), re.I):
                h = re.search(r"href=[\"']([^\"']+)[\"']", m.group(1))
                if h and not re.match(r"https?://|//", h.group(1)):
                    tgt = os.path.normpath(os.path.join(os.path.dirname(rel), h.group(1))).replace(os.sep, "/")
                    if tgt in self.files:
                        g.link(fid, "file:" + tgt, "loads", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
        for m in re.finditer(r"\bon\w+\s*=\s*[\"']\s*(\w+)\s*\(", text):
            self.pending_calls.append({"lang": "jscall", "from": fid, "name": m.group(1), "file": rel, "line": lineno(text, m.start()), "html": True})
        for m in re.finditer(r"<a\b[^>]*\bhref=[\"']([^\"'#?]+\.html?)[\"']", text, re.I):
            tgt = os.path.normpath(os.path.join(os.path.dirname(rel), m.group(1))).replace(os.sep, "/")
            if tgt in self.files:
                g.link(fid, "file:" + tgt, "imports", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
        self.pages_scripts[rel] = scripts

    # ---- SQL ----
    def parse_sql(self, rel):
        text = self.files[rel]
        code = re.sub(r"--[^\n]*", lambda m: " " * len(m.group(0)), text)
        g = self.g
        fid = "file:" + rel
        rls = {m.group(1).replace('"', "").split(".")[-1].lower() for m in re.finditer(r"alter\s+table\s+(?:only\s+)?([\w.\"]+)\s+enable\s+row\s+level\s+security", code, re.I)}
        allow_all = {m.group(1).replace('"', "").split(".")[-1].lower() for m in re.finditer(r"create\s+policy[^;]*?\bon\s+([\w.\"]+)[^;]*?(?:using|with\s+check)\s*\(\s*true\s*\)", code, re.I | re.S)}
        for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w.\"]+)\s*\(", code, re.I):
            name = m.group(1).replace('"', "").split(".")[-1]
            i, depth = m.end(), 1
            while i < len(code) and depth:
                depth += (code[i] == "(") - (code[i] == ")")
                i += 1
            tags = ["rls"] if name.lower() in rls else []
            if name.lower() in allow_all:
                tags.append("allow-all-policy")
            tid = "datastore:table:" + name
            g.node(tid, "datastore", name, rel, lineno(code, m.start()), "sql", kind="table", tags=tags, layer="data")
            g.link(fid, tid, "contains", "EXTRACTED", "%s:%d" % (rel, lineno(code, m.start())))
            for rm in re.finditer(r"references\s+([\w.\"]+)", code[m.end():i], re.I):
                other = rm.group(1).replace('"', "").split(".")[-1]
                if other.lower() != "auth" and "." not in rm.group(1) or True:
                    self.pending_calls.append({"lang": "fk", "from": tid, "name": other, "file": rel, "line": lineno(code, m.start())})

    # ---- Python ----
    def parse_py(self, rel):
        text = self.files[rel]
        g = self.g
        fid = "file:" + rel
        for m in re.finditer(r"(?m)^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", text):
            mod = m.group(1) or m.group(2)
            cand = mod.replace(".", "/")
            for tgt in (cand + ".py", cand + "/__init__.py", os.path.join(os.path.dirname(rel), cand.split("/")[-1] + ".py").replace(os.sep, "/")):
                if tgt in self.files:
                    g.link(fid, "file:" + tgt, "imports", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
                    break
            else:
                top = mod.split(".")[0]
                if top not in {"os", "sys", "re", "json", "typing", "datetime", "pathlib", "collections", "dataclasses"}:
                    g.node("external:" + top, "external", top, "", 0, "", kind="package", layer="external")
                    g.link(fid, "external:" + top, "imports", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
        for m in re.finditer(r"(?m)^(class|def|async def)\s+(\w+)", text):
            nid = "%s:%s#%s" % ("class" if m.group(1) == "class" else "fn", rel, m.group(2))
            g.node(nid, "class" if m.group(1) == "class" else "function", m.group(2), rel, lineno(text, m.start()), "py",
                   kind="class" if m.group(1) == "class" else "function", layer=layer_for(rel, "function"))
            g.link(fid, nid, "contains", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
            if m.group(1) != "class":
                self.file_funcs.setdefault(rel, {})[m.group(2)] = nid
                self.funcs_by_name.setdefault(m.group(2), []).append(nid)
        for m in re.finditer(r"(?m)^@\w+\.(get|post|put|delete|patch|route)\(\s*[\"']([^\"']+)[\"'][^\n]*\n\s*(?:async\s+)?def\s+(\w+)", text):
            eid = "endpoint:%s %s@%s" % (m.group(1).upper(), m.group(2), rel)
            g.node(eid, "endpoint", "%s %s" % (m.group(1).upper(), m.group(2)), rel, lineno(text, m.start()), "py", kind="rest", layer="api")
            g.link(eid, "fn:%s#%s" % (rel, m.group(3)), "exposes", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))

    # ---- config / build ----
    def parse_config(self, rel):
        text = self.files[rel]
        g, fid = self.g, "file:" + rel
        base = os.path.basename(rel)
        for m in re.finditer(r"\$\{([A-Z][A-Z0-9_]+)(?::[^}]*)?\}", text):
            g.node("config:env:" + m.group(1), "config", m.group(1), "", 0, "", kind="env-var", layer="config")
            g.link(fid, "config:env:" + m.group(1), "uses", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
        if base == "package.json":
            try:
                pj = json.loads(text)
            except ValueError:
                pj = {}
            for sect in ("dependencies", "devDependencies"):
                for dep in sorted(pj.get(sect, {})):
                    g.node("external:" + dep, "external", dep, "", 0, "", kind="package", layer="external")
                    g.link(fid, "external:" + dep, "depends_on", "EXTRACTED", rel)
        elif base == "pom.xml":
            for m in re.finditer(r"<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>", text):
                nm = "%s:%s" % (m.group(1).strip(), m.group(2).strip())
                g.node("external:maven:" + nm, "external", nm, "", 0, "", kind="maven", layer="external")
                g.link(fid, "external:maven:" + nm, "depends_on", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))
        elif base.endswith(".gradle"):
            for m in re.finditer(r"(?:implementation|api|runtimeOnly|testImplementation)\s*\(?\s*[\"']([\w.\-]+:[\w.\-]+)", text):
                g.node("external:maven:" + m.group(1), "external", m.group(1), "", 0, "", kind="maven", layer="external")
                g.link(fid, "external:maven:" + m.group(1), "depends_on", "EXTRACTED", "%s:%d" % (rel, lineno(text, m.start())))

    # ---- pass 2 ----
    def resolve_classes(self, name, rel, imports=None, pkg=""):
        cands = []
        for cid in self.classes_by_name.get(name, []):
            if self.class_info.get(cid, {}).get("file") == rel or (cid.split("#")[0][6:] == rel):
                return [cid]
        if imports:
            for imp in imports:
                if imp.endswith("." + name) and imp in self.java_fqn:
                    return [self.java_fqn[imp]]
        same_pkg = [c for c in self.classes_by_name.get(name, []) if self.class_info.get(c, {}).get("pkg") == pkg and pkg]
        if same_pkg:
            return same_pkg[:1]
        cands = self.classes_by_name.get(name, [])
        return cands[:3]

    def pass2(self):
        g = self.g
        for cid, info in sorted(self.class_info.items()):
            rel = info["file"]
            for kind, names in (("extends", info["extends"]), ("implements", info["implements"])):
                for nm in names:
                    t = self.resolve_classes(nm, rel, info["imports"], info["pkg"])
                    t = [x for x in t if x != cid]
                    for x in t:
                        g.link(cid, x, kind, "EXTRACTED" if len(t) == 1 else "AMBIGUOUS", "%s:%d" % (rel, g.nodes[cid]["line"]))
            if info["repo_entity"]:
                t = self.resolve_classes(info["repo_entity"], rel, info["imports"], info["pkg"])
                for x in t[:1]:
                    g.link(cid, x, "manages", "EXTRACTED", "%s:%d" % (rel, g.nodes[cid]["line"]))
            for imp in info["imports"]:
                tid = self.java_fqn.get(imp)
                if tid:
                    g.link("file:" + rel, "file:" + self.class_info[tid]["file"], "imports", "EXTRACTED", "%s" % rel)
                elif not imp.startswith(("java.", "javax.")):
                    top = ".".join(imp.split(".")[:3])
                    g.node("external:" + top, "external", top, "", 0, "", kind="package", layer="external")
                    g.link("file:" + rel, "external:" + top, "imports", "EXTRACTED", rel)
        global_js = {}
        for name, ids in self.funcs_by_name.items():
            global_js[name] = ids
        for pc in self.pending_calls:
            lang = pc["lang"]
            if lang == "none":
                continue
            if lang == "java":
                info = self.class_info[pc["cls"]]
                rel = pc["file"]
                body = pc["body"]
                seen = set()
                for m in re.finditer(r"(?:\b(this)\.)?(?:\b(\w+)\.)?\b(\w+)\s*\(", body):
                    this, qual, meth = m.group(1), m.group(2), m.group(3)
                    if meth in JAVA_KW or meth[:1].isupper() and not qual:
                        continue
                    ln = pc["line0"] + body.count("\n", 0, m.start())
                    targets, conf = [], "INFERRED"
                    if qual:
                        tname = pc["types"].get(qual) or (qual if qual[:1].isupper() else None)
                        if tname:
                            for c in self.resolve_classes(tname, rel, info["imports"], info["pkg"]):
                                mid = self.class_info.get(c, {}).get("methods", {}).get(meth)
                                if mid:
                                    targets.append(mid)
                    else:
                        mid = info["methods"].get(meth)
                        if mid:
                            targets.append(mid)
                        else:
                            for sup in info["extends"] + info["implements"]:
                                for c in self.resolve_classes(sup, rel, info["imports"], info["pkg"]):
                                    mid = self.class_info.get(c, {}).get("methods", {}).get(meth)
                                    if mid:
                                        targets.append(mid)
                    targets = [t for t in dict.fromkeys(targets) if t != pc["from"]]
                    if len(targets) > 1:
                        conf, targets = "AMBIGUOUS", targets[:3]
                    for t in targets:
                        if (t, conf) in seen:
                            continue
                        seen.add((t, conf))
                        g.link(pc["from"], t, "calls", conf, "%s:%d" % (rel, ln))
                for tn in set(pc["types"].values()):
                    for c in self.resolve_classes(tn, rel, info["imports"], info["pkg"])[:1]:
                        if c != pc["cls"] and c in self.class_info:
                            g.link(pc["cls"], c, "uses", "INFERRED", "%s" % rel)
            elif lang == "extends":
                for x in self.classes_by_name.get(pc["name"], [])[:3]:
                    if x != pc["from"]:
                        g.link(pc["from"], x, "extends", "EXTRACTED" if len(self.classes_by_name[pc["name"]]) == 1 else "AMBIGUOUS", pc["file"])
            elif lang in ("jscall", "jsx", "routecomp"):
                rel, name = pc["file"], pc["name"]
                src = pc.get("from") or pc.get("endpoint")
                ev = "%s:%d" % (rel, pc.get("line", 0))
                targets, conf = [], "INFERRED"
                b = self.js_bindings.get(rel, {}).get(name)
                if b and b[0]:
                    trel, imported = b[0], b[1]
                    cand_names = [imported if imported not in ("default", "*") else None]
                    if imported == "default":
                        cand_names = [self.js_bindings.get(trel, {}).get("__default__", (None, name, None))[1], name]
                    for cn in cand_names:
                        if cn and cn in self.file_funcs.get(trel, {}):
                            targets.append(self.file_funcs[trel][cn])
                            break
                        if cn:
                            cls = "class:%s#%s" % (trel, cn)
                            if cls in g.nodes:
                                targets.append(cls)
                                break
                elif name in self.file_funcs.get(rel, {}):
                    targets.append(self.file_funcs[rel][name])
                elif not b:
                    cands = global_js.get(name, [])
                    if pc.get("html") or rel.endswith((".html", ".htm")) or rel.endswith(".js"):
                        # scripts loaded by the same page share a global scope
                        page_sets = [set(s) | {p} for p, s in self.pages_scripts.items()]
                        scoped = [c for c in cands if any(c.split("#")[0][3:] in ps and rel in ps for ps in page_sets)]
                        cands = scoped or (cands if not rel.endswith((".tsx", ".ts", ".jsx")) else [])
                    targets = cands[:4]
                targets = [t for t in dict.fromkeys(targets) if t != src]
                if len(targets) > 1:
                    conf, targets = "AMBIGUOUS", targets[:3]
                ltype = "exposes" if lang == "routecomp" else ("uses" if lang == "jsx" else "calls")
                for t in targets:
                    if lang == "routecomp":
                        g.link(src, t, ltype, "EXTRACTED" if len(targets) == 1 else "AMBIGUOUS", ev)
                    else:
                        g.link(src, t, ltype, conf, ev)
            elif lang == "fk":
                tid = "datastore:table:" + pc["name"]
                if tid in g.nodes:
                    g.link(pc["from"], tid, "references", "EXTRACTED", "%s:%d" % (pc["file"], pc["line"]))

    def run(self):
        self.load()
        for rel in sorted(self.files):
            self.add_file(rel)
        for rel in sorted(self.files):
            ext = os.path.splitext(rel)[1].lower()
            lang = LANG.get(ext, "config")
            if lang == "java":
                self.parse_java(rel)
            elif lang == "js":
                self.parse_js(rel, self.files[rel])
            elif lang == "html":
                pass
            elif lang == "sql":
                self.parse_sql(rel)
            elif lang == "py":
                self.parse_py(rel)
            else:
                self.parse_config(rel)
        for rel in sorted(self.files):
            if LANG.get(os.path.splitext(rel)[1].lower()) == "html":
                self.parse_html(rel)
        self.pass2()
        return self.g


# ----------------------------------------------------------------------------------------------
W_TYPE = {"extends": 2, "implements": 2, "references": 2, "manages": 2, "maps_to": 2, "contains": 3}
W_CONF = {"EXTRACTED": 1.0, "INFERRED": 0.7, "AMBIGUOUS": 0.3}
CORE_TYPES = ("file", "class", "function", "endpoint", "datastore")


def tarjan(nodes, adj):
    index, low, on, stack, out, idx = {}, {}, set(), [], [], [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(sorted(adj.get(root, []))))]
        index[root] = low[root] = idx[0]
        idx[0] += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            adv = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = idx[0]
                    idx[0] += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(sorted(adj.get(w, [])))))
                    adv = True
                    break
                elif w in on:
                    low[v] = min(low[v], index[w])
            if adv:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    out.append(sorted(comp))
    return sorted(out)


LIST_RE = re.compile(r"\[\s*((?:\"[^\"\n]{1,30}\"|'[^'\n]{1,30}')(?:\s*,\s*(?:\"[^\"\n]{1,30}\"|'[^'\n]{1,30}')){2,})\s*,?\s*\]|"
                     r"(?:List|Set|Arrays)\.(?:of|asList)\(\s*((?:\"[^\"\n]{1,30}\")(?:\s*,\s*\"[^\"\n]{1,30}\"){2,})\s*\)")


def similar_lists(files):
    found = []
    for rel in sorted(files):
        if not rel.endswith((".js", ".ts", ".tsx", ".jsx", ".html", ".htm", ".java", ".py")):
            continue
        text = files[rel]
        code = mask(text, keep_strings=True, java=rel.endswith(".java"))
        for m in LIST_RE.finditer(code):
            body = m.group(1) or m.group(2)
            items = frozenset(x.strip().strip("\"'") for x in re.findall(r"\"[^\"\n]*\"|'[^'\n]*'", body))
            found.append((rel, lineno(text, m.start()), items))
    out = []
    for i in range(len(found)):
        for j in range(i + 1, len(found)):
            a, b = found[i], found[j]
            if a[0] == b[0] and abs(a[1] - b[1]) < 1:
                continue
            if a[0] == b[0]:
                continue
            inter, union = len(a[2] & b[2]), len(a[2] | b[2])
            if union and inter / union >= 0.6:
                out.append({"kind": "identical" if a[2] == b[2] else "overlapping", "first": "%s:%d" % (a[0], a[1]),
                            "second": "%s:%d" % (b[0], b[1]), "only_in_first": sorted(a[2] - b[2])[:8],
                            "only_in_second": sorted(b[2] - a[2])[:8], "size": [len(a[2]), len(b[2])]})
    return out[:20]


def analyze(g, files=None):
    nodes = g.nodes
    links = sorted(g.links.values(), key=lambda l: (l["source"], l["target"], l["type"]))
    deg = {k: 0 for k in nodes}
    for l in links:
        if l["type"] != "contains":
            deg[l["source"]] += 1
            deg[l["target"]] += 1
    for k, n in nodes.items():
        n["degree"] = deg[k]
    # communities by weighted label propagation
    mem = sorted(k for k, n in nodes.items() if n["type"] in CORE_TYPES)
    adj = {k: {} for k in mem}
    for l in links:
        a, b = l["source"], l["target"]
        if a in adj and b in adj:
            w = W_TYPE.get(l["type"], 1) * W_CONF[l["confidence"]]
            adj[a][b] = adj[a].get(b, 0) + w
            adj[b][a] = adj[b].get(a, 0) + w
    label = {k: k for k in mem}
    for _ in range(30):
        changed = False
        for k in mem:
            score = {}
            for nb, w in adj[k].items():
                score[label[nb]] = score.get(label[nb], 0) + w
            if score:
                best = sorted(score.items(), key=lambda x: (-x[1], x[0]))[0][0]
                if best != label[k]:
                    label[k], changed = best, True
        if not changed:
            break
    groups = {}
    for k in mem:
        groups.setdefault(label[k], []).append(k)
    for lab in sorted(groups, key=lambda x: (len(groups[x]), x)):
        if lab not in groups or len(groups[lab]) > 2 or len(groups) <= 1:
            continue
        score = {}
        for k in groups[lab]:
            for nb, w in adj[k].items():
                if label[nb] != lab:
                    score[label[nb]] = score.get(label[nb], 0) + w
        if score:
            best = sorted(score.items(), key=lambda x: (-x[1], x[0]))[0][0]
            for k in groups[lab]:
                label[k] = best
            groups[best].extend(groups.pop(lab))
    ordered = sorted(groups.values(), key=lambda m: (-len(m), m[0]))
    communities = []
    for i, m in enumerate(ordered):
        cid = "c%d" % i
        dirs = {}
        for k in m:
            f = nodes[k]["file"] or ""
            d = os.path.dirname(f) or "."
            dirs[d] = dirs.get(d, 0) + 1
        top_dir = sorted(dirs.items(), key=lambda x: (-x[1], x[0]))[0][0] if dirs else "."
        hub = sorted(m, key=lambda k: (-nodes[k]["degree"], k))[0]
        for k in m:
            nodes[k]["community"] = cid
        communities.append({"id": cid, "name": "%s / %s" % (top_dir, nodes[hub]["name"]), "size": len(m),
                            "top_members": sorted(m, key=lambda k: (-nodes[k]["degree"], k))[:5]})
    # hubs
    hubs = [{"id": k, "name": nodes[k]["name"], "degree": nodes[k]["degree"]}
            for k in sorted((k for k in mem if nodes[k]["type"] in ("file", "class", "function", "datastore") and
                             not (nodes[k]["type"] == "file" and nodes[k]["lang"] == "config")),
                            key=lambda k: (-nodes[k]["degree"], k))[:10] if nodes[k]["degree"] > 0]
    # import cycles
    fadj = {}
    for l in links:
        if l["type"] == "imports" and l["source"].startswith("file:") and l["target"].startswith("file:"):
            fadj.setdefault(l["source"], set()).add(l["target"])
    cycles = tarjan(sorted(fadj), fadj)
    # orphans and entry points
    touched = set()
    for l in links:
        if l["type"] != "contains":
            touched.add(l["source"])
            touched.add(l["target"])
    child_touched = set()
    for l in links:
        if l["type"] == "contains" and (l["target"] in touched or l["source"] in touched) and l["source"].startswith("file:"):
            child_touched.add(l["source"])
    entry, orphans = [], []
    for k, n in sorted(nodes.items()):
        if n["type"] != "file" or n["lang"] in ("config",):
            continue
        base = n["name"].lower()
        is_entry = bool(re.match(r"(main|index|app|application)\b", base)) or "@SpringBootApplication" in [
            t for c in nodes if c.startswith("class:" + n["file"] + "#") for t in nodes[c]["tags"]] or (n["lang"] == "html")
        if is_entry:
            entry.append(k)
        elif k not in touched and k not in child_touched and n["layer"] != "test":
            orphans.append(k)
    # duplicates
    by_name = {}
    for k, n in nodes.items():
        if n["type"] in ("function", "class") and n["name"] not in COMMON_NAMES and n.get("kind") != "method" or \
                (n["type"] == "function" and n.get("kind") == "method" and False):
            by_name.setdefault((n["type"], n["name"]), []).append(k)
    dups = [{"name": nm, "type": t, "ids": sorted(ids)} for (t, nm), ids in sorted(by_name.items())
            if len({nodes[i]["file"] for i in ids}) > 1]
    # surprising cross-community links
    pair_count = {}
    cross = []
    for l in links:
        a, b = nodes[l["source"]], nodes[l["target"]]
        if l["type"] in ("contains",) or "community" not in a or "community" not in b or a["community"] == b["community"]:
            continue
        key = tuple(sorted((a["community"], b["community"])))
        pair_count[key] = pair_count.get(key, 0) + 1
        cross.append((key, l))
    surprising = []
    prefer = {"calls", "uses", "reads", "writes", "fetches", "references", "extends", "implements", "exposes", "manages", "maps_to"}
    for key, l in sorted(cross, key=lambda x: (pair_count[x[0]], x[1]["type"] not in prefer,
                                               -CONF_RANK[x[1]["confidence"]], nodes[x[1]["source"]]["degree"] + nodes[x[1]["target"]]["degree"], x[1]["source"])):
        if pair_count[key] <= 2:
            surprising.append({"source": l["source"], "target": l["target"], "type": l["type"], "confidence": l["confidence"],
                               "evidence": l["evidence"]})
        if len(surprising) >= 8:
            break
    layers = {}
    for n in nodes.values():
        if n["type"] in CORE_TYPES:
            layers[n["layer"] or "core"] = layers.get(n["layer"] or "core", 0) + 1
    return communities, {"hubs": hubs, "import_cycles": cycles, "entry_points": entry, "orphan_files": orphans,
                         "duplicate_names": dups, "similar_lists": similar_lists(files or {}), "surprising_links": surprising, "layers": dict(sorted(layers.items()))}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="code folder to map")
    ap.add_argument("--out", required=True, help="output graph.json path")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print("ERROR: root not found: " + root, file=sys.stderr)
        return 2
    ex = Extractor(root)
    g = ex.run()
    communities, analysis = analyze(g, ex.files)
    links = sorted(g.links.values(), key=lambda l: (l["source"], l["target"], l["type"]))
    nodes = [g.nodes[k] for k in sorted(g.nodes)]
    for n in nodes:
        for k in ("summary",):
            n[k] = SECRET_VALUE.sub("[REDACTED]", n[k])
    stats = {"nodes": len(nodes), "links": len(links), "files": sum(1 for n in nodes if n["type"] == "file"),
             "by_node_type": {}, "by_link_type": {}, "by_confidence": {}, "by_language": {}}
    for n in nodes:
        stats["by_node_type"][n["type"]] = stats["by_node_type"].get(n["type"], 0) + 1
        if n["type"] == "file":
            stats["by_language"][n["lang"]] = stats["by_language"].get(n["lang"], 0) + 1
    for l in links:
        stats["by_link_type"][l["type"]] = stats["by_link_type"].get(l["type"], 0) + 1
        stats["by_confidence"][l["confidence"]] = stats["by_confidence"].get(l["confidence"], 0) + 1
    out = {"schema_version": "1.0",
           "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "root_name": os.path.basename(root), "directed": True, "stats": stats, "nodes": nodes, "links": links,
           "communities": communities, "analysis": analysis, "concepts": [], "tours": [],
           "skipped_files": ex.skipped}
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print("graph: %d nodes, %d links (%s) | %d communities | %d hubs, %d import cycles, %d orphans -> %s" % (
        len(nodes), len(links), ", ".join("%s %d" % (k, v) for k, v in sorted(stats["by_confidence"].items())),
        len(communities), len(analysis["hubs"]), len(analysis["import_cycles"]), len(analysis["orphan_files"]), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
