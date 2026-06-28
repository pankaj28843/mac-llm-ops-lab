import json
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

from mac_llm_ops_lab.runtime_guard import RUNTIME_PREFLIGHT_REPORT_SCHEMA_VERSION

RUNTIME_EVIDENCE_MANIFEST_SCHEMA_VERSION = "runtime-evidence-manifest/v1"
RUNTIME_EXECUTION_RECORD_SCHEMA_VERSION = "runtime-execution-record/v1"
RUNTIME_EVIDENCE_BUNDLE_SCHEMA_VERSION = "runtime-evidence-bundle/v1"
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


def build_runtime_execution_record(
    *,
    preflight_report: Mapping[str, object],
    evidence_manifest: Mapping[str, object],
) -> dict[str, object]:
    _validate_schema_version(
        preflight_report,
        expected_schema_version=RUNTIME_PREFLIGHT_REPORT_SCHEMA_VERSION,
        field_name="preflight_report",
    )
    _validate_schema_version(
        evidence_manifest,
        expected_schema_version=RUNTIME_EVIDENCE_MANIFEST_SCHEMA_VERSION,
        field_name="evidence_manifest",
    )
    _validate_evidence_manifest_payload(evidence_manifest)
    _validate_preflight_manifest_consistency(
        preflight_report=preflight_report,
        evidence_manifest=evidence_manifest,
    )
    decision = _validated_preflight_decision(preflight_report)
    return {
        "schema_version": RUNTIME_EXECUTION_RECORD_SCHEMA_VERSION,
        "can_execute": decision["allowed"],
        "reason_code": decision["reason_code"],
        "preflight_report": dict(preflight_report),
        "evidence_manifest": dict(evidence_manifest),
    }


def write_runtime_execution_record(
    record: Mapping[str, object],
    *,
    output_root: Path,
) -> Path:
    canonical_record = _canonical_runtime_execution_record(record)
    evidence_manifest = _mapping_field(canonical_record, "evidence_manifest")
    artifact_dir = str(evidence_manifest["artifact_dir"])
    output_dir = output_root / artifact_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "execution-record.json"
    output_path.write_text(
        json.dumps(canonical_record, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def load_runtime_execution_record(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("execution record JSON must contain a JSON object")
    return _canonical_runtime_execution_record(payload)


def build_runtime_evidence_bundle_index(
    *,
    execution_record: Mapping[str, object],
    evidence_files: Mapping[str, str],
) -> dict[str, object]:
    canonical_record = _canonical_runtime_execution_record(execution_record)
    evidence_manifest = _mapping_field(canonical_record, "evidence_manifest")
    artifact_dir = str(evidence_manifest["artifact_dir"])
    execution_record_path = f"{artifact_dir}/execution-record.json"
    log_path = str(evidence_manifest["log_path"])
    return {
        "schema_version": RUNTIME_EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "artifact_dir": artifact_dir,
        "execution_record_path": execution_record_path,
        "log_path": log_path,
        "can_execute": canonical_record["can_execute"],
        "reason_code": canonical_record["reason_code"],
        "evidence_files": _validated_evidence_files(
            evidence_files,
            artifact_dir=artifact_dir,
        ),
    }


def _canonical_runtime_execution_record(
    record: Mapping[str, object],
) -> dict[str, object]:
    _validate_schema_version(
        record,
        expected_schema_version=RUNTIME_EXECUTION_RECORD_SCHEMA_VERSION,
        field_name="record",
    )
    canonical_record = build_runtime_execution_record(
        preflight_report=_mapping_field(record, "preflight_report"),
        evidence_manifest=_mapping_field(record, "evidence_manifest"),
    )
    if record.get("can_execute") != canonical_record["can_execute"]:
        raise ValueError("can_execute must match the preflight decision")
    if record.get("reason_code") != canonical_record["reason_code"]:
        raise ValueError("reason_code must match the preflight decision")
    return canonical_record


def _validated_evidence_files(
    evidence_files: Mapping[str, str],
    *,
    artifact_dir: str,
) -> list[dict[str, str]]:
    normalized = []
    for label, path in sorted(evidence_files.items()):
        normalized_label = _validated_non_empty_string(
            label,
            field_name="evidence file label",
        )
        normalized_path = _validated_bundle_path(
            path,
            artifact_dir=artifact_dir,
            field_name="evidence file path",
        )
        normalized.append({"label": normalized_label, "path": normalized_path})
    return normalized


def _validated_bundle_path(
    value: object,
    *,
    artifact_dir: str,
    field_name: str,
) -> str:
    path = _validated_relative_path(
        _validated_non_empty_string(value, field_name=field_name),
        field_name=field_name,
    )
    try:
        path.relative_to(PurePosixPath(artifact_dir))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be inside artifact_dir") from exc
    return path.as_posix()


def _validate_schema_version(
    source: Mapping[str, object],
    *,
    expected_schema_version: str,
    field_name: str,
) -> None:
    if source.get("schema_version") != expected_schema_version:
        raise ValueError(
            f"{field_name} schema_version must be {expected_schema_version}",
        )


def _validated_preflight_decision(
    preflight_report: Mapping[str, object],
) -> dict[str, object]:
    decision = _mapping_field(preflight_report, "decision")
    allowed = decision.get("allowed")
    if not isinstance(allowed, bool):
        raise ValueError("decision.allowed must be a boolean")
    reason_code = _validated_non_empty_string(
        decision.get("reason_code"),
        field_name="decision.reason_code",
    )
    return {
        "allowed": allowed,
        "reason_code": reason_code,
    }


def _validate_evidence_manifest_payload(
    evidence_manifest: Mapping[str, object],
) -> None:
    backend = _mapping_field(evidence_manifest, "backend")
    _validated_non_empty_string(evidence_manifest.get("git_sha"), field_name="git_sha")
    _validated_command(_sequence_field(evidence_manifest, "command"))
    artifact_dir = _validated_artifact_dir(
        _validated_non_empty_string(
            evidence_manifest.get("artifact_dir"),
            field_name="artifact_dir",
        )
    )
    _validated_log_path(
        _validated_non_empty_string(
            evidence_manifest.get("log_path"),
            field_name="log_path",
        ),
        artifact_dir=artifact_dir,
    )
    _validated_host(_mapping_field(evidence_manifest, "host"))
    _validated_non_empty_string(backend.get("id"), field_name="backend_id")
    _validated_non_empty_string(backend.get("model_id"), field_name="model_id")
    _validated_non_empty_mapping(
        _mapping_field(evidence_manifest, "runtime_config"),
        field_name="runtime_config",
    )
    _validated_ports(_mapping_field(evidence_manifest, "ports"))


def _validate_preflight_manifest_consistency(
    *,
    preflight_report: Mapping[str, object],
    evidence_manifest: Mapping[str, object],
) -> None:
    backend = _mapping_field(evidence_manifest, "backend")
    preflight_backend_id = preflight_report.get("backend_id")
    manifest_backend_id = backend.get("id")
    if preflight_backend_id != manifest_backend_id:
        raise ValueError("backend id mismatch between preflight and manifest")
    preflight_model_id = preflight_report.get("model_id")
    manifest_model_id = backend.get("model_id")
    if preflight_model_id != manifest_model_id:
        raise ValueError("model id mismatch between preflight and manifest")


def _mapping_field(
    source: Mapping[str, object],
    field_name: str,
) -> Mapping[str, object]:
    value = source.get(field_name)
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return value


def _sequence_field(
    source: Mapping[str, object],
    field_name: str,
) -> Sequence[object]:
    value = source.get(field_name)
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a sequence")
    return value


def _validated_non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value


def _validated_command(command: Sequence[str]) -> list[str]:
    normalized = list(command)
    if not normalized or any(
        not isinstance(part, str) or not part for part in normalized
    ):
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


def _validated_ports(ports: Mapping[str, object]) -> dict[str, int]:
    normalized = dict(ports)
    if not normalized:
        raise ValueError("ports must be non-empty")
    if any(
        not name or not isinstance(port, int) or isinstance(port, bool) or port <= 0
        for name, port in normalized.items()
    ):
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
