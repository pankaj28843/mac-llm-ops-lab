from dataclasses import dataclass, field


@dataclass
class InMemoryMetrics:
    requests_total: dict[tuple[str, str, str], int] = field(default_factory=dict)
    tokens_generated_total: dict[str, int] = field(default_factory=dict)
    stream_errors_total: dict[str, int] = field(default_factory=dict)

    def record_request(self, *, route: str, method: str, status_code: int) -> None:
        key = (route, method, str(status_code))
        self.requests_total[key] = self.requests_total.get(key, 0) + 1

    def record_generated_text(self, *, model: str, content: str) -> None:
        count = len(content.split())
        self.tokens_generated_total[model] = (
            self.tokens_generated_total.get(model, 0) + count
        )

    def record_stream_error(self, *, model: str) -> None:
        self.stream_errors_total[model] = self.stream_errors_total.get(model, 0) + 1

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
            "tokens_generated_total": [
                {"model": model, "count": count}
                for model, count in self.tokens_generated_total.items()
            ],
            "stream_errors_total": [
                {"model": model, "count": count}
                for model, count in self.stream_errors_total.items()
            ],
        }
