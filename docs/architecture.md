# Architecture

## Scope
This document specifies the production reference architecture for SAT Graph RAG. The architecture is designed for controlled deployment, reproducibility, and auditable operation of temporally grounded regulatory question answering.

## Reference Deployment Topology
- API service: `apps/api`, deployed as a stateless Cloud Run service.
- Web service: `apps/web`, deployed as a stateless Cloud Run service.
- Graph persistence: Neo4j AuraDB.
- Language model endpoint: managed OpenAI-compatible endpoint.
- Batch workloads: containerized ingestion and evaluation jobs with workload identity.

## Architectural Principles
- Stateless compute with horizontal elasticity.
- Externalized state with managed backup and restore controls.
- Explicit trust boundaries and short-lived credentials for service communication.
- Explicit migration execution rather than opportunistic schema mutation at runtime.

## Functional Flow
1. A client submits a query through the web interface.
2. The web service forwards the request to the API with identity metadata.
3. The API validates identity and authorization claims.
4. The API resolves temporal scope and retrieves evidence from Neo4j.
5. The API invokes the model endpoint for answer synthesis with citation constraints.
6. The API returns a structured response with citations and request correlation identifiers.

## Identity and Access Model
- Identity protocol: OIDC JWT validation.
- Provider profile: Microsoft Entra ID (default deployment profile).
- Canonical RBAC claim: `roles`.
- Optional compatibility path: `groups` claim mapped to RBAC roles through explicit configuration.
- Role set:
  - `admin`
  - `compliance_analyst`
  - `read_only`

## Data and Schema Governance
- Schema artifacts are versioned in `apps/api/migrations`.
- Migrations are executed via `python -m app.db.migrate`.
- Seed data is excluded from production migration runs by default.
- Migration application state is recorded in Neo4j nodes labeled `:_Migration`.

## Infrastructure Codification
- Deployment resources are codified in `infra/terraform`.
- Staging and production profiles are represented by dedicated tfvars templates.
- Service identities, secret bindings, and Cloud Run configuration are managed as versioned IaC artifacts.

## Service-Level Objectives
- Availability (API): 99.9% per month.
- Retrieval endpoint latency target: p95 <= 1.5 seconds.
- Orchestrated answering endpoint latency target: p95 <= 8 seconds.
- Citation validity target: >= 99%.
- Advisory refusal success target: >= 97%.

## Production Acceptance Matrix
| Control Domain | Target | Owner | Evidence Artifact | Release Gate |
| --- | --- | --- | --- | --- |
| Availability | API monthly availability >= 99.9% | Platform Engineering | uptime dashboard + alert history | required |
| Latency | retrieval p95 <= 1.5s; orchestrated answer p95 <= 8s | API Engineering | per-route latency dashboard + canary report | required |
| Answer quality | citation validity >= 99%; refusal success >= 97% | Applied AI Engineering | `python -m eval run` report in CI/staging | required |
| Security | OIDC validation + RBAC policy active in staging/production | Security Engineering | auth integration test record + config snapshot | required |
| Data schema integrity | migrations applied and vector index aligned to embed dimensions | Data Engineering | `python -m app.db.migrate` output + Neo4j index inspection | required |
| Resilience | documented rollback and incident runbooks for top failure classes | SRE | runbook review record + drill output | required |
| Recovery | backup/restore drill meets defined RTO/RPO | SRE + Data Engineering | recovery drill report | required |
| Cost control | budget threshold alerts at 50/80/100% monthly allocation | Platform Engineering | budget policy + alert notification evidence | required |

## Cost-Control Policies
- Budget monitoring thresholds: 50%, 80%, and 100% of monthly allocation.
- Request-level safeguards:
  - bounded retrieval depth,
  - bounded model timeout and retry counts,
  - bounded request rate per client and route.

## Migration Path to Self-Hosted Inference
Migration from managed LLM endpoints to self-hosted GPU inference is justified only under one or more of the following conditions:
- sustained request volume exceeds managed endpoint cost targets,
- contractual data constraints require isolated model runtime,
- managed endpoint latency cannot satisfy operational SLOs.
