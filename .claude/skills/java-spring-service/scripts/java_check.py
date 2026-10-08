#!/usr/bin/env python3
"""Static production-readiness check for a Spring Boot 4 service (source and build files only; nothing is compiled or run).

Catches the mistakes that most often slip through on the way from prototype to production: Spring Boot 3 habits
in a Boot 4 project, secrets in config, entities leaking through the API, floating-point money, field injection,
missing validation, open actuator, CORS wildcards, root containers, missing migrations and tests.

Each finding has a rule id (JV-nnn), severity (error, warn, info), and the standards control it supports.
Usage: python3 java_check.py --root services/leave-service [--json report.json] [--strict]
Exit: 0 no errors (and no warnings with --strict), 1 otherwise, 2 usage/IO error.   Python 3.8+, standard library only.
"""
import argparse
import json
import os
import re
import sys

SKIP = {"target", ".git", "node_modules", ".idea", "build", ".gradle"}
MONEY = r"(?:amount|price|cost|total|balance|fee|salary|rate|premium|payment|charge)"


def strip_comments(t):
    t = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), t, flags=re.S)
    return re.sub(r"//[^\n]*", lambda m: " " * len(m.group(0)), t)


def line_of(t, i):
    return t.count("\n", 0, i) + 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True)
    ap.add_argument("--json")
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    if not os.path.isdir(root):
        print("ERROR: not a folder: " + root, file=sys.stderr)
        return 2
    files = {}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP]
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            if f.endswith((".java", ".xml", ".yml", ".yaml", ".properties", ".sql", ".gradle", ".kts")) or f == "Dockerfile":
                try:
                    files[rel] = open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    pass
    out = []

    def add(rule, sev, control, file, line, msg):
        out.append({"rule": rule, "severity": sev, "control": control, "file": file, "line": line, "message": msg})
    main_java = {r: t for r, t in files.items() if r.endswith(".java") and "/src/test/" not in "/" + r and r.startswith("src/main/")}
    test_java = {r: t for r, t in files.items() if r.endswith(".java") and r.startswith("src/test/")}
    build = {r: t for r, t in files.items() if r in ("pom.xml", "build.gradle", "build.gradle.kts")}
    cfg_main = {r: t for r, t in files.items() if re.match(r"src/main/resources/application[\w\-]*\.(ya?ml|properties)$", r)}
    if not build:
        add("JV-001", "error", "SUP-01", "(project)", 0, "no pom.xml or build.gradle found")
    btxt = "\n".join(build.values())
    m = re.search(r"<parent>.*?spring-boot-starter-parent.*?<version>([^<]+)</version>", btxt, re.S) or \
        re.search(r"org\.springframework\.boot[\"']?\)?\s*(?:version|:)\s*[\"']?(\d+\.\d+\.\d+[\w.\-]*)", btxt)
    if build and (not m or not m.group(1).startswith("4.")):
        add("JV-001", "error", "SUP-01", next(iter(build)), 1, "Spring Boot version is %s; this skill targets Spring Boot 4.x" % (m.group(1) if m else "not found"))
    for r, t in build.items():
        for mm in re.finditer(r"<artifactId>(spring-boot-starter-web)</artifactId>", t):
            add("JV-002", "error", "SUP-01", r, line_of(t, mm.start()), "Boot 3 starter '%s': in Boot 4 use spring-boot-starter-webmvc" % mm.group(1))
        for mm in re.finditer(r"<artifactId>(spring-boot-starter-aop|spring-boot-starter-json)</artifactId>", t):
            add("JV-002", "warn", "SUP-01", r, line_of(t, mm.start()), "starter '%s' was renamed in Boot 4 (see the Boot 4 migration guide for the current name)" % mm.group(1))
        for mm in re.finditer(r"<artifactId>(spring-boot-starter-[\w\-]*classic)</artifactId>", t):
            add("JV-002", "warn", "SUP-01", r, line_of(t, mm.start()), "classic compatibility starter '%s' is a temporary bridge; move to the modular starters" % mm.group(1))
        for mm in re.finditer(r"<groupId>com\.fasterxml\.jackson\.(?:core|datatype|module)</groupId>", t):
            add("JV-003", "error", "SUP-01", r, line_of(t, mm.start()), "Jackson 2 dependency; Boot 4 uses Jackson 3 (groupId tools.jackson...)")
        for mm in re.finditer(r"<artifactId>h2</artifactId>", t):
            add("JV-018", "warn", "QA-01", r, line_of(t, mm.start()), "H2 on the classpath: tests against H2 do not prove PostgreSQL behaviour; use Testcontainers")
    entities = set()
    for r, t in main_java.items():
        c = strip_comments(t)
        for mm in re.finditer(r"@Entity\b[^{]*?\bclass\s+(\w+)", c, re.S):
            entities.add(mm.group(1))
    for r, t in list(main_java.items()) + list(test_java.items()):
        c = strip_comments(t)
        is_test = r.startswith("src/test/")
        for mm in re.finditer(r"import\s+com\.fasterxml\.jackson\.(?!annotation)[\w.]+;", c):
            add("JV-003", "error", "SUP-01", r, line_of(c, mm.start()), "Jackson 2 import; Boot 4 uses tools.jackson (annotations stay in com.fasterxml.jackson.annotation)")
        for mm in re.finditer(r"@(MockBean|SpyBean)\b|org\.springframework\.boot\.test\.autoconfigure\.web\.servlet\.(WebMvcTest|AutoConfigureMockMvc)", c):
            add("JV-004", "error", "QA-01", r, line_of(c, mm.start()), "removed or moved in Boot 4: use @MockitoBean / @MockitoSpyBean and the org.springframework.boot.webmvc.test.autoconfigure package")
        if is_test:
            continue
        for mm in re.finditer(r"@Autowired\s+(?:(?:private|protected|public|final)\s+)*[\w<>\[\],.? ]+\s+\w+\s*;", c):
            add("JV-005", "error", "QA-01", r, line_of(c, mm.start()), "field injection: use constructor injection")
        for mm in re.finditer(r"System\.(?:out|err)\.print|\.printStackTrace\s*\(", c):
            add("JV-006", "error", "DAT-02", r, line_of(c, mm.start()), "console printing: use a logger and never log personal data")
        for mm in re.finditer(r"""(?i)(?:password|secret|api[_-]?key|token)\s*=\s*"[^"$\s]{4,}\"""", c):
            add("JV-009", "error", "SEC-01", r, line_of(c, mm.start()), "hardcoded credential in source (value hidden)")
        for mm in re.finditer(r"@CrossOrigin\s*\(\s*(?:origins\s*=\s*)?\"\*\"|allowedOrigins\s*\(\s*\"\*\"|allowedOriginPatterns\s*\(\s*\"\*\"", c):
            add("JV-013", "error", "APP-04", r, line_of(c, mm.start()), "CORS wildcard: list the exact origins")
        for mm in re.finditer(r"\b(?:double|float|Double|Float)\s+\w*" + MONEY + r"\w*\b", c, re.I):
            add("JV-014", "error", "COM-05", r, line_of(c, mm.start()), "floating point for a money-like value: use BigDecimal")
        for mm in re.finditer(r"\b(?:Instant|LocalDate|LocalDateTime|OffsetDateTime|ZonedDateTime)\.now\(\s*\)|new\s+Date\(\s*\)|System\.currentTimeMillis", c):
            if "Clock" in c and "clock" in c:
                continue
            add("JV-015", "warn", "QA-01", r, line_of(c, mm.start()), "reads the system clock directly: inject a Clock so rules that depend on time can be tested")
        for mm in re.finditer(r"catch\s*\([^)]*\)\s*\{\s*\}", c):
            add("JV-016", "error", "INT-02", r, line_of(c, mm.start()), "empty catch block hides failures")
        for mm in re.finditer(r"catch\s*\(\s*Throwable\b", c):
            add("JV-016", "warn", "INT-02", r, line_of(c, mm.start()), "catching Throwable also catches errors the JVM cannot recover from")
        for mm in re.finditer(r"(?i)\blog(?:ger)?\.(?:info|debug|warn|error|trace)\s*\([^;]*\b(?:password|passwd|secret|token|ssn|medical|nationalid|taxid)\b", c):
            add("JV-023", "warn", "DAT-02", r, line_of(c, mm.start()), "log statement mentions a sensitive field")
        if re.search(r"@Entity\b", c) and re.search(r"@(Data|Getter\s*\n?\s*@Setter|EqualsAndHashCode)\b", c):
            add("JV-022", "warn", "QA-01", r, 1, "Lombok @Data on an entity breaks equals/hashCode and lazy loading; write them by hand")
        if re.search(r"@(?:Rest)?Controller\b", c):
            for mm in re.finditer(r"\b(" + "|".join(sorted(entities)) + r")\b", re.sub(r"(?m)^import .*$", "", c)) if entities else []:
                add("JV-011", "error", "IAM-02", r, line_of(c, mm.start()), "controller uses entity %s directly: return and accept DTOs (mass assignment and data leaks)" % mm.group(1))
            for mm in re.finditer(r"@RequestBody\s+(?!@)", c):
                before = c[max(0, mm.start() - 25):mm.start()]
                if "@Valid" not in before:
                    add("JV-012", "warn", "APP-02", r, line_of(c, mm.start()), "@RequestBody without @Valid: input is not validated")
            for mm in re.finditer(r"import\s+[\w.]*\.repository\.[\w.]+;", c):
                add("JV-024", "error", "QA-01", r, line_of(c, mm.start()), "controller depends on a repository: go through a service")
            for mm in re.finditer(r"@Transactional\b", c):
                add("JV-021", "warn", "QA-01", r, line_of(c, mm.start()), "transactions belong in the service layer")
            for mm in re.finditer(r"@(Post|Put|Delete|Patch)Mapping\b[^{;]*?\n?(?:\s*@[\w]+(?:\([^)]*\))?)*\s*public", c):
                seg = c[max(0, mm.start() - 160):mm.end()]
                if not re.search(r"@(PreAuthorize|Secured|RolesAllowed|PostAuthorize)", seg):
                    add("JV-026", "warn", "IAM-02", r, line_of(c, mm.start()), "state-changing endpoint without method-level authorization")
        for mm in re.finditer(r"TODO\(spec", t):
            add("JV-025", "info", "DOC-01", r, line_of(t, mm.start()), "spec rule still to implement")
    all_main = "\n".join(strip_comments(t) for t in main_java.values())
    if main_java and ("spring-boot-starter-security" not in btxt or "SecurityFilterChain" not in all_main):
        add("JV-017", "error", "IAM-02", "(project)", 0, "no security: add spring-boot-starter-security and a SecurityFilterChain")
    for r, t in main_java.items():
        c = strip_comments(t)
        for mm in re.finditer(r"anyRequest\(\)\s*\.\s*permitAll\(\)", c):
            add("JV-017", "error", "IAM-02", r, line_of(c, mm.start()), "anyRequest().permitAll() leaves the whole API open")
        if "csrf" in c and re.search(r"csrf\([^)]*(disable|ignoring)", c) and "STATELESS" not in c:
            add("JV-017", "warn", "IAM-02", r, 1, "CSRF disabled without a stateless session policy")
    if main_java and "@EnableMethodSecurity" not in all_main and "@EnableGlobalMethodSecurity" not in all_main:
        add("JV-017", "warn", "IAM-02", "(project)", 0, "method security is not enabled: @PreAuthorize annotations would be ignored")
    cfg_all = "\n".join(cfg_main.values())
    for r, t in cfg_main.items():
        for mm in re.finditer(r"ddl-auto\s*[:=]\s*[\"']?(create-drop|create|update)\b", t):
            add("JV-007", "error", "DB-02", r, line_of(t, mm.start()), "Hibernate must not change the schema (ddl-auto %s): migrations own the schema, use 'validate'" % mm.group(1))
        for mm in re.finditer(r"(?im)^\s*(?:[\w.\-]*\.)?(password|secret|client-secret|api-key|token)\s*[:=]\s*(?![\s]*\$\{)[\"']?([^\s\"'#]{3,})", t):
            add("JV-009", "error", "SEC-01", r, line_of(t, mm.start()), "hardcoded %s in configuration (value hidden): read it from the environment or a secret manager" % mm.group(1))
        for mm in re.finditer(r"jdbc:[\w:]+://[^\s/@]+:[^\s/@]+@", t):
            add("JV-009", "error", "SEC-01", r, line_of(t, mm.start()), "credentials embedded in a JDBC URL")
        for mm in re.finditer(r"""exposure\s*[:=]?\s*\n?\s*(?:include\s*[:=]\s*)?["']?\*""", t):
            add("JV-010", "error", "SEC-02", r, line_of(t, mm.start()), "all actuator endpoints exposed: list only health, info and metrics endpoints you need")
    if cfg_main and not re.search(r"ddl-auto\s*[:=]\s*[\"']?validate", cfg_all):
        add("JV-007", "warn", "DB-02", next(iter(cfg_main)), 1, "set spring.jpa.hibernate.ddl-auto to validate so the mapping is checked against the migrations")
    if cfg_main and not re.search(r"open-in-view\s*[:=]\s*[\"']?false", cfg_all):
        add("JV-008", "warn", "QA-01", next(iter(cfg_main)), 1, "set spring.jpa.open-in-view to false")
    if cfg_main and "probes" not in cfg_all:
        add("JV-010", "warn", "OPS-02", next(iter(cfg_main)), 1, "enable health probes (management.endpoint.health.probes.enabled)")
    if cfg_main and "spring-boot-starter-actuator" not in btxt:
        add("JV-010", "warn", "OPS-02", "(project)", 0, "no actuator: health, metrics and probes are missing")
    uses_jpa = "spring-boot-starter-data-jpa" in btxt
    mig = [r for r in files if re.match(r"src/main/resources/db/migration/V\d+(?:_\d+)*__[\w\-]+\.sql$", r)]
    if uses_jpa and not mig:
        add("JV-020", "error", "DB-02", "(project)", 0, "JPA is used but there are no Flyway migrations (src/main/resources/db/migration/V1__...sql)")
    for r in mig:
        for mm in re.finditer(r"(?i)\bdrop\s+(?:table|column)\b", files[r]):
            add("JV-020", "warn", "DB-02", r, line_of(files[r], mm.start()), "destructive migration: confirm a backup and a rollback plan")
    if not test_java:
        add("JV-018", "error", "QA-01", "(project)", 0, "no tests found under src/test/java")
    elif "testcontainers" not in "\n".join(test_java.values()).lower() and "testcontainers" not in btxt.lower():
        add("JV-018", "warn", "QA-01", "(project)", 0, "no Testcontainers: database behaviour is not tested against a real PostgreSQL")
    if test_java:
        n_dis = sum(len(re.findall(r"@Disabled\(", t)) for t in test_java.values())
        if n_dis:
            add("JV-025", "info", "QA-01", "(tests)", 0, "%d disabled test stub(s): business rules from the spec still lack tests" % n_dis)
    if "Dockerfile" in files:
        d = files["Dockerfile"]
        if not re.search(r"(?m)^USER\s+(?!root\b)\S+", d):
            add("JV-019", "warn", "SEC-02", "Dockerfile", 1, "container runs as root: add a non-root USER")
        for mm in re.finditer(r"(?m)^FROM\s+\S+:latest\b", d):
            add("JV-019", "error", "SUP-01", "Dockerfile", line_of(d, mm.start()), "base image tag :latest is not reproducible")
    sev_rank = {"error": 0, "warn": 1, "info": 2}
    out.sort(key=lambda x: (sev_rank[x["severity"]], x["rule"], x["file"], x["line"]))
    n = {s: sum(1 for x in out if x["severity"] == s) for s in sev_rank}
    print("java check: %d errors, %d warnings, %d notes (%d main files, %d test files)" % (n["error"], n["warn"], n["info"], len(main_java), len(test_java)))
    for x in out:
        if x["severity"] != "info":
            print("  %-5s %s [%s] %s:%s %s" % (x["severity"].upper(), x["rule"], x["control"], x["file"], x["line"] or "-", x["message"]))
    if n["info"]:
        print("  note: %d TODO(spec) or disabled-test markers remain (rules to implement)" % n["info"])
    if a.json:
        json.dump({"summary": n, "findings": out}, open(a.json, "w", encoding="utf-8"), indent=1)
    return 1 if n["error"] or (a.strict and n["warn"]) else 0


if __name__ == "__main__":
    sys.exit(main())
