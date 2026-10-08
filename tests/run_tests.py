#!/usr/bin/env python3
"""Toolkit test suite. Run: python3 tests/run_tests.py   (standard library only, no network)."""
import ast
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import warnings

warnings.simplefilter("ignore")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SK = os.path.join(ROOT, "skills")
SAMPLES = os.path.join(ROOT, "evals", "samples")
EXPECTED = os.path.join(ROOT, "evals", "expected")
EX = os.path.join(ROOT, "examples", "wire-approval-queue")
SAMPLE_NAMES = ["lovable-commercial-loan-desk", "html-kyc-onboarding-desk", "html-wire-approval-queue", "html-leave-request-tracker"]


def run(args, stdin=None, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    p = subprocess.run([sys.executable] + args, input=stdin, capture_output=True, text=True, env=e, cwd=ROOT)
    return p.returncode, p.stdout + p.stderr


def script(skill, name):
    return os.path.join(SK, skill, "scripts", name)


class Repo(unittest.TestCase):
    def test_shared_validator_in_sync(self):
        rc, out = run([os.path.join(ROOT, "tools", "sync_shared.py"), "--check"])
        self.assertEqual(rc, 0, out)

    def test_skill_frontmatter_and_size(self):
        names = sorted(d for d in os.listdir(SK) if os.path.isdir(os.path.join(SK, d)))
        self.assertEqual(len(names), 16)
        for n in names:
            txt = open(os.path.join(SK, n, "SKILL.md"), encoding="utf-8").read()
            m = re.match(r"^---\nname: (.+)\ndescription: (.+)\n---\n", txt)
            self.assertIsNotNone(m, n + ": frontmatter")
            self.assertEqual(m.group(1), n)
            fm = txt.split("---\n")[1]
            self.assertEqual(sorted(re.findall(r"(?m)^([\w\-]+):", fm)), ["description", "name"], n + ": front-matter must use only name and description")
            self.assertLessEqual(len(m.group(2)), 1024, n + ": description too long")
            self.assertLess(txt.count("\n"), 500, n + ": SKILL.md too long")
            for ref in re.findall(r"`((?:references|assets|scripts)/[\w./\-]+)`", txt):
                if "<" in ref:
                    continue
                self.assertTrue(os.path.exists(os.path.join(SK, n, ref)), "%s references missing %s" % (n, ref))

    def test_skills_and_agents_are_model_agnostic(self):
        banned = re.compile(r"\b(Claude|Anthropic|GPT|ChatGPT|OpenAI|Gemini|Sonnet|Opus|Haiku|Copilot)\b")
        paths = glob.glob(os.path.join(ROOT, "skills", "**", "*.md"), recursive=True) + glob.glob(os.path.join(ROOT, "agents", "*.md")) + \
            glob.glob(os.path.join(ROOT, "skills", "**", "*.py"), recursive=True) + glob.glob(os.path.join(ROOT, "skills", "**", "*.tpl"), recursive=True)
        bad = []
        for p in paths:
            for i, line in enumerate(open(p, encoding="utf-8"), 1):
                if banned.search(line):
                    bad.append("%s:%d" % (os.path.relpath(p, ROOT), i))
        self.assertEqual(bad, [], "model names in portable files")
        for p in glob.glob(os.path.join(ROOT, "agents", "*.md")):
            fm = open(p, encoding="utf-8").read().split("---\n")[1]
            self.assertEqual(sorted(re.findall(r"(?m)^([\w\-]+):", fm)), ["description", "name"], p + ": agents carry no model or tool settings")
        self.assertTrue(os.path.exists(os.path.join(ROOT, "AGENTS.md")))

    def test_scripts_are_stdlib_only_and_have_help(self):
        std = getattr(sys, "stdlib_module_names", None)
        for p in glob.glob(os.path.join(ROOT, "skills", "*", "scripts", "*.py")) + glob.glob(os.path.join(ROOT, "hooks", "*.py")):
            tree = ast.parse(open(p, encoding="utf-8").read())
            mods = set()
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    mods |= {a.name.split(".")[0] for a in n.names}
                elif isinstance(n, ast.ImportFrom) and n.level == 0:
                    mods.add(n.module.split(".")[0])
            local = {"validate_json", "pack_loader", "ui_snapshot_static"}
            optional_third_party = {"playwright"}
            if std:
                self.assertFalse(mods - set(std) - local - optional_third_party, "%s imports non-stdlib: %s" % (p, mods - set(std) - local))
            if os.path.basename(p) not in ("validate_json.py", "guard.py"):
                rc, out = run([p, "--help"])
                self.assertEqual(rc, 0, p + "\n" + out)

    def test_packs_valid_rendered_and_consistent(self):
        sk = os.path.join(SK, "standards-gap-analysis")
        sys.path.insert(0, os.path.join(sk, "scripts"))
        import pack_loader
        scan_src = open(script("standards-gap-analysis", "scan.py")).read()
        emitted = set(re.findall(r'bag\.add\("(R-[A-Z]+-\d{3})"', scan_src))
        for pk in ("general", "financial-services"):
            rc, msg = run([script("standards-gap-analysis", "render_standards.py"), "--pack", pk, "--check"])
            self.assertEqual(rc, 0, msg)
            p = pack_loader.load(pk)
            self.assertEqual(pack_loader.problems(p), [])
            mapped = set(pack_loader.rule_map(p))
            self.assertEqual(emitted - mapped, set(), "%s: scanner rules no control claims" % pk)
            self.assertEqual(mapped - emitted, set(), "%s: controls name rules the scanner never emits" % pk)

    def test_core_is_sector_neutral(self):
        pat = re.compile(r"\b(bank|banks|banking|OFAC|PCI DSS|SOX|AML)\b", re.I)
        offenders = []
        roots = [os.path.join(SK, d) for d in os.listdir(SK)]
        for r in roots:
            for dp, dn, fn in os.walk(r):
                if os.path.join("standards-gap-analysis", "packs", "financial-services") in dp:
                    continue
                for f in fn:
                    if f.endswith((".md", ".json", ".py", ".yml", ".sh")):
                        p = os.path.join(dp, f)
                        for i, line in enumerate(open(p, encoding="utf-8"), 1):
                            if pat.search(line) and "scan.py" not in p:
                                offenders.append("%s:%d" % (os.path.relpath(p, ROOT), i))
        for f in ("README.md", "CLAUDE.md", os.path.join("agents", "security-reviewer.md"), os.path.join(".claude-plugin", "plugin.json")):
            p = os.path.join(ROOT, f)
            for i, line in enumerate(open(p, encoding="utf-8"), 1):
                if re.search(r"\b(bank|banks)\b", line, re.I) and "financial" not in line.lower():
                    offenders.append("%s:%d" % (f, i))
        self.assertEqual(offenders, [], "sector-specific wording in core files")


class Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.out = {}
        for s in SAMPLE_NAMES:
            inv = os.path.join(cls.tmp, s + ".inventory.json")
            fnd = os.path.join(cls.tmp, s + ".findings.json")
            rc, m = run([script("app-inventory", "inventory.py"), "--root", os.path.join(SAMPLES, s), "--out", inv])
            assert rc == 0, m
            rc, m = run([script("standards-gap-analysis", "scan.py"), "--root", os.path.join(SAMPLES, s), "--inventory", inv, "--out", fnd])
            assert rc == 0, m
            cls.out[s] = (inv, fnd)
        cls.fin = {}
        for s in ("html-kyc-onboarding-desk", "html-wire-approval-queue"):
            f2 = os.path.join(cls.tmp, s + ".fin.json")
            rc, m = run([script("standards-gap-analysis", "scan.py"), "--root", os.path.join(SAMPLES, s), "--inventory", cls.out[s][0],
                         "--pack", "financial-services", "--out", f2])
            assert rc == 0, m
            cls.fin[s] = f2

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_outputs_match_schemas(self):
        for s, (inv, fnd) in self.out.items():
            rc, m = run([script("app-inventory", "validate_json.py"), os.path.join(SK, "app-inventory", "assets", "inventory.schema.json"), inv])
            self.assertEqual(rc, 0, s + m)
            rc, m = run([script("standards-gap-analysis", "validate_json.py"), os.path.join(SK, "standards-gap-analysis", "assets", "findings.schema.json"), fnd])
            self.assertEqual(rc, 0, s + m)

    def test_project_types_detected(self):
        want = {"lovable-commercial-loan-desk": "node-app", "html-kyc-onboarding-desk": "static-multipage",
                "html-wire-approval-queue": "single-file-html", "html-leave-request-tracker": "single-file-html"}
        for s, (inv, _) in self.out.items():
            d = json.load(open(inv))
            self.assertEqual(d["project"]["root_type"], want[s])
        self.assertIn("lovable", json.load(open(self.out["lovable-commercial-loan-desk"][0]))["project"]["origin"])

    def test_inventory_key_facts(self):
        d = json.load(open(self.out["lovable-commercial-loan-desk"][0]))
        self.assertEqual({r["path"] for r in d["entry_points"]["routes"] if r["path"]}, {"/login", "/", "/new", "/applications/:id", "/admin"})
        names = {t["name"]: t for t in d["data_model"]["sql_tables"]}
        self.assertEqual(set(names), {"profiles", "loan_applications"})
        self.assertEqual(names["loan_applications"]["policies"][0]["using"], "true")
        consts = {c["name"] for c in d["constants"]}
        self.assertTrue({"MIN_DSCR", "LTV_LIMITS", "BLOCKED_INDUSTRIES", "RATE_BY_RATING"} <= consts)
        k = json.load(open(self.out["html-kyc-onboarding-desk"][0]))
        self.assertIn("kyc_cases", {x["key"] for x in k["storage"]["browser"]})
        self.assertEqual(len(k["entry_points"]["html_pages"]), 7)
        self.assertIn("old-dashboard.html", k["legacy_candidates"])

    def test_no_secret_values_in_outputs(self):
        secrets = json.load(open(os.path.join(EXPECTED, "secret_strings.json")))["secrets"]
        for s, paths in self.out.items():
            for p in paths:
                blob = open(p).read()
                for sec in secrets:
                    self.assertFalse(sec in blob, "secret string %r leaked in %s" % (sec[:3] + "...", os.path.basename(p)))

    def test_scan_finds_every_static_defect_in_answer_keys(self):
        exp = json.load(open(os.path.join(EXPECTED, "static_expectations.json")))["expectations"]
        missing = []
        for e in exp:
            fnd = json.load(open(self.out[e["sample"]][1]))["findings"]
            if not any(f["rule_id"] == e["rule_id"] and e["file_contains"] in f["file"] for f in fnd):
                missing.append("%s %s %s (%s)" % (e["sample"], e["rule_id"], e["file_contains"], e["answer_key"]))
        self.assertEqual(missing, [], "scanner recall gap")

    def test_pack_changes_control_mapping_and_severity(self):
        gen = json.load(open(self.out["html-kyc-onboarding-desk"][1]))["findings"]
        fin = json.load(open(self.fin["html-kyc-onboarding-desk"]))["findings"]
        g_scr = [f for f in gen if f["rule_id"] == "R-SCR-001"]
        f_scr = [f for f in fin if f["rule_id"] == "R-SCR-001"]
        self.assertTrue(g_scr and f_scr)
        self.assertEqual({f["control_id"] for f in g_scr}, {"COM-03"})
        self.assertEqual({f["control_id"] for f in f_scr}, {"FIN-01"})
        self.assertEqual({f["severity"] for f in g_scr}, {"Medium"})
        self.assertEqual({f["severity"] for f in f_scr}, {"High"})
        wg = json.load(open(self.out["html-wire-approval-queue"][1]))
        wf = json.load(open(self.fin["html-wire-approval-queue"]))
        sev = lambda d: [f["severity"] for f in d["findings"] if f["rule_id"] == "R-COM-001"][0]
        self.assertEqual((sev(wg), sev(wf)), ("Medium", "High"))
        self.assertEqual(wf["standard"]["extends"], ["general"])
        qg = {q["control_id"] for q in wg["llm_review_queue"]}
        qf = {q["control_id"] for q in wf["llm_review_queue"]}
        self.assertTrue({"FIN-02", "FIN-03"} <= qf - qg)

    def test_financial_overlay_merge(self):
        sys.path.insert(0, os.path.join(SK, "standards-gap-analysis", "scripts"))
        import pack_loader
        g, f = pack_loader.load("general"), pack_loader.load("financial-services")
        gc = {c["id"]: c for c in g["controls"]}
        fc = {c["id"]: c for c in f["controls"]}
        self.assertEqual((gc["COM-01"]["severity"], fc["COM-01"]["severity"]), ("High", "Critical"))
        self.assertTrue({"FIN-01", "FIN-02", "FIN-03", "FIN-04"} <= set(fc) - set(gc))
        self.assertEqual(fc["IAM-02"], gc["IAM-02"])
        self.assertNotIn("FIN", [d["id"] for d in g["domains"]])
        self.assertTrue(any(r["domains"] and "COM" in r["domains"] for r in f["release_gates"][1]["blocking_rules"]))

    def test_non_financial_sample_uses_neutral_pack_only(self):
        s = "html-leave-request-tracker"
        d = json.load(open(self.out[s][1]))
        self.assertEqual(d["standard"]["id"], "general")
        blob = json.dumps(d).lower()
        for w in ("bank", "sanction", "ofac", "loan", "wire"):
            self.assertNotIn(w, blob)
        self.assertEqual(d["summary"]["unmapped_rules"], {})

    def test_unknown_pack_fails_cleanly(self):
        rc, m = run([script("standards-gap-analysis", "scan.py"), "--root", os.path.join(SAMPLES, "html-wire-approval-queue"),
                     "--pack", "no-such-pack", "--out", os.path.join(self.tmp, "x.json")])
        self.assertNotEqual(rc, 0)
        self.assertIn("pack not found", m)

    def test_unmapped_rules_are_reported_not_dropped(self):
        pk = os.path.join(self.tmp, "mini")
        os.makedirs(pk)
        base = json.load(open(os.path.join(SK, "standards-gap-analysis", "packs", "general", "controls.json")))
        base["pack_id"] = "mini"
        for c in base["controls"]:
            c["scanner_rules"] = [r for r in c["scanner_rules"] if r != "R-AUD-001"]
        json.dump(base, open(os.path.join(pk, "controls.json"), "w"))
        out = os.path.join(self.tmp, "mini.json")
        rc, m = run([script("standards-gap-analysis", "scan.py"), "--root", os.path.join(SAMPLES, "html-wire-approval-queue"), "--pack", pk, "--out", out])
        self.assertEqual(rc, 0, m)
        d = json.load(open(out))
        self.assertIn("R-AUD-001", d["summary"]["unmapped_rules"])
        self.assertFalse([f for f in d["findings"] if f["rule_id"] == "R-AUD-001"])

    def test_scan_is_quiet_on_clean_code(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "tests"))
            open(os.path.join(t, "index.html"), "w").write("<html><title>x</title><body><p>hello</p></body></html>")
            open(os.path.join(t, "tests", "a.test.js"), "w").write("// audit trail test\n")
            out = os.path.join(t, "f.json")
            rc, m = run([script("standards-gap-analysis", "scan.py"), "--root", t, "--out", out])
            self.assertEqual(rc, 0, m)
            self.assertEqual(json.load(open(out))["summary"]["total"], 0)

    def test_inventory_is_deterministic(self):
        outs = []
        for i in range(2):
            p = os.path.join(self.tmp, "det%d.json" % i)
            run([script("app-inventory", "inventory.py"), "--root", os.path.join(SAMPLES, "html-kyc-onboarding-desk"), "--out", p])
            d = json.load(open(p))
            d.pop("generated_at")
            outs.append(d)
        self.assertEqual(outs[0], outs[1])

    def test_review_queue_has_candidates(self):
        q = json.load(open(self.out["html-kyc-onboarding-desk"][1]))["llm_review_queue"]
        by = {x["control_id"]: x for x in q}
        self.assertTrue(any("approve" in c.lower() for c in by["COM-01"]["candidates"]))
        self.assertTrue(any("scoreCase" in c or "recalcRisk" in c for c in by["COM-04"]["candidates"]))


class WorkedExample(unittest.TestCase):
    H = os.path.join(EX, "handoff")
    APP = os.path.join(EX, "app")

    def test_chain_checks_pass(self):
        rc, m = run([script("app-spec-extract", "spec_lint.py"), "--spec-dir", os.path.join(self.H, "spec"), "--root", self.APP, "--strict"])
        self.assertEqual(rc, 0, m)
        rc, m = run([script("spec-drift-check", "drift_check.py"), "--root", self.APP, "--manifest", os.path.join(self.H, "spec", ".manifest.json"), "--fail-on", "warn"])
        self.assertEqual(rc, 0, m)
        rc, m = run([script("spec-reconcile", "check_reconciliation.py"), "--reconciliation", os.path.join(self.H, "reconciliation.md"),
                     "--spec-dir", os.path.join(self.H, "spec"), "--intake", os.path.join(self.H, "intake.md")])
        self.assertEqual(rc, 0, m)
        with tempfile.TemporaryDirectory() as t:
            rc, m = run([script("standards-gap-analysis", "gaps_report.py"), "--gaps", os.path.join(self.H, "gaps.json"), "--out", os.path.join(t, "g.md")])
            self.assertEqual(rc, 0, m)
            rc, m = run([script("hardening-backlog", "backlog_check_render.py"), "--backlog", os.path.join(self.H, "backlog.json"), "--findings", os.path.join(self.H, "gaps.json")])
            self.assertEqual(rc, 0, m)
        rc, m = run([script("app-handoff", "status.py"), "--handoff", self.H])
        self.assertRegex(m, r"as-built spec\s+(done|stale)")
        self.assertIn("Next:", m)

    def test_drift_detects_threshold_change_and_fixes_moves(self):
        with tempfile.TemporaryDirectory() as t:
            shutil.copytree(EX, os.path.join(t, "w"))
            app = os.path.join(t, "w", "app", "wire-approval-queue.html")
            man = os.path.join(t, "w", "handoff", "spec", ".manifest.json")
            lines = open(app).read().split("\n")
            txt = "\n".join(["<!-- a -->", "<!-- b -->"] + lines).replace("DUAL_APPROVAL_LIMIT = 100000", "DUAL_APPROVAL_LIMIT = 250000")
            open(app, "w").write(txt)
            rc, m = run([script("spec-drift-check", "drift_check.py"), "--root", os.path.join(t, "w", "app"), "--manifest", man])
            self.assertEqual(rc, 1, m)
            self.assertIn("BR-003", m)
            self.assertIn("250000", m)
            rc, m = run([script("spec-drift-check", "drift_check.py"), "--root", os.path.join(t, "w", "app"), "--manifest", man, "--fix-moves"])
            rc, m = run([script("spec-drift-check", "drift_check.py"), "--root", os.path.join(t, "w", "app"), "--manifest", man, "--format", "json"])
            d = json.loads(m)
            self.assertEqual(d["summary"]["moved"], 0)
            self.assertEqual(sorted(d["summary"]["stale_statements"]), ["BR-002", "BR-003", "QK-003"])

    def test_lint_rejects_uncited_and_invented_numbers(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "spec"))
            open(os.path.join(t, "spec", "02-business-rules.md"), "w").write(
                "- **BR-001** Wires above 55,000 need two approvals. [wire-approval-queue.html:50]\n- **BR-002** Nothing cited.\n")
            rc, m = run([script("app-spec-extract", "spec_lint.py"), "--spec-dir", os.path.join(t, "spec"), "--root", self.APP])
            self.assertEqual(rc, 1)
            self.assertIn("no evidence", m)
            self.assertIn("55,000", m)

    def test_backlog_checker_flags_uncovered_finding(self):
        with tempfile.TemporaryDirectory() as t:
            b = json.load(open(os.path.join(self.H, "backlog.json")))
            b["epics"][0]["stories"] = [s for s in b["epics"][0]["stories"] if s["id"] != "S-002"]
            p = os.path.join(t, "b.json")
            json.dump(b, open(p, "w"))
            rc, m = run([script("hardening-backlog", "backlog_check_render.py"), "--backlog", p, "--findings", os.path.join(self.H, "gaps.json")])
            self.assertEqual(rc, 1)
            self.assertIn("F-001", m)


def has_jdk_compiler():
    try:
        r = subprocess.run(["java", "--list-modules"], capture_output=True, text=True)
        return r.returncode == 0 and "jdk.compiler" in r.stdout
    except OSError:
        return False


EXAMPLE_LEAVE = os.path.join(ROOT, "examples", "leave-request")
MODEL_EX = os.path.join(SK, "data-model-design", "assets", "examples", "leave-request.data-model.json")


class CodebaseGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.g = {}
        targets = dict((n, os.path.join(SAMPLES, n)) for n in SAMPLE_NAMES)
        targets["leave-service"] = os.path.join(EXAMPLE_LEAVE, "services", "leave-service")
        for n, root in targets.items():
            out = os.path.join(cls.tmp, n + ".json")
            rc, m = run([script("codebase-graph", "graph_build.py"), "--root", root, "--out", out])
            assert rc == 0, m
            cls.g[n] = (root, out, json.load(open(out)))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def links(self, name, ltype):
        g = self.g[name][2]
        N = {n["id"]: n for n in g["nodes"]}
        return [(N[l["source"]], N[l["target"]], l) for l in g["links"] if l["type"] == ltype]

    def test_every_graph_passes_the_checker(self):
        for n, (root, out, g) in self.g.items():
            rc, m = run([script("codebase-graph", "graph_check.py"), "--graph", out, "--root", root])
            self.assertEqual(rc, 0, n + "\n" + m)

    def test_react_routes_data_access_and_alias_imports(self):
        routes = {t["name"] for _, t, _ in self.links("lovable-commercial-loan-desk", "exposes") if t["type"] == "function"} | \
                 {s["name"] for s, _, _ in self.links("lovable-commercial-loan-desk", "exposes") if s["type"] == "endpoint"}
        self.assertTrue({"ROUTE /login", "ROUTE /new", "ROUTE /applications/:id", "ROUTE /admin"} <= routes)
        writes = {(s["name"], t["name"]) for s, t, _ in self.links("lovable-commercial-loan-desk", "writes")}
        self.assertIn(("saveApplication", "loan_applications"), writes)
        self.assertIn(("updateStatus", "loan_applications"), writes)
        calls = {(s["name"], t["name"], l["confidence"]) for s, t, l in self.links("lovable-commercial-loan-desk", "calls")}
        self.assertIn(("save", "saveApplication", "INFERRED"), calls)
        imports = {(s["name"], t["name"]) for s, t, _ in self.links("lovable-commercial-loan-desk", "imports")}
        self.assertIn(("NewApplication.tsx", "api.ts"), imports)
        ext = {n["name"] for n in self.g["lovable-commercial-loan-desk"][2]["nodes"] if n["type"] == "external"}
        self.assertTrue({"react", "@supabase/supabase-js"} <= ext)

    def test_html_pages_resolve_calls_across_scripts(self):
        calls = {(s["name"], t["name"]) for s, t, _ in self.links("html-kyc-onboarding-desk", "calls")}
        self.assertIn(("submitCase", "scoreCase"), calls)
        self.assertIn(("submitCase", "screenName"), calls)
        loads = {(s["name"], t["name"]) for s, t, _ in self.links("html-kyc-onboarding-desk", "loads")}
        self.assertIn(("new-case.html", "risk.js"), loads)
        stores = {n["name"] for n in self.g["html-kyc-onboarding-desk"][2]["nodes"] if n["type"] == "datastore"}
        self.assertIn("kyc_cases", stores)

    def test_similar_lists_find_the_diverging_country_lists(self):
        sim = self.g["html-kyc-onboarding-desk"][2]["analysis"]["similar_lists"]
        over = [x for x in sim if x["kind"] == "overlapping"]
        self.assertTrue(over)
        self.assertEqual(sorted(over[0]["only_in_first"] + over[0]["only_in_second"]), ["RU", "VE"])

    def test_java_graph_has_endpoints_repositories_entities_and_tables(self):
        self.assertEqual(len(self.links("leave-service", "maps_to")), 6)
        self.assertEqual(len(self.links("leave-service", "manages")), 6)
        eps = {s["name"] for s, _, _ in self.links("leave-service", "exposes") if s["type"] == "endpoint"}
        self.assertIn("POST /api/v1/leave-requests", eps)
        calls = {(s["name"], t["name"]) for s, t, _ in self.links("leave-service", "calls")}
        self.assertIn(("create", "create"), calls)
        uses = {(s["name"], t["name"]) for s, t, _ in self.links("leave-service", "uses")}
        self.assertIn(("LeaveRequestService", "LeaveRequestRepository"), uses)
        layers = self.g["leave-service"][2]["analysis"]["layers"]
        self.assertTrue({"api", "service", "data"} <= set(layers))

    def test_no_secret_values_in_graph_outputs(self):
        secrets = json.load(open(os.path.join(EXPECTED, "secret_strings.json")))["secrets"]
        for n, (root, out, g) in self.g.items():
            blob = open(out).read()
            for sec in secrets:
                self.assertFalse(sec in blob, "secret leaked into graph of " + n)

    def test_build_is_deterministic(self):
        root = os.path.join(SAMPLES, "html-kyc-onboarding-desk")
        outs = []
        for i in range(2):
            p = os.path.join(self.tmp, "det%d.json" % i)
            run([script("codebase-graph", "graph_build.py"), "--root", root, "--out", p])
            d = json.load(open(p))
            d.pop("generated_at")
            outs.append(d)
        self.assertEqual(outs[0], outs[1])

    def test_query_impact_path_and_ambiguity(self):
        out = self.g["lovable-commercial-loan-desk"][1]
        rc, m = run([script("codebase-graph", "graph_query.py"), "--graph", out, "impact", "fn:src/lib/scoring.ts#evaluate"])
        self.assertEqual(rc, 0, m)
        self.assertIn("NewApplication", m)
        rc, m = run([script("codebase-graph", "graph_query.py"), "--graph", out, "path", "NewApplication", "scoring.ts"])
        self.assertEqual(rc, 0, m)
        rc, m = run([script("codebase-graph", "graph_query.py"), "--graph", out, "node", "a"])
        self.assertEqual(rc, 1)
        self.assertIn("ambiguous", m)
        rc, m = run([script("codebase-graph", "graph_query.py"), "--graph", self.g["leave-service"][1], "datastore", "leave_request"])
        self.assertIn("through repository LeaveRequestRepository", m)

    def test_enrichment_applies_rejects_secrets_and_survives_rebuild(self):
        root, out, _ = self.g["html-wire-approval-queue"]
        g1 = os.path.join(self.tmp, "wire.json")
        shutil.copyfile(out, g1)
        nid = [n["id"] for n in json.load(open(g1))["nodes"] if n["name"] == "approve"][0]
        bad = os.path.join(self.tmp, "bad.json")
        json.dump({"summaries": {nid: "uses token = \"abcd1234efgh\" to approve"}}, open(bad, "w"))
        rc, m = run([script("codebase-graph", "graph_enrich.py"), "--graph", g1, "--enrichment", bad])
        self.assertEqual(rc, 1, m)
        self.assertEqual(json.load(open(g1))["nodes"][0]["summary"], "")
        good = os.path.join(self.tmp, "good.json")
        json.dump({"summaries": {nid: "Approves a wire after asking for a shared code."},
                   "concepts": [{"id": "concept:approval", "name": "Approval", "description": "Where a wire becomes released.", "nodes": [nid, "fn:gone#x"]}],
                   "tours": []}, open(good, "w"))
        rc, m = run([script("codebase-graph", "graph_enrich.py"), "--graph", g1, "--enrichment", good])
        self.assertEqual(rc, 0, m)
        self.assertIn("stale", m)
        d = json.load(open(g1))
        self.assertEqual([n["summary"] for n in d["nodes"] if n["id"] == nid], ["Approves a wire after asking for a shared code."])
        rc, m = run([script("codebase-graph", "graph_check.py"), "--graph", g1, "--root", root])
        self.assertEqual(rc, 0, m)

    def test_exports_are_valid_files(self):
        import xml.dom.minidom
        out = self.g["lovable-commercial-loan-desk"][1]
        d = os.path.join(self.tmp, "exp")
        rc, m = run([script("codebase-graph", "graph_export.py"), "--graph", out, "--out-dir", d])
        self.assertEqual(rc, 0, m)
        xml.dom.minidom.parse(os.path.join(d, "graph.graphml"))
        self.assertIn("flowchart LR", open(os.path.join(d, "graph.mmd")).read())
        rep = open(os.path.join(d, "GRAPH_REPORT.md")).read()
        self.assertIn("## Hubs", rep)
        html = open(os.path.join(d, "graph.html")).read()
        self.assertNotIn("innerHTML", html)
        self.assertNotIn("http://", html.replace("http://www.w3.org/2000/svg", ""))
        if shutil.which("node"):
            js = re.search(r"<script>(.*)</script>", html, re.S).group(1)
            jp = os.path.join(d, "v.js")
            open(jp, "w").write(js)
            r = subprocess.run(["node", "--check", jp], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


class DataModel(unittest.TestCase):
    def check(self, model, extra=()):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "m.json")
            json.dump(model, open(p, "w"))
            return run([script("data-model-design", "model_check.py"), "--model", p] + list(extra))

    def load(self):
        return json.load(open(MODEL_EX))

    def test_example_is_valid_and_clean(self):
        rc, m = run([script("data-model-design", "validate_json.py"), os.path.join(SK, "data-model-design", "assets", "data-model.schema.json"), MODEL_EX])
        self.assertEqual(rc, 0, m)
        rc, m = run([script("data-model-design", "model_check.py"), "--model", MODEL_EX, "--strict"])
        self.assertEqual(rc, 0, m)

    def test_checker_rejects_design_mistakes(self):
        def ent(m, name):
            return [e for e in m["entities"] if e["name"] == name][0]

        def attr(m, e, a):
            return [x for x in ent(m, e)["attributes"] if x["name"] == a][0]
        cases = []
        m = self.load(); attr(m, "leave_request", "employee_id")["type"] = "integer"; cases.append((m, "foreign key"))
        m = self.load(); attr(m, "employee", "full_name")["classification"] = "Internal"; cases.append((m, "personal data"))
        m = self.load(); attr(m, "leave_request", "medical_note")["protection"] = "none"; cases.append((m, "protection"))
        m = self.load(); ent(m, "leave_request")["classification"] = "Internal"; cases.append((m, "below its most sensitive"))
        m = self.load(); ent(m, "leave_policy")["attributes"].append({"name": "late_fee_amount", "type": "integer", "nullable": False, "classification": "Internal", "personal_data": False, "protection": "none", "description": "A fee"}); cases.append((m, "money-like"))
        m = self.load(); attr(m, "leave_request", "status")["type"] = "enum:nope"; cases.append((m, "unknown enum"))
        m = self.load(); ent(m, "employee")["name"] = "user"; cases.append((m, "reserved word"))
        m = self.load(); ent(m, "employee")["attributes"].append({"name": "created_at", "type": "timestamptz", "nullable": False, "classification": "Internal", "personal_data": False, "protection": "none", "description": "dup audit"}); cases.append((m, "audit columns are generated"))
        m = self.load(); attr(m, "leave_request", "from_date")["type"] = "timestamptz"; cases.append((m, "*_date"))
        for model, needle in cases:
            rc, out = self.check(model)
            self.assertEqual(rc, 1, needle + "\n" + out)
            self.assertIn(needle, out)

    def test_spec_references_are_verified(self):
        with tempfile.TemporaryDirectory() as t:
            open(os.path.join(t, "03-data-model.md"), "w").write("- **DM-001** Leave request has dates. [x.html:1]\n- **DM-002** Not covered anywhere. [x.html:2]\n")
            m = self.load(); m["entities"][3]["spec_refs"] = ["DM-001", "BR-999"]
            rc, out = self.check(m, ["--spec-dir", t])
            self.assertEqual(rc, 1)
            self.assertIn("BR-999", out)
            self.assertIn("DM-002", out)

    def test_ddl_erd_and_flyway(self):
        with tempfile.TemporaryDirectory() as t:
            sql = os.path.join(t, "s.sql")
            rc, m = run([script("data-model-design", "generate_ddl.py"), "--model", MODEL_EX, "--out", sql])
            self.assertEqual(rc, 0, m)
            d = open(sql).read()
            self.assertEqual(d.count("CREATE TABLE "), 6)
            for needle in ("CONSTRAINT pk_leave_request PRIMARY KEY (id)", "numeric(5,1)", "CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled'))",
                           "FORCE ROW LEVEL SECURITY", "version bigint NOT NULL DEFAULT 0", "COMMENT ON COLUMN leave_request.medical_note", "protection: encrypted_at_rest",
                           "ALTER TABLE leave_request ADD CONSTRAINT fk_leave_request_employee_id"):
                self.assertIn(needle, d)
            self.assertNotRegex(d, r"(?i)\b(float|real|double)\b")
            self.assertNotIn("audit_log ENABLE", d.split("CREATE TABLE audit_log")[0])
            erd = os.path.join(t, "e.mmd")
            run([script("data-model-design", "generate_erd.py"), "--model", MODEL_EX, "--out", erd])
            e = open(erd).read()
            self.assertTrue(e.startswith("erDiagram"))
            self.assertIn("employee ||--o{ leave_request", e)
            fw = os.path.join(t, "db", "migration")
            rc, m = run([script("data-model-design", "generate_ddl.py"), "--model", MODEL_EX, "--flyway-dir", fw, "--version", "1", "--tooling-dir", os.path.join(t, "db")])
            self.assertTrue(os.path.exists(os.path.join(fw, "V1__create_tables.sql")))

    def test_flyway_scripts_are_split_ordered_and_complete(self):
        with tempfile.TemporaryDirectory() as t:
            fw = os.path.join(t, "db", "migration")
            rc, m = run([script("data-model-design", "generate_ddl.py"), "--model", MODEL_EX, "--flyway-dir", fw, "--tooling-dir", os.path.join(t, "db")])
            self.assertEqual(rc, 0, m)
            names = sorted(os.listdir(fw))
            self.assertEqual(names, ["V1__create_tables.sql", "V2__add_foreign_keys_and_indexes.sql", "V3__table_and_column_comments.sql",
                                     "V4__row_level_security.sql", "V5__reference_data.sql"])
            def read(n):
                return open(os.path.join(fw, n)).read()
            self.assertEqual(read("V1__create_tables.sql").count("CREATE TABLE "), 6)
            self.assertNotIn("FOREIGN KEY", read("V1__create_tables.sql"))
            self.assertIn("FOREIGN KEY", read("V2__add_foreign_keys_and_indexes.sql"))
            self.assertIn("COMMENT ON COLUMN", read("V3__table_and_column_comments.sql"))
            self.assertIn("FORCE ROW LEVEL SECURITY", read("V4__row_level_security.sql"))
            self.assertEqual(read("V5__reference_data.sql").count("INSERT INTO leave_policy"), 3)
            self.assertIn("'flyway'", read("V5__reference_data.sql"))
            conf = open(os.path.join(t, "db", "flyway.conf")).read()
            self.assertIn("flyway.locations=filesystem:migration", conf)
            self.assertNotRegex(conf, r"(?i)password\s*=\s*\S")
            self.assertTrue(os.access(os.path.join(t, "db", "migrate.sh"), os.X_OK))
            # the split scripts together equal the single-file DDL (same statements, same order)
            one = os.path.join(t, "one.sql")
            run([script("data-model-design", "generate_ddl.py"), "--model", MODEL_EX, "--out", one])
            strip = lambda s: [l for l in s.splitlines() if l.strip() and not l.startswith("-- ")]
            joined = [l for n in names for l in strip(read(n))]
            self.assertEqual(joined, strip(open(one).read()))
            # a bad seed row is rejected by the checker
            bad = json.load(open(MODEL_EX))
            [e for e in bad["entities"] if e["name"] == "leave_policy"][0]["seed"][0]["leave_type"] = "holiday"
            p = os.path.join(t, "bad.json")
            json.dump(bad, open(p, "w"))
            rc, out = run([script("data-model-design", "model_check.py"), "--model", p])
            self.assertEqual(rc, 1)
            self.assertIn("not a value of enum", out)

    def test_ddl_is_stable_and_parses_with_the_inventory_parser(self):
        with tempfile.TemporaryDirectory() as t:
            os.makedirs(os.path.join(t, "m"))
            rc, _ = run([script("data-model-design", "generate_ddl.py"), "--model", MODEL_EX, "--out", os.path.join(t, "m", "schema.sql")])
            inv = os.path.join(t, "inv.json")
            rc, m = run([script("app-inventory", "inventory.py"), "--root", os.path.join(t, "m"), "--out", inv])
            self.assertEqual(rc, 0, m)
            tables = {x["name"]: x for x in json.load(open(inv))["data_model"]["sql_tables"]}
            self.assertEqual(set(tables), {"employee", "leave_policy", "leave_balance", "leave_request", "leave_approval", "audit_log"})
            self.assertTrue(tables["leave_request"]["rls_enabled"])
            self.assertFalse(tables["leave_policy"]["rls_enabled"])

    def test_diff_finds_float_money_plaintext_identifier_and_free_text_status(self):
        with tempfile.TemporaryDirectory() as t:
            inv = os.path.join(t, "inv.json")
            run([script("app-inventory", "inventory.py"), "--root", os.path.join(SAMPLES, "lovable-commercial-loan-desk"), "--out", inv])
            out = os.path.join(t, "plan.md")
            js = os.path.join(t, "diff.json")
            rc, m = run([script("data-model-design", "model_diff.py"), "--model", os.path.join(ROOT, "evals", "models", "loan-application.data-model.json"),
                         "--inventory", inv, "--out", out, "--json", js])
            self.assertEqual(rc, 0, m)
            plan = open(out).read()
            self.assertIn("requested_amount: float8 -> numeric(18,2)", plan)
            self.assertIn("tax_id: plain", plan)
            self.assertIn("status: free text -> application_status", plan)
            self.assertIn("lastTaxId", plan)
            self.assertEqual(json.load(open(js))["new"], ["audit_log"])


class JavaService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cfg = json.load(open(os.path.join(EXAMPLE_LEAVE, "handoff", "service.json")))
        cfg["model"] = MODEL_EX
        cls.cfgp = os.path.join(cls.tmp, "service.json")
        json.dump(cfg, open(cls.cfgp, "w"))
        cls.ddl = os.path.join(cls.tmp, "schema.sql")
        run([script("data-model-design", "generate_ddl.py"), "--model", MODEL_EX, "--out", cls.ddl])
        rc, m = run([script("java-spring-service", "scaffold_service.py"), "--config", cls.cfgp, "--out", cls.tmp, "--ddl", cls.ddl])
        assert rc == 0, m
        cls.svc = os.path.join(cls.tmp, "leave-service")
        cls.src = os.path.join(cls.svc, "src", "main", "java", "com", "example", "leave")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def read(self, *p):
        return open(os.path.join(self.src, *p)).read()

    def test_boot4_build_file(self):
        pom = open(os.path.join(self.svc, "pom.xml")).read()
        self.assertIn("<version>4.1.0</version>", pom)
        for a in ("spring-boot-starter-webmvc", "spring-boot-starter-flyway", "spring-boot-starter-oauth2-resource-server", "spring-boot-starter-webmvc-test",
                  "testcontainers-postgresql", "spring-boot-testcontainers", "flyway-database-postgresql"):
            self.assertIn("<artifactId>%s</artifactId>" % a, pom)
        self.assertNotIn("<artifactId>spring-boot-starter-web</artifactId>", pom)
        self.assertNotIn("com.fasterxml.jackson.core", pom)
        self.assertNotIn("{{", pom)

    def test_secure_by_default_dtos(self):
        req = self.read("dto", "CreateLeaveRequestRequest.java")
        for forbidden in ("status", "employeeId", "needsHrApproval", "workingDays", "UUID id"):
            self.assertNotIn(forbidden, req)
        self.assertIn("@NotNull LeaveType leaveType", req)
        resp = self.read("dto", "LeaveRequestResponse.java")
        self.assertNotIn("medicalNote", resp)
        self.assertNotIn("homeAddress", resp)
        self.assertIn("Omitted on purpose", resp)

    def test_controller_service_and_audit(self):
        c = self.read("api", "LeaveRequestController.java")
        self.assertIn('@RequestMapping("/api/v1/leave-requests")', c)
        self.assertIn("@Valid @RequestBody", c)
        self.assertEqual(c.count("@PreAuthorize"), 3)
        self.assertNotIn("Repository", c)
        s = self.read("service", "LeaveRequestService.java")
        self.assertIn('auditTrail.record("leave_request"', s)
        self.assertIn("TODO(spec): employeeId is set by the service", s)
        self.assertIn("PagedModel", c)
        e = self.read("domain", "LeaveRequest.java")
        self.assertIn("extends AuditedEntity", e)
        self.assertIn("precision = 5, scale = 1", e)
        self.assertIn("RequestStatus status = RequestStatus.PENDING", e)

    def test_business_rule_stubs_and_resources(self):
        t = open(os.path.join(self.svc, "src", "test", "java", "com", "example", "leave", "BusinessRulesTest.java")).read()
        self.assertEqual(t.count("@Disabled"), 7)
        self.assertIn("BR-3 A person cannot approve their own request", t)
        self.assertTrue(os.path.exists(os.path.join(self.svc, "src", "main", "resources", "db", "migration", "V1__init.sql")))
        y = open(os.path.join(self.svc, "src", "main", "resources", "application.yml")).read()
        self.assertIn("ddl-auto: validate", y)
        self.assertIn("${DB_PASSWORD}", y)
        self.assertIn("open-in-view: false", y)

    def test_generated_service_passes_java_check(self):
        rc, m = run([script("java-spring-service", "java_check.py"), "--root", self.svc, "--strict"])
        self.assertEqual(rc, 0, m)

    @unittest.skipUnless(has_jdk_compiler(), "needs a JDK or the jdk.compiler module")
    def test_generated_java_is_syntactically_valid(self):
        r = subprocess.run(["java", os.path.join(SK, "java-spring-service", "scripts", "JavaSyntaxCheck.java"), self.svc], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 syntax errors", r.stdout)

    @unittest.skipUnless(has_jdk_compiler(), "needs a JDK or the jdk.compiler module")
    def test_syntax_checker_catches_a_broken_file(self):
        with tempfile.TemporaryDirectory() as t:
            open(os.path.join(t, "A.java"), "w").write("class A { void f( { } }\n")
            r = subprocess.run(["java", os.path.join(SK, "java-spring-service", "scripts", "JavaSyntaxCheck.java"), t], capture_output=True, text=True)
            self.assertEqual(r.returncode, 1)

    def test_bad_service_is_rejected_for_the_right_reasons(self):
        rc, m = run([script("java-spring-service", "java_check.py"), "--root", os.path.join(ROOT, "evals", "java", "bad-service")])
        self.assertEqual(rc, 1)
        for rule in ("JV-001", "JV-002", "JV-003", "JV-004", "JV-005", "JV-006", "JV-007", "JV-009", "JV-010", "JV-011", "JV-013", "JV-014",
                     "JV-016", "JV-017", "JV-019", "JV-020", "JV-024"):
            self.assertIn(rule, m, rule + " not reported")
        for secret in ("Sup3rS3cret", "hunter2-prod"):
            self.assertNotIn(secret, m)

    def test_scaffold_can_take_the_split_flyway_scripts(self):
        with tempfile.TemporaryDirectory() as t:
            mig = os.path.join(t, "m")
            run([script("data-model-design", "generate_ddl.py"), "--model", MODEL_EX, "--flyway-dir", mig])
            rc, m = run([script("java-spring-service", "scaffold_service.py"), "--config", self.cfgp, "--out", t, "--migrations", mig])
            self.assertEqual(rc, 0, m)
            dest = os.path.join(t, "leave-service", "src", "main", "resources", "db", "migration")
            self.assertEqual(len(os.listdir(dest)), 5)
            rc, m = run([script("java-spring-service", "java_check.py"), "--root", os.path.join(t, "leave-service"), "--strict"])
            self.assertEqual(rc, 0, m)

    def test_scaffold_will_not_overwrite_and_validates_input(self):
        rc, m = run([script("java-spring-service", "scaffold_service.py"), "--config", self.cfgp, "--out", self.tmp, "--ddl", self.ddl])
        self.assertEqual(rc, 2)
        self.assertIn("exists", m)

    def test_templates_have_no_unresolved_placeholders(self):
        for dp, dn, fn in os.walk(self.svc):
            for f in fn:
                self.assertNotIn("{{", open(os.path.join(dp, f), encoding="utf-8").read(), f)


def has_playwright():
    rc, _ = run([script("ui-map", "ui_capture.py"), "--check"])
    return rc == 0


LEAVE_H = os.path.join(EXAMPLE_LEAVE, "handoff")
LEAVE_APP = os.path.join(EXAMPLE_LEAVE, "app")


class Orchestration(unittest.TestCase):
    def test_classifier_routes_each_kind_of_input(self):
        cases = [(os.path.join(SAMPLES, "html-kyc-onboarding-desk"), "html-folder"), (os.path.join(SAMPLES, "lovable-commercial-loan-desk"), "node-project"),
                 (os.path.join(SAMPLES, "html-leave-request-tracker", "leave-tracker.html"), "html-file"), ("https://pilot.example.test/app", "url"),
                 ("https://www.figma.com/file/abc123", "design-link")]
        for inp, kind in cases:
            rc, out = run([script("app-handoff", "classify_input.py"), "--input", inp])
            d = json.loads(out)
            self.assertEqual(d["kind"], kind, inp)
        d = json.loads(run([script("app-handoff", "classify_input.py"), "--input", "https://pilot.example.test/app"])[1])
        self.assertTrue(d["capabilities"]["live_capture"] and not d["capabilities"]["source_analysis"])
        self.assertIn("no source code", " ".join(d["warnings"]))
        self.assertEqual(d["route"][1]["skill"], "ui-map")
        d = json.loads(run([script("app-handoff", "classify_input.py"), "--input", "https://www.figma.com/file/abc"])[1])
        self.assertEqual(d["route"], [])
        rc, out = run([script("app-handoff", "classify_input.py"), "--input", "/nonexistent/thing"])
        self.assertEqual(rc, 1)

    def test_classifier_handles_images_and_unsafe_archives(self):
        import zipfile
        with tempfile.TemporaryDirectory() as t:
            open(os.path.join(t, "login.png"), "wb").write(b"\x89PNG\r\n")
            d = json.loads(run([script("app-handoff", "classify_input.py"), "--input", t])[1])
            self.assertEqual(d["kind"], "images")
            z = os.path.join(t, "evil.zip")
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("../escape.txt", "x")
            d = json.loads(run([script("app-handoff", "classify_input.py"), "--input", z, "--unzip-to", os.path.join(t, "out")])[1])
            self.assertEqual(d["kind"], "archive")
            self.assertFalse(os.path.exists(os.path.join(t, "out")))
            self.assertIn("unsafe", " ".join(d["warnings"]))

    def test_status_reads_the_leave_example_end_to_end(self):
        with tempfile.TemporaryDirectory() as t:
            h = os.path.join(t, "handoff")
            shutil.copytree(LEAVE_H, h)
            order = ["intake.md", "ui/ui-map.json", "inventory.json", "spec/.manifest.json", "jira/issues.json", "plan/implementation-plan.json", "data-model/data-model.json"]
            for i, f in enumerate(order):
                os.utime(os.path.join(h, f), (1700000000 + i * 10, 1700000000 + i * 10))
            rc, m = run([script("app-handoff", "status.py"), "--handoff", h, "--services", os.path.join(EXAMPLE_LEAVE, "services")])
            self.assertEqual(rc, 0, m)
            self.assertRegex(m, r"jira issues\s+done\s+review gate open")
            self.assertRegex(m, r"implementation plan\s+done")
            self.assertRegex(m, r"QA run\s+blocked")
            self.assertIn("built service", m)

    def test_commands_and_agents_point_at_real_skills(self):
        skills = set(os.listdir(SK))
        for p in glob.glob(os.path.join(ROOT, "commands", "*.md")):
            txt = open(p, encoding="utf-8").read()
            self.assertTrue(txt.startswith("---\ndescription: "), p)
            named = set(re.findall(r"`([a-z\-]+)` skill", txt))
            self.assertTrue(named and named <= skills, "%s names unknown skill(s): %s" % (p, named - skills))
        wanted = {"poc", "ui-map", "spec", "jira", "plan", "codify", "data-model", "service", "implement", "gap-check", "qa", "preprod"}
        self.assertEqual({os.path.basename(p)[:-3] for p in glob.glob(os.path.join(ROOT, "commands", "*.md"))}, wanted)
        for p in glob.glob(os.path.join(ROOT, "agents", "*.md")):
            for name in re.findall(r"`([a-z\-]+)` skill", open(p, encoding="utf-8").read()):
                self.assertIn(name, skills, p)
        self.assertTrue(os.path.exists(os.path.join(ROOT, "agents", "orchestrator.md")))


class UiMap(unittest.TestCase):
    def test_static_snapshots_map_and_check_for_a_multi_page_app(self):
        with tempfile.TemporaryDirectory() as t:
            snaps = os.path.join(t, "ui")
            rc, m = run([script("ui-map", "ui_snapshot_static.py"), "--input", os.path.join(SAMPLES, "html-kyc-onboarding-desk"), "--out", snaps])
            self.assertEqual(rc, 0, m)
            nc = json.load(open(os.path.join(snaps, "new-case.snapshot.json")))
            self.assertTrue(nc["rendered_by_script"])
            names = {e["name"]: e for e in nc["elements"]}
            self.assertEqual(names["Full name"]["locator"], 'page.get_by_label("Full name")')
            self.assertEqual(names["Full name"]["line"], 10)
            self.assertEqual(names["ID type"]["kind"], "select")
            self.assertNotIn("Passport", names["ID type"]["label"])
            login = json.load(open(os.path.join(snaps, "login.snapshot.json")))
            self.assertEqual(login["script_navigation"], ["index.html", "login.html"])
            self.assertIn('page.get_by_role("button", name="Sign in")', [e["locator"] for e in login["elements"]])
            rc, m = run([script("ui-map", "ui_map_build.py"), "--snapshots", snaps, "--out-dir", t, "--source-kind", "folder", "--source-value", "kyc"])
            self.assertEqual(rc, 0, m)
            ui = json.load(open(os.path.join(t, "ui-map.json")))
            self.assertEqual(len(ui["screens"]), 7)
            self.assertTrue(any(x["from"] == "login" and x["to"] == "index" and x["kind"] == "script" and x["confidence"] == "INFERRED" for x in ui["transitions"]))
            self.assertTrue(any(f["name"] == "idNumber" or f["label"] == "ID number" for f in ui["data_fields"]))
            rc, m = run([script("ui-map", "ui_map_check.py"), "--map", os.path.join(t, "ui-map.json")])
            self.assertEqual(rc, 0, m)
            self.assertIn("built by script", m)
            md = open(os.path.join(t, "ui-map.md")).read()
            self.assertIn("```mermaid", md)
            self.assertIn("run a live capture", md)

    def test_static_snapshots_record_no_input_values_or_secrets(self):
        with tempfile.TemporaryDirectory() as t:
            f = os.path.join(t, "page.html")
            open(f, "w").write('<html><title>T</title><body><label for="u">User</label><input id="u" value="alice@corp.example"><input type="password" value="hunter2">'
                               '<script>fetch("/api/x?token=abc123&q=1");</script></body></html>')
            run([script("ui-map", "ui_snapshot_static.py"), "--input", f, "--out", t])
            blob = open(os.path.join(t, "page.snapshot.json")).read()
            for s in ("alice@corp.example", "hunter2", "abc123"):
                self.assertNotIn(s, blob)
            self.assertIn("<redacted>", blob)

    def test_image_input_creates_stubs_and_the_checker_asks_for_descriptions(self):
        with tempfile.TemporaryDirectory() as t:
            open(os.path.join(t, "Login Screen.png"), "wb").write(b"\x89PNG\r\n\x1a\n")
            out = os.path.join(t, "ui")
            rc, m = run([script("ui-map", "ui_snapshot_images.py"), "--input", t, "--out", out])
            self.assertEqual(rc, 0, m)
            run([script("ui-map", "ui_map_build.py"), "--snapshots", out, "--out-dir", out])
            rc, m = run([script("ui-map", "ui_map_check.py"), "--map", os.path.join(out, "ui-map.json")])
            self.assertEqual(rc, 0, m)
            self.assertIn("image screens with no controls", m)

    def test_spec_can_cite_ui_screens_and_drift_is_detected(self):
        ui = os.path.join(LEAVE_H, "ui", "ui-map.json")
        with tempfile.TemporaryDirectory() as t:
            sd = os.path.join(t, "spec")
            os.makedirs(sd)
            open(os.path.join(sd, "06-ui-screens.md"), "w").write("- **UI-001** An employee sees a request form after signing in. [ui:leave-tracker@employee]\n")
            rc, m = run([script("app-spec-extract", "spec_lint.py"), "--spec-dir", sd, "--root", LEAVE_APP])
            self.assertEqual(rc, 1)
            self.assertIn("needs --ui-map", m)
            rc, m = run([script("app-spec-extract", "spec_lint.py"), "--spec-dir", sd, "--root", LEAVE_APP, "--ui-map", ui, "--write-manifest"])
            self.assertEqual(rc, 0, m)
            man = os.path.join(sd, ".manifest.json")
            self.assertTrue(any(e["file"] == "ui:leave-tracker@employee" for e in json.load(open(man))["entries"]))
            rc, m = run([script("spec-drift-check", "drift_check.py"), "--root", LEAVE_APP, "--manifest", man, "--ui-map", ui])
            self.assertEqual(rc, 0, m)
            d = json.load(open(ui))
            for s in d["screens"]:
                if s["id"] == "leave-tracker@employee":
                    s["elements"][0]["locator"] = 'page.get_by_label("Changed")'
            p2 = os.path.join(t, "ui2.json")
            json.dump(d, open(p2, "w"))
            rc, m = run([script("spec-drift-check", "drift_check.py"), "--root", LEAVE_APP, "--manifest", man, "--ui-map", p2])
            self.assertEqual(rc, 1)
            self.assertIn("UI-001", m)
            open(os.path.join(sd, "06-ui-screens.md"), "w").write("- **UI-001** x. [ui:no-such-screen]\n")
            rc, m = run([script("app-spec-extract", "spec_lint.py"), "--spec-dir", sd, "--root", LEAVE_APP, "--ui-map", ui])
            self.assertEqual(rc, 1)
            self.assertIn("not in the UI map", m)

    def test_example_map_is_valid_and_has_flows_with_screenshots(self):
        rc, m = run([script("ui-map", "ui_map_check.py"), "--map", os.path.join(LEAVE_H, "ui", "ui-map.json"), "--ui-dir", os.path.join(LEAVE_H, "ui")])
        self.assertEqual(rc, 0, m)
        ui = json.load(open(os.path.join(LEAVE_H, "ui", "ui-map.json")))
        self.assertEqual({s["id"] for s in ui["screens"]}, {"leave-tracker", "leave-tracker@employee", "leave-tracker@manager"})
        self.assertEqual([f["id"] for f in ui["flows"]], ["F-1", "F-2", "F-3"])
        self.assertTrue(all(s["purpose"] for s in ui["screens"]))

    @unittest.skipUnless(has_playwright(), "needs Playwright and Chromium")
    def test_live_capture_with_scripted_states_and_secret_refusal(self):
        with tempfile.TemporaryDirectory() as t:
            states = os.path.join(t, "states.json")
            json.dump(json.load(open(os.path.join(LEAVE_H, "ui", "states.json"))) + [{"name": "pw", "steps": [{"action": "fill", "locator": "#pw", "value": "x"}]}], open(states, "w"))
            out = os.path.join(t, "ui")
            rc, m = run([script("ui-map", "ui_capture.py"), "--input", LEAVE_APP, "--out", out, "--states", states, "--max-pages", "3"])
            self.assertEqual(rc, 0, m)
            self.assertIn("refused step on a secret-looking field", m)
            snaps = sorted(f for f in os.listdir(out) if f.endswith(".snapshot.json"))
            self.assertEqual(snaps, ["leave-tracker.snapshot.json", "leave-tracker__employee.snapshot.json", "leave-tracker__manager.snapshot.json"])
            for f in os.listdir(os.path.join(out, "screens")):
                self.assertGreater(os.path.getsize(os.path.join(out, "screens", f)), 1000)
            emp = json.load(open(os.path.join(out, "leave-tracker__employee.snapshot.json")))
            self.assertIn("Submit", [e["name"] for e in emp["elements"] if e["visible"]])
            self.assertNotIn("Test Employee", json.dumps(emp))
            rc, m = run([script("ui-map", "ui_map_build.py"), "--snapshots", out, "--out-dir", out])
            rc, m = run([script("ui-map", "ui_map_check.py"), "--map", os.path.join(out, "ui-map.json")])
            self.assertEqual(rc, 0, m)

    def test_snapshot_script_is_valid_javascript(self):
        if not shutil.which("node"):
            self.skipTest("node not available")
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "s.js")
            open(p, "w").write("const f = " + open(os.path.join(SK, "ui-map", "assets", "snapshot.js")).read() + ";\n")
            r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


class JiraAndPlan(unittest.TestCase):
    ISSUES = os.path.join(LEAVE_H, "jira", "issues.json")
    FEATURES = os.path.join(LEAVE_H, "jira", "features.json")

    def build(self, t, features=None, extra=(), previous=None):
        args = [script("spec-to-jira", "jira_build.py"), "--features", features or self.FEATURES, "--spec-dir", os.path.join(LEAVE_H, "spec"),
                "--ui-map", os.path.join(LEAVE_H, "ui", "ui-map.json"), "--data-model", os.path.join(LEAVE_H, "data-model", "data-model.json"), "--out-dir", t]
        if previous:
            args += ["--previous", previous]
        return run(args + list(extra))

    def test_example_issues_are_valid_and_the_gate_is_open(self):
        rc, m = run([script("spec-to-jira", "validate_json.py"), os.path.join(SK, "spec-to-jira", "assets", "jira-issues.schema.json"), self.ISSUES]) if os.path.exists(script("spec-to-jira", "validate_json.py")) else (0, "")
        self.assertEqual(rc, 0, m)
        rc, m = run([script("spec-to-jira", "jira_gate.py"), "--issues", self.ISSUES])
        self.assertEqual(rc, 0, m)
        doc = json.load(open(self.ISSUES))
        self.assertTrue({"E-01", "E-02", "E-03", "E-DATA", "T-D1", "T-D2", "T-D3"} <= {i["key"] for i in doc["issues"]})
        self.assertTrue(all(i["review"]["business"]["status"] == "approved" for i in doc["issues"]))

    def test_rebuild_keeps_approvals_and_text_changes_reset_them(self):
        with tempfile.TemporaryDirectory() as t:
            shutil.copy(self.ISSUES, os.path.join(t, "prev.json"))
            rc, m = self.build(t, previous=os.path.join(t, "prev.json"))
            self.assertEqual(rc, 0, m)
            rc, m = run([script("spec-to-jira", "jira_gate.py"), "--issues", os.path.join(t, "issues.json")])
            self.assertEqual(rc, 0, m)
            f = json.load(open(self.FEATURES))
            f["epics"][0]["stories"][0]["acceptance_criteria"][0] += " Also, then the employee gets a confirmation."
            ff = os.path.join(t, "features.json")
            json.dump(f, open(ff, "w"))
            rc, m = self.build(t, features=ff, previous=os.path.join(t, "prev.json"))
            rc, m = run([script("spec-to-jira", "jira_gate.py"), "--issues", os.path.join(t, "issues.json")])
            self.assertEqual(rc, 1)
            self.assertIn("S-001 business review is pending", m)
            self.assertIn("changed since last review", m)

    def test_build_rejects_bad_issues(self):
        base = json.load(open(self.FEATURES))
        def mutate(fn):
            f = json.loads(json.dumps(base))
            fn(f)
            with tempfile.TemporaryDirectory() as t:
                p = os.path.join(t, "f.json")
                json.dump(f, open(p, "w"))
                return self.build(os.path.join(t, "o"), features=p)
        s1 = lambda f: f["epics"][0]["stories"][0]
        rc, m = mutate(lambda f: s1(f).__setitem__("acceptance_criteria", ["The employee can send a request without trouble."]))
        self.assertEqual(rc, 1); self.assertIn("Given/When/Then", m)
        rc, m = mutate(lambda f: s1(f).__setitem__("spec_refs", ["BR-999"]))
        self.assertEqual(rc, 1); self.assertIn("BR-999", m)
        rc, m = mutate(lambda f: s1(f).__setitem__("ui_refs", ["no-screen"]))
        self.assertEqual(rc, 1); self.assertIn("no-screen", m)
        rc, m = mutate(lambda f: s1(f).__setitem__("depends_on", ["S-004"]))
        self.assertEqual(rc, 1); self.assertIn("cycle", m)
        rc, m = mutate(lambda f: s1(f).__setitem__("data_refs", ["ghost_table"]))
        self.assertEqual(rc, 1); self.assertIn("ghost_table", m)
        rc, m = mutate(lambda f: s1(f).__setitem__("acceptance_criteria", []))
        self.assertEqual(rc, 1); self.assertIn("no acceptance criteria", m)

    def test_coverage_is_reported_and_strict_fails(self):
        f = json.load(open(self.FEATURES))
        f["epics"] = f["epics"][:1]
        f["epics"][0]["stories"] = f["epics"][0]["stories"][:1]
        f["out_of_scope"] = []
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "f.json")
            json.dump(f, open(p, "w"))
            rc, m = self.build(os.path.join(t, "o"), features=p)
            self.assertEqual(rc, 0, m)
            self.assertIn("business rules not covered", m)
            self.assertIn("F-3", m)
            rc, m = self.build(os.path.join(t, "o2"), features=p, extra=["--strict"])
            self.assertEqual(rc, 1)

    def test_review_records_only_named_people(self):
        with tempfile.TemporaryDirectory() as t:
            p = os.path.join(t, "issues.json")
            shutil.copy(self.ISSUES, p)
            rc, m = run([script("spec-to-jira", "jira_review.py"), "--issues", p, "--issue", "S-001", "--role", "business", "--decision", "approved"])
            self.assertEqual(rc, 2)
            rc, m = run([script("spec-to-jira", "jira_review.py"), "--issues", p, "--issue", "S-001", "--role", "technical", "--decision", "changes_requested", "--reviewer", "Sam"])
            self.assertEqual(rc, 2)
            rc, m = run([script("spec-to-jira", "jira_review.py"), "--issues", p, "--issue", "S-001", "--role", "technical", "--decision", "changes_requested", "--reviewer", "Sam", "--comment", "split by role"])
            self.assertEqual(rc, 0, m)
            rc, m = run([script("spec-to-jira", "jira_gate.py"), "--issues", p])
            self.assertEqual(rc, 1)
            self.assertIn("changes_requested: split by role", m)
            rc, m = run([script("spec-to-jira", "jira_review.py"), "--issues", p, "--issue", "S-001", "--jira-key", "LEAVE-12"])
            self.assertEqual(rc, 0)
            self.assertEqual([i["jira_key"] for i in json.load(open(p))["issues"] if i["key"] == "S-001"], ["LEAVE-12"])
            rc, m = run([script("spec-to-jira", "jira_gate.py"), "--issues", p, "--require", "business", "--require-keys"])
            self.assertEqual(rc, 1)
            self.assertIn("no Jira key", m)

    def test_exports_for_jira(self):
        import csv
        with tempfile.TemporaryDirectory() as t:
            rc, m = self.build(t)
            rows = list(csv.DictReader(open(os.path.join(t, "issues.csv"), encoding="utf-8")))
            self.assertEqual(rows[0]["Issue Type"], "Epic")
            self.assertEqual({r["Issue id"] for r in rows if r["Parent id"]} & {"S-001", "T-D1"}, {"S-001", "T-D1"})
            pl = json.load(open(os.path.join(t, "jira-create-payload.json")))
            seen = set()
            for i in pl["issues"]:
                if i["parent_local_key"]:
                    self.assertIn(i["parent_local_key"], seen, "parent must be created first")
                seen.add(i["local_key"])
            bus = open(os.path.join(t, "review-business.md")).read()
            self.assertIn("![leave-tracker@employee](../ui/screens/leave-tracker@employee.png)", bus)
            self.assertNotIn("technical_notes", bus)
            eng = open(os.path.join(t, "review-engineering.md")).read()
            self.assertIn("Technical notes:", eng)
            self.assertIn("Spec: BR-001", eng)

    def test_plan_orders_work_and_is_checked(self):
        with tempfile.TemporaryDirectory() as t:
            rc, m = run([script("implementation-plan", "plan_build.py"), "--issues", self.ISSUES, "--out-dir", t])
            self.assertEqual(rc, 0, m)
            plan = json.load(open(os.path.join(t, "implementation-plan.json")))
            wave = {w["key"]: w["wave"] for w in plan["work_items"]}
            self.assertLess(wave["T-D1"], wave["P-SERVICE"])
            self.assertLess(wave["P-SERVICE"], wave["S-001"])
            self.assertLess(wave["S-001"], wave["S-002"])
            self.assertEqual(max(wave.values()), wave["P-PREPROD"])
            self.assertEqual(plan["critical_path"]["keys"][-1], "P-PREPROD")
            self.assertTrue(plan["gate"]["open"])
            cmds = [s.get("command", "") for w in plan["work_items"] if w["key"] == "S-001" for s in w["steps"]]
            self.assertTrue(any(c.startswith("/implement S-001") for c in cmds) and any(c.startswith("/qa S-001") for c in cmds))
            rc, m = run([script("implementation-plan", "plan_check.py"), "--plan", os.path.join(t, "implementation-plan.json"), "--issues", self.ISSUES])
            self.assertEqual(rc, 0, m)
            rc, m = run([script("implementation-plan", "plan_build.py"), "--issues", self.ISSUES, "--out-dir", os.path.join(t, "cap"), "--capacity-points", "4"])
            self.assertGreater(json.load(open(os.path.join(t, "cap", "implementation-plan.json")))["summary"]["waves"], plan["summary"]["waves"])
            rc, m = run([script("implementation-plan", "plan_check.py"), "--plan", os.path.join(t, "cap", "implementation-plan.json"), "--issues", self.ISSUES])
            self.assertEqual(rc, 0, m)

    def test_plan_refuses_unreviewed_scope_and_detects_stale_plans(self):
        with tempfile.TemporaryDirectory() as t:
            doc = json.load(open(self.ISSUES))
            [i for i in doc["issues"] if i["key"] == "S-003"][0]["review"]["technical"] = {"status": "pending"}
            p = os.path.join(t, "issues.json")
            json.dump(doc, open(p, "w"))
            rc, m = run([script("implementation-plan", "plan_build.py"), "--issues", p, "--out-dir", os.path.join(t, "o")])
            self.assertEqual(rc, 1)
            self.assertIn("gate is not open", m)
            rc, m = run([script("implementation-plan", "plan_build.py"), "--issues", p, "--out-dir", os.path.join(t, "d"), "--allow-unreviewed"])
            self.assertEqual(rc, 0, m)
            self.assertIn("NOT OPEN", open(os.path.join(t, "d", "implementation-plan.md")).read())
            plan = json.load(open(os.path.join(LEAVE_H, "plan", "implementation-plan.json")))
            rc, m = run([script("implementation-plan", "plan_check.py"), "--plan", os.path.join(LEAVE_H, "plan", "implementation-plan.json"), "--issues", p])
            self.assertEqual(rc, 1)
            self.assertIn("S-003", m)


class QaAndPreprod(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.tests = os.path.join(cls.tmp, "tests")
        rc, m = run([script("qa-playwright", "gen_playwright_tests.py"), "--ui-map", os.path.join(LEAVE_H, "ui", "ui-map.json"), "--issues", os.path.join(LEAVE_H, "jira", "issues.json"),
                     "--states", os.path.join(LEAVE_H, "ui", "states.json"), "--out-dir", cls.tests])
        assert rc == 0, m

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_generated_tests_compile_and_trace_every_criterion(self):
        import py_compile
        for f in glob.glob(os.path.join(self.tests, "*.py")):
            py_compile.compile(f, doraise=True)
        rc, m = run([script("qa-playwright", "qa_trace_check.py"), "--issues", os.path.join(LEAVE_H, "jira", "issues.json"), "--tests-dir", self.tests])
        self.assertEqual(rc, 0, m)
        acc = open(os.path.join(self.tests, "test_acceptance.py")).read()
        flows = open(os.path.join(self.tests, "test_flows.py")).read()
        self.assertIn("AC: S-001#1", flows)
        self.assertNotIn("AC: S-001#1", acc)
        self.assertIn("AC: S-002#2", acc)
        self.assertIn("todo(", acc)
        self.assertEqual(open(os.path.join(self.tests, "test_smoke.py")).read().count("def test_smoke_"), 3)

    def test_without_states_screens_behind_a_role_become_todos_not_wrong_tests(self):
        with tempfile.TemporaryDirectory() as t:
            rc, m = run([script("qa-playwright", "gen_playwright_tests.py"), "--ui-map", os.path.join(LEAVE_H, "ui", "ui-map.json"), "--out-dir", t])
            self.assertEqual(rc, 0, m)
            self.assertIn("needs the scripted state", open(os.path.join(t, "test_smoke.py")).read())

    def test_trace_requires_passing_tests_for_the_gate(self):
        rc, m = run([script("qa-playwright", "qa_trace_check.py"), "--issues", os.path.join(LEAVE_H, "jira", "issues.json"), "--tests-dir", self.tests,
                     "--report", os.path.join(LEAVE_H, "qa", "report", "qa-report.json"), "--require-passing"])
        self.assertEqual(rc, 1)
        self.assertIn("S-002#2", m)
        rc, m = run([script("qa-playwright", "qa_trace_check.py"), "--issues", os.path.join(LEAVE_H, "jira", "issues.json"), "--tests-dir", os.path.join(self.tests, "nonexistent")])
        self.assertEqual(rc, 1)

    @unittest.skipUnless(has_playwright(), "needs Playwright and Chromium")
    def test_runner_executes_generated_tests_against_the_prototype(self):
        rep = os.path.join(self.tmp, "report")
        rc, m = run([script("qa-playwright", "qa_runner.py"), "--tests-dir", self.tests, "--serve", LEAVE_APP, "--report-dir", rep])
        r = json.load(open(os.path.join(rep, "qa-report.json")))
        status = {x["test"]: x["status"] for x in r["results"]}
        for name in ("test_flow_f_1_employee_requests_leave", "test_flow_f_2_employee_is_refused_when_the_days_exceed_the_balance", "test_flow_f_3_manager_approves_a_request"):
            self.assertEqual(status[name], "passed", name)
        self.assertTrue(all(v == "passed" for k, v in status.items() if k.startswith(("test_smoke", "test_controls"))))
        self.assertTrue(all(v == "failed" for k, v in status.items() if k.startswith("test_a11y")), "the prototype's unlabelled fields should be reported")
        self.assertEqual(rc, 1)
        self.assertEqual(r["counts"]["skipped"], 13)
        self.assertTrue(os.path.exists(os.path.join(rep, "artifacts", "test_a11y_leave_tracker.png")))
        rc, m = run([script("qa-playwright", "qa_trace_check.py"), "--issues", os.path.join(LEAVE_H, "jira", "issues.json"), "--tests-dir", self.tests, "--report", os.path.join(rep, "qa-report.json")])
        self.assertEqual(rc, 0, m)
        self.assertIn("3 passing", m)

    @unittest.skipUnless(has_playwright(), "needs Playwright and Chromium")
    def test_a_broken_assertion_is_reported_as_a_failure_with_a_screenshot(self):
        with tempfile.TemporaryDirectory() as t:
            td = os.path.join(t, "tests")
            os.makedirs(td)
            shutil.copy(os.path.join(self.tests, "qa_support.py"), td)
            open(os.path.join(td, "test_bad.py"), "w").write(
                "from playwright.sync_api import Page, expect\nfrom qa_support import goto_screen, todo\n\n\ndef test_wrong_title(page: Page, base_url):\n    goto_screen(page, base_url, '/leave-tracker.html')\n"
                "    expect(page.get_by_text('This text is not on the page')).to_be_visible(timeout=500)\n\n\ndef test_skip(page, base_url):\n    todo('later')\n")
            rc, m = run([script("qa-playwright", "qa_runner.py"), "--tests-dir", td, "--serve", LEAVE_APP, "--report-dir", os.path.join(t, "r"), "--timeout", "1500"])
            self.assertEqual(rc, 1)
            r = json.load(open(os.path.join(t, "r", "qa-report.json")))
            self.assertEqual(r["counts"], {"passed": 0, "failed": 1, "skipped": 1, "error": 0})
            self.assertTrue(os.path.exists(os.path.join(t, "r", "artifacts", "test_wrong_title.png")))

    def gate(self, h, *extra):
        return run([script("aws-preprod", "preprod_gate.py"), "--handoff", h, "--service", os.path.join(EXAMPLE_LEAVE, "services", "leave-service")] + list(extra))

    def test_gate_blocks_the_example_until_qa_gaps_and_approval_are_done(self):
        with tempfile.TemporaryDirectory() as t:
            h = os.path.join(t, "handoff")
            shutil.copytree(LEAVE_H, h)
            rc, m = self.gate(h, "--skip-approval")
            self.assertEqual(rc, 1)
            self.assertRegex(m, r"qa\s+FAIL")
            self.assertRegex(m, r"gaps\s+FAIL")
            self.assertRegex(m, r"reviews\s+ok")
            self.assertRegex(m, r"safety\s+ok")
            # make QA pass and add a clean gap analysis
            rp = os.path.join(h, "qa", "report", "qa-report.json")
            r = json.load(open(rp))
            for x in r["results"]:
                if x["status"] == "failed":
                    x["status"] = "passed"
            r["counts"] = {"passed": r["counts"]["passed"] + r["counts"]["failed"], "failed": 0, "skipped": r["counts"]["skipped"], "error": 0}
            json.dump(r, open(rp, "w"))
            json.dump({"findings": [{"id": "F-001", "severity": "Medium", "status": "confirmed"}]}, open(os.path.join(h, "gaps.json"), "w"))
            rc, m = self.gate(h, "--skip-approval")
            self.assertEqual(rc, 0, m)
            rc, m = self.gate(h)
            self.assertEqual(rc, 1)
            self.assertIn("no change ticket", m)
            d = json.load(open(os.path.join(h, "preprod", "deploy.json")))
            d["approvals"] = {"change_ticket": "CHG-1", "approver": "A. Person", "date": "2026-10-07", "scope": "pre-production only"}
            json.dump(d, open(os.path.join(h, "preprod", "deploy.json"), "w"))
            rc, m = self.gate(h)
            self.assertEqual(rc, 0, m)
            rc, m = self.gate(h, "--require-passing")
            self.assertEqual(rc, 1)
            self.assertIn("criteria without a passing test", m)

    def test_gate_rejects_unsafe_deployment_decisions(self):
        def run_with(change):
            with tempfile.TemporaryDirectory() as t:
                h = os.path.join(t, "handoff")
                shutil.copytree(LEAVE_H, h)
                p = os.path.join(h, "preprod", "deploy.json")
                d = json.load(open(p))
                change(d)
                json.dump(d, open(p, "w"))
                return self.gate(h, "--skip-approval")
        rc, m = run_with(lambda d: d["network"].__setitem__("private_subnets", False)); self.assertIn("private subnets", m)
        rc, m = run_with(lambda d: d["database"].__setitem__("encrypted", False)); self.assertIn("encrypted", m)
        rc, m = run_with(lambda d: d["data"].__setitem__("synthetic_only", False)); self.assertIn("named approver", m)
        rc, m = run_with(lambda d: d["service"].__setitem__("image", "x")); self.assertNotIn("FAIL deploy", m)
        rc, m = run_with(lambda d: d["secrets"]["names"].append("password=hunter2")); self.assertIn("secret values", m)
        rc, m = run_with(lambda d: d["target"].__setitem__("environment", "prod")); self.assertRegex(m, r"deploy\s+FAIL")

    def test_deploy_example_matches_its_schema(self):
        rc, m = run([script("aws-preprod", "validate_json.py"), os.path.join(SK, "aws-preprod", "assets", "deploy.schema.json"), os.path.join(SK, "aws-preprod", "assets", "deploy.example.json")])
        self.assertEqual(rc, 0, m)


class Guard(unittest.TestCase):
    def call(self, tool, ti, env=None):
        rc, _ = run([os.path.join(ROOT, "hooks", "guard.py")], stdin=json.dumps({"tool_name": tool, "tool_input": ti}), env=env)
        return rc

    def test_guard(self):
        self.assertEqual(self.call("Write", {"file_path": "/a/app/src/x.ts"}), 2)
        self.assertEqual(self.call("Write", {"file_path": "/a/app/handoff/spec/x.md"}), 0)
        self.assertEqual(self.call("Write", {"file_path": "/a/app/src/x.ts"}, {"HANDOFF_ALLOW_APP_EDIT": "1"}), 0)
        self.assertEqual(self.call("Read", {"file_path": "/a/app/.env"}), 2)
        self.assertEqual(self.call("Read", {"file_path": "/a/app/.env.example"}), 0)
        self.assertEqual(self.call("Bash", {"command": "curl https://x"}), 2)
        self.assertEqual(self.call("Bash", {"command": "npm install left-pad"}), 2)
        self.assertEqual(self.call("Bash", {"command": "cat .env"}), 2)
        self.assertEqual(self.call("Bash", {"command": "python3 scripts/inventory.py --root . --out handoff/inventory.json"}), 0)


if __name__ == "__main__":
    unittest.main(verbosity=1, warnings="ignore")
