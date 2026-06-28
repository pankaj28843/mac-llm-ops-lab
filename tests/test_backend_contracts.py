import json
from pathlib import Path

import pytest

from mac_llm_ops_lab.backend_contracts import (
    build_backend_contract_report,
    build_benchmark_artifact_manifest,
    build_benchmark_summary,
    build_benchmark_workload_policy,
    load_benchmark_artifact_manifest,
    load_benchmark_rows,
    summarize_vllm_mlx_metrics,
    write_backend_contract_report,
    write_benchmark_artifact_manifest,
)

METRICS_TEXT = "\n".join(
    [
        "# HELP vllm_mlx_http_requests_total HTTP requests handled by the server.",
        "# TYPE vllm_mlx_http_requests_total counter",
        'vllm_mlx_http_requests_total{method="GET",path="/v1/models",'
        'status_code="200"} 11.0',
        'vllm_mlx_http_requests_total{method="POST",'
        'path="/v1/chat/completions",status_code="200"} 3.0',
        'vllm_mlx_inference_requests_total{endpoint="chat_completions",'
        'result="success",stream="false"} 3.0',
        'vllm_mlx_prompt_tokens_total{endpoint="chat_completions",stream="false"} 44.0',
        'vllm_mlx_completion_tokens_total{endpoint="chat_completions",'
        'stream="false"} 78.0',
        "vllm_mlx_model_loaded 1.0",
        'vllm_mlx_engine_type{engine_type="simple"} 1.0',
        'vllm_mlx_engine_type{engine_type="batched"} 0.0',
        "vllm_mlx_scheduler_waiting_requests 0.0",
        "vllm_mlx_scheduler_running_requests 0.0",
        'vllm_mlx_metal_memory_bytes{kind="active"} 6.3e+08',
        'vllm_mlx_metal_memory_bytes{kind="peak"} 7.1e+08',
        'vllm_mlx_metal_memory_bytes{kind="cache"} 4e+07',
        'vllm_mlx_cache_type{cache_type="none"} 1.0',
        'vllm_mlx_cache_type{cache_type="paged_cache"} 0.0',
        "vllm_mlx_cache_hits 0.0",
        "vllm_mlx_cache_misses 0.0",
        "vllm_mlx_cache_hit_rate 0.0",
        "vllm_mlx_cache_memory_bytes 0.0",
        "vllm_mlx_cache_tokens_saved 0.0",
    ]
)


BENCHMARK_ROW = {
    "run_id": "3dc480c8",
    "timestamp": "2026-06-28T15:02:25.943892+00:00",
    "tag": "contract-probe",
    "chip": "M3 Max",
    "memory_gb": 36.0,
    "os_version": "macOS-26.5.1-arm64-arm-64bit-Mach-O",
    "model_id": "mlx-community/Qwen3-0.6B-8bit",
    "prompt_set": "short",
    "concurrency": 1,
    "max_tokens": 4,
    "repetition": 0,
    "prompt_tokens": 22,
    "ttft_ms": 76.68983296025544,
    "e2e_latency_ms": 93.35883299354464,
    "gen_tps": 423.25802795463176,
    "requests_per_s": 10.71135925691301,
    "metal_active_gb": 0.63,
    "metal_peak_gb": 0.77,
    "metal_cache_gb": 0.04,
    "cache_hits": 0,
    "cache_misses": 0,
    "cache_hit_rate": 0.0,
    "tokens_saved": 0,
    "validated": False,
}


def test_vllm_mlx_metrics_summary_extracts_core_runtime_signals() -> None:
    summary = summarize_vllm_mlx_metrics(METRICS_TEXT)

    assert summary == {
        "schema_version": "vllm-mlx-metrics-summary/v1",
        "contract_passed": True,
        "missing_required_metrics": [],
        "model_loaded": True,
        "engine_type": "simple",
        "cache_type": "none",
        "http_requests": [
            {
                "method": "GET",
                "path": "/v1/models",
                "status_code": "200",
                "count": 11.0,
            },
            {
                "method": "POST",
                "path": "/v1/chat/completions",
                "status_code": "200",
                "count": 3.0,
            },
        ],
        "inference_requests": [
            {
                "endpoint": "chat_completions",
                "result": "success",
                "stream": "false",
                "count": 3.0,
            }
        ],
        "token_totals": {"prompt": 44.0, "completion": 78.0},
        "scheduler": {"waiting_requests": 0.0, "running_requests": 0.0},
        "metal_memory_bytes": {
            "active": 630000000.0,
            "peak": 710000000.0,
            "cache": 40000000.0,
        },
        "cache": {
            "hits": 0.0,
            "misses": 0.0,
            "hit_rate": 0.0,
            "memory_bytes": 0.0,
            "tokens_saved": 0.0,
        },
    }
    assert json.loads(json.dumps(summary, sort_keys=True)) == summary


def test_vllm_mlx_metrics_summary_records_missing_required_metrics() -> None:
    summary = summarize_vllm_mlx_metrics("vllm_mlx_model_loaded 1.0\n")

    assert summary["contract_passed"] is False
    assert "vllm_mlx_http_requests_total" in summary["missing_required_metrics"]
    assert "vllm_mlx_metal_memory_bytes" in summary["missing_required_metrics"]


def test_benchmark_summary_preserves_validation_and_runtime_shape() -> None:
    summary = build_benchmark_summary([BENCHMARK_ROW])

    assert summary == {
        "schema_version": "vllm-mlx-benchmark-summary/v1",
        "contract_passed": True,
        "run_count": 1,
        "validated_count": 0,
        "all_validated": False,
        "models": ["mlx-community/Qwen3-0.6B-8bit"],
        "prompt_sets": ["short"],
        "concurrency_levels": [1],
        "max_tokens": [4],
        "latency_ms": {
            "ttft_avg": 76.68983296025544,
            "e2e_avg": 93.35883299354464,
            "e2e_p95": 93.35883299354464,
            "e2e_max": 93.35883299354464,
        },
        "throughput": {
            "gen_tps_avg": 423.25802795463176,
            "requests_per_s_avg": 10.71135925691301,
        },
        "metal_memory_gb": {"active_max": 0.63, "peak_max": 0.77, "cache_max": 0.04},
        "cache": {
            "hits_total": 0.0,
            "misses_total": 0.0,
            "hit_rate_avg": 0.0,
            "tokens_saved_total": 0.0,
        },
    }
    assert json.loads(json.dumps(summary, sort_keys=True)) == summary


def test_benchmark_summary_rejects_missing_required_fields() -> None:
    row = dict(BENCHMARK_ROW)
    row.pop("model_id")

    with pytest.raises(ValueError, match="model_id"):
        build_benchmark_summary([row])


def test_benchmark_workload_policy_names_representative_workloads() -> None:
    policy = build_benchmark_workload_policy()

    assert policy["schema_version"] == "vllm-mlx-benchmark-policy/v1"
    assert json.loads(json.dumps(policy, sort_keys=True)) == policy
    workload_names = {workload["name"] for workload in policy["workloads"]}
    assert workload_names == {
        "smoke_short",
        "conversational_sharegpt",
        "prefix_repetition_cache",
    }
    source_grounding = "\n".join(policy["source_grounding"])
    assert "Mac LLM Ops Lab chapter 9" in source_grounding
    assert "OpenTelemetry performance benchmark" in source_grounding

    production_workloads = [
        workload
        for workload in policy["workloads"]
        if workload["production_claim_eligible"] is True
    ]
    assert production_workloads
    for workload in production_workloads:
        assert workload["warmup_requests"] > 0
        assert workload["repetitions"] >= 3
        assert workload["output_token_targets"]
        assert workload["concurrency_levels"]
        assert workload["request_rates_per_second"]


def test_benchmark_workload_policy_requires_metadata_metrics_and_boundaries() -> None:
    policy = build_benchmark_workload_policy()

    required_metadata = set(policy["required_metadata"])
    for field in (
        "git_sha",
        "command",
        "host_chip",
        "unified_memory_gb",
        "macos_version",
        "backend_name",
        "backend_version",
        "model_id",
        "model_revision",
        "quantization",
        "api_port",
        "backend_port",
        "phoenix_port",
        "otlp_grpc_port",
        "prompt_set",
        "input_token_distribution",
        "output_token_target",
        "concurrency",
        "request_rate_per_second",
        "burstiness",
        "warmup_requests",
        "repetition_index",
        "validated",
    ):
        assert field in required_metadata

    required_metrics = set(policy["required_metrics"])
    for metric in (
        "ttft_ms",
        "e2e_latency_ms",
        "tpot_or_itl_ms",
        "total_tps",
        "output_tps",
        "requests_per_s",
        "prompt_tokens",
        "completion_tokens",
        "error_rate",
        "metal_active_gb",
        "metal_peak_gb",
        "metal_cache_gb",
        "cache_hit_rate",
        "tokens_saved",
        "phoenix_gen_ai_spans",
    ):
        assert metric in required_metrics

    boundaries = "\n".join(policy["claim_boundaries"])
    assert "validated:false is smoke-only" in boundaries
    assert "MacBook measurements are local baselines" in boundaries
    assert "Mac Studio cluster claims require Mac Studio runs" in boundaries
    assert policy["local_port_range"] == {"min": 20000, "max": 50000}


def test_benchmark_artifact_manifest_is_json_safe_and_reproducible() -> None:
    manifest = build_benchmark_artifact_manifest(
        git_sha="c0f033f",
        command=(
            "uv",
            "tool",
            "run",
            "vllm-mlx",
            "bench-serve",
            "--url",
            "http://127.0.0.1:28100",
        ),
        artifact_dir="artifacts/runtime/c0f033f-vllm-mlx-benchmark",
        raw_benchmark_path=(
            "artifacts/runtime/c0f033f-vllm-mlx-benchmark/bench-raw.json"
        ),
        summary_path=(
            "artifacts/runtime/c0f033f-vllm-mlx-benchmark/backend-contract-report.json"
        ),
        model_id="mlx-community/Qwen3-0.6B-8bit",
        model_revision="11de96878523501bcaa86104e3c186de07ff9068",
        host={
            "os": "macOS",
            "chip": "M3 Max",
            "memory_gib": 36,
        },
        ports={
            "api": 28020,
            "backend": 28100,
            "phoenix": 26006,
            "otlp_grpc": 24317,
        },
        env={
            "MAC_LLM_OPS_BACKEND_KIND": "openai-compatible",
            "VLLM_MLX_BENCH_PROMPTS": "conversational_sharegpt",
            "VLLM_MLX_BENCH_REPETITIONS": "3",
        },
        no_leak_scan={
            "path": (
                "artifacts/runtime/c0f033f-vllm-mlx-benchmark/"
                "publish-safety-summary.json"
            ),
            "passed": True,
            "findings_count": 0,
        },
    )

    assert manifest == {
        "schema_version": "vllm-mlx-benchmark-artifact-manifest/v1",
        "git_sha": "c0f033f",
        "command": [
            "uv",
            "tool",
            "run",
            "vllm-mlx",
            "bench-serve",
            "--url",
            "http://127.0.0.1:28100",
        ],
        "artifact_dir": "artifacts/runtime/c0f033f-vllm-mlx-benchmark",
        "raw_benchmark_path": (
            "artifacts/runtime/c0f033f-vllm-mlx-benchmark/bench-raw.json"
        ),
        "summary_path": (
            "artifacts/runtime/c0f033f-vllm-mlx-benchmark/backend-contract-report.json"
        ),
        "model": {
            "id": "mlx-community/Qwen3-0.6B-8bit",
            "revision": "11de96878523501bcaa86104e3c186de07ff9068",
        },
        "host": {
            "os": "macOS",
            "chip": "M3 Max",
            "memory_gib": 36,
        },
        "ports": {
            "api": 28020,
            "backend": 28100,
            "phoenix": 26006,
            "otlp_grpc": 24317,
        },
        "env": {
            "MAC_LLM_OPS_BACKEND_KIND": "openai-compatible",
            "VLLM_MLX_BENCH_PROMPTS": "conversational_sharegpt",
            "VLLM_MLX_BENCH_REPETITIONS": "3",
        },
        "no_leak_scan": {
            "path": (
                "artifacts/runtime/c0f033f-vllm-mlx-benchmark/"
                "publish-safety-summary.json"
            ),
            "passed": True,
            "findings_count": 0,
        },
    }
    assert json.loads(json.dumps(manifest, sort_keys=True)) == manifest


def test_benchmark_artifact_manifest_rejects_malformed_bundles() -> None:
    base_kwargs = {
        "git_sha": "c0f033f",
        "command": ("uv", "tool", "run", "vllm-mlx", "bench-serve"),
        "artifact_dir": "artifacts/runtime/c0f033f-vllm-mlx-benchmark",
        "raw_benchmark_path": (
            "artifacts/runtime/c0f033f-vllm-mlx-benchmark/bench-raw.json"
        ),
        "summary_path": (
            "artifacts/runtime/c0f033f-vllm-mlx-benchmark/backend-contract-report.json"
        ),
        "model_id": "mlx-community/Qwen3-0.6B-8bit",
        "model_revision": "11de96878523501bcaa86104e3c186de07ff9068",
        "host": {"os": "macOS", "chip": "M3 Max", "memory_gib": 36},
        "ports": {"api": 28020, "backend": 28100},
        "env": {"VLLM_MLX_BENCH_PROMPTS": "conversational_sharegpt"},
        "no_leak_scan": {
            "path": (
                "artifacts/runtime/c0f033f-vllm-mlx-benchmark/"
                "publish-safety-summary.json"
            ),
            "passed": True,
            "findings_count": 0,
        },
    }

    with pytest.raises(ValueError, match="raw_benchmark_path"):
        build_benchmark_artifact_manifest(
            **{**base_kwargs, "raw_benchmark_path": "artifacts/runtime/other/raw.json"}
        )
    with pytest.raises(ValueError, match="summary_path"):
        build_benchmark_artifact_manifest(
            **{**base_kwargs, "summary_path": "/tmp/summary.json"}
        )
    with pytest.raises(ValueError, match="command"):
        build_benchmark_artifact_manifest(**{**base_kwargs, "command": ()})
    with pytest.raises(ValueError, match="model_revision"):
        build_benchmark_artifact_manifest(**{**base_kwargs, "model_revision": ""})
    with pytest.raises(ValueError, match="host"):
        build_benchmark_artifact_manifest(
            **{**base_kwargs, "host": {"os": "macOS", "memory_gib": 36}}
        )
    with pytest.raises(ValueError, match="ports"):
        build_benchmark_artifact_manifest(**{**base_kwargs, "ports": {"api": 8000}})
    with pytest.raises(ValueError, match="env"):
        build_benchmark_artifact_manifest(**{**base_kwargs, "env": {}})
    with pytest.raises(ValueError, match="no_leak_scan"):
        build_benchmark_artifact_manifest(
            **{
                **base_kwargs,
                "no_leak_scan": {
                    **base_kwargs["no_leak_scan"],
                    "findings_count": 1,
                },
            }
        )


def test_benchmark_artifact_manifest_persists_and_loads_under_artifact_dir(
    tmp_path: Path,
) -> None:
    manifest = build_benchmark_artifact_manifest(
        git_sha="c0f033f",
        command=("uv", "tool", "run", "vllm-mlx", "bench-serve"),
        artifact_dir="artifacts/runtime/c0f033f-vllm-mlx-benchmark",
        raw_benchmark_path=(
            "artifacts/runtime/c0f033f-vllm-mlx-benchmark/bench-raw.json"
        ),
        summary_path=(
            "artifacts/runtime/c0f033f-vllm-mlx-benchmark/backend-contract-report.json"
        ),
        model_id="mlx-community/Qwen3-0.6B-8bit",
        model_revision="11de96878523501bcaa86104e3c186de07ff9068",
        host={"os": "macOS", "chip": "M3 Max", "memory_gib": 36},
        ports={"api": 28020, "backend": 28100},
        env={"VLLM_MLX_BENCH_PROMPTS": "conversational_sharegpt"},
        no_leak_scan={
            "path": (
                "artifacts/runtime/c0f033f-vllm-mlx-benchmark/"
                "publish-safety-summary.json"
            ),
            "passed": True,
            "findings_count": 0,
        },
    )

    output_path = write_benchmark_artifact_manifest(
        manifest,
        output_root=tmp_path,
    )

    assert output_path == (
        tmp_path / "artifacts/runtime/c0f033f-vllm-mlx-benchmark/"
        "benchmark-artifact-manifest.json"
    )
    written_text = output_path.read_text(encoding="utf-8")
    assert written_text.endswith("\n")
    assert json.loads(written_text) == manifest
    assert load_benchmark_artifact_manifest(output_path) == manifest

    output_path.write_text(json.dumps({**manifest, "git_sha": ""}), encoding="utf-8")
    with pytest.raises(ValueError, match="git_sha"):
        load_benchmark_artifact_manifest(output_path)


def test_load_benchmark_rows_requires_json_list(tmp_path: Path) -> None:
    path = tmp_path / "bench.json"
    path.write_text(json.dumps([BENCHMARK_ROW]), encoding="utf-8")

    assert load_benchmark_rows(path) == [BENCHMARK_ROW]

    path.write_text(json.dumps({"not": "a-list"}), encoding="utf-8")
    with pytest.raises(ValueError, match="JSON list"):
        load_benchmark_rows(path)


def test_backend_contract_report_combines_metrics_and_benchmark() -> None:
    report = build_backend_contract_report(
        metrics_text=METRICS_TEXT,
        benchmark_rows=[BENCHMARK_ROW],
    )

    assert report["schema_version"] == "vllm-mlx-backend-contract/v1"
    assert report["contract_passed"] is True
    assert report["metrics"]["contract_passed"] is True
    assert report["benchmark"]["contract_passed"] is True
    assert report["benchmark"]["all_validated"] is False


def test_write_backend_contract_report_persists_sorted_json(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.prom"
    benchmark_path = tmp_path / "bench.json"
    report_path = tmp_path / "contract" / "report.json"
    metrics_path.write_text(METRICS_TEXT, encoding="utf-8")
    benchmark_path.write_text(json.dumps([BENCHMARK_ROW]), encoding="utf-8")

    assert (
        write_backend_contract_report(
            metrics_path=metrics_path,
            benchmark_path=benchmark_path,
            report_path=report_path,
        )
        == report_path
    )

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["schema_version"] == "vllm-mlx-backend-contract/v1"
    assert report["contract_passed"] is True


def test_probe_script_generates_backend_contract_report() -> None:
    script = Path("scripts/probe-vllm-mlx-contract.sh").read_text(encoding="utf-8")

    assert 'URL="${VLLM_MLX_URL:-http://127.0.0.1:28100}"' in script
    assert 'curl -fsS "$URL/metrics"' in script
    assert "vllm-mlx bench-serve" in script
    assert "mac_llm_ops_lab.backend_contracts" in script
    assert "backend-contract-report.json" in script


def test_backend_contract_docs_describe_metrics_and_benchmark_boundaries() -> None:
    text = Path("docs/backend-contracts.md").read_text(encoding="utf-8")

    for required in (
        "vllm_mlx_http_requests_total",
        "vllm_mlx_metal_memory_bytes",
        "vllm-mlx bench-serve",
        "validated:false",
        "Open WebUI against the native backend is now runtime-proven",
        "fuller production benchmark remains separate",
    ):
        assert required in text


def test_backend_contract_docs_define_representative_benchmark_policy() -> None:
    text = Path("docs/backend-contracts.md").read_text(encoding="utf-8")

    for required in (
        "Benchmark Workload Policy",
        "Benchmark Artifact Manifest",
        "benchmark-artifact-manifest.json",
        "raw_benchmark_path",
        "summary_path",
        "no_leak_scan",
        "smoke_short",
        "conversational_sharegpt",
        "prefix_repetition_cache",
        "warmup",
        "repetitions",
        "TTFT",
        "TPOT",
        "ITL",
        "request throughput",
        "Metal memory",
        "Phoenix GenAI spans",
        "input token distribution",
        "output token target",
        "MacBook measurements are local baselines",
        "Mac Studio cluster claims require Mac Studio runs",
        "validated:false is smoke-only",
        "20000-50000",
    ):
        assert required in text
