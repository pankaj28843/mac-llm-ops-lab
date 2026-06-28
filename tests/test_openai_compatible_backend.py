import json

import httpx
import pytest

from mac_llm_ops_lab.openai_compatible_backend import OpenAICompatibleBackend


@pytest.mark.anyio
async def test_openai_backend_proxies_models_and_chat_without_prompt_leaks() -> None:
    requests: list[httpx.Request] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET" and request.url.path == "/v1/models":
            return httpx.Response(
                200,
                json={
                    "object": "list",
                    "data": [
                        {
                            "id": "mlx-community/Qwen3-0.6B-8bit",
                            "object": "model",
                        }
                    ],
                },
            )
        if request.method == "POST" and request.url.path == "/v1/chat/completions":
            payload = json.loads(request.content)
            assert payload == {
                "model": "mlx-community/Qwen3-0.6B-8bit",
                "messages": [{"role": "user", "content": "hello real model"}],
                "stream": False,
            }
            return httpx.Response(
                200,
                json={
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "real backend response",
                            }
                        }
                    ]
                },
            )
        return httpx.Response(404)

    backend = OpenAICompatibleBackend(
        base_url="http://backend.test/v1",
        api_key="test-api-key",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    await backend.load()
    try:
        assert await backend.ready() is True
        assert await backend.list_models() == [
            {"id": "mlx-community/Qwen3-0.6B-8bit", "object": "model"}
        ]
        assert (
            await backend.generate(
                "hello real model",
                model="mlx-community/Qwen3-0.6B-8bit",
            )
            == "real backend response"
        )
    finally:
        await backend.close()

    assert requests[0].headers["authorization"] == "Bearer test-api-key"


@pytest.mark.anyio
async def test_openai_compatible_backend_streams_openai_sse_chunks() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content)
        assert payload["stream"] is True
        return httpx.Response(
            200,
            content=(
                b'data: {"choices":[{"delta":{"content":"real "}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"stream"}}]}\n\n'
                b"data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )

    backend = OpenAICompatibleBackend(
        base_url="http://backend.test/v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    await backend.load()
    try:
        chunks = [
            chunk
            async for chunk in backend.stream(
                "hello stream",
                model="mlx-community/Qwen3-0.6B-8bit",
            )
        ]
    finally:
        await backend.close()

    assert chunks == ["real ", "stream"]
