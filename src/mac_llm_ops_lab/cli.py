from fastapi import FastAPI

from mac_llm_ops_lab.app import create_app
from mac_llm_ops_lab.batching import FakeBatchedBackend
from mac_llm_ops_lab.config import Settings, load_settings

DEFAULT_FAKE_MODEL_ID = "fake-local-model"


def build_app(*, settings: Settings | None = None) -> FastAPI:
    app_settings = settings or load_settings()
    return create_app(
        backend=FakeBatchedBackend(model_id=_fake_model_id(app_settings)),
        settings=app_settings,
    )


def _fake_model_id(settings: Settings) -> str:
    if settings.model_allowlist:
        return settings.model_allowlist[0]
    return DEFAULT_FAKE_MODEL_ID


app = build_app()
