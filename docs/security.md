# Security Model

## Objective
This document formalizes the identity, authorization, and request-protection model for SAT Graph RAG.

## Identity Provider Profile
- Default provider profile: Microsoft Entra ID.
- OIDC token validation inputs:
  - issuer (`OIDC_ISSUER`),
  - audience (`OIDC_AUDIENCE`),
  - JWKS endpoint (`OIDC_JWKS_URL`),
  - tenant identifier (`OIDC_TENANT_ID` when provider profile is `entra`).

JWT signature verification is performed against provider JWKS keys with bounded cache lifetime.

## RBAC Policy
Canonical role claim: `roles`.

Allowed role vocabulary:
- `admin`
- `compliance_analyst`
- `read_only`

Compatibility mechanism:
- If the canonical role claim is absent, group claim values (`groups`) may be mapped to RBAC roles via `OIDC_GROUP_ROLE_MAP`.

## Route Authorization Classes
- Read access (`search-items`, `resolve-temporal-scope`, `get-valid-version`, `search-text-units`):
  - `read_only`, `compliance_analyst`, or `admin`.
- Elevated access (`answer`, `answer-orchestrated`):
  - `compliance_analyst` or `admin`.

## Service Authentication
- Internal service calls may use a short-lived service token channel (`X-Service-Token`) when explicitly configured.
- Production recommendation remains workload identity for service-to-service trust.

## Request Protection
- Request IDs are generated or propagated (`X-Request-Id`) and included in logs and response headers.
- Optional rate limiting is configurable with:
  - route-specific limits,
  - configurable window duration,
  - proxy-aware client identity derivation.

## Rate Limiter Backends
- Development baseline: in-memory limiter.
- Production baseline: Redis-backed limiter (`RATE_LIMIT_BACKEND=redis`).
- Failure strategy:
  - fail-open (`RATE_LIMIT_FAIL_OPEN=true`) to prioritize availability,
  - fail-closed (`RATE_LIMIT_FAIL_OPEN=false`) to prioritize strict admission control.

## Framework Advisory Mitigations
The web workspace is upgraded to Next.js `15.5.10`, which is within the patched line for advisories `GHSA-9g9p-9gw9-jx7f` and `GHSA-h25m-26qc-wcjf`.

Compensating controls remain enabled as defense-in-depth:
- built-in image optimization is disabled (`images.unoptimized=true`),
- requests to `/_next/image` are rejected at middleware,
- requests carrying `next-action` are rejected,
- non-read HTTP methods are rejected for web routes.

Dependency scanning baseline (`npm audit --audit-level=critical`) reports zero vulnerabilities after this upgrade.

## Dependency Vulnerability Governance
- Python dependency vulnerability scanning is executed with `pip-audit` in CI.
- CI is blocked on any vulnerability without an approved exception entry.
- Exception register location: `security/pip-audit-exceptions.json`.
- Required exception fields:
  - `package`,
  - `vulnerability_id`,
  - `reason`,
  - `owner`,
  - `expires_on`,
  - `tracking_issue`.
- Expired exceptions and stale entries are treated as policy violations.

## Operational Requirements
- Secrets are not stored in source control.
- Role claims and group mappings are version-controlled as infrastructure configuration.
- Auth and limiter behavior must be covered by automated tests before release promotion.
