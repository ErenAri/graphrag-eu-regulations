# Runbook: Neo4j Unavailable

## Trigger
- `/ready` returns `503` with Neo4j connectivity errors.
- API logs contain repeated `neo4j` connection failures.
- Retrieval endpoints fail or return elevated `5xx` rates.

## Immediate Actions
1. Confirm blast radius by checking `/health`, `/ready`, and retrieval endpoint error rate.
2. Validate Neo4j service state and network path from API runtime.
3. If outage is isolated to an instance/revision, shift traffic to healthy revision.
4. If outage is backend-wide, suspend canary progression and declare degraded mode.

## Diagnostics
- Check database host resolution and TLS/auth settings.
- Inspect Neo4j provider status page and project-level alerts.
- Validate credentials and secret versions used by API service.

## Mitigation
1. Restore connectivity (network policy, DNS, credentials, or provider recovery).
2. Re-run readiness checks until stable success over at least 5 consecutive intervals.
3. Execute synthetic retrieval smoke tests.

## Recovery Validation
- `5xx` error rate returns below 1%.
- Retrieval latency returns to baseline envelope.
- No ongoing Neo4j reconnect storms in logs.

## Post-Incident
- Archive timeline, root cause, and corrective action.
- Open follow-up tasks for guardrail improvements (retry policy, timeout tuning, alert threshold tuning).
