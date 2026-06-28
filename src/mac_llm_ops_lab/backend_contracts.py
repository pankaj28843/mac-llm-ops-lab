import argparse
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path, PurePosixPath

VLLM_MLX_METRICS_SUMMARY_SCHEMA_VERSION = "vllm-mlx-metrics-summary/v1"
VLLM_MLX_BENCHMARK_SUMMARY_SCHEMA_VERSION = "vllm-mlx-benchmark-summary/v1"
VLLM_MLX_BACKEND_CONTRACT_SCHEMA_VERSION = "vllm-mlx-backend-contract/v1"
VLLM_MLX_BENCHMARK_POLICY_SCHEMA_VERSION = "vllm-mlx-benchmark-policy/v1"
VLLM_MLX_BENCHMARK_ARTIFACT_MANIFEST_SCHEMA_VERSION = (
    "vllm-mlx-benchmark-artifact-manifest/v1"
)
LOCAL_PORT_MIN = 20000
LOCAL_PORT_MAX = 50000

_SAMPLE_PATTERN = re.compile(
    r"^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{(?P<labels>[^}]*)\})?\s+"
    r"(?P<value>[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?|[-+]?Inf|NaN)$"
)
_REQUIRED_METRICS = (
    "vllm_mlx_http_requests_total",
    "vllm_mlx_inference_requests_total",
    "vllm_mlx_prompt_tokens_total",
    "vllm_mlx_completion_tokens_total",
    "vllm_mlx_model_loaded",
    "vllm_mlx_engine_type",
    "vllm_mlx_scheduler_waiting_requests",
    "vllm_mlx_scheduler_running_requests",
    "vllm_mlx_metal_memory_bytes",
    "vllm_mlx_cache_type",
    "vllm_mlx_cache_hits",
    "vllm_mlx_cache_misses",
    "vllm_mlx_cache_hit_rate",
    "vllm_mlx_cache_memory_bytes",
    "vllm_mlx_cache_tokens_saved",
)
_BENCHMARK_REQUIRED_FIELDS = (
    "model_id",
    "prompt_set",
    "concurrency",
    "max_tokens",
    "ttft_ms",
    "e2e_latency_ms",
    "gen_tps",
    "requests_per_s",
    "metal_active_gb",
    "metal_peak_gb",
    "metal_cache_gb",
    "cache_hits",
    "cache_misses",
    "cache_hit_rate",
    "tokens_saved",
    "validated",
)
_BENCHMARK_REQUIRED_HOST_LABELS = ("os", "chip", "memory_gib")


def build_benchmark_workload_policy() -> dict[str, object]:
    return {
        "schema_version": VLLM_MLX_BENCHMARK_POLICY_SCHEMA_VERSION,
        "source_grounding": [
            "Mac LLM Ops Lab chapter 9: examine hardware, "
            "generate representative benchmark traffic, define metrics, verify "
            "memory/KV cache, then compare baseline, cache, quantized, and "
            "distributed configurations.",
            "Mac LLM Ops Lab chapter 4: measure latency and "
            "throughput with TTFT, ITL/TPOT, end-to-end latency, and request or "
            "token throughput according to the user-facing workload.",
            "OpenTelemetry performance benchmark: use warm-up before measurement, "
            "repeat measurements, and report CPU/memory plus the target platform.",
            "OpenTelemetry GenAI semantic conventions: keep model, provider, "
            "operation, server, and error attributes available in trace evidence.",
        ],
        "local_port_range": {"min": 20000, "max": 50000},
        "workloads": [
            {
                "name": "smoke_short",
                "purpose": "Command-surface, parser, metrics, and trace smoke only.",
                "prompt_set": "short",
                "profile": "tiny deterministic request for safe local wiring proof",
                "production_claim_eligible": False,
                "output_token_targets": [4, 16, 64],
                "concurrency_levels": [1],
                "request_rates_per_second": [1.0],
                "burstiness": [1.0],
                "warmup_requests": 0,
                "repetitions": 1,
                "validation_policy": "validated:false allowed only for this smoke.",
            },
            {
                "name": "conversational_sharegpt",
                "purpose": "Interactive chat baseline with realistic turn lengths.",
                "prompt_set": "sharegpt",
                "profile": "balanced prefill/decode conversational traffic",
                "production_claim_eligible": True,
                "output_token_targets": [64, 128, 256],
                "concurrency_levels": [1, 2, 4],
                "request_rates_per_second": [1.0, 2.0, 5.0],
                "burstiness": [1.0],
                "warmup_requests": 10,
                "repetitions": 3,
                "validation_policy": "validated:true required for performance claims.",
            },
            {
                "name": "prefix_repetition_cache",
                "purpose": "Cache and repeated-prefix behavior under controlled reuse.",
                "prompt_set": "prefix_repetition",
                "profile": "prefill-heavy repeated-prefix cache workload",
                "production_claim_eligible": True,
                "output_token_targets": [64, 128],
                "concurrency_levels": [1, 2, 4],
                "request_rates_per_second": [1.0, 2.0, 5.0],
                "burstiness": [1.0],
                "warmup_requests": 10,
                "repetitions": 3,
                "prefix_repetition": {
                    "prefix_lengths": [256],
                    "suffix_lengths": [256],
                    "unique_prefix_counts": [5, 10],
                },
                "validation_policy": "validated:true required for performance claims.",
            },
        ],
        "required_metadata": [
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
        ],
        "required_metrics": [
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
        ],
        "claim_boundaries": [
            "validated:false is smoke-only; it can prove command shape but not "
            "quality or production performance.",
            "MacBook measurements are local baselines for this development host, "
            "with the capsule-local 24 GiB real-model memory ceiling.",
            "Mac Studio cluster claims require Mac Studio runs with node count, "
            "chip, memory, network, model, routing, and trace evidence.",
        ],
    }


def build_benchmark_artifact_manifest(
    *,
    git_sha: str,
    command: Sequence[str],
    artifact_dir: str,
    raw_benchmark_path: str,
    summary_path: str,
    model_id: str,
    model_revision: str,
    host: Mapping[str, object],
    ports: Mapping[str, object],
    env: Mapping[str, object],
    no_leak_scan: Mapping[str, object],
) -> dict[str, object]:
    normalized_artifact_dir = _validated_artifact_dir(artifact_dir)
    return {
        "schema_version": VLLM_MLX_BENCHMARK_ARTIFACT_MANIFEST_SCHEMA_VERSION,
        "git_sha": _validated_non_empty_string(git_sha, field_name="git_sha"),
        "command": _validated_command(command),
        "artifact_dir": normalized_artifact_dir,
        "raw_benchmark_path": _validated_json_path_in_artifact_dir(
            raw_benchmark_path,
            artifact_dir=normalized_artifact_dir,
            field_name="raw_benchmark_path",
        ),
        "summary_path": _validated_json_path_in_artifact_dir(
            summary_path,
            artifact_dir=normalized_artifact_dir,
            field_name="summary_path",
        ),
        "model": {
            "id": _validated_non_empty_string(model_id, field_name="model_id"),
            "revision": _validated_non_empty_string(
                model_revision,
                field_name="model_revision",
            ),
        },
        "host": _validated_benchmark_host(host),
        "ports": _validated_high_ports(ports),
        "env": _validated_env(env),
        "no_leak_scan": _validated_no_leak_scan(
            no_leak_scan,
            artifact_dir=normalized_artifact_dir,
        ),
    }


def write_benchmark_artifact_manifest(
    manifest: Mapping[str, object],
    *,
    output_root: Path,
) -> Path:
    canonical_manifest = _canonical_benchmark_artifact_manifest(manifest)
    artifact_dir = str(canonical_manifest["artifact_dir"])
    output_dir = output_root / artifact_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "benchmark-artifact-manifest.json"
    output_path.write_text(
        json.dumps(canonical_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def load_benchmark_artifact_manifest(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("benchmark artifact manifest JSON must contain an object")
    return _canonical_benchmark_artifact_manifest(payload)


def summarize_vllm_mlx_metrics(metrics_text: str) -> dict[str, object]:
    samples = _parse_prometheus_samples(metrics_text)
    names = {sample["name"] for sample in samples}
    missing_metrics = [name for name in _REQUIRED_METRICS if name not in names]
    return {
        "schema_version": VLLM_MLX_METRICS_SUMMARY_SCHEMA_VERSION,
        "contract_passed": not missing_metrics,
        "missing_required_metrics": missing_metrics,
        "model_loaded": _sample_value(samples, "vllm_mlx_model_loaded") == 1.0,
        "engine_type": _active_labeled_value(
            samples,
            metric_name="vllm_mlx_engine_type",
            label_name="engine_type",
            fallback="unknown",
        ),
        "cache_type": _active_labeled_value(
            samples,
            metric_name="vllm_mlx_cache_type",
            label_name="cache_type",
            fallback="unknown",
        ),
        "http_requests": _http_request_counts(samples),
        "inference_requests": _inference_request_counts(samples),
        "token_totals": {
            "prompt": _sample_value(samples, "vllm_mlx_prompt_tokens_total"),
            "completion": _sample_value(
                samples,
                "vllm_mlx_completion_tokens_total",
            ),
        },
        "scheduler": {
            "waiting_requests": _sample_value(
                samples,
                "vllm_mlx_scheduler_waiting_requests",
            ),
            "running_requests": _sample_value(
                samples,
                "vllm_mlx_scheduler_running_requests",
            ),
        },
        "metal_memory_bytes": _kind_values(samples, "vllm_mlx_metal_memory_bytes"),
        "cache": {
            "hits": _sample_value(samples, "vllm_mlx_cache_hits"),
            "misses": _sample_value(samples, "vllm_mlx_cache_misses"),
            "hit_rate": _sample_value(samples, "vllm_mlx_cache_hit_rate"),
            "memory_bytes": _sample_value(samples, "vllm_mlx_cache_memory_bytes"),
            "tokens_saved": _sample_value(samples, "vllm_mlx_cache_tokens_saved"),
        },
    }


def load_benchmark_rows(path: Path) -> list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("benchmark JSON must contain a JSON list")
    if any(not isinstance(row, Mapping) for row in payload):
        raise ValueError("benchmark JSON list must contain objects")
    return [dict(row) for row in payload]


def build_benchmark_summary(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    normalized_rows = [dict(row) for row in rows]
    if not normalized_rows:
        raise ValueError("benchmark rows must not be empty")
    for row in normalized_rows:
        _validate_benchmark_row(row)

    validated_count = sum(1 for row in normalized_rows if row["validated"] is True)
    return {
        "schema_version": VLLM_MLX_BENCHMARK_SUMMARY_SCHEMA_VERSION,
        "contract_passed": True,
        "run_count": len(normalized_rows),
        "validated_count": validated_count,
        "all_validated": validated_count == len(normalized_rows),
        "models": _sorted_unique_strings(row["model_id"] for row in normalized_rows),
        "prompt_sets": _sorted_unique_strings(
            (row["prompt_set"] for row in normalized_rows),
        ),
        "concurrency_levels": _sorted_unique_numbers(
            (row["concurrency"] for row in normalized_rows),
        ),
        "max_tokens": _sorted_unique_numbers(
            row["max_tokens"] for row in normalized_rows
        ),
        "latency_ms": {
            "ttft_avg": _average(_float_values(normalized_rows, "ttft_ms")),
            "e2e_avg": _average(_float_values(normalized_rows, "e2e_latency_ms")),
            "e2e_p95": _percentile(
                _float_values(normalized_rows, "e2e_latency_ms"),
                percentile=0.95,
            ),
            "e2e_max": max(_float_values(normalized_rows, "e2e_latency_ms")),
        },
        "throughput": {
            "gen_tps_avg": _average(_float_values(normalized_rows, "gen_tps")),
            "requests_per_s_avg": _average(
                _float_values(normalized_rows, "requests_per_s"),
            ),
        },
        "metal_memory_gb": {
            "active_max": max(_float_values(normalized_rows, "metal_active_gb")),
            "peak_max": max(_float_values(normalized_rows, "metal_peak_gb")),
            "cache_max": max(_float_values(normalized_rows, "metal_cache_gb")),
        },
        "cache": {
            "hits_total": sum(_float_values(normalized_rows, "cache_hits")),
            "misses_total": sum(_float_values(normalized_rows, "cache_misses")),
            "hit_rate_avg": _average(_float_values(normalized_rows, "cache_hit_rate")),
            "tokens_saved_total": sum(_float_values(normalized_rows, "tokens_saved")),
        },
    }


def build_backend_contract_report(
    *,
    metrics_text: str,
    benchmark_rows: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    metrics = summarize_vllm_mlx_metrics(metrics_text)
    benchmark = build_benchmark_summary(benchmark_rows)
    return {
        "schema_version": VLLM_MLX_BACKEND_CONTRACT_SCHEMA_VERSION,
        "contract_passed": metrics["contract_passed"] and benchmark["contract_passed"],
        "metrics": metrics,
        "benchmark": benchmark,
    }


def write_backend_contract_report(
    *,
    metrics_path: Path,
    benchmark_path: Path,
    report_path: Path,
) -> Path:
    report = build_backend_contract_report(
        metrics_text=metrics_path.read_text(encoding="utf-8"),
        benchmark_rows=load_benchmark_rows(benchmark_path),
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report_path


def _canonical_benchmark_artifact_manifest(
    manifest: Mapping[str, object],
) -> dict[str, object]:
    if (
        manifest.get("schema_version")
        != VLLM_MLX_BENCHMARK_ARTIFACT_MANIFEST_SCHEMA_VERSION
    ):
        raise ValueError(
            "schema_version must be "
            f"{VLLM_MLX_BENCHMARK_ARTIFACT_MANIFEST_SCHEMA_VERSION}",
        )
    model = _mapping_field(manifest, "model")
    return build_benchmark_artifact_manifest(
        git_sha=_validated_non_empty_string(
            manifest.get("git_sha"),
            field_name="git_sha",
        ),
        command=_sequence_field(manifest, "command"),
        artifact_dir=_validated_non_empty_string(
            manifest.get("artifact_dir"),
            field_name="artifact_dir",
        ),
        raw_benchmark_path=_validated_non_empty_string(
            manifest.get("raw_benchmark_path"),
            field_name="raw_benchmark_path",
        ),
        summary_path=_validated_non_empty_string(
            manifest.get("summary_path"),
            field_name="summary_path",
        ),
        model_id=_validated_non_empty_string(model.get("id"), field_name="model_id"),
        model_revision=_validated_non_empty_string(
            model.get("revision"),
            field_name="model_revision",
        ),
        host=_mapping_field(manifest, "host"),
        ports=_mapping_field(manifest, "ports"),
        env=_mapping_field(manifest, "env"),
        no_leak_scan=_mapping_field(manifest, "no_leak_scan"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a vllm-mlx metrics and benchmark contract report.",
    )
    parser.add_argument("--metrics-path", required=True)
    parser.add_argument("--benchmark-path", required=True)
    parser.add_argument("--report-path", required=True)
    args = parser.parse_args(argv)
    write_backend_contract_report(
        metrics_path=Path(args.metrics_path),
        benchmark_path=Path(args.benchmark_path),
        report_path=Path(args.report_path),
    )
    return 0


def _parse_prometheus_samples(metrics_text: str) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for raw_line in metrics_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = _SAMPLE_PATTERN.match(line)
        if not match:
            continue
        samples.append(
            {
                "name": match.group("name"),
                "labels": _parse_labels(match.group("labels") or ""),
                "value": _parse_float(match.group("value")),
            }
        )
    return samples


def _parse_labels(labels: str) -> dict[str, str]:
    if not labels:
        return {}
    parsed: dict[str, str] = {}
    for part in re.split(r',(?=(?:[^"]*"[^"]*")*[^"]*$)', labels):
        key, _, value = part.partition("=")
        parsed[key.strip()] = value.strip().strip('"')
    return parsed


def _parse_float(value: str) -> float:
    if value == "+Inf":
        return math.inf
    if value == "-Inf":
        return -math.inf
    return float(value)


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
) -> Sequence[str]:
    value = source.get(field_name)
    if isinstance(value, str) or not isinstance(value, Sequence):
        raise ValueError(f"{field_name} must be a sequence")
    return value


def _validated_artifact_dir(artifact_dir: str) -> str:
    path = _validated_relative_path(artifact_dir, field_name="artifact_dir")
    if len(path.parts) < 3 or path.parts[:2] != ("artifacts", "runtime"):
        raise ValueError("artifact_dir must be under artifacts/runtime/")
    return path.as_posix()


def _validated_json_path_in_artifact_dir(
    value: str,
    *,
    artifact_dir: str,
    field_name: str,
) -> str:
    path = _validated_relative_path(value, field_name=field_name)
    try:
        path.relative_to(PurePosixPath(artifact_dir))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be inside artifact_dir") from exc
    if path.suffix != ".json":
        raise ValueError(f"{field_name} must point to a .json file")
    return path.as_posix()


def _validated_relative_path(value: str, *, field_name: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a relative path without traversal")
    return path


def _validated_benchmark_host(host: Mapping[str, object]) -> dict[str, object]:
    normalized = _validated_non_empty_mapping(host, field_name="host")
    missing = [key for key in _BENCHMARK_REQUIRED_HOST_LABELS if key not in normalized]
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


def _validated_high_ports(ports: Mapping[str, object]) -> dict[str, int]:
    normalized = _validated_non_empty_mapping(ports, field_name="ports")
    if any(
        not name
        or not isinstance(port, int)
        or isinstance(port, bool)
        or port < LOCAL_PORT_MIN
        or port > LOCAL_PORT_MAX
        for name, port in normalized.items()
    ):
        raise ValueError(
            f"ports must use non-empty names and values in {LOCAL_PORT_MIN}-"
            f"{LOCAL_PORT_MAX}",
        )
    return dict(normalized)


def _validated_env(env: Mapping[str, object]) -> dict[str, str]:
    normalized = _validated_non_empty_mapping(env, field_name="env")
    if any(
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(value, str)
        or not value.strip()
        for name, value in normalized.items()
    ):
        raise ValueError("env must use non-empty string names and values")
    return dict(normalized)


def _validated_no_leak_scan(
    no_leak_scan: Mapping[str, object],
    *,
    artifact_dir: str,
) -> dict[str, object]:
    normalized = _validated_non_empty_mapping(
        no_leak_scan,
        field_name="no_leak_scan",
    )
    path = _validated_json_path_in_artifact_dir(
        _validated_non_empty_string(
            normalized.get("path"),
            field_name="no_leak_scan.path",
        ),
        artifact_dir=artifact_dir,
        field_name="no_leak_scan.path",
    )
    passed = normalized.get("passed")
    findings_count = normalized.get("findings_count")
    if passed is not True:
        raise ValueError("no_leak_scan must have passed=true")
    if (
        not isinstance(findings_count, int)
        or isinstance(findings_count, bool)
        or findings_count != 0
    ):
        raise ValueError("no_leak_scan findings_count must be 0")
    return {
        "path": path,
        "passed": True,
        "findings_count": 0,
    }


def _sample_value(
    samples: list[dict[str, object]],
    metric_name: str,
    *,
    default: float = 0.0,
) -> float:
    for sample in samples:
        if sample["name"] == metric_name:
            return float(sample["value"])
    return default


def _active_labeled_value(
    samples: list[dict[str, object]],
    *,
    metric_name: str,
    label_name: str,
    fallback: str,
) -> str:
    for sample in samples:
        labels = sample["labels"]
        if (
            sample["name"] == metric_name
            and isinstance(labels, Mapping)
            and float(sample["value"]) == 1.0
        ):
            value = labels.get(label_name)
            return value if isinstance(value, str) else fallback
    return fallback


def _http_request_counts(samples: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for sample in samples:
        labels = sample["labels"]
        if sample["name"] != "vllm_mlx_http_requests_total" or not isinstance(
            labels,
            Mapping,
        ):
            continue
        rows.append(
            {
                "method": str(labels.get("method", "")),
                "path": str(labels.get("path", "")),
                "status_code": str(labels.get("status_code", "")),
                "count": float(sample["value"]),
            }
        )
    return rows


def _inference_request_counts(
    samples: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows = []
    for sample in samples:
        labels = sample["labels"]
        if sample["name"] != "vllm_mlx_inference_requests_total" or not isinstance(
            labels,
            Mapping,
        ):
            continue
        rows.append(
            {
                "endpoint": str(labels.get("endpoint", "")),
                "result": str(labels.get("result", "")),
                "stream": str(labels.get("stream", "")),
                "count": float(sample["value"]),
            }
        )
    return rows


def _kind_values(
    samples: list[dict[str, object]], metric_name: str
) -> dict[str, float]:
    values: dict[str, float] = {}
    for sample in samples:
        labels = sample["labels"]
        if sample["name"] == metric_name and isinstance(labels, Mapping):
            kind = labels.get("kind")
            if isinstance(kind, str):
                values[kind] = float(sample["value"])
    return values


def _validate_benchmark_row(row: Mapping[str, object]) -> None:
    for field in _BENCHMARK_REQUIRED_FIELDS:
        if field not in row:
            raise ValueError(f"benchmark row missing required field: {field}")


def _sorted_unique_strings(values: Iterable[object]) -> list[str]:
    return sorted({str(value) for value in values})


def _sorted_unique_numbers(values: Iterable[object]) -> list[int | float]:
    return sorted({_number(value) for value in values})


def _float_values(rows: list[Mapping[str, object]], field: str) -> list[float]:
    return [_number(row[field]) for row in rows]


def _number(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("numeric benchmark fields must be numbers")
    return value


def _average(values: list[float]) -> float:
    return sum(values) / len(values)


def _percentile(values: list[float], *, percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * percentile) - 1)
    return ordered[index]


if __name__ == "__main__":
    raise SystemExit(main())
