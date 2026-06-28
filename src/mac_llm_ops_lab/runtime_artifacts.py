from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

RUNTIME_EVIDENCE_MANIFEST_SCHEMA_VERSION = "runtime-evidence-manifest/v1"
REQUIRED_HOST_LABELS = ("os", "chip", "memory_gib")


def build_runtime_evidence_manifest(
    *,
    git_sha: str,
    command: Sequence[str],
    artifact_dir: str,
    log_path: str,
    host: Mapping[str, object],
    backend_id: str,
    model_id: str,
    runtime_config: Mapping[str, object],
    ports: Mapping[str, int],
) -> dict[str, object]:
    normalized_git_sha = _validated_non_empty_string(git_sha, field_name="git_sha")
    normalized_backend_id = _validated_non_empty_string(
        backend_id,
        field_name="backend_id",
    )
    normalized_model_id = _validated_non_empty_string(model_id, field_name="model_id")
    normalized_command = _validated_command(command)
    normalized_artifact_dir = _validated_artifact_dir(artifact_dir)
    normalized_log_path = _validated_log_path(
        log_path,
        artifact_dir=normalized_artifact_dir,
    )
    normalized_host = _validated_host(host)
    normalized_runtime_config = _validated_non_empty_mapping(
        runtime_config,
        field_name="runtime_config",
    )
    normalized_ports = _validated_ports(ports)
    return {
        "schema_version": RUNTIME_EVIDENCE_MANIFEST_SCHEMA_VERSION,
        "git_sha": normalized_git_sha,
        "command": normalized_command,
        "artifact_dir": normalized_artifact_dir,
        "log_path": normalized_log_path,
        "host": normalized_host,
        "backend": {
            "id": normalized_backend_id,
            "model_id": normalized_model_id,
        },
        "runtime_config": normalized_runtime_config,
        "ports": normalized_ports,
    }


def _validated_non_empty_string(value: str, *, field_name: str) -> str:
    if not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value


def _validated_command(command: Sequence[str]) -> list[str]:
    normalized = list(command)
    if not normalized or any(not part for part in normalized):
        raise ValueError("command must contain at least one non-empty part")
    return normalized


def _validated_host(host: Mapping[str, object]) -> dict[str, object]:
    normalized = _validated_non_empty_mapping(host, field_name="host")
    missing = [key for key in REQUIRED_HOST_LABELS if key not in normalized]
    if missing:
        raise ValueError(f"host is missing required labels: {', '.join(missing)}")
    return normalized


def _validated_non_empty_mapping(
    value: Mapping[str, object],
    *,
    field_name: str,
) -> dict[str, object]:
    normalized = dict(value)
    if not normalized:
        raise ValueError(f"{field_name} must be non-empty")
    return normalized


def _validated_ports(ports: Mapping[str, int]) -> dict[str, int]:
    normalized = dict(ports)
    if not normalized:
        raise ValueError("ports must be non-empty")
    if any(not name or port <= 0 for name, port in normalized.items()):
        raise ValueError("ports must use non-empty names and positive values")
    return normalized


def _validated_artifact_dir(artifact_dir: str) -> str:
    path = _validated_relative_path(artifact_dir, field_name="artifact_dir")
    if len(path.parts) < 3 or path.parts[:2] != ("artifacts", "runtime"):
        raise ValueError("artifact_dir must be under artifacts/runtime/")
    return path.as_posix()


def _validated_log_path(log_path: str, *, artifact_dir: str) -> str:
    path = _validated_relative_path(log_path, field_name="log_path")
    artifact_path = PurePosixPath(artifact_dir)
    try:
        path.relative_to(artifact_path)
    except ValueError as exc:
        raise ValueError("log_path must be inside artifact_dir") from exc
    if path.suffix != ".log":
        raise ValueError("log_path must point to a .log file")
    return path.as_posix()


def _validated_relative_path(value: str, *, field_name: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a relative path without traversal")
    return path
