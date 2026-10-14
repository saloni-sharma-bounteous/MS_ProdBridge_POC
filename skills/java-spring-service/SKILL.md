---
name: java-spring-service
description: Build production-grade Java services on Spring Boot 4 (Java 21+, Spring Security 7, JPA, Flyway, PostgreSQL, Testcontainers). Scaffolds a secure, tested service from a validated data model, then implements spec business rules test-first. Use when asked to build a Spring Boot backend or REST API, or after data-model-design and implementation-plan.
---

# Java Spring Boot 4 service

The prototype proved the idea. This skill builds the real backend: the same behaviour the business agreed, enforced on the server, with security and audit controls built in rather than bolted on.

Do not write Spring Boot from memory of Boot 3. Boot 4 changed starters, test packages, Jackson, Testcontainers and several defaults. Read `references/boot4-baseline.md` first and let the compiler overrule your habits.

## What this skill needs

1. A validated `data-model.json` and its `schema.sql` (from `data-model-design`).
2. The spec (`handoff/spec.md`) for the business rules, and the approved stories (`handoff/stories.json`) for acceptance criteria. Security, audit, masking and limits listed there must be enforced.
4. Decisions from the person: service name, base package, Java version, which entities get endpoints, which Restricted fields may appear in responses, which role may do what. Record them in `service.json`; ask for any that are missing rather than guessing.

## Environment honesty

The scripts here generate and check source files; they do not download dependencies or compile Spring code. The first build happens on a machine with Maven, a JDK and Docker. State what was and was not verified in your report.

## Steps

1. **Write `service.json`** next to the data model. Fields are described in the header of `scripts/scaffold_service.py`. List the spec rules to cover under `rules` (id and one-line text); each becomes a disabled test stub.
2. **Scaffold** (paths relative to this skill's folder):
   ```
   python3 scripts/scaffold_service.py --config <handoff>/service.json --out <repo>/services --migrations <handoff>/data-model/migrations
   java scripts/JavaSyntaxCheck.java <repo>/services/<name>        # parse-only check, needs a JDK
   python3 scripts/java_check.py --root <repo>/services/<name>
   ```
   Fix anything the checkers report before going further. The scaffold is secure by default: request DTOs exclude server-managed fields, responses omit Restricted personal data, every endpoint requires authentication, errors are RFC 9457 problems, `ddl-auto` is `validate`, actuator is limited, and the container runs as non-root.
3. **Build it for real**: `mvn -B verify` (Docker needed for Testcontainers). Fix compile errors against `references/boot4-baseline.md`. Never silence a failing test or loosen a rule to get green.
4. **Implement the rules, tests first.** For each `TODO(spec ...)` marker and each disabled stub in `BusinessRulesTest`:
   - read the spec statement (and its boundary behaviour: inclusive or exclusive limits)
   - write the failing test, including the negative cases (wrong role, wrong owner, same person twice, boundary values)
   - implement the rule in the service (see `references/architecture.md` and `references/security-and-controls.md`)
   - replace `isAuthenticated()` with the real role and ownership rule
   - enable the stub, run the tests
5. **Add what the scaffold cannot know**: update and delete endpoints that the spec requires, approval flows, queries with the filters the screens need, row-level security policies, outbound clients with timeouts, API documentation. Follow `references/persistence.md` and `references/operations.md`.
6. **Check**: run `java_check.py` again (zero errors; each warning explained), then walk `references/checklist.md`. Confirm each relevant control in `references/security-and-controls.md` has its test.
7. **Report** in plain words: what was built, which spec rules are implemented and tested, which are not, what was verified (syntax check, java_check, Maven build and test results) and what was not, and the decisions that remain with the owner.

## Gate: tech lead review

Show the person the package layout, the endpoint list with the role rule on each, the rules implemented with their tests, and the unresolved `TODO(spec)` count. Do not describe a service as production-ready while errors remain, spec rules lack tests, or the Maven build has not been run.

## Rules

- Constructor injection only. No Lombok on entities. No `System.out`. No catch blocks that swallow errors.
- Never accept an identity, owner, status, price or limit from the request body when the server can determine it.
- Every state change is authorised on the server, validated on the server, and audited.
- Secrets come from the environment. Never put a secret, token or personal data in code, tests, fixtures, logs or this report.
- If the spec is silent or contradictory on a rule, ask; do not invent a rule.
- Prefer boring, well-known Spring features over clever ones.

## Output

A service folder under `services/<name>` (source, Flyway migration, tests, Dockerfile, README), `java-check.json` if requested, and a short report. The `understand-anything` skill can map the result for comparison with the prototype it replaces. When the build is done, continue with `release-to-qa`.

## Self-learning

At the end of every run, reflect on what went wrong or was slow, what the user corrected, and what was missing or unclear in this skill. If you find a concrete improvement, do not edit this skill on your own. Instead:

1. Propose it as a short list. For each item give the section affected, the exact change, and the reason (what it prevents next run).
2. Ask the user to approve, edit, or reject each item.
3. Apply only the approved items to this `SKILL.md` (or its scripts, templates or references), keeping edits small. Tell the user what changed.
4. If nothing needs changing, say so in one line. Never record secrets, personal data or one-off project details as lessons.
