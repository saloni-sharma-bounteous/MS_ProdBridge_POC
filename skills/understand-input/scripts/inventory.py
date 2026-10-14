#!/usr/bin/env python3
"""Deterministic inventory of a vibe-coded application (Lovable/Vite/React, static HTML, single-file HTML).

Reads source only. Never executes app code, never touches the network, never prints secret
values (env files are reported by variable NAME only; secret-looking literals are redacted).

Usage:
    python3 inventory.py --root <app-dir> --out <handoff-dir>/inventory.json
Python 3.8+, standard library only.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

IGNORE_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".nuxt", ".svelte-kit", "coverage",
               "handoff", ".venv", "venv", "__pycache__", ".idea", ".vscode", ".turbo", ".cache"}
TEXT_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".html", ".htm", ".css", ".scss", ".sql", ".json",
            ".toml", ".md", ".yml", ".yaml", ".vue", ".svelte", ".txt", ".csv", ".svg", ".env"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".vue", ".svelte"}
MAX_BYTES = 1000000
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "bun.lock"}

SECRET_NAME = re.compile(r"(?i)(secret|token|password|passwd|pwd|(?:^|_)pin|(?:^|_)key)$")
NOT_SECRET_NAME = re.compile(r"(?i)(?:DB|STORAGE|CACHE|QUERY|SORT|REACT|MAP|LOOKUP|PRIMARY|LOCAL)_KEY$")
SECRET_VALUE = re.compile(r"eyJ[\w.\-]{10,}|\b(?:cb|sk|pk|scr|rk)_(?:live|test)_[\w\-]{6,}")
CRED_LITERAL = re.compile(r"""(?i)((?<![a-z0-9])(?:password|passwd|pwd|pass|p|pin|secret|token|api[_-]?key)["']?\s*(?:===?|[:=])\s*)["'][^"']*["']""")


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def redact(text):
    text = SECRET_VALUE.sub("[REDACTED]", text)
    return CRED_LITERAL.sub(r'\1"[REDACTED]"', text)


def classify(rel):
    ext = os.path.splitext(rel)[1].lower()
    base = os.path.basename(rel)
    if base.startswith(".env"):
        return "config"
    if ext in CODE_EXT:
        return "source"
    if ext in {".html", ".htm"}:
        return "markup"
    if ext in {".css", ".scss"}:
        return "style"
    if ext == ".sql":
        return "sql"
    if ext in {".json", ".toml", ".yml", ".yaml"}:
        return "config"
    if ext in {".md", ".txt"}:
        return "doc"
    return "other"


def walk(root):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORE_DIRS)
        for fn in sorted(filenames):
            abs_p = os.path.join(dirpath, fn)
            rel = os.path.relpath(abs_p, root).replace(os.sep, "/")
            out.append((rel, abs_p))
    return out


def is_comment(line):
    s = line.strip()
    return s.startswith(("//", "/*", "*", "#", "<!--", "--"))


def lineno(text, idx):
    return text.count("\n", 0, idx) + 1


def split_top(body):
    parts, depth, cur = [], 0, []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def parse_sql(rel, text, tables, policies, rls):
    clean = re.sub(r"--[^\n]*", lambda m: " " * len(m.group(0)), text)
    for m in re.finditer(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w.\"]+)\s*\(", clean, re.I):
        name = m.group(1).replace('"', "").split(".")[-1]
        i, depth = m.end(), 1
        while i < len(clean) and depth:
            depth += (clean[i] == "(") - (clean[i] == ")")
            i += 1
        cols = []
        for part in split_top(clean[m.end():i - 1]):
            toks = part.strip().split(None, 2)
            if len(toks) < 2 or toks[0].lower() in {"primary", "foreign", "unique", "check", "constraint"}:
                continue
            cols.append({"name": toks[0].strip('"'), "type": toks[1].lower(),
                         "constraints": re.sub(r"\s+", " ", toks[2]).strip() if len(toks) > 2 else ""})
        tables.append({"name": name, "columns": cols, "rls_enabled": False, "policies": [],
                       "file": rel, "line": lineno(clean, m.start())})
    for m in re.finditer(r"alter\s+table\s+(?:only\s+)?([\w.\"]+)\s+enable\s+row\s+level\s+security", clean, re.I):
        rls.add(m.group(1).replace('"', "").split(".")[-1])
    for m in re.finditer(r'create\s+policy\s+"?([^"\n]+?)"?\s+on\s+([\w."]+)(.*?);', clean, re.I | re.S):
        rest = m.group(3)
        f = re.search(r"\bfor\s+(\w+)", rest, re.I)
        u = re.search(r"using\s*\(([^)]*)\)", rest, re.I)
        w = re.search(r"with\s+check\s*\(([^)]*)\)", rest, re.I)
        policies.append({"table": m.group(2).replace('"', "").split(".")[-1], "name": m.group(1),
                         "for": (f.group(1).lower() if f else "all"),
                         "using": (u.group(1).strip() if u else None),
                         "with_check": (w.group(1).strip() if w else None),
                         "file": rel, "line": lineno(clean, m.start())})


def parse_ts_types(rel, text, out):
    for m in re.finditer(r"(?:export\s+)?interface\s+(\w+)\s*\{", text):
        i, depth = m.end(), 1
        while i < len(text) and depth:
            depth += (text[i] == "{") - (text[i] == "}")
            i += 1
        fields = [{"name": a, "type": b.strip()} for a, b in re.findall(r"(\w+)\??\s*:\s*([^;,\n}]+)", text[m.end():i - 1])]
        out.append({"name": m.group(1), "kind": "interface", "fields": fields, "file": rel, "line": lineno(text, m.start())})
    for m in re.finditer(r"(?:export\s+)?type\s+(\w+)\s*=\s*([^;]+);", text):
        vals = re.findall(r"\"([^\"]+)\"|'([^']+)'", m.group(2))
        if vals:
            out.append({"name": m.group(1), "kind": "union", "values": [a or b for a, b in vals],
                        "file": rel, "line": lineno(text, m.start())})


def parse_routes(rel, text, out):
    starts = [m.start() for m in re.finditer(r"<Route\b", text)]
    for n, s in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(text)
        end = min(end, text.find("</Routes>", s) if text.find("</Routes>", s) != -1 else end)
        window = text[s:end]
        p = re.search(r'path="([^"]+)"', window)
        comps = [c for c in re.findall(r"<([A-Z]\w*)", window) if c != "Route"]
        out.append({"path": p.group(1) if p else None, "components": comps, "file": rel, "line": lineno(text, s)})


def parse_html(rel, text, pages, ext_scripts):
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    scripts, inline = [], 0
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", text, re.I | re.S):
        attrs, body = m.group(1), m.group(2)
        src = re.search(r'\bsrc=["\']([^"\']+)["\']', attrs)
        if src:
            scripts.append(src.group(1))
            if re.match(r"https?://|//", src.group(1)):
                ext_scripts.append({"src": src.group(1), "integrity": "integrity=" in attrs.lower(),
                                    "file": rel, "line": lineno(text, m.start())})
        elif body.strip():
            inline += 1
    sheets = []
    for m in re.finditer(r"<link\b([^>]*)>", text, re.I):
        if re.search(r'rel=["\']stylesheet["\']', m.group(1), re.I):
            h = re.search(r'href=["\']([^"\']+)["\']', m.group(1))
            if h:
                sheets.append(h.group(1))
    pages.append({"path": rel, "title": re.sub(r"\s+", " ", title.group(1)).strip() if title else "",
                  "scripts": scripts, "stylesheets": sheets, "inline_script_count": inline})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help="application root folder")
    ap.add_argument("--out", required=True, help="output inventory.json path")
    args = ap.parse_args()
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print("ERROR: root not found: " + root, file=sys.stderr)
        return 2

    files, texts = [], {}
    lang_count = {}
    loc = 0
    for rel, abs_p in walk(root):
        try:
            raw = open(abs_p, "rb").read()
        except OSError:
            continue
        ext = os.path.splitext(rel)[1].lower()
        base = os.path.basename(rel)
        is_text = (ext in TEXT_EXT or base.startswith(".env")) and len(raw) <= MAX_BYTES and b"\x00" not in raw
        txt = raw.decode("utf-8", "replace") if is_text else None
        n_lines = txt.count("\n") + (1 if txt and not txt.endswith("\n") else 0) if txt is not None else 0
        kind = classify(rel)
        files.append({"path": rel, "bytes": len(raw), "sha256": sha256_bytes(raw), "lines": n_lines, "kind": kind})
        if txt is not None:
            texts[rel] = txt
            if kind in {"source", "markup", "style", "sql"}:
                loc += n_lines
                lang_count[ext] = lang_count.get(ext, 0) + 1

    # ---- dependencies / stack ----
    pkg = {}
    if "package.json" in texts:
        try:
            pkg = json.loads(texts["package.json"])
        except ValueError:
            pkg = {}
    runtime, dev = pkg.get("dependencies", {}), pkg.get("devDependencies", {})
    alldeps = dict(runtime)
    alldeps.update(dev)
    lock = any(os.path.basename(f["path"]) in LOCKFILES for f in files)

    pages, ext_scripts = [], []
    for rel, txt in texts.items():
        if rel.lower().endswith((".html", ".htm")):
            parse_html(rel, txt, pages, ext_scripts)

    fw, backend, origin = [], [], []
    for dep, label in [("react", "React"), ("vue", "Vue"), ("svelte", "Svelte"), ("next", "Next.js"), ("vite", "Vite"),
                       ("tailwindcss", "Tailwind CSS"), ("react-router-dom", "React Router"),
                       ("@tanstack/react-query", "TanStack Query"), ("typescript", "TypeScript"),
                       ("lucide-react", "lucide-react icons")]:
        if dep in alldeps:
            fw.append(label)
    if any("components.json" == f["path"] for f in files):
        fw.append("shadcn/ui")
    if "@supabase/supabase-js" in alldeps or any("supabase" in t for r, t in texts.items() if r.endswith(tuple(CODE_EXT))):
        backend.append("Supabase")
    if any(re.search(r"jquery", s["src"], re.I) for s in ext_scripts):
        fw.append("jQuery (CDN)")
    if "lovable-tagger" in alldeps or any("gptengineer" in s["src"] for s in ext_scripts) or \
            re.search(r"lovable", texts.get("README.md", ""), re.I):
        origin.append("lovable")
    html_n = len(pages)
    if pkg:
        root_type = "node-app"
    elif html_n > 1:
        root_type = "static-multipage"
    elif html_n == 1:
        root_type = "single-file-html"
    else:
        root_type = "unknown"
    if root_type in {"static-multipage", "single-file-html"} and not fw:
        fw.append("vanilla JS")

    # ---- constant strings (to resolve storage keys) ----
    const_str = {}
    for rel, txt in texts.items():
        if rel.endswith(tuple(CODE_EXT | {".html", ".htm"})):
            for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*[\"']([^\"']*)[\"']", txt):
                const_str.setdefault(m.group(1), m.group(2))

    # ---- per-file extraction ----
    routes, tables, policies, rls, ts_types = [], [], [], set(), []
    sb_used, http_calls, url_lits, clients = [], [], [], []
    storage, env_ref, env_def = [], [], []
    auth, consts, funcs, comments = [], [], [], []
    for rel, txt in texts.items():
        ext = os.path.splitext(rel)[1].lower()
        base = os.path.basename(rel)
        lines = txt.splitlines()
        if base.startswith(".env"):
            names = sorted(set(re.findall(r"^\s*([A-Za-z_]\w*)\s*=", txt, re.M)))
            env_def.append({"file": rel, "names": names})
            continue
        if ext == ".sql":
            parse_sql(rel, txt, tables, policies, rls)
            continue
        if ext not in CODE_EXT and ext not in {".html", ".htm"}:
            continue
        if ext in {".ts", ".tsx"}:
            parse_ts_types(rel, txt, ts_types)
        if ext in {".tsx", ".jsx", ".js"} and "<Route" in txt:
            parse_routes(rel, txt, routes)
        for m in re.finditer(r"""\.from\(\s*["'](\w+)["']\s*\)""", txt):
            sb_used.append({"table": m.group(1), "file": rel, "line": lineno(txt, m.start())})
        for m in re.finditer(r"createClient\(", txt):
            clients.append({"kind": "createClient", "file": rel, "line": lineno(txt, m.start())})
        for i, line in enumerate(lines, 1):
            for m in re.finditer(r"""fetch\(\s*([`"'])(.*?)\1""", line):
                http_calls.append({"kind": "fetch", "url": redact(m.group(2)), "file": rel, "line": i})
            for m in re.finditer(r"XMLHttpRequest|\$\.(?:ajax|get|post)\(|axios\.", line):
                http_calls.append({"kind": m.group(0), "url": "", "file": rel, "line": i})
            for m in re.finditer(r"https?://[^\s\"'`<>)]+", line):
                u = m.group(0).rstrip(".,;")
                if re.search(r"w3\.org|schema\.org|ui\.shadcn\.com|lovable\.dev/projects", u):
                    continue
                url_lits.append({"url": redact(u), "file": rel, "line": i, "in_comment": is_comment(line)})
            for m in re.finditer(r"(localStorage|sessionStorage)\.(getItem|setItem|removeItem|clear)\(\s*([^,)]*)", line):
                k = m.group(3).strip()
                if k and k[0] in "\"'`":
                    key = k.strip("\"'`")
                else:
                    key = const_str.get(k, "<dynamic:%s>" % k) if k else "*"
                storage.append({"api": m.group(1), "op": m.group(2), "key": key, "file": rel, "line": i})
            for m in re.finditer(r"import\.meta\.env\.(\w+)|process\.env\.(\w+)", line):
                env_ref.append({"name": m.group(1) or m.group(2), "file": rel, "line": i})
            for m in re.finditer(r"supabase\w*\.auth\.(\w+)", line):
                auth.append({"signal": "supabase-auth", "detail": m.group(1), "file": rel, "line": i})
            if re.search(r"(?:function\s+login\b|\blogin\s*[:=]\s*(?:async\s*)?\()", line):
                auth.append({"signal": "login-function", "detail": "defines login()", "file": rel, "line": i})
            m = re.search(r"(?:localStorage|sessionStorage)\.(?:get|set)Item\(\s*[\"']role[\"']", line)
            if m:
                auth.append({"signal": "client-stored-role", "detail": "role kept in browser storage", "file": rel, "line": i})
            for m in re.finditer(r"""\brole\s*(===?|!==?)\s*["'](\w+)["']""", line):
                auth.append({"signal": "role-check", "detail": "role %s %s" % (m.group(1), m.group(2)), "file": rel, "line": i})
            if re.search(r"<Navigate\b", line):
                auth.append({"signal": "route-guard", "detail": redact(line.strip())[:120], "file": rel, "line": i})
            if re.search(r"requireLogin\s*\(\s*\)\s*;?\s*\}?", line) and "function" not in line:
                auth.append({"signal": "page-guard", "detail": "requireLogin() on page", "file": rel, "line": i})
            for m in re.finditer(r"\bfunction\s+(\w+)\s*\(", line):
                funcs.append({"name": m.group(1), "file": rel, "line": i})
            m = re.match(r"\s*(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*(?::\s*[\w<>\[\]| ]+)?\s*=>", line)
            if m:
                funcs.append({"name": m.group(1), "file": rel, "line": i})
            m = re.match(r"\s*(?:export\s+)?(?:const|let|var)\s+([A-Z][A-Z0-9_]{2,})\b[^=]*=\s*(.*)$", line)
            if m and not is_comment(line):
                val = m.group(2).strip()
                if not val and i < len(lines):
                    val = lines[i].strip()
                if val.endswith(("{", "[", "(")):
                    j, buf = i, [val]
                    while j < len(lines) and len(buf) < 9:
                        buf.append(lines[j].strip())
                        if re.match(r"^[\]})]+;?,?$", lines[j].strip()):
                            break
                        j += 1
                    val = " ".join(buf)
                val = re.sub(r"\s+", " ", redact(val))
                if SECRET_NAME.search(m.group(1)) and not NOT_SECRET_NAME.search(m.group(1)) \
                        and re.search(r"[\"'][^\"']{4,}[\"']", val):
                    val = "[REDACTED]"
                val = val.rstrip(";").rstrip()
                consts.append({"name": m.group(1), "file": rel, "line": i, "value_preview": val[:160]})
            m = re.search(r"\b(TODO|FIXME|HACK|XXX)\b:?\s*(.*)", line)
            if m:
                comments.append({"tag": m.group(1), "text": redact(m.group(2).strip())[:160], "file": rel, "line": i})
    # de-dup helpers
    http_calls = [dict(t) for t in {tuple(sorted(d.items())) for d in http_calls}]
    http_calls.sort(key=lambda d: (d["file"], d["line"]))

    tbl_by = {t["name"]: t for t in tables}
    for t in tables:
        t["rls_enabled"] = t["name"] in rls
    for p in policies:
        if p["table"] in tbl_by:
            tbl_by[p["table"]]["policies"].append({k: p[k] for k in ("name", "for", "using", "with_check")})

    legacy = sorted(f["path"] for f in files
                    if re.search(r"(?i)(^|[/_.-])(old|legacy|backup|deprecated|copy|temp|tmp)([/_.-]|$)", f["path"]))

    env_names_ref = sorted({e["name"] for e in env_ref})
    inv = {
        "schema_version": "1.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": {"name": pkg.get("name") or os.path.basename(root), "root_type": root_type, "origin": origin,
                    "file_count": len(files), "loc": loc},
        "stack": {"languages": dict(sorted(lang_count.items())), "frameworks": fw, "backend_services": backend},
        "dependencies": {"manifest": "package.json" if pkg else None, "runtime": runtime, "dev": dev,
                         "lockfile_present": lock},
        "files": files,
        "entry_points": {"html_pages": sorted(pages, key=lambda p: p["path"]), "routes": routes},
        "data_model": {"sql_tables": tables, "ts_types": ts_types, "supabase_tables_used": sb_used},
        "integrations": {"http_calls": http_calls, "url_literals": url_lits, "clients": clients,
                         "external_scripts": ext_scripts},
        "storage": {"browser": storage},
        "env_vars": {"referenced": env_ref, "defined_in": env_def},
        "auth_signals": auth,
        "constants": consts,
        "functions": funcs,
        "comments": comments,
        "legacy_candidates": legacy,
        "summary": {
            "html_pages": len(pages), "routes": len([r for r in routes if r["path"]]), "sql_tables": len(tables),
            "ts_types": len(ts_types), "http_calls": len(http_calls), "external_scripts": len(ext_scripts),
            "browser_storage_keys": len({s["key"] for s in storage}), "env_vars_referenced": len(env_names_ref),
            "env_files": len(env_def), "auth_signals": len(auth), "constants": len(consts), "functions": len(funcs),
            "todo_comments": len(comments), "lockfile_present": lock,
        },
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(inv, f, indent=2)
        f.write("\n")
    s = inv["summary"]
    print("inventory: %s | %s | %d files, %d LOC | pages=%d routes=%d tables=%d storage_keys=%d auth_signals=%d -> %s" % (
        inv["project"]["name"], root_type, len(files), loc, s["html_pages"], s["routes"], s["sql_tables"],
        s["browser_storage_keys"], s["auth_signals"], args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
