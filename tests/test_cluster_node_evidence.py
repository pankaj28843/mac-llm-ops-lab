import json
from pathlib import Path

import pytest

from mac_llm_ops_lab.cluster import (
    ClusterNode,
    build_node_evidence_report,
    main,
)


def _node(*, ports: dict[str, int] | None = None) -> ClusterNode:
    return ClusterNode(
        node_id="macbook-pro-local",
        hostname="macbook-pro.local",
        api_base_url="http://127.0.0.1:28020/v1",
        backend_base_url="http://127.0.0.1:28100/v1",
        backend_id="vllm-mlx",
        chip="Apple M3 Max",
        memory_gib=36,
        models=("mlx-community/Qwen3-0.6B-8bit",),
        queue_depth=0,
        ready=True,
        healthy=True,
        capabilities=("mlx", "openai-compatible", "streaming", "otel"),
        ports=ports or {"api": 28020, "backend": 28100, "phoenix": 26006},
    )


def _report_kwargs(**overrides: object) -> dict[str, object]:
    artifact_dir = "artifacts/runtime/test-node-evidence"
    values: dict[str, object] = {
        "node": _node(),
        "git_sha": "be50a7a",
        "command": ("scripts/run-model-backed-api.sh",),
        "artifact_dir": artifact_dir,
        "macos_version": "15.5",
        "model_id": "mlx-community/Qwen3-0.6B-8bit",
        "model_revision": "11de96878523501bcaa86104e3c186de07ff9068",
        "health_urls": {
            "api_ready": "http://127.0.0.1:28020/ready",
            "backend_models": "http://127.0.0.1:28100/v1/models",
        },
        "phoenix_url": "http://127.0.0.1:26006",
        "evidence_files": {
            "node_evidence": f"{artifact_dir}/node-evidence.json",
            "api_log": f"{artifact_dir}/api.log",
            "backend_log": f"{artifact_dir}/backend.log",
            "phoenix_spans": f"{artifact_dir}/phoenix-spans.json",
            "metrics": f"{artifact_dir}/metrics.json",
        },
    }
    values.update(overrides)
    return values


def test_node_evidence_report_is_json_safe_and_labels_high_port_runtime() -> None:
    report = build_node_evidence_report(**_report_kwargs())

    assert report == {
        "schema_version": "mac-studio-node-evidence/v1",
        "git_sha": "be50a7a",
        "artifact_dir": "artifacts/runtime/test-node-evidence",
        "command": ["scripts/run-model-backed-api.sh"],
        "requires_real_multi_node_proof": True,
        "node": {
            "node_id": "macbook-pro-local",
            "hostname": "macbook-pro.local",
            "api_base_url": "http://127.0.0.1:28020/v1",
            "backend_base_url": "http://127.0.0.1:28100/v1",
            "backend_id": "vllm-mlx",
            "chip": "Apple M3 Max",
            "memory_gib": 36,
            "models": ["mlx-community/Qwen3-0.6B-8bit"],
            "queue_depth": 0,
            "ready": True,
            "healthy": True,
            "capabilities": ["mlx", "openai-compatible", "streaming", "otel"],
            "ports": {"api": 28020, "backend": 28100, "phoenix": 26006},
        },
        "host": {
            "hostname": "macbook-pro.local",
            "chip": "Apple M3 Max",
            "memory_gib": 36,
            "macos_version": "15.5",
        },
        "backend": {
            "backend_id": "vllm-mlx",
            "model_id": "mlx-community/Qwen3-0.6B-8bit",
            "model_revision": "11de96878523501bcaa86104e3c186de07ff9068",
        },
        "service_endpoints": {
            "api_base_url": "http://127.0.0.1:28020/v1",
            "backend_base_url": "http://127.0.0.1:28100/v1",
            "health_urls": {
                "api_ready": "http://127.0.0.1:28020/ready",
                "backend_models": "http://127.0.0.1:28100/v1/models",
            },
            "phoenix_url": "http://127.0.0.1:26006",
        },
        "evidence_files": {
            "api_log": "artifacts/runtime/test-node-evidence/api.log",
            "backend_log": "artifacts/runtime/test-node-evidence/backend.log",
            "metrics": "artifacts/runtime/test-node-evidence/metrics.json",
            "node_evidence": "artifacts/runtime/test-node-evidence/node-evidence.json",
            "phoenix_spans": (
                "artifacts/runtime/test-node-evidence/phoenix-spans.json"
            ),
        },
    }
    assert json.loads(json.dumps(report, sort_keys=True)) == report


@pytest.mark.parametrize(
    ("override", "match"),
    (
        ({"node": _node(ports={"api": 8000})}, "20000-50000"),
        ({"command": ()}, "command"),
        ({"macos_version": ""}, "macos_version"),
        ({"model_id": "other-model"}, "model_id must be listed"),
        ({"health_urls": {"api_ready": "http://127.0.0.1:8000/ready"}}, "port"),
        ({"phoenix_url": "http://127.0.0.1:6006"}, "port"),
        (
            {
                "evidence_files": {
                    "node_evidence": (
                        "artifacts/runtime/test-node-evidence/node-evidence.json"
                    ),
                    "api_log": "/" + "Users/pankaj/private/api.log",
                    "backend_log": "artifacts/runtime/test-node-evidence/backend.log",
                    "phoenix_spans": (
                        "artifacts/runtime/test-node-evidence/phoenix-spans.json"
                    ),
                    "metrics": "artifacts/runtime/test-node-evidence/metrics.json",
                }
            },
            "relative path",
        ),
        (
            {
                "evidence_files": {
                    "node_evidence": (
                        "artifacts/runtime/test-node-evidence/node-evidence.json"
                    ),
                    "api_log": "artifacts/runtime/test-node-evidence/api.log",
                    "backend_log": "artifacts/runtime/test-node-evidence/backend.log",
                    "phoenix_spans": (
                        "artifacts/runtime/test-node-evidence/phoenix-spans.json"
                    ),
                }
            },
            "metrics",
        ),
    ),
)
def test_node_evidence_report_rejects_unpublishable_or_ambiguous_input(
    override: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(ValueError, match=match):
        build_node_evidence_report(**_report_kwargs(**override))


def test_node_evidence_cli_writes_sorted_json_under_runtime_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "node-evidence",
            "--node-id",
            "macbook-pro-local",
            "--hostname",
            "macbook-pro.local",
            "--api-base-url",
            "http://127.0.0.1:28020/v1",
            "--backend-base-url",
            "http://127.0.0.1:28100/v1",
            "--backend-id",
            "vllm-mlx",
            "--chip",
            "Apple M3 Max",
            "--memory-gib",
            "36",
            "--model-id",
            "mlx-community/Qwen3-0.6B-8bit",
            "--model-revision",
            "11de96878523501bcaa86104e3c186de07ff9068",
            "--macos-version",
            "15.5",
            "--capability",
            "mlx",
            "--capability",
            "openai-compatible",
            "--port",
            "api=28020",
            "--port",
            "backend=28100",
            "--port",
            "phoenix=26006",
            "--health-url",
            "api_ready=http://127.0.0.1:28020/ready",
            "--health-url",
            "backend_models=http://127.0.0.1:28100/v1/models",
            "--phoenix-url",
            "http://127.0.0.1:26006",
            "--git-sha",
            "be50a7a",
            "--command",
            "scripts/run-model-backed-api.sh",
            "--artifact-dir",
            "artifacts/runtime/test-node-evidence",
            "--api-log",
            "artifacts/runtime/test-node-evidence/api.log",
            "--backend-log",
            "artifacts/runtime/test-node-evidence/backend.log",
            "--phoenix-spans",
            "artifacts/runtime/test-node-evidence/phoenix-spans.json",
            "--metrics",
            "artifacts/runtime/test-node-evidence/metrics.json",
            "--output",
            "artifacts/runtime/test-node-evidence/node-evidence.json",
        ]
    )

    assert exit_code == 0
    written = tmp_path / "artifacts/runtime/test-node-evidence/node-evidence.json"
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert text.startswith('{\n  "artifact_dir":')
    report = json.loads(text)
    assert report["schema_version"] == "mac-studio-node-evidence/v1"
    assert report["evidence_files"]["node_evidence"] == (
        "artifacts/runtime/test-node-evidence/node-evidence.json"
    )


def test_mac_studio_cluster_docs_describe_node_evidence_capture() -> None:
    text = Path("docs/mac-studio-cluster.md").read_text(encoding="utf-8")

    for required in (
        "mac-studio-node-evidence/v1",
        "python -m mac_llm_ops_lab.cluster node-evidence",
        "node-evidence.json",
        "20000-50000",
        "requires_real_multi_node_proof",
        "does not complete real multi-node proof",
    ):
        assert required in text
