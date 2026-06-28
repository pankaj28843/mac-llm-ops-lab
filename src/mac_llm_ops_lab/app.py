import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager, nullcontext
from typing import Protocol
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from opentelemetry.trace import SpanKind
from pydantic import BaseModel, ConfigDict, Field

from mac_llm_ops_lab.config import Settings, load_settings
from mac_llm_ops_lab.metrics import InMemoryMetrics
from mac_llm_ops_lab.observability import (
    NoopSpan,
    Observability,
    configure_observability,
    mark_span_error,
    safe_token_count,
)

HTTP_LOGGER = logging.getLogger("mac_llm_ops_lab.http")
GenerationOptions = Mapping[str, object]


class ModelBackend(Protocol):
    async def load(self) -> None: ...

    async def close(self) -> None: ...

    async def ready(self) -> bool: ...

    async def list_models(self) -> list[dict[str, object]]: ...

    async def generate(
        self,
        prompt: str,
        model: str,
        *,
        options: GenerationOptions | None = None,
    ) -> str: ...

    async def stream(
        self,
        prompt: str,
        model: str,
        *,
        options: GenerationOptions | None = None,
    ) -> AsyncIterator[str]: ...


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionStreamOptions(BaseModel):
    include_usage: bool | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    max_completion_tokens: int | None = None
    stop: str | list[str] | None = None
    seed: int | None = None
    logit_bias: dict[str, float] | None = None
    user: str | None = None
    tools: list[dict[str, object]] | None = None
    tool_choice: str | dict[str, object] | None = None
    stream_options: ChatCompletionStreamOptions | None = None


def create_app(
    *,
    backend: ModelBackend,
    settings: Settings | None = None,
    observability: Observability | None = None,
) -> FastAPI:
    app_settings = settings or load_settings()
    metrics = InMemoryMetrics()
    app_observability = observability or configure_observability(app_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await backend.load()
        app.state.backend = backend
        try:
            yield
        finally:
            await backend.close()

    app = FastAPI(title=app_settings.service_name, lifespan=lifespan)
    app.state.settings = app_settings
    app.state.metrics = metrics
    app.state.observability = app_observability

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get(app_settings.request_id_header) or uuid4().hex
        request.state.request_id = request_id
        started_at = time.perf_counter()
        route = _request_route(request)
        with app_observability.start_span(
            f"{request.method} {route}",
            kind=SpanKind.SERVER,
            attributes={
                "http.request.method": request.method,
                "http.route": route,
                "mac_llm_ops.request.id": request_id,
                "mac_llm_ops.backend.kind": app_settings.backend_kind,
            },
        ) as span:
            try:
                response = await call_next(request)
            except Exception:
                mark_span_error(span, "unhandled_exception")
                raise
            duration_ms = (time.perf_counter() - started_at) * 1000
            response.headers[app_settings.request_id_header] = request_id
            route = _request_route(request)
            span.set_attribute("http.route", route)
            span.set_attribute("http.response.status_code", response.status_code)
            span.set_attribute("mac_llm_ops.http.duration_ms", duration_ms)
            if model_id := getattr(request.state, "model_id", ""):
                span.set_attribute("mac_llm_ops.model.id", model_id)
            metrics.record_request(
                route=route,
                method=request.method,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            error_code = getattr(request.state, "error_code", "")
            if error_code:
                metrics.record_http_error(
                    route=route,
                    status_code=response.status_code,
                    code=error_code,
                )
                span.set_attribute("error.type", error_code)
                if response.status_code >= 500:
                    mark_span_error(span, error_code)
            elif response.status_code >= 500:
                mark_span_error(span, str(response.status_code))
            HTTP_LOGGER.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "http_method": request.method,
                    "http_route": route,
                    "http_status_code": response.status_code,
                    "http_duration_ms": duration_ms,
                    "model_id": getattr(request.state, "model_id", ""),
                    "error_code": error_code,
                    "backend_id": type(
                        getattr(request.app.state, "backend", backend)
                    ).__name__,
                },
            )
            return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        code = str(detail.get("code", "http_error"))
        message = str(detail.get("message", "Request failed"))
        return _error_response(
            request=request,
            status_code=exc.status_code,
            code=code,
            message=message,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request=request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            code="request_validation_failed",
            message="Request validation failed",
        )

    @app.get("/live")
    async def live() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/ready")
    async def ready(request: Request) -> dict[str, str]:
        active_backend: ModelBackend = request.app.state.backend
        if not await active_backend.ready():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "backend_not_ready",
                    "message": "Backend is not ready",
                },
            )
        return {"status": "ready"}

    @app.get("/v1/models")
    async def models(request: Request) -> dict[str, object]:
        active_backend: ModelBackend = request.app.state.backend
        return {
            "object": "list",
            "data": _filter_allowed_models(
                await active_backend.list_models(), settings=app_settings
            ),
        }

    @app.get("/metrics/snapshot")
    async def metrics_snapshot(request: Request) -> dict[str, object]:
        active_metrics: InMemoryMetrics = request.app.state.metrics
        snapshot: dict[str, object] = active_metrics.snapshot()
        if backend_metrics := _backend_batch_metrics(request.app.state.backend):
            snapshot["backend_batch_metrics"] = backend_metrics
        return snapshot

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(
        payload: ChatCompletionRequest, request: Request
    ) -> dict[str, object] | StreamingResponse:
        active_backend: ModelBackend = request.app.state.backend
        request.state.model_id = payload.model
        _ensure_model_allowed(payload.model, settings=app_settings)
        prompt = _last_user_message(payload.messages)
        generation_options = _generation_options(payload)
        if payload.stream:
            return StreamingResponse(
                _stream_events(
                    active_backend,
                    prompt=prompt,
                    model=payload.model,
                    options=generation_options,
                    metrics=metrics,
                    observability=app_observability,
                    request_id=getattr(request.state, "request_id", ""),
                    backend_kind=app_settings.backend_kind,
                ),
                media_type="text/event-stream",
            )

        scheduler_attributes = _scheduler_span_attributes(
            model=payload.model,
            request_id=getattr(request.state, "request_id", ""),
            backend_kind=app_settings.backend_kind,
        )
        with app_observability.start_span(
            "mac_llm_ops.scheduler.dispatch",
            attributes=scheduler_attributes,
        ):
            backend_attributes = _backend_span_attributes(
                model=payload.model,
                prompt=prompt,
                request_id=getattr(request.state, "request_id", ""),
                backend_kind=app_settings.backend_kind,
            )
            with app_observability.start_span(
                f"gen_ai.chat {payload.model}",
                kind=SpanKind.CLIENT,
                attributes=backend_attributes,
            ) as backend_span:
                try:
                    content = await active_backend.generate(
                        prompt,
                        payload.model,
                        options=generation_options,
                    )
                except Exception as exc:
                    metrics.record_backend_generation_error(
                        model=payload.model,
                        code="backend_generation_failed",
                    )
                    mark_span_error(backend_span, "backend_generation_failed")
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail={
                            "code": "backend_generation_failed",
                            "message": "Backend generation failed",
                        },
                    ) from exc
                backend_span.set_attribute(
                    "gen_ai.usage.output_tokens",
                    safe_token_count(content),
                )
                backend_span.set_attribute("gen_ai.response.model", payload.model)
                backend_span.set_attribute("gen_ai.response.finish_reasons", ("stop",))
        metrics.record_generated_text(model=payload.model, content=content)
        return _completion_response(
            model=payload.model,
            prompt=prompt,
            content=content,
        )

    return app


def _last_user_message(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return messages[-1].content


def _filter_allowed_models(
    models: list[dict[str, object]], *, settings: Settings
) -> list[dict[str, object]]:
    if not settings.model_allowlist:
        return [_model_response(model) for model in models]
    allowed = set(settings.model_allowlist)
    return [
        _model_response(model)
        for model in models
        if isinstance(model.get("id"), str) and model["id"] in allowed
    ]


def _model_response(model: Mapping[str, object]) -> dict[str, object]:
    model_id = model.get("id")
    model_object = model.get("object", "model")
    created = model.get("created", 0)
    owned_by = model.get("owned_by", "mac-llm-ops-lab")
    return {
        **dict(model),
        "id": model_id if isinstance(model_id, str) else "",
        "object": model_object if isinstance(model_object, str) else "model",
        "created": created if isinstance(created, int) else 0,
        "owned_by": owned_by if isinstance(owned_by, str) else "mac-llm-ops-lab",
    }


def _ensure_model_allowed(model: str, *, settings: Settings) -> None:
    if not settings.model_allowlist or model in settings.model_allowlist:
        return
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "model_not_allowed",
            "message": "Model is not allowed",
        },
    )


def _completion_response(*, model: str, prompt: str, content: str) -> dict[str, object]:
    prompt_tokens = safe_token_count(prompt)
    completion_tokens = safe_token_count(content)
    return {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def _error_response(
    *, request: Request, status_code: int, code: str, message: str
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid4().hex)
    request.state.error_code = code
    request_id_header = _request_id_header(request)
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers={request_id_header: request_id},
    )


def _request_id_header(request: Request) -> str:
    settings = getattr(request.app.state, "settings", None)
    if isinstance(settings, Settings):
        return settings.request_id_header
    return "x-request-id"


def _request_route(request: Request) -> str:
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str):
        return path
    return request.url.path


def _backend_batch_metrics(backend: object) -> dict[str, object] | None:
    snapshot = getattr(backend, "batch_metrics_snapshot", None)
    if not callable(snapshot):
        return None
    metrics = snapshot()
    if isinstance(metrics, dict):
        return metrics
    return None


async def _stream_events(
    backend: ModelBackend,
    *,
    prompt: str,
    model: str,
    options: GenerationOptions | None = None,
    metrics: InMemoryMetrics | None = None,
    observability: Observability | None = None,
    request_id: str = "",
    backend_kind: str = "fake",
) -> AsyncIterator[str]:
    scheduler_span = (
        observability.start_span(
            "mac_llm_ops.scheduler.dispatch",
            attributes=_scheduler_span_attributes(
                model=model,
                request_id=request_id,
                backend_kind=backend_kind,
            ),
        )
        if observability is not None
        else nullcontext(NoopSpan())
    )
    with scheduler_span:
        stream_span = (
            observability.start_span(
                f"gen_ai.stream {model}",
                kind=SpanKind.CLIENT,
                attributes=_backend_span_attributes(
                    model=model,
                    prompt=prompt,
                    request_id=request_id,
                    backend_kind=backend_kind,
                ),
            )
            if observability is not None
            else nullcontext(NoopSpan())
        )
        with stream_span as span:
            output_tokens = 0
            try:
                yield _sse_event(
                    model=model,
                    delta={"role": "assistant"},
                    finish_reason=None,
                )
                async for chunk in backend.stream(prompt, model, options=options):
                    output_tokens += safe_token_count(chunk)
                    yield _sse_event(
                        model=model,
                        delta={"content": chunk},
                        finish_reason=None,
                    )
            except (asyncio.CancelledError, GeneratorExit):
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                span.set_attribute("gen_ai.response.model", model)
                span.set_attribute("gen_ai.response.finish_reasons", ("cancelled",))
                span.set_attribute("mac_llm_ops.stream.cancelled", True)
                if metrics is not None:
                    metrics.record_stream_cancellation(model=model)
                raise
            except Exception:
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                span.set_attribute("gen_ai.response.model", model)
                mark_span_error(span, "backend_stream_failed")
                if metrics is not None:
                    metrics.record_stream_error(model=model)
                yield _sse_event(
                    model=model,
                    delta={},
                    finish_reason="error",
                    error={
                        "code": "backend_stream_failed",
                        "message": "Backend stream failed",
                    },
                )
            else:
                span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
                span.set_attribute("gen_ai.response.model", model)
                span.set_attribute("gen_ai.response.finish_reasons", ("stop",))
                yield _sse_event(model=model, delta={}, finish_reason="stop")
            yield "data: [DONE]\n\n"


def _sse_event(
    *,
    model: str,
    delta: dict[str, str],
    finish_reason: str | None,
    error: dict[str, str] | None = None,
) -> str:
    event = {
        "id": f"chatcmpl-{uuid4().hex}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    if error is not None:
        event["error"] = error
    return f"data: {json.dumps(event)}\n\n"


def _scheduler_span_attributes(
    *,
    model: str,
    request_id: str,
    backend_kind: str,
) -> dict[str, object]:
    return {
        "mac_llm_ops.request.id": request_id,
        "mac_llm_ops.backend.kind": backend_kind,
        "mac_llm_ops.model.id": model,
        "mac_llm_ops.queue.wait_ms": 0.0,
    }


def _backend_span_attributes(
    *,
    model: str,
    prompt: str,
    request_id: str,
    backend_kind: str,
) -> dict[str, object]:
    provider = "openai-compatible" if backend_kind == "openai-compatible" else "local"
    return {
        "mac_llm_ops.request.id": request_id,
        "mac_llm_ops.backend.kind": backend_kind,
        "mac_llm_ops.model.id": model,
        "gen_ai.operation.name": "chat",
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
        "gen_ai.usage.input_tokens": safe_token_count(prompt),
    }


def _generation_options(payload: ChatCompletionRequest) -> dict[str, object]:
    options: dict[str, object] = {}
    for name in (
        "temperature",
        "top_p",
        "max_tokens",
        "max_completion_tokens",
        "stop",
        "seed",
        "logit_bias",
        "user",
        "tools",
        "tool_choice",
    ):
        value = getattr(payload, name)
        if value is not None:
            options[name] = value
    if payload.stream_options is not None:
        stream_options = payload.stream_options.model_dump(exclude_none=True)
        if stream_options:
            options["stream_options"] = stream_options
    return options
