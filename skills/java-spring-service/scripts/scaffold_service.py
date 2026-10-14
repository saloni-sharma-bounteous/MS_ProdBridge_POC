#!/usr/bin/env python3
"""Scaffold a Spring Boot 4 service from a data model: build file, security, error handling, auditing,
entities, repositories, DTOs, services, controllers, Flyway migration, and tests.

The output is a starting point, not a finished service. Business rules from the spec are left as
TODO(spec ...) markers and disabled test stubs. Sensitive and server-managed fields are protected by default:
  - request DTOs never contain primary keys, audit columns or attributes marked server_managed
  - response DTOs omit Restricted personal data unless listed under expose_restricted in service.json
  - controllers require authentication and carry a marker where the role rule from the spec must go

Usage: python3 scaffold_service.py --config service.json --out services/ [--ddl schema.sql] [--force]
service.json: {"service": {"name","group_id","package","java_version","boot_version","description"},
               "model": "path/to/data-model.json", "expose": ["entity", ...], "expose_restricted": ["entity.attr", ...],
               "rules": [{"id": "BR-002", "text": "..."}]}
Templates live in ../assets/templates and can be replaced with the organisation's own.
Python 3.8+, standard library only. The generated Java is not compiled here: build it with Maven first.
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = os.path.join(HERE, "..", "assets", "templates")
JAVA_WORDS = {"abstract", "assert", "boolean", "break", "byte", "case", "catch", "char", "class", "const", "continue", "default", "do",
              "double", "else", "enum", "extends", "final", "finally", "float", "for", "goto", "if", "implements", "import",
              "instanceof", "int", "interface", "long", "native", "new", "package", "private", "protected", "public", "return",
              "short", "static", "strictfp", "super", "switch", "synchronized", "this", "throw", "throws", "transient", "try",
              "void", "volatile", "while", "record", "var", "yield"}


def camel(s):
    p = s.split("_")
    out = p[0] + "".join(x[:1].upper() + x[1:] for x in p[1:])
    return out + "_" if out in JAVA_WORDS else out


def pascal(s):
    return "".join(x[:1].upper() + x[1:] for x in re.split(r"[_\-]", s))


def kebab_plural(s):
    k = s.replace("_", "-")
    return k if k.endswith("s") else k + "s"


def render(name, subs):
    text = open(os.path.join(TPL, name), encoding="utf-8").read()
    for k, v in subs.items():
        text = text.replace("{{" + k + "}}", v)
    left = re.findall(r"\{\{(\w+)\}\}", text)
    if left:
        raise SystemExit("template %s has unresolved placeholders: %s" % (name, ", ".join(sorted(set(left)))))
    return text


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def jtype(a, imports):
    t = a["type"]
    if t == "uuid":
        imports.add("java.util.UUID")
        return "UUID"
    if t in ("text", "jsonb") or t.startswith("varchar("):
        return "String"
    if t == "integer":
        return "Integer"
    if t == "bigint":
        return "Long"
    if t == "smallint":
        return "Short"
    if t == "boolean":
        return "Boolean"
    if t == "date":
        imports.add("java.time.LocalDate")
        return "LocalDate"
    if t == "timestamptz":
        imports.add("java.time.Instant")
        return "Instant"
    if t.startswith("numeric("):
        imports.add("java.math.BigDecimal")
        return "BigDecimal"
    if t.startswith("enum:"):
        return pascal(t[5:])
    raise SystemExit("unsupported type " + t)


def default_literal(a, jt):
    d = a.get("default")
    if not d or a.get("primary_key"):
        return None
    d = d.strip()
    if a["type"].startswith("enum:") and d.startswith("'"):
        return "%s.%s" % (jt, d.strip("'").upper())
    if a["type"] == "boolean" and d in ("true", "false"):
        return d
    if jt == "BigDecimal" and re.match(r"^-?\d+(\.\d+)?$", d.strip("'")):
        return 'new BigDecimal("%s")' % d.strip("'")
    if jt in ("Integer", "Long", "Short") and re.match(r"^-?\d+$", d):
        return d + ("L" if jt == "Long" else "")
    if jt == "String" and d.startswith("'"):
        return '"%s"' % d.strip("'")
    return None


def gen_enum(pkg, e):
    name = pascal(e["name"])
    consts = ",\n".join('    %s("%s")' % (v.upper(), v) for v in e["values"])
    enum_src = """package %s.domain;

import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

/** %s */
public enum %s {
%s;

    private final String dbValue;

    %s(String dbValue) {
        this.dbValue = dbValue;
    }

    @JsonValue
    public String dbValue() {
        return dbValue;
    }

    @JsonCreator
    public static %s fromDb(String value) {
        for (%s v : values()) {
            if (v.dbValue.equals(value)) {
                return v;
            }
        }
        throw new IllegalArgumentException("Unknown %s: " + value);
    }
}
""" % (pkg, e.get("description", name), name, consts, name, name, name, e["name"])
    conv = """package %s.domain;

import jakarta.persistence.AttributeConverter;
import jakarta.persistence.Converter;

@Converter(autoApply = true)
public class %sConverter implements AttributeConverter<%s, String> {

    @Override
    public String convertToDatabaseColumn(%s value) {
        return value == null ? null : value.dbValue();
    }

    @Override
    public %s convertToEntityAttribute(String value) {
        return value == null ? null : %s.fromDb(value);
    }
}
""" % (pkg, name, name, name, name, name)
    return name, enum_src, conv


def gen_entity(pkg, e):
    cls = pascal(e["name"])
    imports = {"jakarta.persistence.Entity", "jakarta.persistence.Table", "jakarta.persistence.Column", "jakarta.persistence.Id",
               "jakarta.persistence.GeneratedValue", "jakarta.persistence.GenerationType"}
    fields, accessors = [], []
    for a in e["attributes"]:
        jt = jtype(a, imports)
        n = camel(a["name"])
        col = ['name = "%s"' % a["name"]]
        if not a["nullable"] and not a.get("primary_key"):
            col.append("nullable = false")
        t = a["type"]
        if t.startswith("varchar("):
            col.append("length = %s" % re.search(r"\((\d+)\)", t).group(1))
        if t.startswith("numeric("):
            p, s = re.search(r"\((\d+),(\d+)\)", t).groups()
            col.append("precision = %s" % p)
            col.append("scale = %s" % s)
        ann = []
        if a.get("primary_key"):
            ann += ["    @Id", "    @GeneratedValue(strategy = GenerationType.UUID)"]
        if t == "jsonb":
            imports.update({"org.hibernate.annotations.JdbcTypeCode", "org.hibernate.type.SqlTypes"})
            ann.append("    @JdbcTypeCode(SqlTypes.JSON)")
            col.append('columnDefinition = "jsonb"')
        ann.append("    @Column(%s)" % ", ".join(col))
        init = default_literal(a, jt)
        decl = "    private %s %s%s;" % (jt, n, " = " + init if init else "")
        fields.append("\n".join(ann + [decl]))
        up = n[:1].upper() + n[1:]
        accessors.append("    public %s get%s() {\n        return %s;\n    }" % (jt, up, n))
        if not a.get("primary_key"):
            accessors.append("    public void set%s(%s %s) {\n        this.%s = %s;\n    }" % (up, jt, n, n, n))
    ext = " extends AuditedEntity" if e["audit"] else ""
    imp = "\n".join("import %s;" % i for i in sorted(imports))
    return cls, """package %s.domain;

%s

@Entity
@Table(name = "%s")
public class %s%s {

%s

    protected %s() {
        // for JPA
    }

%s

    @Override
    public boolean equals(Object o) {
        if (this == o) {
            return true;
        }
        if (!(o instanceof %s other)) {
            return false;
        }
        return id != null && id.equals(other.id);
    }

    @Override
    public int hashCode() {
        return getClass().hashCode();
    }
}
""" % (pkg, imp, e["name"], cls, ext, "\n\n".join(fields), cls, "\n\n".join(accessors), cls)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True, help="folder that will contain <artifact>/")
    ap.add_argument("--ddl", help="single schema.sql from data-model-design, copied in as V1__init.sql")
    ap.add_argument("--migrations", help="folder of Flyway V*.sql scripts from data-model-design (generate_ddl.py --flyway-dir), copied as they are")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    try:
        cfg = json.load(open(a.config, encoding="utf-8"))
        model = json.load(open(os.path.join(os.path.dirname(os.path.abspath(a.config)), cfg["model"]), encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        print("ERROR: " + str(exc), file=sys.stderr)
        return 2
    s = cfg["service"]
    pkg = s["package"]
    artifact = s["name"]
    subs = {"package": pkg, "group_id": s.get("group_id", pkg.rsplit(".", 1)[0]), "artifact_id": artifact,
            "java_version": str(s.get("java_version", 21)), "boot_version": s.get("boot_version", "4.1.0"),
            "description": s.get("description", artifact), "app_class": pascal(artifact) + "Application"}
    root = os.path.join(a.out, artifact)
    if os.path.exists(root) and not a.force:
        print("ERROR: %s exists (use --force to overwrite)" % root, file=sys.stderr)
        return 2
    if os.path.exists(root):
        shutil.rmtree(root)
    pp = pkg.replace(".", "/")
    main_java = os.path.join(root, "src/main/java", pp)
    test_java = os.path.join(root, "src/test/java", pp)
    files = 0

    def put(path, text):
        nonlocal files
        write(path, text)
        files += 1
    for tpl, dest in (("pom.xml.tpl", "pom.xml"), ("Dockerfile.tpl", "Dockerfile"), ("gitignore.tpl", ".gitignore"), ("README.md.tpl", "README.md"),
                      ("application.yml.tpl", "src/main/resources/application.yml")):
        put(os.path.join(root, dest), render(tpl, subs))
    put(os.path.join(main_java, subs["app_class"] + ".java"), render("Application.java.tpl", subs))
    for tpl, sub in (("SecurityConfig", "config"), ("AuditingConfig", "config"), ("ApiExceptionHandler", "config"),
                     ("NotFoundException", "service")):
        put(os.path.join(main_java, sub, tpl + ".java"), render(tpl + ".java.tpl", subs))
    if any(e["audit"] for e in model["entities"]):
        put(os.path.join(main_java, "domain", "AuditedEntity.java"), render("AuditedEntity.java.tpl", subs))
    for tpl in ("TestcontainersConfiguration", "TestApplication", "ApplicationTests", "ArchitectureTest"):
        put(os.path.join(test_java, tpl + ".java"), render(tpl + ".java.tpl", subs))
    enum_names = {}
    for en in model["enums"]:
        name, src, conv = gen_enum(pkg, en)
        enum_names[en["name"]] = name
        put(os.path.join(main_java, "domain", name + ".java"), src)
        put(os.path.join(main_java, "domain", name + "Converter.java"), conv)
    ents = {e["name"]: e for e in model["entities"]}
    has_audit_log = "audit_log" in ents and {"entity_name", "entity_id", "action", "actor", "occurred_at"} <= {x["name"] for x in ents["audit_log"]["attributes"]}
    expose = [x for x in cfg.get("expose", []) if x in ents]
    reveal = set(cfg.get("expose_restricted", []))
    for e in model["entities"]:
        for at in e["attributes"]:
            if at.get("primary_key") and "," in at["name"]:
                raise SystemExit("composite keys are not scaffolded; add them by hand")
        if sum(1 for at in e["attributes"] if at.get("primary_key")) != 1:
            raise SystemExit("entity %s needs exactly one primary key attribute for scaffolding" % e["name"])
        cls, src = gen_entity(pkg, e)
        put(os.path.join(main_java, "domain", cls + ".java"), src)
        put(os.path.join(main_java, "repository", cls + "Repository.java"),
            "package %s.repository;\n\nimport java.util.UUID;\n\nimport org.springframework.data.jpa.repository.JpaRepository;\n\nimport %s.domain.%s;\n\npublic interface %sRepository extends JpaRepository<%s, UUID> {\n}\n" % (pkg, pkg, cls, cls, cls))
    todos = 0
    for en in expose:
        e = ents[en]
        cls = pascal(en)
        imp_resp, imp_req = set(), set()
        resp_fields, req_fields, set_lines, todo_lines, omitted = [], [], [], [], []
        for at in e["attributes"]:
            jt = jtype(at, imp_resp)
            jtype(at, imp_req)
            n = camel(at["name"])
            up = n[:1].upper() + n[1:]
            restricted_pd = at["classification"] == "Restricted" and at["personal_data"] and ("%s.%s" % (en, at["name"])) not in reveal
            if restricted_pd:
                omitted.append(at["name"])
            else:
                resp_fields.append("%s %s" % (jt, n))
            if at.get("primary_key") or at.get("server_managed"):
                if at.get("server_managed") and not at["nullable"] and not default_literal(at, jt):
                    todo_lines.append("        // TODO(spec): %s is set by the service (not the client); set it before saving." % n)
                    todos += 1
                continue
            ann = []
            if not at["nullable"]:
                ann.append("@NotNull")
                imp_req.add("jakarta.validation.constraints.NotNull")
            if at["type"].startswith("varchar("):
                ann.append("@Size(max = %s)" % re.search(r"\((\d+)\)", at["type"]).group(1))
                imp_req.add("jakarta.validation.constraints.Size")
            if at["type"].startswith("numeric("):
                p, sc = re.search(r"\((\d+),(\d+)\)", at["type"]).groups()
                ann.append("@Digits(integer = %d, fraction = %s)" % (int(p) - int(sc), sc))
                imp_req.add("jakarta.validation.constraints.Digits")
            req_fields.append("%s %s %s" % (" ".join(ann), jt, n) if ann else "%s %s" % (jt, n))
            set_lines.append("        entity.set%s(request.%s());" % (up, n))
        if e["audit"]:
            imp_resp.add("java.time.Instant")
            resp_fields += ["Instant createdAt", "Instant updatedAt", "long version"]
        dto_dir = os.path.join(main_java, "dto")
        put(os.path.join(dto_dir, cls + "Response.java"),
            "package %s.dto;\n\n%s\n%s\n/**\n * API response for %s. %s%s\n */\npublic record %sResponse(\n    %s) {\n}\n" % (
                pkg, "\n".join("import %s;" % i for i in sorted(imp_resp)) + ("\n" if imp_resp else ""),
                "import %s.domain.*;\n" % pkg if any(x.startswith("enum:") for x in (at["type"] for at in e["attributes"])) else "", en, e["description"],
                (" Omitted on purpose (Restricted personal data): %s." % ", ".join(omitted)) if omitted else "", cls, ",\n    ".join(resp_fields)))
        put(os.path.join(dto_dir, "Create%sRequest.java" % cls),
            "package %s.dto;\n\n%s\n%s\n/** Fields a client may set. Keys, audit columns and server-managed fields are never accepted. */\npublic record Create%sRequest(%s) {\n}\n" % (
                pkg, "\n".join("import %s;" % i for i in sorted(imp_req)) + ("\n" if imp_req else ""),
                "import %s.domain.*;\n" % pkg if any(x.startswith("enum:") for x in (at["type"] for at in e["attributes"])) else "", cls, ("\n    " + ",\n    ".join(req_fields)) if req_fields else ""))
        getters = []
        for at in e["attributes"]:
            n = camel(at["name"])
            up = n[:1].upper() + n[1:]
            if at["name"] in omitted:
                continue
            getters.append("            entity.get%s()" % up)
        if e["audit"]:
            getters += ["            entity.getCreatedAt()", "            entity.getUpdatedAt()", "            entity.getVersion()"]
        audit_call = ""
        audit_ctor = ""
        audit_field = ""
        if has_audit_log:
            audit_field = "    private final AuditTrail auditTrail;\n"
            audit_call = '        auditTrail.record("%s", saved.getId(), "create");\n' % en
        service_src = """package %(pkg)s.service;

import java.util.UUID;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import %(pkg)s.domain.%(cls)s;
import %(pkg)s.dto.Create%(cls)sRequest;
import %(pkg)s.dto.%(cls)sResponse;
import %(pkg)s.repository.%(cls)sRepository;

/** Business rules for %(en)s belong here, not in the controller. %(desc)s */
@Service
public class %(cls)sService {

    private final %(cls)sRepository repository;
%(audit_field)s
    public %(cls)sService(%(cls)sRepository repository%(audit_param)s) {
        this.repository = repository;
%(audit_assign)s    }

    @Transactional(readOnly = true)
    public Page<%(cls)sResponse> list(Pageable pageable) {
        return repository.findAll(pageable).map(%(cls)sService::toResponse);
    }

    @Transactional(readOnly = true)
    public %(cls)sResponse get(UUID id) {
        return repository.findById(id).map(%(cls)sService::toResponse)
            .orElseThrow(() -> new NotFoundException("%(cls)s", id));
    }

    @Transactional
    public %(cls)sResponse create(Create%(cls)sRequest request) {
        %(cls)s entity = new %(cls)s();
%(sets)s
%(todos)s        // TODO(spec): apply the business rules for creating a %(en)s here, and cover them with tests.
        %(cls)s saved = repository.save(entity);
%(audit_call)s        return toResponse(saved);
    }

    static %(cls)sResponse toResponse(%(cls)s entity) {
        return new %(cls)sResponse(
%(getters)s);
    }
}
""" % {"pkg": pkg, "cls": cls, "desc": e["description"], "audit_field": audit_field, "audit_param": ", AuditTrail auditTrail" if has_audit_log else "",
       "audit_assign": "        this.auditTrail = auditTrail;\n" if has_audit_log else "", "sets": "\n".join(set_lines), "todos": ("\n".join(todo_lines) + "\n") if todo_lines else "",
       "en": en, "audit_call": audit_call, "getters": ",\n".join(getters)}
        service_src = service_src.replace("import %s.domain.%s;" % (pkg, cls), "import %s.domain.%s;" % (pkg, cls))
        if has_audit_log:
            service_src = service_src.replace("import %s.dto." % pkg, "import %s.dto." % pkg, 1)
        put(os.path.join(main_java, "service", cls + "Service.java"), service_src)
        base = "/api/v1/" + kebab_plural(en)
        put(os.path.join(main_java, "api", cls + "Controller.java"), """package %(pkg)s.api;

import java.net.URI;
import java.util.UUID;

import jakarta.validation.Valid;

import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PagedModel;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.support.ServletUriComponentsBuilder;

import %(pkg)s.dto.Create%(cls)sRequest;
import %(pkg)s.dto.%(cls)sResponse;
import %(pkg)s.service.%(cls)sService;

@RestController
@RequestMapping("%(base)s")
public class %(cls)sController {

    private final %(cls)sService service;

    public %(cls)sController(%(cls)sService service) {
        this.service = service;
    }

    // TODO(spec): replace isAuthenticated() with the role and ownership rule from the spec (who may list, read, create).
    @GetMapping
    @PreAuthorize("isAuthenticated()")
    public PagedModel<%(cls)sResponse> list(Pageable pageable) {
        return new PagedModel<>(service.list(pageable));
    }

    @GetMapping("/{id}")
    @PreAuthorize("isAuthenticated()")
    public %(cls)sResponse get(@PathVariable UUID id) {
        return service.get(id);
    }

    @PostMapping
    @PreAuthorize("isAuthenticated()")
    public ResponseEntity<%(cls)sResponse> create(@Valid @RequestBody Create%(cls)sRequest request) {
        %(cls)sResponse created = service.create(request);
        URI location = ServletUriComponentsBuilder.fromCurrentRequest().path("/{id}").buildAndExpand(created.id()).toUri();
        return ResponseEntity.created(location).body(created);
    }
}
""" % {"pkg": pkg, "cls": cls, "base": base})
        todos += 3
    if has_audit_log:
        put(os.path.join(main_java, "service", "AuditTrail.java"), """package %(pkg)s.service;

import java.time.Clock;
import java.util.UUID;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

import %(pkg)s.domain.AuditLog;
import %(pkg)s.repository.AuditLogRepository;

/**
 * Appends to audit_log in the same transaction as the business change (control AUD-01).
 * TODO(spec): record before and after state for updates and decisions; keep Restricted values out of free text.
 */
@Component
public class AuditTrail {

    private final AuditLogRepository repository;
    private final Clock clock;

    public AuditTrail(AuditLogRepository repository, Clock clock) {
        this.repository = repository;
        this.clock = clock;
    }

    @Transactional(propagation = Propagation.MANDATORY)
    public void record(String entityName, UUID entityId, String action) {
        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        AuditLog row = new AuditLog();
        row.setEntityName(entityName);
        row.setEntityId(entityId);
        row.setAction(action);
        row.setActor(auth == null ? "system" : auth.getName());
        row.setOccurredAt(clock.instant());
        repository.save(row);
    }
}
""" % {"pkg": pkg})
    if a.migrations:
        dest = os.path.join(root, "src/main/resources/db/migration")
        os.makedirs(dest, exist_ok=True)
        scripts = sorted(x for x in os.listdir(a.migrations) if re.match(r"V\d+__[\w\-]+\.sql$", x))
        if not scripts:
            raise SystemExit("no V<n>__name.sql scripts in " + a.migrations)
        for x in scripts:
            shutil.copyfile(os.path.join(a.migrations, x), os.path.join(dest, x))
            files += 1
    elif a.ddl:
        mig = os.path.join(root, "src/main/resources/db/migration", "V1__init.sql")
        os.makedirs(os.path.dirname(mig), exist_ok=True)
        shutil.copyfile(a.ddl, mig)
        files += 1
    else:
        print("note: no --migrations or --ddl given; add the Flyway scripts under db/migration before starting the service")
    rules = cfg.get("rules", [])
    if rules:
        body = "\n".join('    @Test\n    @Disabled("Not implemented yet: %s %s")\n    void %s() {\n    }\n' % (r["id"], r["text"].replace('"', "'"), r["id"].lower().replace("-", "_")) for r in rules)
        put(os.path.join(test_java, "BusinessRulesTest.java"),
            "package %s;\n\nimport org.junit.jupiter.api.Disabled;\nimport org.junit.jupiter.api.Test;\n\n/** One test per business rule in the spec. Enable each one as the rule is implemented. */\nclass BusinessRulesTest {\n\n%s}\n" % (pkg, body))
    print("scaffolded %s: %d files, %d entities, %d exposed, %d TODO(spec) markers -> %s" % (artifact, files, len(model["entities"]), len(expose), todos, root))
    print("next: build with Maven, fix anything the compiler reports, then implement the TODO(spec) markers with tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
