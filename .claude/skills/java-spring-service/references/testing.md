# Testing

## What must exist before a service is called done
1. **One test per business rule in the spec**, written first from the rule and its boundary values. The scaffold creates disabled stubs (`BusinessRulesTest`) with the spec id in the message; enable each as the rule is implemented. These are characterization tests: they pin the behaviour the business agreed, and they are what makes later refactoring safe.
2. **Negative tests for every control story**: the forbidden action is refused for the wrong role, the wrong owner, the same person twice.
3. **Real database tests** with Testcontainers PostgreSQL: migrations apply, mapping validates, constraints reject bad data, optimistic locking conflicts, audit rows are written. Do not use H2 as a stand-in.
4. **Architecture tests** (`ArchitectureTest`, ArchUnit) so layering cannot erode.
5. **Context test** (`ApplicationTests`) that starts the whole application.

## Layers
| Layer | Tool | Notes |
|---|---|---|
| Rules | plain JUnit 5, AssertJ, Mockito | no Spring; inject a fixed `Clock`; table-driven boundary tests |
| Web slice | `@WebMvcTest` (package `org.springframework.boot.webmvc.test.autoconfigure`), `MockMvcTester`, `@MockitoBean` | covers validation, status codes, ProblemDetail bodies, security rules with `spring-security-test` |
| Persistence slice | `@DataJpaTest` from the Boot 4 modular package (let the IDE resolve it) with the Testcontainers config | covers queries and constraints |
| End to end | `@SpringBootTest` with `TestcontainersConfiguration` | a few journeys, not hundreds |
| Architecture | ArchUnit | layering, no field injection, no cycles |

Imports changed in Boot 4: never copy a Boot 3 test import; let the compiler tell you.

## Security tests
Use `spring-security-test` request post-processors (`jwt().authorities(...)`) or `@WithMockUser`; keep the real `SecurityFilterChain`. Assert both sides: allowed role gets 2xx, forbidden role gets 403, no token gets 401, another user's resource gets 404.

## Data and time
Build test data with builders or small factory methods, never with copies of production data or real personal data. Fix the clock (`Clock.fixed(...)`) for anything date-dependent (leave counted across a weekend, an approval after midnight).

## Quality gates
The build fails on test failure. Add the organisation's coverage and mutation tools; the number matters less than every spec rule having a test. Run `java_check.py` and fix every error; treat warnings as questions.
