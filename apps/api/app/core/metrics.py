from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS_TOTAL = Counter(
    "sat_api_http_requests_total",
    "Total HTTP requests served by the API.",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "sat_api_http_request_duration_seconds",
    "HTTP request latency for the API.",
    ["method", "path", "status_code"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
RATE_LIMIT_REJECTIONS_TOTAL = Counter(
    "sat_api_rate_limit_rejections_total",
    "Total requests rejected due to rate limiting.",
    ["method", "path"],
)
RATE_LIMIT_BACKEND_ERRORS_TOTAL = Counter(
    "sat_api_rate_limit_backend_errors_total",
    "Total rate limiter backend errors.",
    ["backend"],
)


def observe_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    status = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status_code=status).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, path=path, status_code=status).observe(
        duration_seconds
    )


def observe_rate_limit_rejection(method: str, path: str) -> None:
    RATE_LIMIT_REJECTIONS_TOTAL.labels(method=method, path=path).inc()


def observe_rate_limit_backend_error(backend: str) -> None:
    RATE_LIMIT_BACKEND_ERRORS_TOTAL.labels(backend=backend).inc()


def render_metrics() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
