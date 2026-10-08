# Operations

## Observability
- Health: actuator `health` with liveness and readiness probes enabled; `info`; metrics through Micrometer (Prometheus endpoint or OTLP). Expose only the endpoints you need; never `*`.
- Logs: structured (`logging.structured.format.console`), one line per event, trace and correlation ids included, no personal data, no payloads.
- Traces: OpenTelemetry through Boot's support; propagate headers on outbound calls.
- Business metrics worth having: requests by outcome, approvals and rejections, rule violations, audit rows written.

## Resilience
- Timeouts on every outbound call (connect and read); a `RestClient` bean with explicit timeouts, not a default.
- Retries only for idempotent calls: `@Retryable` (Framework 7) with a small maximum and backoff; `@ConcurrencyLimit` to protect scarce resources.
- Fail visibly: a failed dependency is an error response, never a fabricated value.
- Graceful shutdown (`server.shutdown=graceful`) and a termination grace period that matches `spring.lifecycle.timeout-per-shutdown-phase`.

## Runtime
- Virtual threads (`spring.threads.virtual.enabled=true`, Java 21+) simplify blocking code; size the database pool, and avoid long synchronized blocks that pin carrier threads.
- Container: non-root user, JRE-only base image with a pinned tag, `-XX:MaxRAMPercentage`, no secrets baked in. Spring Boot's buildpacks (`mvn spring-boot:build-image`) are an alternative to the Dockerfile.
- Configuration: environment variables from the platform; `DB_URL`, `DB_USERNAME`, `DB_PASSWORD`, `OIDC_ISSUER_URI` in the template.

## Release
- The pipeline builds, tests (with Docker for Testcontainers), scans dependencies and secrets, runs `java_check.py`, builds the image and deploys from the pipeline only.
- Database changes ship as migrations in the same release; keep application versions compatible with the previous schema for one release (expand then contract).
- A runbook covers: how to see health, where logs and traces are, how to roll back, what each alert means, who owns the service, and recovery objectives from the intake.
