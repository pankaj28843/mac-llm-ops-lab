import json
from pathlib import Path

from mac_llm_ops_lab.runtime_guard import (
    DEFAULT_MEMORY_CEILING_GIB,
    REQUIRED_RUNTIME_IGNORE_PATTERNS,
    RuntimePreflightPlan,
    build_runtime_preflight_report,
    evaluate_runtime_preflight,
    missing_runtime_ignore_patterns,
)


def test_runtime_preflight_skips_unauthorized_real_model_plan() -> None:
    plan = RuntimePreflightPlan(
        backend_id="vllm-mlx",
        model_id="mlx-community/Qwen3-0.6B-8bit",
        explicitly_authorized=False,
        model_weights_gib=1.2,
        kv_cache_gib=2.0,
        runtime_overhead_gib=1.0,
        service_overhead_gib=0.5,
    )

    decision = evaluate_runtime_preflight(plan)

    assert decision.allowed is False
    assert decision.reason_code == "runtime_not_authorized"
    assert decision.estimated_total_gib == 4.7
    assert decision.memory_ceiling_gib == DEFAULT_MEMORY_CEILING_GIB
    assert "Qwen3" not in decision.message
    assert "vllm-mlx" not in decision.message


def test_runtime_preflight_skips_authorized_plan_over_memory_ceiling() -> None:
    plan = RuntimePreflightPlan(
        backend_id="vllm-mlx",
        model_id="mlx-community/large-test-model",
        explicitly_authorized=True,
        model_weights_gib=14.0,
        kv_cache_gib=8.0,
        runtime_overhead_gib=2.0,
        service_overhead_gib=1.5,
    )

    decision = evaluate_runtime_preflight(plan)

    assert decision.allowed is False
    assert decision.reason_code == "memory_ceiling_exceeded"
    assert decision.estimated_total_gib == 25.5
    assert decision.memory_ceiling_gib == DEFAULT_MEMORY_CEILING_GIB
    assert "large-test-model" not in decision.message


def test_runtime_preflight_allows_authorized_plan_within_memory_ceiling() -> None:
    plan = RuntimePreflightPlan(
        backend_id="vllm-mlx",
        model_id="mlx-community/Qwen3-0.6B-8bit",
        explicitly_authorized=True,
        model_weights_gib=1.2,
        kv_cache_gib=2.0,
        runtime_overhead_gib=1.0,
        service_overhead_gib=0.5,
    )

    decision = evaluate_runtime_preflight(plan)

    assert decision.allowed is True
    assert decision.reason_code == "runtime_preflight_passed"
    assert decision.estimated_total_gib == 4.7
    assert decision.memory_ceiling_gib == DEFAULT_MEMORY_CEILING_GIB


def test_runtime_preflight_report_is_json_safe_and_deterministic() -> None:
    plan = RuntimePreflightPlan(
        backend_id="vllm-mlx",
        model_id="mlx-community/Qwen3-0.6B-8bit",
        explicitly_authorized=False,
        model_weights_gib=1.2,
        kv_cache_gib=2.0,
        runtime_overhead_gib=1.0,
        service_overhead_gib=0.5,
    )

    report = build_runtime_preflight_report(plan)

    assert report == {
        "schema_version": "runtime-preflight/v1",
        "backend_id": "vllm-mlx",
        "model_id": "mlx-community/Qwen3-0.6B-8bit",
        "explicitly_authorized": False,
        "memory_gib": {
            "model_weights": 1.2,
            "kv_cache": 2.0,
            "runtime_overhead": 1.0,
            "service_overhead": 0.5,
            "estimated_total": 4.7,
            "ceiling": DEFAULT_MEMORY_CEILING_GIB,
        },
        "decision": {
            "allowed": False,
            "reason_code": "runtime_not_authorized",
            "message": (
                "Explicit authorization is required before real-model runtime "
                "execution."
            ),
        },
    }
    assert json.loads(json.dumps(report, sort_keys=True)) == report


def test_runtime_publish_sensitive_paths_are_covered_by_gitignore() -> None:
    gitignore_text = Path(".gitignore").read_text(encoding="utf-8")

    assert REQUIRED_RUNTIME_IGNORE_PATTERNS == (
        ".env",
        ".env.*",
        "data/",
        "artifacts/",
        "benchmarks/raw/",
        "traces/",
        "model-cache/",
        "models/",
        "*.sqlite*",
        "*.log",
    )
    assert missing_runtime_ignore_patterns(gitignore_text) == ()
    assert missing_runtime_ignore_patterns("model-cache/\ntraces/\n") == (
        ".env",
        ".env.*",
        "data/",
        "artifacts/",
        "benchmarks/raw/",
        "models/",
        "*.sqlite*",
        "*.log",
    )
