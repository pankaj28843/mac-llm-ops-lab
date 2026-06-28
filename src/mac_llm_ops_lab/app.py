import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field


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


def create_app(*, backend: ModelBackend) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await backend.load()
        app.state.backend = backend
        try:
            yield
        finally:
            await backend.close()

    app = FastAPI(title="Mac LLM Ops Lab", lifespan=lifespan)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
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
        return {"object": "list", "data": await active_backend.list_models()}

    @app.post("/v1/chat/completions", response_model=None)
    async def chat_completions(
        payload: ChatCompletionRequest, request: Request
    ) -> dict[str, object] | StreamingResponse:
        active_backend: ModelBackend = request.app.state.backend
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
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
        headers={"x-request-id": request_id},
    )


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
