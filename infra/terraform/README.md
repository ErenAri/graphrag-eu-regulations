# Terraform Infrastructure Baseline

## Objective
This Terraform baseline codifies production deployment primitives for SAT Graph RAG on Google Cloud Run with explicit service identities and secret-bound configuration.

## Managed Resources
- required project services (`run`, `iam`, `secretmanager`, `monitoring`),
- service accounts for API and web services,
- Cloud Run v2 services for API and web,
- optional unauthenticated invoker IAM bindings,
- monitoring dashboard for API/canary operability,
- canary guard alert policies on custom canary metrics.

## Prerequisites
- Terraform >= 1.6
- authenticated Google Cloud CLI context with deployment permissions
- pre-built container images for API and web services
- Secret Manager entries referenced by `api_secret_env` and `web_secret_env`

## Initialization
```bash
cd infra/terraform
terraform init
```

## Plan (Staging)
```bash
terraform plan -var-file=environments/staging.tfvars.example
```

## Apply (Staging)
```bash
terraform apply -var-file=environments/staging.tfvars.example
```

## Environment Promotion Model
- Staging and production use separate tfvars files.
- Promotion requires image tag progression and successful canary evidence from staging.
- Production apply should run from an audited CI/CD pipeline, not ad hoc local execution.

## Notes
- API service defaults to authenticated invocation.
- Web service defaults to unauthenticated invocation to serve public UI traffic.
- Alert notification channels are passed through `monitoring_notification_channel_ids`.
- Observability artifacts can be disabled with `enable_observability_artifacts=false`.
- Canary metric types expected by alert policies:
  - `custom.googleapis.com/sat/canary/error_rate_5xx`
  - `custom.googleapis.com/sat/canary/latency_p95_ratio`
  - `custom.googleapis.com/sat/canary/auth_failure_ratio`
