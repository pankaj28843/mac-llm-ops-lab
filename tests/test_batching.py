import asyncio

from mac_llm_ops_lab.batching import FakeBatchedBackend, GenerationRequest


def test_fake_batched_backend_records_bounded_batch_and_cache_metrics() -> None:
    backend = FakeBatchedBackend(model_id="fake-batched-model")

    async def run_batches() -> tuple[list[str], list[str], dict[str, object]]:
        await backend.load()
        first_batch = await backend.generate_many(
            [
                GenerationRequest(
                    model="fake-batched-model", prompt="shared prefix one"
                ),
                GenerationRequest(
                    model="fake-batched-model", prompt="shared prefix two"
                ),
            ]
        )
        second_batch = await backend.generate_many(
            [
                GenerationRequest(
                    model="fake-batched-model", prompt="shared prefix one"
                ),
            ]
        )
        await backend.close()
        return first_batch, second_batch, backend.batch_metrics_snapshot()

    first_batch, second_batch, metrics = asyncio.run(run_batches())

    assert first_batch == [
        "fake-batched-model response to shared prefix one",
        "fake-batched-model response to shared prefix two",
    ]
    assert second_batch == ["fake-batched-model response to shared prefix one"]
    assert metrics == {
        "model": "fake-batched-model",
        "batches_total": 2,
        "requests_total": 3,
        "max_active_batch_size": 2,
        "queue_wait_ms_total": 3,
        "prefill_tokens_total": 6,
        "decode_tokens_total": 18,
        "cache_hits_total": 1,
        "cache_misses_total": 2,
        "cache_saved_tokens_total": 3,
        "cancelled_requests_total": 0,
        "batch_observations": [
            {
                "active_batch_size": 2,
                "cache_hits": 0,
                "cache_misses": 2,
                "prefill_tokens": 6,
                "decode_tokens": 12,
                "cache_saved_tokens": 0,
            },
            {
                "active_batch_size": 1,
                "cache_hits": 1,
                "cache_misses": 0,
                "prefill_tokens": 0,
                "decode_tokens": 6,
                "cache_saved_tokens": 3,
            },
        ],
    }
    assert "shared prefix" not in repr(metrics)
