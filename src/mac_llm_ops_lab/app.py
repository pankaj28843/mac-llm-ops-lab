import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from mac_llm_ops_lab.config import Settings, load_settings

HTTP_LOGGER = logging.getLogger("mac_llm_ops_lab.http")


class ModelBackend(Protocol):
    async def load(self) -> None: ...

    async def close(self) -> None: ...

    async def ready(self) -> bool: ...

    async def list_models(self) -> list[dict[str, str]]: ...

    async def generate(self, prompt: str, model: str) -> str: ...

    async def stream(self, prompt: str, model: str) -> AsyncIterator[str]: ...


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[ChatMessage] = Field(min_length=1)
    stream: bool = False


def create_app(*, backend: ModelBackend, settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()

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

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get(app_settings.request_id_header) or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[app_settings.request_id_header] = request_id
        HTTP_LOGGER.info(
            "http_request",
            extra={
                "request_id": request_id,
                "http_method": request.method,
                "http_route": _request_route(request),
                "http_status_code": response.status_code,
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

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(
        payload: ChatCompletionRequest, request: Request
    ) -> dict[str, object] | StreamingResponse:
        active_backend: ModelBackend = request.app.state.backend
        _ensure_model_allowed(payload.model, settings=app_settings)
        prompt = _last_user_message(payload.messages)
        if payload.stream:
            return StreamingResponse(
                _stream_events(active_backend, prompt=prompt, model=payload.model),
                media_type="text/event-stream",
            )

        try:
            content = await active_backend.generate(prompt, payload.model)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "backend_generation_failed",
                    "message": "Backend generation failed",
                },
            ) from exc
        return _completion_response(model=payload.model, content=content)

    return app


def _last_user_message(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return messages[-1].content


def _filter_allowed_models(
    models: list[dict[str, str]], *, settings: Settings
) -> list[dict[str, str]]:
    if not settings.model_allowlist:
        return models
    allowed = set(settings.model_allowlist)
    return [model for model in models if model.get("id") in allowed]


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


def _completion_response(*, model: str, content: str) -> dict[str, object]:
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
    }


def _error_response(
    *, request: Request, status_code: int, code: str, message: str
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", uuid4().hex)
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


async def _stream_events(
    backend: ModelBackend, *, prompt: str, model: str
) -> AsyncIterator[str]:
    yield _sse_event(
        model=model,
        delta={"role": "assistant"},
        finish_reason=None,
    )
    try:
        async for chunk in backend.stream(prompt, model):
            yield _sse_event(
                model=model,
                delta={"content": chunk},
                finish_reason=None,
            )
    except Exception:
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
