from fastapi.testclient import TestClient

from mac_llm_ops_lab.cli import build_app, build_backend
from mac_llm_ops_lab.config import Settings
from mac_llm_ops_lab.openai_compatible_backend import OpenAICompatibleBackend


def test_cli_build_app_uses_fake_backend_without_external_services() -> None:
    app = build_app(settings=Settings(service_name="cli-test-serving"))

    with TestClient(app) as client:
        ready_response = client.get("/ready")
        models_response = client.get("/v1/models")
        generation_response = client.post(
            "/v1/chat/completions",
            json={
                "model": "fake-local-model",
                "messages": [{"role": "user", "content": "hello cli"}],
                "stream": False,
            },
        )

    assert app.title == "cli-test-serving"
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
    assert models_response.status_code == 200
    assert models_response.json()["data"] == [
        {"id": "fake-local-model", "object": "model"}
    ]
    assert generation_response.status_code == 200
    assert generation_response.json()["choices"][0]["message"]["content"] == (
        "fake-local-model response to hello cli"
    )


def test_cli_module_exports_fake_backend_asgi_app_without_external_services() -> None:
    from mac_llm_ops_lab import cli

    with TestClient(cli.app) as client:
        ready_response = client.get("/ready")
        models_response = client.get("/v1/models")

    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
    assert models_response.status_code == 200
    assert models_response.json()["data"] == [
        {"id": "fake-local-model", "object": "model"}
    ]


def test_cli_build_backend_selects_openai_compatible_backend_from_settings() -> None:
    backend = build_backend(
        Settings(
            backend_kind="openai-compatible",
            openai_base_url="http://127.0.0.1:8100/v1",
            openai_api_key="local-key",
            openai_timeout_seconds=3.0,
        )
    )

    assert isinstance(backend, OpenAICompatibleBackend)
    assert backend.base_url == "http://127.0.0.1:8100/v1"
