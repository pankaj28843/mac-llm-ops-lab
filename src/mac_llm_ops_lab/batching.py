from dataclasses import dataclass, field


@dataclass(frozen=True)
class GenerationRequest:
    model: str
    prompt: str


@dataclass
class _BatchMetrics:
    batches_total: int = 0
    requests_total: int = 0
    max_active_batch_size: int = 0
    queue_wait_ms_total: int = 0
    prefill_tokens_total: int = 0
    decode_tokens_total: int = 0
    cache_hits_total: int = 0
    cache_misses_total: int = 0
    cache_saved_tokens_total: int = 0
    cancelled_requests_total: int = 0
    batch_observations: list[dict[str, int]] = field(default_factory=list)


class FakeBatchedBackend:
    def __init__(self, *, model_id: str) -> None:
        self.model_id = model_id
        self.loaded = False
        self.closed = False
        self._cache: set[str] = set()
        self._metrics = _BatchMetrics()

    async def load(self) -> None:
        self.loaded = True
        self.closed = False

    async def close(self) -> None:
        self.closed = True

    async def generate_many(self, requests: list[GenerationRequest]) -> list[str]:
        if not self.loaded or self.closed:
            raise RuntimeError("FakeBatchedBackend is not ready")
        if any(request.model != self.model_id for request in requests):
            raise ValueError("All fake batch requests must use the backend model")

        active_batch_size = len(requests)
        cache_hits = sum(1 for request in requests if request.prompt in self._cache)
        cache_misses = active_batch_size - cache_hits
        prefill_tokens = sum(
            len(request.prompt.split())
            for request in requests
            if request.prompt not in self._cache
        )
        cache_saved_tokens = sum(
            len(request.prompt.split())
            for request in requests
            if request.prompt in self._cache
        )
        decode_tokens = sum(
            len(_fake_response(self.model_id, request.prompt).split())
            for request in requests
        )

        self._metrics.batches_total += 1
        self._metrics.requests_total += active_batch_size
        self._metrics.max_active_batch_size = max(
            self._metrics.max_active_batch_size, active_batch_size
        )
        self._metrics.queue_wait_ms_total += active_batch_size
        self._metrics.prefill_tokens_total += prefill_tokens
        self._metrics.decode_tokens_total += decode_tokens
        self._metrics.cache_hits_total += cache_hits
        self._metrics.cache_misses_total += cache_misses
        self._metrics.cache_saved_tokens_total += cache_saved_tokens
        self._metrics.batch_observations.append(
            {
                "active_batch_size": active_batch_size,
                "cache_hits": cache_hits,
                "cache_misses": cache_misses,
                "prefill_tokens": prefill_tokens,
                "decode_tokens": decode_tokens,
                "cache_saved_tokens": cache_saved_tokens,
            }
        )

        responses = []
        for request in requests:
            self._cache.add(request.prompt)
            responses.append(_fake_response(self.model_id, request.prompt))
        return responses

    def batch_metrics_snapshot(self) -> dict[str, object]:
        return {
            "model": self.model_id,
            "batches_total": self._metrics.batches_total,
            "requests_total": self._metrics.requests_total,
            "max_active_batch_size": self._metrics.max_active_batch_size,
            "queue_wait_ms_total": self._metrics.queue_wait_ms_total,
            "prefill_tokens_total": self._metrics.prefill_tokens_total,
            "decode_tokens_total": self._metrics.decode_tokens_total,
            "cache_hits_total": self._metrics.cache_hits_total,
            "cache_misses_total": self._metrics.cache_misses_total,
            "cache_saved_tokens_total": self._metrics.cache_saved_tokens_total,
            "cancelled_requests_total": self._metrics.cancelled_requests_total,
            "batch_observations": list(self._metrics.batch_observations),
        }


def _fake_response(model: str, prompt: str) -> str:
    return f"{model} response to {prompt}"
