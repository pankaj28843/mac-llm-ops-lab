import os
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    service_name: str = "mac-llm-ops-lab"
    request_id_header: str = "x-request-id"
    model_allowlist: tuple[str, ...] = ()
    capture_request_bodies: bool = False


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    source = os.environ if env is None else env
    values: dict[str, object] = {}

    if service_name := source.get("MAC_LLM_OPS_SERVICE_NAME"):
        values["service_name"] = service_name
    if request_id_header := source.get("MAC_LLM_OPS_REQUEST_ID_HEADER"):
        values["request_id_header"] = request_id_header
    if model_allowlist := source.get("MAC_LLM_OPS_MODEL_ALLOWLIST"):
        values["model_allowlist"] = _parse_csv(model_allowlist)
    if capture_request_bodies := source.get("MAC_LLM_OPS_CAPTURE_REQUEST_BODIES"):
        values["capture_request_bodies"] = _parse_bool(capture_request_bodies)

    return Settings(**values)


def _parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean setting: {value!r}")
