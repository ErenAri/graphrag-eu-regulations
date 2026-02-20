# Deployment and Canary Policy

## Objective
This document defines release progression and rollback conditions for staging and production rollouts.

## Release Preconditions
Before canary traffic is enabled, all conditions must be satisfied:
- CI quality gates pass.
- Database migration job succeeds.
- Backup checkpoint exists for managed graph storage.
- Health and readiness probes return stable success.

## Canary Progression
Default staged rollout profile:
1. 5% traffic for 15 minutes.
2. 25% traffic for 30 minutes.
3. 50% traffic for 60 minutes.
4. 100% traffic after successful completion of prior stages.

Promotion to the next stage requires all guard conditions to remain satisfied for the full stage duration.

## Guard Conditions
Rollback is triggered if any condition is violated:
- `5xx` error rate > 1.0%.
- p95 latency increase > 20% relative to baseline.
- Authentication failure rate (`401` + `403`) > 2x baseline.
- Readiness endpoint instability persists beyond the configured threshold.

## Migration Control
- Execute `python -m app.db.migrate` before traffic shift.
- Use non-seed migrations for staging and production.
- Rollback path must include:
  - service revision rollback,
  - migration impact review,
  - operator decision on forward-fix versus recovery action.

## Observability Requirements During Canary
Monitor at minimum:
- request volume,
- error distribution by status code,
- p95 latency by route,
- auth failure distribution,
- rate-limiter rejection rate.

## Post-Deployment Validation
- Run synthetic smoke checks against read and answer endpoints.
- Confirm citation and refusal evaluation thresholds in the target environment.
- Archive deployment report with version, timestamps, and observed guard metrics.

## Optional Automated Gate Script
This repository includes `scripts/check_canary_metrics.py` for CI or release-pipeline enforcement of guard thresholds.

Example:
```bash
python scripts/check_canary_metrics.py --metrics canary-metrics.json
```

## Canary Metric Publication
This repository includes `scripts/publish_canary_metrics.py` to publish canary metrics to Cloud Monitoring custom metric types consumed by Terraform-managed alert policies:
- `custom.googleapis.com/sat/canary/error_rate_5xx`
- `custom.googleapis.com/sat/canary/latency_p95_ratio`
- `custom.googleapis.com/sat/canary/auth_failure_ratio`

Example:
```bash
python scripts/publish_canary_metrics.py \
  --metrics canary-metrics.json \
  --project-id <gcp-project-id> \
  --service-name <cloud-run-service-name> \
  --environment <staging-or-production>
```

## CI/CD Automation Path
Workflow `.github/workflows/canary-gate.yml` supports both gate evaluation and optional metric publication:
- set `publish_metrics=true`,
- provide `project_id`, `service_name`, and `environment`,
- configure repository secrets:
  - `GCP_WORKLOAD_IDENTITY_PROVIDER`
  - `GCP_CANARY_METRIC_WRITER_SERVICE_ACCOUNT`

The metric writer service account should have Monitoring time-series write permissions.
