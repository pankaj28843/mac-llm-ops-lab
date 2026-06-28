from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

RUNTIME_EVIDENCE_MANIFEST_SCHEMA_VERSION = "runtime-evidence-manifest/v1"


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
    normalized_command = _validated_command(command)
    normalized_artifact_dir = _validated_artifact_dir(artifact_dir)
    normalized_log_path = _validated_log_path(
        log_path,
        artifact_dir=normalized_artifact_dir,
    )
    return {
        "schema_version": RUNTIME_EVIDENCE_MANIFEST_SCHEMA_VERSION,
        "git_sha": git_sha,
        "command": normalized_command,
        "artifact_dir": normalized_artifact_dir,
        "log_path": normalized_log_path,
        "host": dict(host),
        "backend": {
            "id": backend_id,
            "model_id": model_id,
        },
        "runtime_config": dict(runtime_config),
        "ports": dict(ports),
    }


def _validated_command(command: Sequence[str]) -> list[str]:
    normalized = list(command)
    if not normalized or any(not part for part in normalized):
        raise ValueError("command must contain at least one non-empty part")
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
