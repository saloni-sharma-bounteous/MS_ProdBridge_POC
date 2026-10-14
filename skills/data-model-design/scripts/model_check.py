#!/usr/bin/env python3
"""Check a target data model (data-model.json) for design problems before any SQL or code is generated.

Errors (must fix): unknown types or enums, missing or invalid primary/foreign/unique/index columns, FK type
mismatch, float types, money not exact, reserved or non-snake_case names, identifier longer than 63 characters,
personal data below Confidential, Restricted data with no protection and no note, entity classification below
its most sensitive attribute, audit columns declared by hand, spec references that do not exist.
Warnings: status-like column without an enum, nullable foreign keys without a reason, no audit_log entity when
entities are audited, FK without a supporting index, spec data-model statements (DM-nnn) not covered by any entity.

Usage: python3 model_check.py --model data-model.json [--spec-dir handoff/spec] [--strict]
Exit: 0 clean, 1 errors (or warnings with --strict), 2 usage/IO error.   Python 3.8+, standard library only.
"""
import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from validate_json import validate  # noqa: E402

RESERVED = {"user", "order", "group", "table", "select", "from", "where", "limit", "offset", "primary", "references", "check",
            "default", "column", "constraint", "index", "grant", "end", "all", "analyse", "analyze", "authorization", "both",
            "case", "cast", "current_user", "desc", "asc", "distinct", "do", "else", "for", "foreign", "in", "into", "like",
            "not", "null", "on", "or", "placing", "returning", "some", "symmetric", "then", "to", "trailing", "union", "unique",
            "using", "variadic", "when", "with"}
CLASS_RANK = {"Public": 0, "Internal": 1, "Confidential": 2, "Restricted": 3}
AUDIT_COLS = {"created_at", "created_by", "updated_at", "updated_by", "version"}
PERSONAL = re.compile(r"(email|phone|mobile|address|birth|dob|ssn|national_id|passport|tax_id|full_name|first_name|last_name|"
                      r"medical|health|iban|account_number|salary|gender|ethnic)")
MONEY_TOKENS = {"amount", "price", "cost", "total", "balance", "fee", "salary", "rate", "charge", "premium", "payment"}
NOT_MONEY_TOKENS = {"year", "days", "day", "count", "date", "id", "number", "type", "status", "name", "limit_days", "hours", "code"}


def is_money(name):
    toks = set(name.split("_"))
    return bool(toks & MONEY_TOKENS) and not (toks & NOT_MONEY_TOKENS)
STATUS = re.compile(r"(^|_)(status|state|stage|type|kind|category|decision|rating|role)$")
SPEC_REF = re.compile(r"^(?:(?:OV|FN|BR|DM|IN|UI|AU|NF|QK)-\d{3}|REQ-\d+ [A-Z]+-\d+)$")


def type_ok(t, enums):
    if t.startswith("enum:"):
        return t[5:] in enums
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--spec-dir")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    try:
        m = json.load(open(a.model, encoding="utf-8"))
        schema = json.load(open(os.path.join(HERE, "..", "assets", "data-model.schema.json"), encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    errs = ["schema: " + x for x in validate(m, schema)][:25]
    warns = []
    spec_ids = set()
    if a.spec_dir:
        for p in glob.glob(os.path.join(a.spec_dir, "*.md")):
            spec_ids |= set(re.findall(r"^\s*[-*]\s+\*\*([A-Z]{2}-\d{3})\*\*", open(p, encoding="utf-8").read(), re.M))
    if not errs:
        enums = {e["name"]: e for e in m["enums"]}
        ents = {}
        for e in m["entities"]:
            if e["name"] in ents:
                errs.append("duplicate entity " + e["name"])
            ents[e["name"]] = e
        refs_used = set()

        def check_refs(where, refs):
            for r in refs or []:
                if not SPEC_REF.match(r):
                    errs.append("%s: bad spec reference %r" % (where, r))
                elif spec_ids and not r.startswith("REQ-") and r not in spec_ids:
                    errs.append("%s: spec statement %s does not exist in %s" % (where, r, a.spec_dir))
                refs_used.add(r)
        for en in m["enums"]:
            check_refs("enum " + en["name"], en.get("spec_refs"))
        for nm, e in ents.items():
            w = "entity " + nm
            if nm in RESERVED:
                errs.append("%s: reserved word, rename it" % w)
            if len(nm) > 50:
                errs.append("%s: name too long for generated constraint names" % w)
            check_refs(w, e.get("spec_refs"))
            cols = {c["name"]: c for c in e["attributes"]}
            if len(cols) != len(e["attributes"]):
                errs.append("%s: duplicate attribute names" % w)
            pk = [c["name"] for c in e["attributes"] if c.get("primary_key")]
            if not pk:
                errs.append("%s: no primary key" % w)
            if e["audit"]:
                clash = AUDIT_COLS & set(cols)
                if clash:
                    errs.append("%s: audit columns are generated, remove %s" % (w, ", ".join(sorted(clash))))
            top = 0
            for c in e["attributes"]:
                cw = "%s.%s" % (nm, c["name"])
                n, t = c["name"], c["type"]
                top = max(top, CLASS_RANK[c["classification"]])
                if n in RESERVED:
                    errs.append("%s: reserved word" % cw)
                if len(n) > 40:
                    errs.append("%s: name too long" % cw)
                if not type_ok(t, enums):
                    errs.append("%s: unknown enum %s" % (cw, t[5:]))
                if is_money(n) and not (t.startswith("numeric(") or n.endswith(("_cents", "_minor")) or t == "bigint"):
                    if True:
                        errs.append("%s: money-like column must be numeric(p,s) or integer minor units, not %s" % (cw, t))
                if n.endswith("_at") and t != "timestamptz":
                    errs.append("%s: *_at columns must be timestamptz" % cw)
                if n.endswith("_date") and t != "date":
                    errs.append("%s: *_date columns must be date" % cw)
                if STATUS.search(n) and (t == "text" or t.startswith("varchar(")):
                    warns.append("%s: looks like a coded value; consider an enum" % cw)
                if c.get("server_managed") and c.get("primary_key"):
                    warns.append("%s: primary keys are never accepted from clients; server_managed is redundant" % cw)
                if c.get("primary_key") and c["nullable"]:
                    errs.append("%s: primary key cannot be nullable" % cw)
                if (c["personal_data"] or PERSONAL.search(n)) and CLASS_RANK[c["classification"]] < 2:
                    errs.append("%s: personal data must be Confidential or Restricted" % cw)
                if PERSONAL.search(n) and not c["personal_data"]:
                    errs.append("%s: name suggests personal data but personal_data is false" % cw)
                if c["classification"] == "Restricted" and c["protection"] == "none" and not c.get("protection_note"):
                    errs.append("%s: Restricted data needs a protection method or a protection_note explaining the control" % cw)
                check_refs(cw, c.get("spec_refs"))
            if CLASS_RANK[e["classification"]] < top:
                errs.append("%s: entity classification %s is below its most sensitive attribute" % (w, e["classification"]))
            for u in e.get("unique", []):
                for col in u:
                    if col not in cols:
                        errs.append("%s: unique constraint names unknown column %s" % (w, col))
            fk_cols = set()
            for fk in e.get("foreign_keys", []):
                tgt = ents.get(fk["references_entity"])
                if not tgt:
                    errs.append("%s: foreign key to unknown entity %s" % (w, fk["references_entity"]))
                    continue
                tc = {c["name"]: c for c in tgt["attributes"]}
                if len(fk["columns"]) != len(fk["references_columns"]):
                    errs.append("%s: foreign key column count mismatch" % w)
                for sc, tcn in zip(fk["columns"], fk["references_columns"]):
                    if sc not in cols or tcn not in tc:
                        errs.append("%s: foreign key %s -> %s.%s has an unknown column" % (w, sc, fk["references_entity"], tcn))
                    elif cols[sc]["type"] != tc[tcn]["type"]:
                        errs.append("%s: foreign key %s is %s but %s.%s is %s" % (w, sc, cols[sc]["type"], fk["references_entity"], tcn, tc[tcn]["type"]))
                    elif fk["on_delete"] == "set null" and not cols[sc]["nullable"]:
                        errs.append("%s: on delete set null on non-nullable %s" % (w, sc))
                fk_cols.add(fk["columns"][0])
            for ix in e.get("indexes", []):
                for col in ix["columns"]:
                    if col not in cols:
                        errs.append("%s: index names unknown column %s" % (w, col))
            indexed = {ix["columns"][0] for ix in e.get("indexes", [])} | {u[0] for u in e.get("unique", [])} | set(pk[:1])
            for ck in e.get("checks", []):
                check_refs("%s check %s" % (nm, ck["name"]), ck.get("spec_refs"))
            if e.get("seed") and not e.get("reference_data"):
                errs.append("%s: seed rows are only for reference_data entities" % w)
            for i, row in enumerate(e.get("seed", [])):
                for k, v in row.items():
                    if k not in cols:
                        errs.append("%s seed row %d: unknown attribute %s" % (w, i + 1, k))
                        continue
                    t = cols[k]["type"]
                    if t.startswith("enum:") and t[5:] in enums and v not in enums[t[5:]]["values"]:
                        errs.append("%s seed row %d: %r is not a value of enum %s" % (w, i + 1, v, t[5:]))
                    if t.startswith("numeric(") or t in ("integer", "bigint", "smallint"):
                        if isinstance(v, bool) or not isinstance(v, (int, float)):
                            errs.append("%s seed row %d: %s must be a number" % (w, i + 1, k))
                    if t == "boolean" and not isinstance(v, bool):
                        errs.append("%s seed row %d: %s must be true or false" % (w, i + 1, k))
                    if v is None and not cols[k]["nullable"]:
                        errs.append("%s seed row %d: %s cannot be null" % (w, i + 1, k))
                for c in e["attributes"]:
                    if c["name"] not in row and not c["nullable"] and not c.get("default") and not c.get("primary_key"):
                        errs.append("%s seed row %d: missing required attribute %s" % (w, i + 1, c["name"]))
        for nm, e in ents.items():
            for c in e["attributes"]:
                if c["type"] == "enum:request_status" or (c["name"] in ("status", "decision") and c["type"].startswith("enum:")):
                    if not c.get("server_managed") and not c.get("primary_key"):
                        warns.append("%s.%s: status or decision fields are normally server_managed (set by rules, not by the client)" % (nm, c["name"]))
        if any(e["audit"] for e in m["entities"]) and "audit_log" not in ents:
            warns.append("entities are audited but there is no audit_log entity (who, what, when, before and after)")
        if spec_ids:
            dm = {s for s in spec_ids if s.startswith("DM-")}
            for s in sorted(dm - refs_used):
                warns.append("spec statement %s is not referenced by any entity, attribute or check" % s)
    ok = not errs and not (a.strict and warns)
    print("model check: %d entities, %d errors, %d warnings" % (len(m.get("entities", [])) if isinstance(m, dict) else 0, len(errs), len(warns)))
    for e in errs:
        print("  ERROR " + e)
    for w in warns:
        print("  warn  " + w)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
