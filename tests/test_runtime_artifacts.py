import json

import pytest

from mac_llm_ops_lab.runtime_artifacts import build_runtime_evidence_manifest


def test_runtime_evidence_manifest_is_json_safe_and_deterministic() -> None:
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={
            "os": "macOS",
            "chip": "Apple Silicon",
            "memory_gib": 24,
        },
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={
            "quantization": "none",
            "max_context_tokens": 2048,
            "max_concurrency": 1,
        },
        ports={"api": 8000},
    )

    assert manifest == {
        "schema_version": "runtime-evidence-manifest/v1",
        "git_sha": "bce02cc",
        "command": ["uv", "run", "python", "-m", "mac_llm_ops_lab.cli"],
        "artifact_dir": "artifacts/runtime/bce02cc-fake-smoke",
        "log_path": "artifacts/runtime/bce02cc-fake-smoke/service.log",
        "host": {
            "os": "macOS",
            "chip": "Apple Silicon",
            "memory_gib": 24,
        },
        "backend": {
            "id": "fake-batched-backend",
            "model_id": "fake-local-model",
        },
        "runtime_config": {
            "quantization": "none",
            "max_context_tokens": 2048,
            "max_concurrency": 1,
        },
        "ports": {"api": 8000},
    }
    assert json.loads(json.dumps(manifest, sort_keys=True)) == manifest


def test_runtime_evidence_manifest_rejects_unsafe_paths_and_empty_commands() -> None:
    base_kwargs = {
        "git_sha": "bce02cc",
        "command": ("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        "artifact_dir": "artifacts/runtime/bce02cc-fake-smoke",
        "log_path": "artifacts/runtime/bce02cc-fake-smoke/service.log",
        "host": {"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        "backend_id": "fake-batched-backend",
        "model_id": "fake-local-model",
        "runtime_config": {"quantization": "none"},
        "ports": {"api": 8000},
    }

    with pytest.raises(ValueError, match="artifact_dir"):
        build_runtime_evidence_manifest(
            **{**base_kwargs, "artifact_dir": "/tmp/runtime-artifacts"}
        )
    with pytest.raises(ValueError, match="artifact_dir"):
        build_runtime_evidence_manifest(
            **{**base_kwargs, "artifact_dir": "artifacts/../private"}
        )
    with pytest.raises(ValueError, match="log_path"):
        build_runtime_evidence_manifest(
            **{**base_kwargs, "log_path": "artifacts/runtime/other/service.log"}
        )
    with pytest.raises(ValueError, match="command"):
        build_runtime_evidence_manifest(**{**base_kwargs, "command": ()})


def test_runtime_evidence_manifest_rejects_missing_required_labels() -> None:
    base_kwargs = {
        "git_sha": "bce02cc",
        "command": ("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        "artifact_dir": "artifacts/runtime/bce02cc-fake-smoke",
        "log_path": "artifacts/runtime/bce02cc-fake-smoke/service.log",
        "host": {"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        "backend_id": "fake-batched-backend",
        "model_id": "fake-local-model",
        "runtime_config": {"quantization": "none"},
        "ports": {"api": 8000},
    }

    with pytest.raises(ValueError, match="git_sha"):
        build_runtime_evidence_manifest(**{**base_kwargs, "git_sha": ""})
    with pytest.raises(ValueError, match="backend_id"):
        build_runtime_evidence_manifest(**{**base_kwargs, "backend_id": ""})
    with pytest.raises(ValueError, match="model_id"):
        build_runtime_evidence_manifest(**{**base_kwargs, "model_id": ""})
    with pytest.raises(ValueError, match="host"):
        build_runtime_evidence_manifest(
            **{**base_kwargs, "host": {"os": "macOS", "memory_gib": 24}}
        )
    with pytest.raises(ValueError, match="runtime_config"):
        build_runtime_evidence_manifest(**{**base_kwargs, "runtime_config": {}})
    with pytest.raises(ValueError, match="ports"):
        build_runtime_evidence_manifest(**{**base_kwargs, "ports": {}})
