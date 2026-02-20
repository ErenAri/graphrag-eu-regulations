# Configuration Profiles

## Objective
This document defines deterministic configuration profiles for host-executed commands and Docker Compose services. The purpose is to eliminate ambiguous runtime behavior caused by mixed Neo4j hostnames and environment scopes.

## Profiles
- `host` profile:
  - template: `.env.host.example`
  - expected Neo4j endpoint: `bolt://localhost:7687`
  - use case: local Python commands (`pytest`, `ingest`, `app.db.migrate`) executed from the host shell
- `docker` profile:
  - template: `.env.docker.example`
  - expected Neo4j endpoint: `bolt://neo4j:7687`
  - use case: `docker-compose` service runtime

## Setup Procedure
```bash
cp .env.host.example .env.host
cp .env.docker.example .env.docker
```

## Host Command Execution
Set `APP_ENV_FILE` (and optionally `INGEST_ENV_FILE`) before running host commands:

```powershell
$env:APP_ENV_FILE='.env.host'
$env:INGEST_ENV_FILE='.env.host'
```

Examples:
```powershell
$env:APP_ENV_FILE='.env.host'; $env:PYTHONPATH='apps/api'; venv/Scripts/python -m pytest apps/api/tests
$env:APP_ENV_FILE='.env.host'; $env:PYTHONPATH='apps/api'; venv/Scripts/python -m app.db.migrate
$env:INGEST_ENV_FILE='.env.host'; venv/Scripts/python -m ingest run --source_url <url> --work_title "<title>" --jurisdiction EU --authority_level 1 --valid_from 2024-01-01
```

## Docker Compose Execution
Use `.env.docker` as Compose substitution input and keep API env file aligned:

```bash
docker-compose --env-file .env.docker up -d neo4j
API_ENV_FILE=.env.docker docker-compose --env-file .env.docker up -d api web
```

Optional local observability stack:

```bash
API_ENV_FILE=.env.docker docker-compose --env-file .env.docker --profile observability up -d neo4j api prometheus alertmanager grafana
```

## Runtime Resolution Rules
- API settings loader reads from `APP_ENV_FILE` if provided; otherwise `.env`.
- Ingestion settings loader reads from `INGEST_ENV_FILE` if provided, then `APP_ENV_FILE`, then `.env`.
- Docker Compose API service reads `${API_ENV_FILE:-.env}`.
