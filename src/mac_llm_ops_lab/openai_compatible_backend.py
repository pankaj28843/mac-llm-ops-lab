import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx


class OpenAICompatibleBackend:
    """Backend adapter for local OpenAI-compatible servers such as vllm-mlx."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        self._owns_client = client is None

    async def load(self) -> None:
        return None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def ready(self) -> bool:
        try:
            response = await self._client.get(
                self._url("/models"),
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json().get("data")
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return False
        return isinstance(data, list)

    async def list_models(self) -> list[dict[str, object]]:
        response = await self._client.get(self._url("/models"), headers=self._headers())
        response.raise_for_status()
        models = response.json().get("data", [])
        if not isinstance(models, list):
            return []
        return [_normalize_model(model) for model in models if isinstance(model, dict)]

    async def generate(
        self,
        prompt: str,
        model: str,
        *,
        options: Mapping[str, object] | None = None,
    ) -> str:
        response = await self._client.post(
            self._url("/chat/completions"),
            headers=self._headers(),
            json=_chat_completion_payload(
                prompt=prompt,
                model=model,
                stream=False,
                options=options,
            ),
        )
        response.raise_for_status()
        return _extract_completion_content(response.json())

    async def stream(
        self,
        prompt: str,
        model: str,
        *,
        options: Mapping[str, object] | None = None,
    ) -> AsyncIterator[str]:
        async with self._client.stream(
            "POST",
            self._url("/chat/completions"),
            headers=self._headers(),
            json=_chat_completion_payload(
                prompt=prompt,
                model=model,
                stream=True,
                options=options,
            ),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                chunk = _extract_sse_content(line)
                if chunk:
                    yield chunk

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _headers(self) -> dict[str, str]:
        if self.api_key is None:
            return {}
        return {"Authorization": f"Bearer {self.api_key}"}


def _chat_completion_payload(
    *,
    prompt: str,
    model: str,
    stream: bool,
    options: Mapping[str, object] | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": stream,
    }
    if options:
        payload.update(dict(options))
    return payload


def _normalize_model(model: dict[str, Any]) -> dict[str, object]:
    model_id = model.get("id")
    model_object = model.get("object", "model")
    return {
        "id": model_id if isinstance(model_id, str) else "",
        "object": model_object if isinstance(model_object, str) else "model",
    }


def _extract_completion_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    message = first_choice.get("message", {})
    if not isinstance(message, dict):
        return ""
    return _first_text_value(message, "content", "reasoning_content")


def _extract_sse_content(line: str) -> str:
    if not line.startswith("data: "):
        return ""
    data = line.removeprefix("data: ").strip()
    if data == "[DONE]":
        return ""
    try:
        payload = json.loads(data)
    except json.JSONDecodeError:
        return ""
    choices = payload.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    delta = first_choice.get("delta", {})
    if not isinstance(delta, dict):
        return ""
    return _first_text_value(delta, "content", "reasoning_content")


def _first_text_value(payload: Mapping[str, Any], *names: str) -> str:
    for name in names:
        value = payload.get(name, "")
        if isinstance(value, str) and value:
            return value
    return ""
