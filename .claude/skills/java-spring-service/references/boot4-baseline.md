# Spring Boot 4 baseline

Facts below come from the Spring Boot 4.0 and 4.1 release notes and migration guides as of mid-2026. Check the release notes for the exact patch you pin; where this file says "verify", the detail was not confirmed against primary documentation.

## Versions
- Spring Boot 4.0 shipped in November 2025 on Spring Framework 7. Spring Boot 4.1.0 shipped on 10 June 2026. New services should start on the latest 4.1.x patch. The template pins `4.1.0`; replace it with the newest patch from Maven Central before building.
- Java: baseline 17, Java 21 or later recommended (virtual threads), Java 25 (LTS) supported. The template defaults to 21; use the organisation's standard JDK.
- Jakarta EE 11, Servlet 6.1, Spring Security 7, Hibernate ORM 7 (verify the exact version in the dependency tree), Jackson 3.
- 4.1 removed things deprecated in 4.0 (for example the `layertools` jar mode, now `tools`), so do not copy 4.0-era snippets that use deprecated settings.

## Starters (modular)
| Need | Dependency |
|---|---|
| REST with Spring MVC | `spring-boot-starter-webmvc` (not `spring-boot-starter-web`) |
| Validation, JPA, Security, Actuator | `spring-boot-starter-validation`, `-data-jpa`, `-security`, `-actuator` |
| JWT resource server | `spring-boot-starter-oauth2-resource-server` |
| Flyway migrations | `spring-boot-starter-flyway` plus `org.flywaydb:flyway-database-postgresql`; PostgreSQL driver `org.postgresql:postgresql` |
| Tests | one test starter per technology under test: `spring-boot-starter-webmvc-test`, `-data-jpa-test`, `-security-test` |
| Testcontainers | `spring-boot-testcontainers` plus `org.testcontainers:testcontainers-postgresql` and `testcontainers-junit-jupiter` |
| Compatibility bridge | `spring-boot-starter-test-classic` and `-classic` restore the old monolithic classpath temporarily; do not use in new code |

Renames in Boot 4 migration guides include `spring-boot-starter-web` to `-webmvc` and `-json` to `-jackson`; AOP also changed name in some guides (verify before using it).

## Code-level changes that break Boot 3 habits
- **Jackson 3.** Packages move from `com.fasterxml.jackson.databind` to `tools.jackson.databind`; Maven groups move to `tools.jackson...`. The annotations stay in `com.fasterxml.jackson.annotation` (`@JsonValue`, `@JsonCreator`). Boot auto-configures a `JsonMapper`. Jackson 3 exceptions are unchecked. Property prefixes changed (for example `spring.jackson.json.read.*`; 4.1 adds common `spring.jackson.read.*` and `write.*`).
- **Tests.** `@MockBean` and `@SpyBean` are replaced by `@MockitoBean` and `@MockitoSpyBean` (`org.springframework.test.context.bean.override.mockito`). Test slices live in modular packages, for example `org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest`; do not copy Boot 3 imports. Prefer `MockMvcTester` (AssertJ style) for MVC tests; `RestTestClient` arrives with Framework 7 (verify).
- **Testcontainers 2.** Artifacts are `testcontainers-postgresql` etc., and the container class is `org.testcontainers.postgresql.PostgreSQLContainer`. `@ServiceConnection` is still `org.springframework.boot.testcontainers.service.connection.ServiceConnection`.
- **Null safety** uses JSpecify (`org.jspecify.annotations.NullMarked`, `@Nullable`) instead of Spring's own annotations.
- **Resilience in core.** `@Retryable`, `@ConcurrencyLimit` and `@EnableResilientMethods` are part of Spring Framework 7; Spring Retry is no longer needed for the basics (verify the package: `org.springframework.resilience.annotation`).
- **API versioning.** `@RequestMapping(version = "1")` with path, header, query-parameter or media-type strategies, configured through an `ApiVersionConfigurer` (verify property names for your 4.x).
- **HTTP clients.** Use `RestClient` or declarative `@HttpExchange` interfaces, registered with `@ImportHttpServices`. Boot 4.1 adds `InetAddressFilter` to block SSRF through auto-configured clients.
- **Observability.** Micrometer plus OpenTelemetry (Boot provides a starter and `management.opentelemetry.*` properties). Structured logging: `logging.structured.format.console`.
- **Virtual threads.** `spring.threads.virtual.enabled=true` on Java 21+.

## Do not
Copy a Boot 3 blog post's dependencies or imports without checking them against this file and the compiler. Pin versions through the Spring Boot BOM; add an explicit version only for libraries the BOM does not manage (the template does this for ArchUnit).
