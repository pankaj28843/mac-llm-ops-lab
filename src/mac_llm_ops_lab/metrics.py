from dataclasses import dataclass, field


@dataclass
class InMemoryMetrics:
    requests_total: dict[tuple[str, str, str], int] = field(default_factory=dict)
    request_latency_ms_total: dict[tuple[str, str, str], float] = field(
        default_factory=dict
    )
    request_latency_ms_max: dict[tuple[str, str, str], float] = field(
        default_factory=dict
    )
    http_errors_total: dict[tuple[str, str, str], int] = field(default_factory=dict)
    tokens_generated_total: dict[str, int] = field(default_factory=dict)
    backend_generation_errors_total: dict[tuple[str, str], int] = field(
        default_factory=dict
    )
    stream_errors_total: dict[str, int] = field(default_factory=dict)
    stream_cancellations_total: dict[str, int] = field(default_factory=dict)

    def record_request(
        self, *, route: str, method: str, status_code: int, duration_ms: float
    ) -> None:
        key = (route, method, str(status_code))
        self.requests_total[key] = self.requests_total.get(key, 0) + 1
        bounded_duration = max(duration_ms, 0.0)
        self.request_latency_ms_total[key] = (
            self.request_latency_ms_total.get(key, 0.0) + bounded_duration
        )
        self.request_latency_ms_max[key] = max(
            self.request_latency_ms_max.get(key, 0.0),
            bounded_duration,
        )

    def record_generated_text(self, *, model: str, content: str) -> None:
        count = len(content.split())
        self.tokens_generated_total[model] = (
            self.tokens_generated_total.get(model, 0) + count
        )

    def record_http_error(self, *, route: str, status_code: int, code: str) -> None:
        key = (route, str(status_code), code)
        self.http_errors_total[key] = self.http_errors_total.get(key, 0) + 1

    def record_backend_generation_error(self, *, model: str, code: str) -> None:
        key = (model, code)
        self.backend_generation_errors_total[key] = (
            self.backend_generation_errors_total.get(key, 0) + 1
        )

    def record_stream_error(self, *, model: str) -> None:
        self.stream_errors_total[model] = self.stream_errors_total.get(model, 0) + 1

    def record_stream_cancellation(self, *, model: str) -> None:
        self.stream_cancellations_total[model] = (
            self.stream_cancellations_total.get(model, 0) + 1
        )

    def snapshot(self) -> dict[str, list[dict[str, object]]]:
        return {
            "requests_total": [
                {
                    "route": route,
                    "method": method,
                    "status_code": status_code,
                    "count": count,
                }
                for (route, method, status_code), count in self.requests_total.items()
            ],
            "request_latency_ms": [
                {
                    "route": route,
                    "method": method,
                    "status_code": status_code,
                    "count": self.requests_total[(route, method, status_code)],
                    "total_ms": total_ms,
                    "max_ms": self.request_latency_ms_max[(route, method, status_code)],
                }
                for (
                    route,
                    method,
                    status_code,
                ), total_ms in self.request_latency_ms_total.items()
            ],
            "tokens_generated_total": [
                {"model": model, "count": count}
                for model, count in self.tokens_generated_total.items()
            ],
            "http_errors_total": [
                {
                    "route": route,
                    "status_code": status_code,
                    "code": code,
                    "count": count,
                }
                for (route, status_code, code), count in self.http_errors_total.items()
            ],
            "backend_generation_errors_total": [
                {"model": model, "code": code, "count": count}
                for (model, code), count in self.backend_generation_errors_total.items()
            ],
            "stream_errors_total": [
                {"model": model, "count": count}
                for model, count in self.stream_errors_total.items()
            ],
            "stream_cancellations_total": [
                {"model": model, "count": count}
                for model, count in self.stream_cancellations_total.items()
            ],
        }
