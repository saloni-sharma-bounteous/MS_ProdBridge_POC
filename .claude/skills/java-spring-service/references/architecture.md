# Architecture rules

## Packages and dependencies
`api` (controllers) -> `service` -> `repository` -> `domain`. `dto` records are used by `api` and `service`. `config` holds cross-cutting configuration. Rules enforced by `ArchitectureTest`: controllers never touch repositories or entities; no field injection; no package cycles.

## Controllers
- Translate HTTP to a service call and back. No business rules, no transactions, no repository access.
- Accept and return DTO records only. Entities never cross the API boundary (mass assignment and data leaks).
- `@Valid` on every `@RequestBody`; validation annotations on the DTO. Bean validation is a first line of defence, not the rule engine; business rules live in the service.
- Return `201` with a `Location` header on create, `204` on delete, `404` through `NotFoundException`, `409` for conflicts, `403` and `401` through Spring Security.
- Paginate every list endpoint (`Pageable`, a maximum page size in configuration, `PagedModel` as the response). Never return unbounded lists.
- Version the API in the path (`/api/v1/...`) or with Framework 7 versioning; never change a released response shape in place.

## DTOs and mass assignment
- A request DTO contains only fields a client may set. Primary keys, audit columns, status, computed values, owner identity and anything marked `server_managed` in the data model are set by the service.
- A response DTO omits Restricted personal data unless a role needs it; add a second, richer DTO for those roles rather than a flag.

## Services
- One transaction per use case, opened in the service (`@Transactional`, `readOnly = true` for reads).
- Business rules are plain methods on the service or a small domain class, with no HTTP types, so they can be unit tested without Spring.
- Inject a `Clock` for anything time-dependent. Never call `Instant.now()` in rule code.
- Money and quantities are `BigDecimal` with an explicit scale and `RoundingMode`; never `double`.
- Throw specific exceptions (`NotFoundException`, a `BusinessRuleViolation` mapped to 422 or 409); never return null to signal failure.

## Errors
One `@RestControllerAdvice` returns RFC 9457 `ProblemDetail`. Responses never contain stack traces, SQL, class names or entity ids that the caller cannot see. Unexpected errors are logged with a correlation id that is also returned. A catch-all handler must let Spring Security's `AccessDeniedException` and `AuthenticationException` map to 403 and 401 (the template handles both).

## Idempotency and retries
Make unsafe operations idempotent where clients may retry (an idempotency key header stored with a unique constraint). Retry only idempotent calls, with a limit and backoff.

## Configuration
Everything environment-specific comes from environment variables or the secret manager. No secrets, hostnames or credentials in the repository. `application.yml` holds defaults and structure only.
