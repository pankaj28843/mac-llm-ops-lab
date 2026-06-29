import json
import re
from collections.abc import AsyncIterator
from pathlib import Path

import anyio
import httpx
from fastapi.testclient import TestClient

from mac_llm_ops_lab.app import create_app
from mac_llm_ops_lab.openai_compatible_backend import OpenAICompatibleBackend


class RecordingBackend:
    def __init__(self) -> None:
        self.generated_options: list[dict[str, object]] = []
        self.streamed_options: list[dict[str, object]] = []

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
        options: dict[str, object] | None = None,
    ) -> str:
        self.generated_options.append(dict(options or {}))
        return f"fake response to {prompt}"

    async def stream(
        self,
        prompt: str,
        model: str,
        *,
        options: dict[str, object] | None = None,
    ) -> AsyncIterator[str]:
        self.streamed_options.append(dict(options or {}))
        yield f"fake stream response to {prompt}"


def test_open_webui_can_discover_models_with_placeholder_bearer_token() -> None:
    backend = RecordingBackend()
    app = create_app(backend=backend)

    with TestClient(app) as client:
        response = client.get(
            "/v1/models",
            headers={"Authorization": "Bearer local-dev-placeholder"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "object": "list",
        "data": [
            {
                "id": "fake-local-model",
                "object": "model",
                "created": 0,
                "owned_by": "mac-llm-ops-lab",
            }
        ],
    }


def test_open_webui_chat_params_are_accepted_forwarded_and_counted() -> None:
    backend = RecordingBackend()
    app = create_app(backend=backend)

    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer local-dev-placeholder"},
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "hello webui"}],
                "temperature": 0.2,
                "top_p": 0.9,
                "max_tokens": 12,
                "max_completion_tokens": 16,
                "stop": ["</s>"],
                "seed": 7,
                "logit_bias": {"42": -1},
                "user": "local-operator",
                "stream": False,
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["object"] == "chat.completion"
    assert body["choices"][0]["message"] == {
        "role": "assistant",
        "content": "fake response to hello webui",
    }
    assert body["usage"] == {
        "prompt_tokens": 2,
        "completion_tokens": 5,
        "total_tokens": 7,
    }
    assert backend.generated_options == [
        {
            "temperature": 0.2,
            "top_p": 0.9,
            "max_tokens": 12,
            "max_completion_tokens": 16,
            "stop": ["</s>"],
            "seed": 7,
            "logit_bias": {"42": -1},
            "user": "local-operator",
        }
    ]


def test_openai_compatible_backend_forwards_open_webui_generation_options() -> None:
    seen_payloads: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_payloads.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "backend response"}}
                ]
            },
        )

    backend = OpenAICompatibleBackend(
        base_url="http://backend.test/v1",
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    async def call_backend() -> str:
        await backend.load()
        try:
            return await backend.generate(
                "hello",
                "mlx-model",
                options={"temperature": 0.1, "max_tokens": 8},
            )
        finally:
            await backend.close()

    assert anyio.run(call_backend) == "backend response"
    assert seen_payloads == [
        {
            "model": "mlx-model",
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "temperature": 0.1,
            "max_tokens": 8,
        }
    ]


def test_native_open_webui_launch_defaults_have_visible_answer_budget() -> None:
    script = Path("scripts/run-vllm-mlx-backend.sh").read_text(encoding="utf-8")

    max_tokens_default = _shell_default(script, "VLLM_MLX_MAX_TOKENS")
    max_request_tokens_default = _shell_default(script, "VLLM_MLX_MAX_REQUEST_TOKENS")

    assert max_tokens_default >= 512
    assert max_request_tokens_default >= 1024
    assert "--default-chat-template-kwargs" in script
    assert '{"enable_thinking": false}' in script
    assert "--reasoning-parser" in script
    assert "qwen3" in script


def test_open_webui_docs_describe_compose_and_host_connection_contract() -> None:
    docs_path = Path("docs/operations.md")

    assert docs_path.exists()
    text = docs_path.read_text(encoding="utf-8")
    text_flat = " ".join(text.split())

    for required in (
        "Version/source-surface",
        "https://docs.openwebui.com",
        "OPENAI_API_BASE_URLS=http://api:8000/v1",
        "OPENAI_API_KEYS=local-dev-placeholder",
        "WEBUI_AUTH=False",
        "ENABLE_PERSISTENT_CONFIG=False",
        "ENABLE_OLLAMA_API=False",
        "host.docker.internal",
        "http://localhost:23000",
        "http://127.0.0.1:23001",
        "http://localhost:28000",
        "http://127.0.0.1:28020/v1",
        "/v1/models",
        "/v1/chat/completions",
        "temperature",
        "max_completion_tokens",
        "Do not commit real provider keys",
        "artifacts/runtime/2026-06-28T163030+0200-open-webui/",
        "artifacts/runtime/2026-06-28T174936+0200-open-webui-native-backend/",
        "visible final answer",
        "`finish_reason` is not `length`",
        "VLLM_MLX_MAX_TOKENS=512",
        "VLLM_MLX_DEFAULT_CHAT_TEMPLATE_KWARGS='{\"enable_thinking\": false}'",
        "VLLM_MLX_REASONING_PARSER=qwen3",
        "`delta.reasoning_content`",
        "non-empty `delta.content` chunks",
        "artifacts/runtime/2026-06-28T195945+0200-open-webui-visible-answer-no-think/",
    ):
        assert required in text_flat

    assert "little visible final-answer text" not in text_flat


def _shell_default(script: str, name: str) -> int:
    match = re.search(rf"\$\{{{name}:-(\d+)}}", script)
    assert match is not None
    return int(match.group(1))
