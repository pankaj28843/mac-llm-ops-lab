from fastapi import FastAPI

from mac_llm_ops_lab.app import ModelBackend, create_app
from mac_llm_ops_lab.batching import FakeBatchedBackend
from mac_llm_ops_lab.config import Settings, load_settings
from mac_llm_ops_lab.openai_compatible_backend import OpenAICompatibleBackend

DEFAULT_FAKE_MODEL_ID = "fake-local-model"


def build_app(*, settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    return create_app(backend=build_backend(app_settings), settings=app_settings)


def build_backend(settings: Settings) -> ModelBackend:
    if settings.backend_kind == "openai-compatible":
        return OpenAICompatibleBackend(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    return FakeBatchedBackend(model_id=_fake_model_id(settings))


def _fake_model_id(settings: Settings) -> str:
    if settings.model_allowlist:
        return settings.model_allowlist[0]
    return DEFAULT_FAKE_MODEL_ID


app = build_app()
