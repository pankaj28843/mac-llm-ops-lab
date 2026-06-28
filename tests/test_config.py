from mac_llm_ops_lab.config import load_settings


def test_settings_parse_environment_overrides_without_external_services() -> None:
    settings = load_settings(
        {
            "MAC_LLM_OPS_SERVICE_NAME": "local-serving-lab",
            "MAC_LLM_OPS_REQUEST_ID_HEADER": "x-trace-id",
            "MAC_LLM_OPS_MODEL_ALLOWLIST": "fake-small, fake-large ,, fake-mlx",
            "MAC_LLM_OPS_CAPTURE_REQUEST_BODIES": "true",
            "MAC_LLM_OPS_BACKEND_KIND": "openai-compatible",
            "MAC_LLM_OPS_OPENAI_BASE_URL": "http://127.0.0.1:8100/v1",
            "MAC_LLM_OPS_OPENAI_API_KEY": "local-key",
            "MAC_LLM_OPS_OPENAI_TIMEOUT_SECONDS": "7.5",
        }
    )

    assert settings.service_name == "local-serving-lab"
    assert settings.request_id_header == "x-trace-id"
    assert settings.model_allowlist == ("fake-small", "fake-large", "fake-mlx")
    assert settings.capture_request_bodies is True
    assert settings.backend_kind == "openai-compatible"
    assert settings.openai_base_url == "http://127.0.0.1:8100/v1"
    assert settings.openai_api_key == "local-key"
    assert settings.openai_timeout_seconds == 7.5


def test_settings_defaults_keep_prompt_capture_disabled() -> None:
    settings = load_settings({})

    assert settings.service_name == "mac-llm-ops-lab"
    assert settings.request_id_header == "x-request-id"
    assert settings.model_allowlist == ()
    assert settings.capture_request_bodies is False
    assert settings.backend_kind == "fake"
    assert settings.openai_base_url == "http://127.0.0.1:8100/v1"
    assert settings.openai_api_key is None
    assert settings.openai_timeout_seconds == 30.0
