#!/bin/sh
set -eu

TEMPLATE="/etc/alertmanager/alertmanager.yml"
RENDERED="/tmp/alertmanager-rendered.yml"

escape_for_sed() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

SLACK_WEBHOOK_ESC="$(escape_for_sed "${ALERTMANAGER_SLACK_WEBHOOK_URL}")"
SLACK_CHANNEL_ESC="$(escape_for_sed "${ALERTMANAGER_SLACK_CHANNEL}")"
SLACK_USERNAME_ESC="$(escape_for_sed "${ALERTMANAGER_SLACK_USERNAME}")"
TEAMS_WEBHOOK_ESC="$(escape_for_sed "${ALERTMANAGER_TEAMS_WEBHOOK_URL}")"

sed \
  -e "s|__ALERTMANAGER_SLACK_WEBHOOK_URL__|${SLACK_WEBHOOK_ESC}|g" \
  -e "s|__ALERTMANAGER_SLACK_CHANNEL__|${SLACK_CHANNEL_ESC}|g" \
  -e "s|__ALERTMANAGER_SLACK_USERNAME__|${SLACK_USERNAME_ESC}|g" \
  -e "s|__ALERTMANAGER_TEAMS_WEBHOOK_URL__|${TEAMS_WEBHOOK_ESC}|g" \
  "${TEMPLATE}" > "${RENDERED}"

exec /bin/alertmanager --config.file="${RENDERED}"
