# Local Observability Stack

## Objective
This document defines a local observability baseline using Prometheus, Alertmanager, and Grafana for environments where Google Cloud Monitoring is not used.

## Scope
The stack collects API metrics from `/metrics`, evaluates guard-condition-style Prometheus alerts, and provides a pre-provisioned Grafana dashboard.

## Components
- Prometheus:
  - scrape target: `api:8000/metrics`
  - rule set: `infra/observability/prometheus/rules/sat_api_alerts.yml`
- Alertmanager:
  - receives alert events from Prometheus
  - local default receiver for inspection/testing
- Grafana:
  - pre-provisioned Prometheus datasource
  - dashboard: `SAT API Operability`

## Startup Procedure
```bash
docker-compose --env-file .env.docker --profile observability up -d neo4j api web prometheus alertmanager grafana
```

## Service Endpoints
- Prometheus UI: `http://localhost:9090`
- Alertmanager UI: `http://localhost:9093`
- Grafana UI: `http://localhost:3001`
- API metrics endpoint: `http://localhost:8000/metrics`

## Grafana Authentication
Credentials are configured through `.env.docker`:
- `GRAFANA_ADMIN_USER`
- `GRAFANA_ADMIN_PASSWORD`

## External Alert Channels
Alertmanager supports Slack and Microsoft Teams webhook routing through `.env.docker`:
- `ALERTMANAGER_SLACK_WEBHOOK_URL`
- `ALERTMANAGER_SLACK_CHANNEL`
- `ALERTMANAGER_SLACK_USERNAME`
- `ALERTMANAGER_TEAMS_WEBHOOK_URL`

After updating webhook values, reload alertmanager:
```bash
docker-compose --env-file .env.docker --profile observability up -d --no-build alertmanager
```

## Alert Coverage
The local rule set includes:
- API scrape availability (`SatApiScrapeDown`),
- 5xx error-rate threshold (`SatApiHigh5xxRate`),
- p95 latency degradation versus offset baseline (`SatApiP95LatencyDegradation`),
- auth failure-rate degradation versus offset baseline (`SatApiAuthFailureRateDegradation`),
- rate-limit rejection spike (`SatApiRateLimitRejectionsSpike`).

## Notes
- Baseline-relative alerts depend on sufficient historical data to evaluate offsets.
- For low-traffic local sessions, baseline-relative alerts may remain inactive until enough samples exist.
- Teams receivers use webhook forwarding from Alertmanager webhook payloads. If your tenant requires card formatting middleware, route `ALERTMANAGER_TEAMS_WEBHOOK_URL` to your preferred Teams alert bridge.
