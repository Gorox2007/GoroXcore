import time

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    CONTENT_TYPE_LATEST,
    generate_latest,
)


SERVICE_NAME = "payment"
REGISTRY = CollectorRegistry()

HTTP_REQUESTS_TOTAL = Counter(
    "gx_http_requests_total",
    "Total HTTP requests.",
    ("service", "method", "path", "status"),
    registry=REGISTRY,
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "gx_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("service", "method", "path"),
    registry=REGISTRY,
)
HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "gx_http_requests_in_progress",
    "HTTP requests currently being processed.",
    ("service", "method", "path"),
    registry=REGISTRY,
)
PAYMENT_STATUS_CHANGES_TOTAL = Counter(
    "gx_payment_status_changes_total",
    "Payment status changes.",
    ("service", "status"),
    registry=REGISTRY,
)


def _path_label(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


def setup_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def prometheus_metrics_middleware(request: Request, call_next):
        if request.url.path.rstrip("/") == "/metrics":
            return await call_next(request)

        method = request.method
        in_progress_path = request.url.path
        start = time.monotonic()
        status = "500"
        HTTP_REQUESTS_IN_PROGRESS.labels(SERVICE_NAME, method, in_progress_path).inc()
        try:
            response = await call_next(request)
            status = str(response.status_code)
            return response
        finally:
            HTTP_REQUESTS_IN_PROGRESS.labels(
                SERVICE_NAME, method, in_progress_path
            ).dec()
            path = _path_label(request)
            HTTP_REQUESTS_TOTAL.labels(SERVICE_NAME, method, path, status).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                SERVICE_NAME, method, path
            ).observe(time.monotonic() - start)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
