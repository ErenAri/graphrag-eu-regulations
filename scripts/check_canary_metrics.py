import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="check-canary-metrics")
    parser.add_argument("--metrics", required=True, help="Path to JSON metrics snapshot.")
    return parser.parse_args()


def load_metrics(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(value) for key, value in payload.items()}


def evaluate(metrics: dict[str, float]) -> tuple[bool, list[str]]:
    failures: list[str] = []
    error_rate_5xx = metrics.get("error_rate_5xx", 0.0)
    p95_latency_ms = metrics.get("p95_latency_ms", 0.0)
    baseline_p95_latency_ms = metrics.get("baseline_p95_latency_ms", 0.0)
    auth_failure_rate = metrics.get("auth_failure_rate", 0.0)
    baseline_auth_failure_rate = metrics.get("baseline_auth_failure_rate", 0.0)

    if error_rate_5xx > 0.01:
        failures.append("error_rate_5xx_exceeds_1_percent")
    if baseline_p95_latency_ms > 0 and p95_latency_ms > baseline_p95_latency_ms * 1.2:
        failures.append("p95_latency_exceeds_20_percent_of_baseline")
    if baseline_auth_failure_rate > 0 and auth_failure_rate > baseline_auth_failure_rate * 2:
        failures.append("auth_failure_rate_exceeds_2x_baseline")

    return (len(failures) == 0, failures)


def main() -> None:
    args = parse_args()
    metrics_path = Path(args.metrics)
    metrics = load_metrics(metrics_path)
    passed, failures = evaluate(metrics)
    result = {
        "passed": passed,
        "failures": failures,
        "metrics": metrics,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

