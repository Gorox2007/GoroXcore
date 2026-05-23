import time

from django.http import HttpResponse
from django.urls import Resolver404, resolve
from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    CONTENT_TYPE_LATEST,
    generate_latest,
)


SERVICE_NAME = "monolith"
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


def _path_label(request):
    path = request.path_info or request.path or "/"
    try:
        match = resolve(path)
    except Resolver404:
        return path

    route = match.route or "/"
    if not route.startswith("/"):
        route = f"/{route}"
    return route


def metrics_view(request):
    return HttpResponse(generate_latest(REGISTRY), content_type=CONTENT_TYPE_LATEST)


class PrometheusMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (request.path_info or request.path).rstrip("/") == "/metrics":
            return self.get_response(request)

        method = request.method
        path = _path_label(request)
        start = time.monotonic()
        status = "500"
        HTTP_REQUESTS_IN_PROGRESS.labels(SERVICE_NAME, method, path).inc()
        try:
            response = self.get_response(request)
            status = str(getattr(response, "status_code", 500))
            return response
        finally:
            HTTP_REQUESTS_IN_PROGRESS.labels(SERVICE_NAME, method, path).dec()
            HTTP_REQUESTS_TOTAL.labels(SERVICE_NAME, method, path, status).inc()
            HTTP_REQUEST_DURATION_SECONDS.labels(
                SERVICE_NAME, method, path
            ).observe(time.monotonic() - start)
