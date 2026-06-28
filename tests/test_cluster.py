import json
from pathlib import Path

import pytest

from mac_llm_ops_lab.cluster import (
    ClusterNode,
    build_cluster_evidence_manifest,
    register_cluster_node,
    route_to_model,
)


def _node(
    node_id: str,
    *,
    queue_depth: int,
    ready: bool = True,
    healthy: bool = True,
    models: tuple[str, ...] = ("mlx-community/Qwen3-0.6B-8bit",),
    capabilities: tuple[str, ...] = ("mlx", "openai-compatible", "streaming", "otel"),
    ports: dict[str, int] | None = None,
) -> ClusterNode:
    return ClusterNode(
        node_id=node_id,
        hostname=f"{node_id}.local",
        api_base_url=f"http://{node_id}.local:28020/v1",
        backend_base_url=f"http://{node_id}.local:28100/v1",
        backend_id="vllm-mlx",
        chip="Apple M3 Ultra",
        memory_gib=256,
        models=models,
        queue_depth=queue_depth,
        ready=ready,
        healthy=healthy,
        capabilities=capabilities,
        ports=ports or {"api": 28020, "backend": 28100, "phoenix": 26006},
    )


def test_fake_cluster_nodes_expose_capabilities_and_high_ports() -> None:
    node = register_cluster_node(_node("studio-a", queue_depth=1))

    assert node.to_inventory_record() == {
        "node_id": "studio-a",
        "hostname": "studio-a.local",
        "api_base_url": "http://studio-a.local:28020/v1",
        "backend_base_url": "http://studio-a.local:28100/v1",
        "backend_id": "vllm-mlx",
        "chip": "Apple M3 Ultra",
        "memory_gib": 256,
        "models": ["mlx-community/Qwen3-0.6B-8bit"],
        "queue_depth": 1,
        "ready": True,
        "healthy": True,
        "capabilities": ["mlx", "openai-compatible", "streaming", "otel"],
        "ports": {"api": 28020, "backend": 28100, "phoenix": 26006},
    }


def test_conservative_router_selects_lowest_queue_healthy_registered_node() -> None:
    nodes = (
        register_cluster_node(_node("studio-a", queue_depth=5)),
        register_cluster_node(_node("studio-b", queue_depth=1)),
        register_cluster_node(_node("studio-c", queue_depth=0, ready=False)),
        register_cluster_node(_node("studio-d", queue_depth=0, healthy=False)),
        register_cluster_node(
            _node("studio-e", queue_depth=0, models=("other-model",))
        ),
    )

    decision = route_to_model(nodes, model_id="mlx-community/Qwen3-0.6B-8bit")

    assert decision.to_record() == {
        "node_id": "studio-b",
        "backend_id": "vllm-mlx",
        "model_id": "mlx-community/Qwen3-0.6B-8bit",
        "api_base_url": "http://studio-b.local:28020/v1",
        "reason": "least_queue_depth",
        "fallback": False,
    }


def test_router_falls_back_when_no_registered_healthy_node_can_serve_model() -> None:
    nodes = (
        register_cluster_node(_node("studio-a", queue_depth=0, ready=False)),
        register_cluster_node(_node("studio-b", queue_depth=0, healthy=False)),
        register_cluster_node(_node("studio-c", queue_depth=0, models=("other",))),
    )

    decision = route_to_model(nodes, model_id="mlx-community/Qwen3-0.6B-8bit")

    assert decision.to_record() == {
        "node_id": "local-fallback",
        "backend_id": "fake",
        "model_id": "mlx-community/Qwen3-0.6B-8bit",
        "api_base_url": None,
        "reason": "no_healthy_registered_node",
        "fallback": True,
    }


def test_cluster_registration_rejects_unsafe_ports_and_empty_capabilities() -> None:
    with pytest.raises(ValueError, match="ports"):
        register_cluster_node(
            _node("studio-a", queue_depth=0, capabilities=("mlx",), ports={"api": 8000})
        )
    with pytest.raises(ValueError, match="capabilities"):
        register_cluster_node(
            _node("studio-a", queue_depth=0, capabilities=(), ports={"api": 28020})
        )


def test_cluster_evidence_manifest_requires_node_route_logs_traces_and_metrics() -> (
    None
):
    node = register_cluster_node(_node("studio-a", queue_depth=0))
    decision = route_to_model((node,), model_id="mlx-community/Qwen3-0.6B-8bit")

    manifest = build_cluster_evidence_manifest(
        git_sha="51cdb2e",
        command=("uv", "run", "python", "-m", "mac_llm_ops_lab.cluster"),
        artifact_dir="artifacts/runtime/51cdb2e-cluster-proof",
        nodes=(node,),
        route_decisions=(decision,),
        node_evidence={
            "studio-a": {
                "api_log": "artifacts/runtime/51cdb2e-cluster-proof/studio-a-api.log",
                "backend_log": (
                    "artifacts/runtime/51cdb2e-cluster-proof/studio-a-backend.log"
                ),
                "phoenix_spans": (
                    "artifacts/runtime/51cdb2e-cluster-proof/studio-a-spans.json"
                ),
                "metrics": (
                    "artifacts/runtime/51cdb2e-cluster-proof/studio-a-metrics.json"
                ),
            }
        },
    )

    assert manifest["schema_version"] == "cluster-evidence-manifest/v1"
    assert manifest["git_sha"] == "51cdb2e"
    assert manifest["nodes"] == [node.to_inventory_record()]
    assert manifest["route_decisions"] == [decision.to_record()]
    assert json.loads(json.dumps(manifest, sort_keys=True)) == manifest

    with pytest.raises(ValueError, match="node_evidence"):
        build_cluster_evidence_manifest(
            git_sha="51cdb2e",
            command=("uv",),
            artifact_dir="artifacts/runtime/51cdb2e-cluster-proof",
            nodes=(node,),
            route_decisions=(decision,),
            node_evidence={"other-node": {}},
        )


def test_mac_studio_cluster_docs_describe_code_backed_contracts() -> None:
    text = Path("docs/mac-studio-cluster.md").read_text(encoding="utf-8")

    for required in (
        "mac_llm_ops_lab.cluster",
        "ClusterNode",
        "route_to_model",
        "cluster-evidence-manifest/v1",
        "least_queue_depth",
        "no_healthy_registered_node",
        "api_log",
        "backend_log",
        "phoenix_spans",
        "metrics",
        "20000-50000",
        "real multi-node proof",
    ):
        assert required in text
