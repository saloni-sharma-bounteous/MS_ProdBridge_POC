# Security and controls in Spring Boot

How common security controls become code and tests. Control ids are for cross-reference only.

| Control | Implementation | Test that must exist |
|---|---|---|
| IAM-01 organisational sign-in | OAuth2 resource server validating tokens from the organisation's identity provider (`issuer-uri` from the environment). No local passwords, no shared codes. | Request without a token gets 401; token from another issuer is rejected. |
| IAM-02 server-side authorization | `@EnableMethodSecurity`, `@PreAuthorize` on every endpoint and service method that changes or reveals data; ownership checks in queries (`findByIdAndEmployeeId`), not only role checks. | For each rule in the spec: the forbidden action is refused (403 or 404) for the wrong role and the wrong owner. |
| IAM-03 no default credentials | Nothing in code, config or test fixtures that works in production. | `java_check` finds no hardcoded secrets (JV-009). |
| SEC-01 and SEC-02 secrets | Values come from environment variables injected by the platform from the secret manager. | CI secret scan clean. |
| DAT-02 no sensitive data in logs | Log identifiers and outcomes, not payloads; never log tokens, personal data or request bodies. | Review of log statements; JV-023 warnings. |
| DAT-05 masking by role | Separate DTOs per audience; Restricted fields only in the DTO for roles that need them. | Test that a manager's response lacks the medical note and an HR user's has it. |
| APP-01 and APP-02 | JSON only, bean validation on DTOs, output is JSON never HTML; server-side checks for every business constraint. | Invalid input returns 400 with a ProblemDetail and no echo of internals. |
| APP-04 headers | Security headers come from Spring Security defaults plus a restrictive CORS configuration listing exact origins. | CORS test: a foreign origin is refused. |
| AUD-01 audit trail | Write `audit_log` rows in the same transaction as the change (the scaffold provides `AuditTrail`); record who, what, when, before and after. | Each state-changing endpoint creates exactly one audit row; update and delete of audit rows are impossible. |
| COM-01 dual control | The approver's identity (from the token) is compared with the creator and with earlier approvers inside the service; a unique constraint on (request, approver) backs it. | Creator cannot approve; the same person cannot approve twice; the required number of distinct approvers releases the item. |
| COM-02 approval limits | Limits are read from the reference-data table and applied in one decision method. | Boundary tests: just below, equal to, and just above each limit. |
| COM-05 exact money | `BigDecimal` and `numeric(p,s)` end to end. | A rounding test at the boundaries the spec names. |
| COM-06 explainable decisions | Persist inputs, rule version and outcome with each decision. | A decision can be reproduced from its stored record. |
| DB-01 data access | Row-level security enabled by the migration; the service runs with a least-privilege database role. | An integration test that a user cannot read another user's rows when policies apply. |

## Patterns

**Dual control in the service**
```java
if (approverId.equals(request.getEmployeeId())) {
    throw new BusinessRuleViolation("A person cannot approve their own request");
}
if (approvalRepository.existsByLeaveRequestIdAndApproverId(request.getId(), approverId)) {
    throw new BusinessRuleViolation("This person has already approved");
}
```
The approver id comes from the verified token (`Authentication.getName()` or a claim), never from the request body.

**Ownership in queries**: expose `findByIdAndEmployeeId(id, currentEmployeeId)` for employee endpoints so another person's id returns 404, and use the unrestricted finder only in code paths guarded by an elevated role.

**Token validation**: validate issuer (automatic with `issuer-uri`) and audience (add a validator); map roles from one named claim; reject tokens without it.

**CORS**: configure explicitly with the exact front-end origins, no wildcard, credentials only when needed.

Never disable security in tests by weakening the production configuration; use `spring-security-test` (`jwt()` request post-processors or `@WithMockUser`) and keep the real filter chain.
