import json
from collections.abc import AsyncIterator, Mapping

import pytest
from fastapi.testclient import TestClient

from mac_llm_ops_lab.app import _stream_events, create_app
from mac_llm_ops_lab.config import Settings, load_settings
from mac_llm_ops_lab.observability import (
    InMemorySpanRecorder,
    configure_observability,
)
from mac_llm_ops_lab.persistence.sqlalchemy import (
    Base,
    SQLAlchemyUnitOfWork,
    create_async_session_factory,
)


class FakeBackend:
    def __init__(
        self,
        *,
        generation_error: Exception | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        self.generation_error = generation_error
        self.stream_error = stream_error

    async def load(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def ready(self) -> bool:
        return True

    async def list_models(self) -> list[dict[str, object]]:
        return [{"id": "fake-local-model", "object": "model"}]

    async def generate(
        self,
        prompt: str,
        model: str,
        *,
        options: Mapping[str, object] | None = None,
    ) -> str:
        if self.generation_error is not None:
            raise self.generation_error
        return f"fake response to {prompt}"

    async def stream(
        self,
        prompt: str,
        model: str,
        *,
        options: Mapping[str, object] | None = None,
    ) -> AsyncIterator[str]:
        yield "fake "
        if self.stream_error is not None:
            raise self.stream_error
        yield "stream"


def test_observability_settings_parse_phoenix_otlp_environment() -> None:
    settings = load_settings(
        {
            "MAC_LLM_OPS_SERVICE_NAME": "local-serving-lab",
            "MAC_LLM_OPS_OTEL_ENABLED": "true",
            "MAC_LLM_OPS_PHOENIX_PROJECT_NAME": "mac-studio-lab",
            "MAC_LLM_OPS_PHOENIX_COLLECTOR_ENDPOINT": "http://localhost:6006/v1/traces",
            "MAC_LLM_OPS_OTEL_CAPTURE_CONTENT": "false",
            "MAC_LLM_OPS_OTEL_EXPORT_TIMEOUT_SECONDS": "3.5",
        }
    )

    assert settings.otel_enabled is True
    assert settings.otel_exporter_otlp_traces_endpoint == (
        "http://localhost:6006/v1/traces"
    )
    assert settings.phoenix_project_name == "mac-studio-lab"
    assert settings.otel_capture_content is False
    assert settings.otel_export_timeout_seconds == 3.5


def test_observability_defaults_are_disabled_and_prompt_safe() -> None:
    settings = load_settings({})

    assert settings.otel_enabled is False
    assert settings.otel_exporter_otlp_traces_endpoint is None
    assert settings.phoenix_project_name == "mac-llm-ops-lab"
    assert settings.otel_capture_content is False

    observability = configure_observability(settings)

    assert observability.enabled is False
    with observability.start_span("manual.noop", attributes={"secret": "not-exported"}):
        pass


def test_enabled_observability_uses_resource_and_phoenix_endpoint() -> None:
    settings = Settings(
        service_name="local-serving-lab",
        otel_enabled=True,
        otel_exporter_otlp_traces_endpoint="http://phoenix:6006/v1/traces",
        phoenix_project_name="mac-studio-lab",
    )
    recorder = InMemorySpanRecorder()

    observability = configure_observability(settings, span_exporter=recorder)

    assert observability.enabled is True
    assert observability.endpoint == "http://phoenix:6006/v1/traces"
    assert observability.resource_attributes["service.name"] == "local-serving-lab"
    assert observability.resource_attributes["phoenix.project.name"] == (
        "mac-studio-lab"
    )


def test_chat_request_exports_prompt_safe_correlated_http_scheduler_backend_spans() -> (
    None
):
    settings = _otel_settings()
    recorder = InMemorySpanRecorder()
    observability = configure_observability(settings, span_exporter=recorder)
    app = create_app(
        backend=FakeBackend(),
        settings=settings,
        observability=observability,
    )

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"x-request-id": "req-otel"},
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "secret prompt"}],
                "stream": False,
            },
        )

    assert response.status_code == 200
    spans = recorder.get_finished_spans()
    http_span = _span_by_name(spans, "POST /v1/chat/completions")
    scheduler_span = _span_by_name(spans, "mac_llm_ops.scheduler.dispatch")
    backend_span = _span_by_name(spans, "gen_ai.chat fake-local-model")

    assert http_span.attributes["http.request.method"] == "POST"
    assert http_span.attributes["http.route"] == "/v1/chat/completions"
    assert http_span.attributes["http.response.status_code"] == 200
    assert http_span.attributes["mac_llm_ops.request.id"] == "req-otel"
    assert http_span.attributes["mac_llm_ops.backend.kind"] == "fake"

    assert scheduler_span.attributes["mac_llm_ops.queue.wait_ms"] == 0.0
    assert scheduler_span.attributes["mac_llm_ops.model.id"] == "fake-local-model"

    assert backend_span.attributes["gen_ai.operation.name"] == "chat"
    assert backend_span.attributes["gen_ai.provider.name"] == "local"
    assert backend_span.attributes["gen_ai.request.model"] == "fake-local-model"
    assert backend_span.attributes["gen_ai.response.model"] == "fake-local-model"
    assert backend_span.attributes["gen_ai.usage.input_tokens"] == 2
    assert backend_span.attributes["gen_ai.usage.output_tokens"] == 5

    assert {
        http_span.context.trace_id,
        scheduler_span.context.trace_id,
        backend_span.context.trace_id,
    } == {http_span.context.trace_id}
    assert _span_text(spans).find("secret prompt") == -1
    assert _span_text(spans).find("fake response to secret prompt") == -1


def test_backend_error_span_uses_low_cardinality_error_without_raw_details() -> None:
    settings = _otel_settings()
    recorder = InMemorySpanRecorder()
    observability = configure_observability(settings, span_exporter=recorder)
    app = create_app(
        backend=FakeBackend(
            generation_error=RuntimeError(
                "raw backend failure /Users/pankaj shh-local-secret"
            )
        ),
        settings=settings,
        observability=observability,
    )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"x-request-id": "req-error"},
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "secret prompt"}],
                "stream": False,
            },
        )

    assert response.status_code == 502
    spans = recorder.get_finished_spans()
    http_span = _span_by_name(spans, "POST /v1/chat/completions")
    backend_span = _span_by_name(spans, "gen_ai.chat fake-local-model")

    assert http_span.attributes["http.response.status_code"] == 502
    assert http_span.attributes["error.type"] == "backend_generation_failed"
    assert backend_span.attributes["error.type"] == "backend_generation_failed"
    assert "secret prompt" not in _span_text(spans)
    assert "raw backend failure" not in _span_text(spans)
    assert "/Users/pankaj" not in _span_text(spans)
    assert "shh-local-secret" not in _span_text(spans)


def test_streaming_request_exports_token_and_error_safe_span() -> None:
    settings = _otel_settings()
    recorder = InMemorySpanRecorder()
    observability = configure_observability(settings, span_exporter=recorder)
    app = create_app(
        backend=FakeBackend(stream_error=RuntimeError("raw stream failure")),
        settings=settings,
        observability=observability,
    )

    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/v1/chat/completions",
            headers={"x-request-id": "req-stream"},
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "secret prompt"}],
                "stream": True,
            },
        ) as response:
            lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    events = [json.loads(line.removeprefix("data: ")) for line in lines[:-1]]
    assert events[-1]["choices"][0]["finish_reason"] == "error"
    stream_span = _span_by_name(
        recorder.get_finished_spans(),
        "gen_ai.stream fake-local-model",
    )

    assert stream_span.attributes["gen_ai.operation.name"] == "chat"
    assert stream_span.attributes["gen_ai.usage.input_tokens"] == 2
    assert stream_span.attributes["gen_ai.usage.output_tokens"] == 1
    assert stream_span.attributes["error.type"] == "backend_stream_failed"
    assert "secret prompt" not in _span_text(recorder.get_finished_spans())
    assert "raw stream failure" not in _span_text(recorder.get_finished_spans())


@pytest.mark.anyio
async def test_streaming_cancellation_exports_cancelled_span_without_error() -> None:
    settings = _otel_settings()
    recorder = InMemorySpanRecorder()
    observability = configure_observability(settings, span_exporter=recorder)
    events = _stream_events(
        FakeBackend(),
        prompt="secret prompt",
        model="fake-local-model",
        observability=observability,
        request_id="req-cancel",
        backend_kind="openai-compatible",
    )

    await anext(events)
    await anext(events)
    await events.aclose()

    stream_span = _span_by_name(
        recorder.get_finished_spans(),
        "gen_ai.stream fake-local-model",
    )

    assert stream_span.attributes["mac_llm_ops.request.id"] == "req-cancel"
    assert stream_span.attributes["mac_llm_ops.backend.kind"] == "openai-compatible"
    assert stream_span.attributes["mac_llm_ops.stream.cancelled"] is True
    assert stream_span.attributes["gen_ai.response.finish_reasons"] == ("cancelled",)
    assert "error.type" not in stream_span.attributes
    assert "secret prompt" not in _span_text(recorder.get_finished_spans())


@pytest.mark.anyio
async def test_sqlalchemy_unit_of_work_exports_db_transaction_span(tmp_path) -> None:
    settings = _otel_settings()
    recorder = InMemorySpanRecorder()
    observability = configure_observability(settings, span_exporter=recorder)
    engine, session_factory = create_async_session_factory(
        f"sqlite+aiosqlite:///{tmp_path / 'observed.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with SQLAlchemyUnitOfWork(
            session_factory,
            observability=observability,
            db_system="sqlite",
        ) as uow:
            await uow.commit()
    finally:
        await engine.dispose()

    db_span = _span_by_name(recorder.get_finished_spans(), "db.transaction")

    assert db_span.attributes["db.system.name"] == "sqlite"
    assert db_span.attributes["db.operation.name"] == "transaction"
    assert db_span.attributes["mac_llm_ops.db.uow"] == "SQLAlchemyUnitOfWork"
    assert db_span.attributes["db.transaction.outcome"] == "commit"


def _otel_settings() -> Settings:
    return Settings(
        otel_enabled=True,
        otel_exporter_otlp_traces_endpoint="http://localhost:6006/v1/traces",
        phoenix_project_name="test-project",
    )


def _span_by_name(spans: list[object], name: str) -> object:
    for span in spans:
        if span.name == name:
            return span
    names = [span.name for span in spans]
    raise AssertionError(f"missing span {name!r}; got {names!r}")


def _span_text(spans: list[object]) -> str:
    payload = []
    for span in spans:
        payload.append(
            {
                "name": span.name,
                "attributes": dict(span.attributes),
                "resource": dict(span.resource.attributes),
            }
        )
    return repr(payload)
