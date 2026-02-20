# Runbook: Migration Failure

## Trigger
- `python -m app.db.migrate` exits non-zero.
- Partial migration application detected.
- Startup logs indicate schema mismatch or index incompatibility.

## Immediate Actions
1. Halt traffic shift and prevent further rollout.
2. Capture migration command output and current `_Migration` node state.
3. Determine whether failure occurred before or after state mutation.

## Diagnostics
- Identify failing migration file and statement.
- Check database permissions, syntax compatibility, and existing schema state.
- Verify vector index dimensions against embedding configuration.

## Mitigation
1. If no partial state was written, fix migration and rerun.
2. If partial state exists, execute forward-fix migration rather than destructive rollback.
3. Reconcile schema with `python -m app.db.migrate` after corrective patch.

## Recovery Validation
- Migration command completes with no pending unexpected failures.
- `_Migration` tracking state is consistent with migration files.
- API readiness and retrieval/answer smoke tests pass.

## Post-Incident
- Document migration defect category (syntax, environment mismatch, ordering, dependency).
- Add preflight checks or CI simulation to prevent recurrence.
