import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import requests

try:
    from scripts.check_canary_metrics import evaluate
except ModuleNotFoundError:
    from check_canary_metrics import evaluate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="publish-canary-metrics")
    parser.add_argument("--metrics", required=True, help="Path to JSON metrics snapshot.")
    parser.add_argument("--project-id", required=True, help="GCP project ID.")
    parser.add_argument("--service-name", required=True, help="Service label value.")
    parser.add_argument("--environment", required=True, help="Environment label value.")
    parser.add_argument(
        "--access-token",
        default=None,
        help="OAuth access token with monitoring.write scope. Falls back to environment or gcloud.",
    )
    return parser.parse_args()


def load_metrics(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(value) for key, value in payload.items()}


def ratio(numerator: float, baseline: float) -> float:
    if baseline <= 0:
        return 1.0
    return numerator / baseline


def resolve_access_token(explicit_token: str | None) -> str:
    if explicit_token:
        return explicit_token
    env_token = os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN") or os.environ.get("ACCESS_TOKEN")
    if env_token:
        return env_token
    command = ["gcloud", "auth", "print-access-token"]
    try:
        output = subprocess.check_output(command, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc:
        raise RuntimeError(
            "unable_to_resolve_access_token: provide --access-token or set GOOGLE_OAUTH_ACCESS_TOKEN"
        ) from exc
    if not output:
        raise RuntimeError("empty_access_token")
    return output


def build_time_series(
    project_id: str,
    service_name: str,
    environment: str,
    values: dict[str, float],
) -> list[dict]:
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    base_labels = {
        "service": service_name,
        "environment": environment,
    }
    metric_map = {
        "error_rate_5xx": "custom.googleapis.com/sat/canary/error_rate_5xx",
        "latency_p95_ratio": "custom.googleapis.com/sat/canary/latency_p95_ratio",
        "auth_failure_ratio": "custom.googleapis.com/sat/canary/auth_failure_ratio",
    }
    series: list[dict] = []
    for key, metric_type in metric_map.items():
        series.append(
            {
                "metric": {
                    "type": metric_type,
                    "labels": base_labels,
                },
                "resource": {"type": "global", "labels": {"project_id": project_id}},
                "points": [
                    {
                        "interval": {"endTime": timestamp},
                        "value": {"doubleValue": float(values[key])},
                    }
                ],
            }
        )
    return series


def publish(
    project_id: str,
    access_token: str,
    time_series: list[dict],
) -> None:
    endpoint = f"https://monitoring.googleapis.com/v3/projects/{project_id}/timeSeries"
    response = requests.post(
        endpoint,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"timeSeries": time_series},
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(
            f"monitoring_write_failed:{response.status_code}:{response.text.strip()[:500]}"
        )


def main() -> None:
    args = parse_args()
    metrics = load_metrics(Path(args.metrics))
    passed, failures = evaluate(metrics)

    values = {
        "error_rate_5xx": metrics.get("error_rate_5xx", 0.0),
        "latency_p95_ratio": ratio(
            metrics.get("p95_latency_ms", 0.0),
            metrics.get("baseline_p95_latency_ms", 0.0),
        ),
        "auth_failure_ratio": ratio(
            metrics.get("auth_failure_rate", 0.0),
            metrics.get("baseline_auth_failure_rate", 0.0),
        ),
    }
    token = resolve_access_token(args.access_token)
    series = build_time_series(
        project_id=args.project_id,
        service_name=args.service_name,
        environment=args.environment,
        values=values,
    )
    publish(args.project_id, token, series)
    print(
        json.dumps(
            {
                "published": True,
                "project_id": args.project_id,
                "service_name": args.service_name,
                "environment": args.environment,
                "values": values,
                "canary_passed": passed,
                "canary_failures": failures,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
