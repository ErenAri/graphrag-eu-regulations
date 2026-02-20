# Runbook: OIDC or JWKS Validation Outage

## Trigger
- Elevated `401`/`403` rates across authenticated endpoints.
- Token validation failures due to issuer, JWKS fetch, or key rotation mismatch.
- Authentication canary guard violated.

## Immediate Actions
1. Verify whether outage is identity-provider-side or application configuration-side.
2. Confirm current OIDC settings (`OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`, tenant settings).
3. Freeze deployment promotions and canary rollout.

## Diagnostics
- Inspect API logs for token validation error categories.
- Validate JWKS endpoint reachability and response integrity.
- Compare active signing keys with cached keys in runtime.

## Mitigation
1. If provider outage is confirmed, communicate degraded auth status and maintain strict access policy.
2. If configuration drift is detected, roll back to last known-good configuration revision.
3. Restart affected service revisions after correction to refresh key caches.

## Recovery Validation
- Auth failure rate returns to baseline.
- Synthetic authentication tests pass for expected role classes.
- No ongoing JWT verification errors in logs.

## Post-Incident
- Record whether issue was provider, network, or config drift.
- Add or adjust alerts for early detection of JWKS reachability and key mismatch.
