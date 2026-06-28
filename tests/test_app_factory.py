import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from mac_llm_ops_lab.app import _stream_events, create_app
from mac_llm_ops_lab.config import Settings


class FakeBackend:
    def __init__(
        self,
        *,
        ready_after_load: bool = True,
        generation_error: Exception | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        self.ready_after_load = ready_after_load
        self.generation_error = generation_error
        self.stream_error = stream_error
        self.loaded = 0
        self.closed = 0
        self.stream_closed = 0
        self.generated_prompts: list[str] = []

    async def load(self) -> None:
        self.loaded += 1

    async def close(self) -> None:
        self.closed += 1

    async def ready(self) -> bool:
        return self.ready_after_load and self.loaded == 1 and self.closed == 0

    async def list_models(self) -> list[dict[str, str]]:
        return [{"id": "fake-local-model", "object": "model"}]

    async def generate(self, prompt: str, model: str) -> str:
        if self.generation_error is not None:
            raise self.generation_error
        self.generated_prompts.append(f"{model}:{prompt}")
        return f"fake response to {prompt}"

    async def stream(self, prompt: str, model: str) -> AsyncIterator[str]:
        self.generated_prompts.append(f"{model}:{prompt}")
        try:
            yield "fake "
            if self.stream_error is not None:
                raise self.stream_error
            yield "stream"
        finally:
            self.stream_closed += 1


def test_app_constructs_with_fake_backend_and_no_external_services() -> None:
    backend = FakeBackend()
    app = create_app(backend=backend)

    with TestClient(app) as client:
        live_response = client.get("/live")
        ready_response = client.get("/ready")
        models_response = client.get("/v1/models")
        generation_response = client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
            },
        )

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "alive"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
    assert models_response.status_code == 200
    assert models_response.json()["data"] == [
        {"id": "fake-local-model", "object": "model"}
    ]
    assert generation_response.status_code == 200
    assert generation_response.json()["choices"][0]["message"] == {
        "role": "assistant",
        "content": "fake response to hello",
    }
    assert backend.loaded == 1
    assert backend.closed == 1
    assert backend.generated_prompts == ["fake-local-model:hello"]


def test_liveness_does_not_require_backend_readiness() -> None:
    backend = FakeBackend(ready_after_load=False)
    app = create_app(backend=backend)

    with TestClient(app) as client:
        live_response = client.get("/live")
        ready_response = client.get("/ready", headers={"x-request-id": "req-123"})

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "alive"}
    assert ready_response.status_code == 503
    assert ready_response.headers["x-request-id"] == "req-123"
    assert ready_response.json() == {
        "error": {
            "code": "backend_not_ready",
            "message": "Backend is not ready",
            "request_id": "req-123",
        }
    }


def test_streaming_chat_emits_openai_compatible_sse_chunks() -> None:
    backend = FakeBackend()
    app = create_app(backend=backend)

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/v1/chat/completions",
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": True,
            },
        ) as response:
            lines = [line for line in response.iter_lines() if line]

    data_lines = [line.removeprefix("data: ") for line in lines]
    events = [json.loads(line) for line in data_lines[:-1]]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert data_lines[-1] == "[DONE]"
    assert events[0]["choices"][0]["delta"] == {"role": "assistant"}
    assert [event["choices"][0]["delta"].get("content") for event in events[1:-1]] == [
        "fake ",
        "stream",
    ]
    assert events[-1]["choices"][0]["delta"] == {}
    assert events[-1]["choices"][0]["finish_reason"] == "stop"
    assert backend.generated_prompts == ["fake-local-model:hello"]


def test_generation_backend_failures_return_sanitized_error() -> None:
    backend = FakeBackend(generation_error=RuntimeError("raw backend failure"))
    app = create_app(backend=backend)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"x-request-id": "req-fail"},
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "secret prompt"}],
                "stream": False,
            },
        )

    assert response.status_code == 502
    assert response.headers["x-request-id"] == "req-fail"
    assert response.json() == {
        "error": {
            "code": "backend_generation_failed",
            "message": "Backend generation failed",
            "request_id": "req-fail",
        }
    }
    assert "secret prompt" not in response.text
    assert "raw backend failure" not in response.text


def test_closing_streaming_events_closes_backend_stream() -> None:
    backend = FakeBackend()

    async def consume_one_content_chunk_then_close() -> None:
        events = _stream_events(backend, prompt="hello", model="fake-local-model")
        await anext(events)
        await anext(events)
        await events.aclose()

    asyncio.run(consume_one_content_chunk_then_close())

    assert backend.generated_prompts == ["fake-local-model:hello"]
    assert backend.stream_closed == 1


def test_streaming_backend_failures_emit_sanitized_error_chunk() -> None:
    backend = FakeBackend(stream_error=RuntimeError("raw stream failure"))

    async def collect_stream_events() -> list[str]:
        return [
            event
            async for event in _stream_events(
                backend, prompt="secret prompt", model="fake-local-model"
            )
        ]

    lines = asyncio.run(collect_stream_events())
    data_lines = [line.removeprefix("data: ").strip() for line in lines]
    events = [json.loads(line) for line in data_lines[:-1]]

    assert data_lines[-1] == "[DONE]"
    assert events[-1]["choices"][0]["delta"] == {}
    assert events[-1]["choices"][0]["finish_reason"] == "error"
    assert events[-1]["error"] == {
        "code": "backend_stream_failed",
        "message": "Backend stream failed",
    }
    assert "secret prompt" not in lines[-2]
    assert "raw stream failure" not in lines[-2]
    assert backend.stream_closed == 1


def test_request_validation_failures_return_structured_error() -> None:
    backend = FakeBackend()
    app = create_app(backend=backend)

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"x-request-id": "req-invalid"},
            json={"model": "fake-local-model", "messages": [], "stream": False},
        )

    assert response.status_code == 422
    assert response.headers["x-request-id"] == "req-invalid"
    assert response.json() == {
        "error": {
            "code": "request_validation_failed",
            "message": "Request validation failed",
            "request_id": "req-invalid",
        }
    }


def test_app_uses_configured_request_id_header() -> None:
    backend = FakeBackend(ready_after_load=False)
    app = create_app(
        backend=backend,
        settings=Settings(request_id_header="x-trace-id"),
    )

    with TestClient(app) as client:
        response = client.get("/ready", headers={"x-trace-id": "trace-123"})

    assert response.status_code == 503
    assert response.headers["x-trace-id"] == "trace-123"
    assert response.json()["error"]["request_id"] == "trace-123"


def test_model_allowlist_rejects_disallowed_generation_without_backend_call() -> None:
    backend = FakeBackend()
    app = create_app(
        backend=backend,
        settings=Settings(model_allowlist=("allowed-model",)),
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"x-request-id": "req-model"},
            json={
                "model": "blocked-model",
                "messages": [{"role": "user", "content": "secret prompt"}],
                "stream": False,
            },
        )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "model_not_allowed",
            "message": "Model is not allowed",
            "request_id": "req-model",
        }
    }
    assert "secret prompt" not in response.text
    assert backend.generated_prompts == []


def test_http_request_log_uses_bounded_fields_without_prompt_text(caplog) -> None:
    caplog.set_level(logging.INFO, logger="mac_llm_ops_lab.http")
    backend = FakeBackend()
    app = create_app(backend=backend)

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"x-request-id": "req-log"},
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "secret prompt"}],
                "stream": False,
            },
        )

    request_logs = [
        record
        for record in caplog.records
        if record.name == "mac_llm_ops_lab.http"
        and record.getMessage() == "http_request"
    ]

    assert response.status_code == 200
    assert len(request_logs) == 1
    record = request_logs[0]
    assert record.request_id == "req-log"
    assert record.http_method == "POST"
    assert record.http_route == "/v1/chat/completions"
    assert record.http_status_code == 200
    assert "secret prompt" not in caplog.text


def test_metrics_snapshot_uses_bounded_labels_without_prompt_text() -> None:
    backend = FakeBackend()
    app = create_app(backend=backend)

    with TestClient(app) as client:
        generation_response = client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "secret prompt"}],
                "stream": False,
            },
        )
        metrics_response = client.get("/metrics/snapshot")

    assert generation_response.status_code == 200
    assert metrics_response.status_code == 200
    assert metrics_response.json() == {
        "requests_total": [
            {
                "route": "/v1/chat/completions",
                "method": "POST",
                "status_code": "200",
                "count": 1,
            },
        ],
        "tokens_generated_total": [
            {"model": "fake-local-model", "count": 5},
        ],
        "stream_errors_total": [],
    }
    assert "secret prompt" not in metrics_response.text
