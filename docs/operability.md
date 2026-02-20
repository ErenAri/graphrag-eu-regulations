# Operability

## Execution Environments
- `development`
- `staging`
- `production`

All environments should execute equivalent container artifacts. Behavioral variation is controlled exclusively by validated configuration.

## Configuration and Secret Management
- Application settings are validated at startup.
- Sensitive production values are expected from a managed secret store.
- Repository `.env` files are restricted to local development.
- Profile templates (`.env.host.example`, `.env.docker.example`) define host and container execution contexts.
- Runtime profile selection is explicit through `APP_ENV_FILE`/`INGEST_ENV_FILE` for host commands and `API_ENV_FILE` for Compose.
- For Hugging Face embedding execution, `NEO4J_VECTOR_DIMENSIONS` and `EMBED_DIM` must remain equal.

## GPU Execution Profile
- CUDA acceleration is optional and currently scoped to embedding workloads.
- Recommended controls:
  - explicit device policy (`EMBED_DEVICE`),
  - bounded embedding batch size (`EMBED_BATCH_SIZE`),
  - pre-deployment batch-size benchmark on target GPU hardware.
- Benchmark utility: `scripts/benchmark_embedding_batch.py`.
- Reference result on NVIDIA RTX 2060 (6 GB), measured on February 20, 2026 with `BAAI/bge-m3` and 220-word synthetic samples:
  - recommended `EMBED_BATCH_SIZE=80`.

## Observability Baseline
- Log format: structured JSON with `request_id` correlation.
- Health probes:
  - liveness endpoint: `/health`
  - readiness endpoint: `/ready`
  - metrics endpoint: `/metrics`
- Required operational signals:
  - route-level request count and error count,
  - latency distribution by endpoint,
  - Neo4j retry and connectivity failure frequency,
  - model timeout and model failure frequency,
  - rate-limiter rejection frequency.

## Operational Controls
- Schema migrations are executed explicitly before traffic shifts.
- Migration execution (`python -m app.db.migrate`) reconciles vector-index dimensions with current embedding settings.
- Releases are promoted through staged canary rollout.
- Rollback is triggered automatically when canary guard conditions are violated.
- Every deployment produces an auditable release record.

## Incident Response Requirements
Runbooks are required for at least the following scenarios:
- graph database unavailability,
- model endpoint degradation,
- OIDC/JWKS validation outage,
- migration failure or partial migration.

## CI Quality Gates
Minimum merge and deployment gates:
- Python lint checks (`ruff`),
- Python type checks (`mypy` on critical modules),
- API unit tests (`pytest`),
- evaluation suite (`python -m eval run` in CI environment with Neo4j),
- TypeScript type checks and production builds,
- `npm audit --audit-level=critical`,
- `pip-audit` report enforced by exception register (`security/pip-audit-exceptions.json`) with expiry and owner requirements.

## Recovery and Continuity
- Neo4j backup and restore must be enabled and tested.
- Migration history must remain immutable.
- Recovery targets (RTO/RPO) must be defined and tracked in operational dashboards.

## Operational Readiness Gates
| Gate | Threshold | Evidence | Status Owner |
| --- | --- | --- | --- |
| CI baseline | all mandatory jobs pass | CI run URL + artifacts | Feature Author |
| Security scans | no unapproved critical findings | audit reports + exception register | Security Reviewer |
| Canary guard | all guard conditions satisfied during staged rollout | canary metrics JSON + gate output | Release Manager |
| Incident preparedness | runbooks reviewed and current | `docs/runbooks/` review checklist | On-call Lead |
| Recovery readiness | latest backup/restore drill within 30 days | drill report with measured RTO/RPO | SRE |
