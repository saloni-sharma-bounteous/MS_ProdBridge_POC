#!/usr/bin/env python3
"""Generate PostgreSQL DDL (tables, constraints, indexes, comments, row-level security switch) from data-model.json.

Run model_check.py first. Generated rules:
  - enums become varchar(n) with a named CHECK constraint (easy to migrate)
  - audited entities get created_at, created_by, updated_at, updated_by and a version column (optimistic locking)
  - foreign keys are added after all tables exist, so entity order and cycles never matter
  - every table and column gets a COMMENT with its classification and protection, for data catalogues
  - rls: true switches row-level security on (ENABLE and FORCE); policies are written per role separately

Usage: python3 generate_ddl.py --model data-model.json --out schema.sql            (one file, for review)
       python3 generate_ddl.py --model data-model.json --flyway-dir src/main/resources/db/migration [--version 1] [--tooling-dir db]
Flyway mode writes one versioned script per concern, in dependency order:
  V<n>__create_tables.sql            structure: tables, columns, primary keys, uniques, enum and rule checks
  V<n+1>__add_foreign_keys_and_indexes.sql
  V<n+2>__table_and_column_comments.sql   classification, protection and personal-data notes for the data catalogue
  V<n+3>__row_level_security.sql          ENABLE and FORCE (policies are separate, per role)
  V<n+4>__reference_data.sql              seed rows for reference_data entities (only if the model has any)
and, with --tooling-dir, flyway.conf (environment placeholders only) and migrate.sh.
Python 3.8+, standard library only. The SQL is generated, not executed; test it against your database.
"""
import argparse
import json
import os
import re
import sys


def sql_type(t, enums):
    if t.startswith("enum:"):
        vals = enums[t[5:]]["values"]
        return "varchar(%d)" % max(16, max(len(v) for v in vals))
    return t


def q(s):
    return "'" + s.replace("'", "''") + "'"


def sections(m):
    """Return the DDL as ordered (name, sql) parts. The names become the Flyway script descriptions."""
    enums = {e["name"]: e for e in m["enums"]}
    tables, fks, indexes, comments, rls, seeds = [], [], [], [], [], []
    for e in m["entities"]:
        t = e["name"]
        lines = []
        pk = [c["name"] for c in e["attributes"] if c.get("primary_key")]
        for c in e["attributes"]:
            parts = ["  %s %s" % (c["name"], sql_type(c["type"], enums))]
            if not c["nullable"] or c.get("primary_key"):
                parts.append("NOT NULL")
            if c.get("default"):
                parts.append("DEFAULT " + c["default"])
            lines.append(" ".join(parts))
        if e["audit"]:
            lines += ["  created_at timestamptz NOT NULL DEFAULT now()", "  created_by varchar(100) NOT NULL",
                      "  updated_at timestamptz NOT NULL DEFAULT now()", "  updated_by varchar(100) NOT NULL",
                      "  version bigint NOT NULL DEFAULT 0"]
        lines.append("  CONSTRAINT pk_%s PRIMARY KEY (%s)" % (t, ", ".join(pk)))
        for u in e.get("unique", []):
            lines.append("  CONSTRAINT uq_%s_%s UNIQUE (%s)" % (t, "_".join(u), ", ".join(u)))
        for c in e["attributes"]:
            if c["type"].startswith("enum:"):
                vals = ", ".join(q(v) for v in enums[c["type"][5:]]["values"])
                lines.append("  CONSTRAINT ck_%s_%s CHECK (%s IN (%s))" % (t, c["name"], c["name"], vals))
        for ck in e.get("checks", []):
            lines.append("  CONSTRAINT ck_%s_%s CHECK (%s)" % (t, ck["name"], ck["expression"]))
        tables.append("CREATE TABLE %s (\n%s\n);\n" % (t, ",\n".join(lines)))
        for fk in e.get("foreign_keys", []):
            fks.append("ALTER TABLE %s ADD CONSTRAINT fk_%s_%s FOREIGN KEY (%s) REFERENCES %s (%s) ON DELETE %s;" % (
                t, t, "_".join(fk["columns"]), ", ".join(fk["columns"]), fk["references_entity"], ", ".join(fk["references_columns"]), fk["on_delete"].upper()))
        for ix in e.get("indexes", []):
            indexes.append("CREATE %sINDEX ix_%s_%s ON %s (%s);" % ("UNIQUE " if ix.get("unique") else "", t, "_".join(ix["columns"]), t, ", ".join(ix["columns"])))
        for fk in e.get("foreign_keys", []):
            covered = [ix["columns"][:1] for ix in e.get("indexes", [])] + [u[:1] for u in e.get("unique", [])] + [pk[:1]]
            if fk["columns"][:1] not in covered:
                indexes.append("CREATE INDEX ix_%s_%s ON %s (%s);" % (t, "_".join(fk["columns"]), t, ", ".join(fk["columns"])))
        meta = "%s (classification: %s%s%s)" % (e["description"], e["classification"], "; retention: " + e["retention"] if e.get("retention") else "", "; audited" if e["audit"] else "")
        comments.append("COMMENT ON TABLE %s IS %s;" % (t, q(meta)))
        for c in e["attributes"]:
            note = "%s [classification: %s; personal data: %s; protection: %s%s]" % (
                c["description"], c["classification"], "yes" if c["personal_data"] else "no", c["protection"], "; " + c["protection_note"] if c.get("protection_note") else "")
            comments.append("COMMENT ON COLUMN %s.%s IS %s;" % (t, c["name"], q(note)))
        if e.get("rls"):
            rls += ["ALTER TABLE %s ENABLE ROW LEVEL SECURITY;" % t, "ALTER TABLE %s FORCE ROW LEVEL SECURITY;" % t]
        for row in e.get("seed", []):
            cols = [k for k in row]
            vals = [literal(row[k]) for k in cols]
            if e["audit"]:
                cols += ["created_by", "updated_by"]
                vals += ["'flyway'", "'flyway'"]
            seeds.append("INSERT INTO %s (%s) VALUES (%s);" % (t, ", ".join(cols), ", ".join(vals)))
    out = [("create_tables", "\n".join(tables)),
           ("add_foreign_keys_and_indexes", "\n".join(fks + [""] + sorted(set(indexes)))),
           ("table_and_column_comments", "\n".join(comments)),
           ("row_level_security", "-- Row-level security is switched on here; policies are written per role in a separate migration.\n" + "\n".join(rls) if rls else "")]
    if seeds:
        out.append(("reference_data", "-- Reference data owned by the business; change it with a new migration, not by hand.\n" + "\n".join(seeds)))
    return [(n, t.strip() + "\n") for n, t in out if t.strip()]


def literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    return q(str(v))


def header(m):
    return "-- Generated by generate_ddl.py from data-model.json (%s %s). Do not edit by hand; change the model and regenerate.\n" % (m["model"]["name"], m["model"]["version"])


def build(m):
    return header(m) + "\n" + "\n".join(t for _, t in sections(m))


FLYWAY_CONF = """# Flyway command-line settings. The connection (FLYWAY_URL, FLYWAY_USER, FLYWAY_PASSWORD) is read from
# environment variables by Flyway itself, so nothing secret is stored here.
flyway.locations=filesystem:%(loc)s
flyway.validateMigrationNaming=true
flyway.cleanDisabled=true
flyway.baselineOnMigrate=false
"""

MIGRATE_SH = """#!/usr/bin/env bash
# Apply the migrations with the Flyway command-line tool. Set FLYWAY_URL, FLYWAY_USER and FLYWAY_PASSWORD first.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
flyway -configFiles="$here/flyway.conf" info
flyway -configFiles="$here/flyway.conf" validate
flyway -configFiles="$here/flyway.conf" migrate
flyway -configFiles="$here/flyway.conf" info
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out")
    ap.add_argument("--flyway-dir")
    ap.add_argument("--version", type=int, default=1, help="first Flyway version number (default 1)")
    ap.add_argument("--tooling-dir", help="also write flyway.conf and migrate.sh here")
    a = ap.parse_args()
    try:
        m = json.load(open(a.model, encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    if a.flyway_dir:
        os.makedirs(a.flyway_dir, exist_ok=True)
        written = []
        for i, (name, text) in enumerate(sections(m)):
            path = os.path.join(a.flyway_dir, "V%d__%s.sql" % (a.version + i, name))
            open(path, "w", encoding="utf-8").write(header(m) + "\n" + text)
            written.append(os.path.basename(path))
        if a.tooling_dir:
            os.makedirs(a.tooling_dir, exist_ok=True)
            open(os.path.join(a.tooling_dir, "flyway.conf"), "w", encoding="utf-8").write(FLYWAY_CONF % {"loc": os.path.relpath(a.flyway_dir, a.tooling_dir).replace(os.sep, "/")})
            sh = os.path.join(a.tooling_dir, "migrate.sh")
            open(sh, "w", encoding="utf-8").write(MIGRATE_SH)
            os.chmod(sh, 0o755)
        print("Flyway scripts for %d entities -> %s: %s" % (len(m["entities"]), a.flyway_dir, ", ".join(written)))
        return 0
    sql = build(m)
    if not a.out:
        print(sql)
        return 0
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(sql)
    print("DDL for %d entities -> %s" % (len(m["entities"]), a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
