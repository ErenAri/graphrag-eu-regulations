# Local Observability Assets

This directory contains local (non-GCP) observability assets for Docker Compose deployments.

## Structure
- `prometheus/prometheus.yml`: scrape and alertmanager wiring.
- `prometheus/rules/sat_api_alerts.yml`: recording and alert rules for API guard conditions.
- `alertmanager/alertmanager.yml`: local alert routing.
- `grafana/provisioning`: datasource and dashboard providers.
- `grafana/dashboards/sat-api-operability.json`: pre-provisioned dashboard.

## Compose Integration
Assets are mounted by `docker-compose.yml` under the `observability` profile.

## Alert Channel Variables
Alertmanager channel routing is configured with environment variables:
- `ALERTMANAGER_SLACK_WEBHOOK_URL`
- `ALERTMANAGER_SLACK_CHANNEL`
- `ALERTMANAGER_SLACK_USERNAME`
- `ALERTMANAGER_TEAMS_WEBHOOK_URL`
