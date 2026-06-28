import json

import pytest

from mac_llm_ops_lab.runtime_artifacts import (
    build_runtime_evidence_bundle_index,
    build_runtime_evidence_manifest,
    build_runtime_execution_record,
    load_runtime_execution_record,
    write_runtime_execution_record,
)
from mac_llm_ops_lab.runtime_guard import (
    RuntimePreflightPlan,
    build_runtime_preflight_report,
)


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


def test_runtime_execution_record_combines_manifest_and_preflight_decision() -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="fake-batched-backend",
            model_id="fake-local-model",
            explicitly_authorized=False,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )

    record = build_runtime_execution_record(
        preflight_report=preflight_report,
        evidence_manifest=manifest,
    )

    assert record == {
        "schema_version": "runtime-execution-record/v1",
        "can_execute": False,
        "reason_code": "runtime_not_authorized",
        "preflight_report": preflight_report,
        "evidence_manifest": manifest,
    }
    assert json.loads(json.dumps(record, sort_keys=True)) == record


def test_runtime_execution_record_rejects_backend_or_model_mismatch() -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="vllm-mlx",
            model_id="mlx-community/Qwen3-0.6B-8bit",
            explicitly_authorized=True,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )

    with pytest.raises(ValueError, match="backend"):
        build_runtime_execution_record(
            preflight_report=preflight_report,
            evidence_manifest=manifest,
        )


def test_runtime_execution_record_rejects_malformed_payload_shape() -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="fake-batched-backend",
            model_id="fake-local-model",
            explicitly_authorized=True,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )

    malformed_preflight_schema = {
        **preflight_report,
        "schema_version": "runtime-preflight/v0",
    }
    with pytest.raises(ValueError, match="preflight_report schema_version"):
        build_runtime_execution_record(
            preflight_report=malformed_preflight_schema,
            evidence_manifest=manifest,
        )

    malformed_manifest_schema = {
        **manifest,
        "schema_version": "runtime-evidence-manifest/v0",
    }
    with pytest.raises(ValueError, match="evidence_manifest schema_version"):
        build_runtime_execution_record(
            preflight_report=preflight_report,
            evidence_manifest=malformed_manifest_schema,
        )

    non_boolean_decision = {
        **preflight_report,
        "decision": {
            **preflight_report["decision"],
            "allowed": "yes",
        },
    }
    with pytest.raises(ValueError, match="decision.allowed"):
        build_runtime_execution_record(
            preflight_report=non_boolean_decision,
            evidence_manifest=manifest,
        )

    empty_reason_code = {
        **preflight_report,
        "decision": {
            **preflight_report["decision"],
            "reason_code": "",
        },
    }
    with pytest.raises(ValueError, match="decision.reason_code"):
        build_runtime_execution_record(
            preflight_report=empty_reason_code,
            evidence_manifest=manifest,
        )


def test_runtime_execution_record_rejects_malformed_manifest_payload() -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="fake-batched-backend",
            model_id="fake-local-model",
            explicitly_authorized=True,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )

    missing_command = {
        key: value for key, value in manifest.items() if key != "command"
    }
    with pytest.raises(ValueError, match="command"):
        build_runtime_execution_record(
            preflight_report=preflight_report,
            evidence_manifest=missing_command,
        )

    invalid_artifact_dir = {
        **manifest,
        "artifact_dir": "runtime/bce02cc-fake-smoke",
    }
    with pytest.raises(ValueError, match="artifact_dir"):
        build_runtime_execution_record(
            preflight_report=preflight_report,
            evidence_manifest=invalid_artifact_dir,
        )

    missing_host_label = {
        **manifest,
        "host": {"os": "macOS", "memory_gib": 24},
    }
    with pytest.raises(ValueError, match="host"):
        build_runtime_execution_record(
            preflight_report=preflight_report,
            evidence_manifest=missing_host_label,
        )

    empty_runtime_config = {
        **manifest,
        "runtime_config": {},
    }
    with pytest.raises(ValueError, match="runtime_config"):
        build_runtime_execution_record(
            preflight_report=preflight_report,
            evidence_manifest=empty_runtime_config,
        )

    invalid_ports = {
        **manifest,
        "ports": {"api": 0},
    }
    with pytest.raises(ValueError, match="ports"):
        build_runtime_execution_record(
            preflight_report=preflight_report,
            evidence_manifest=invalid_ports,
        )


def test_write_runtime_execution_record_persists_json_under_artifact_dir(
    tmp_path,
) -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="fake-batched-backend",
            model_id="fake-local-model",
            explicitly_authorized=True,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )
    record = build_runtime_execution_record(
        preflight_report=preflight_report,
        evidence_manifest=manifest,
    )

    output_path = write_runtime_execution_record(record, output_root=tmp_path)

    assert output_path == (
        tmp_path / "artifacts/runtime/bce02cc-fake-smoke/execution-record.json"
    )
    written_text = output_path.read_text(encoding="utf-8")
    assert written_text.endswith("\n")
    assert json.loads(written_text) == record
    assert list(json.loads(written_text)) == [
        "can_execute",
        "evidence_manifest",
        "preflight_report",
        "reason_code",
        "schema_version",
    ]


def test_write_runtime_execution_record_rejects_tampered_top_level_state(
    tmp_path,
) -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="fake-batched-backend",
            model_id="fake-local-model",
            explicitly_authorized=False,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )
    record = build_runtime_execution_record(
        preflight_report=preflight_report,
        evidence_manifest=manifest,
    )

    with pytest.raises(ValueError, match="can_execute"):
        write_runtime_execution_record(
            {**record, "can_execute": True},
            output_root=tmp_path,
        )
    with pytest.raises(ValueError, match="reason_code"):
        write_runtime_execution_record(
            {**record, "reason_code": "runtime_preflight_passed"},
            output_root=tmp_path,
        )


def test_load_runtime_execution_record_round_trips_and_validates_json(
    tmp_path,
) -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="fake-batched-backend",
            model_id="fake-local-model",
            explicitly_authorized=False,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )
    record = build_runtime_execution_record(
        preflight_report=preflight_report,
        evidence_manifest=manifest,
    )
    output_path = write_runtime_execution_record(record, output_root=tmp_path)

    assert load_runtime_execution_record(output_path) == record

    output_path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_runtime_execution_record(output_path)

    output_path.write_text(
        json.dumps({**record, "can_execute": True}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="can_execute"):
        load_runtime_execution_record(output_path)


def test_runtime_evidence_bundle_index_is_json_safe_and_deterministic() -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="fake-batched-backend",
            model_id="fake-local-model",
            explicitly_authorized=False,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )
    record = build_runtime_execution_record(
        preflight_report=preflight_report,
        evidence_manifest=manifest,
    )

    bundle_index = build_runtime_evidence_bundle_index(
        execution_record=record,
        evidence_files={
            "metrics": "artifacts/runtime/bce02cc-fake-smoke/metrics.json",
            "chat_sample": "artifacts/runtime/bce02cc-fake-smoke/chat.json",
        },
    )

    assert bundle_index == {
        "schema_version": "runtime-evidence-bundle/v1",
        "artifact_dir": "artifacts/runtime/bce02cc-fake-smoke",
        "execution_record_path": (
            "artifacts/runtime/bce02cc-fake-smoke/execution-record.json"
        ),
        "log_path": "artifacts/runtime/bce02cc-fake-smoke/service.log",
        "can_execute": False,
        "reason_code": "runtime_not_authorized",
        "evidence_files": [
            {
                "label": "chat_sample",
                "path": "artifacts/runtime/bce02cc-fake-smoke/chat.json",
            },
            {
                "label": "metrics",
                "path": "artifacts/runtime/bce02cc-fake-smoke/metrics.json",
            },
        ],
    }
    assert json.loads(json.dumps(bundle_index, sort_keys=True)) == bundle_index


def test_runtime_evidence_bundle_index_rejects_unsafe_evidence_paths() -> None:
    preflight_report = build_runtime_preflight_report(
        RuntimePreflightPlan(
            backend_id="fake-batched-backend",
            model_id="fake-local-model",
            explicitly_authorized=False,
            model_weights_gib=1.0,
            kv_cache_gib=1.0,
            runtime_overhead_gib=1.0,
            service_overhead_gib=1.0,
        )
    )
    manifest = build_runtime_evidence_manifest(
        git_sha="bce02cc",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cli"),
        artifact_dir="artifacts/runtime/bce02cc-fake-smoke",
        log_path="artifacts/runtime/bce02cc-fake-smoke/service.log",
        host={"os": "macOS", "chip": "Apple Silicon", "memory_gib": 24},
        backend_id="fake-batched-backend",
        model_id="fake-local-model",
        runtime_config={"quantization": "none"},
        ports={"api": 8000},
    )
    record = build_runtime_execution_record(
        preflight_report=preflight_report,
        evidence_manifest=manifest,
    )

    with pytest.raises(ValueError, match="evidence file label"):
        build_runtime_evidence_bundle_index(
            execution_record=record,
            evidence_files={"": "artifacts/runtime/bce02cc-fake-smoke/chat.json"},
        )
    with pytest.raises(ValueError, match="evidence file path"):
        build_runtime_evidence_bundle_index(
            execution_record=record,
            evidence_files={
                "absolute": "/tmp/artifacts/runtime/bce02cc-fake-smoke/chat.json",
            },
        )
    with pytest.raises(ValueError, match="evidence file path"):
        build_runtime_evidence_bundle_index(
            execution_record=record,
            evidence_files={
                "traversal": "artifacts/runtime/bce02cc-fake-smoke/../chat.json",
            },
        )
    with pytest.raises(ValueError, match="evidence file path"):
        build_runtime_evidence_bundle_index(
            execution_record=record,
            evidence_files={"outside": "artifacts/runtime/other/chat.json"},
        )
