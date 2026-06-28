import json
from pathlib import Path

import pytest

from mac_llm_ops_lab.backend_contracts import (
    build_backend_contract_report,
    build_benchmark_summary,
    load_benchmark_rows,
    summarize_vllm_mlx_metrics,
    write_backend_contract_report,
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
