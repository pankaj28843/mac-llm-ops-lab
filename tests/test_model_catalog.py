import json
from pathlib import Path

from mac_llm_ops_lab.model_catalog import (
    APPROVED_MODEL_CATALOG_SCHEMA_VERSION,
    build_model_download_gate_report,
    get_approved_model_entry,
)


def test_approved_mlx_model_catalog_records_source_and_cache_policy() -> None:
    entry = get_approved_model_entry("mlx-community/Qwen3-0.6B-8bit")

    assert entry.model_id == "mlx-community/Qwen3-0.6B-8bit"
    assert entry.backend_id == "vllm-mlx"
    assert entry.source_url == "https://huggingface.co/mlx-community/Qwen3-0.6B-8bit"
    assert entry.revision == "11de96878523501bcaa86104e3c186de07ff9068"
    assert entry.license == "apache-2.0"
    assert {"mlx", "8-bit", "text-generation"}.issubset(entry.tags)
    assert entry.cache_root == "model-cache/huggingface"
    assert entry.model_weights_gib > 0
    assert entry.estimated_runtime_total_gib <= 24.0


def test_model_download_gate_rejects_unknown_models() -> None:
    report = build_model_download_gate_report(
        model_id="mlx-community/not-reviewed",
        explicitly_approved=True,
        gitignore_text=Path(".gitignore").read_text(encoding="utf-8"),
    )

    assert report["decision"] == {
        "allowed": False,
        "reason_code": "model_not_in_catalog",
        "message": "Model is not in the approved local catalog.",
    }
    assert "model_card" not in report


def test_model_download_gate_requires_explicit_download_approval() -> None:
    report = build_model_download_gate_report(
        model_id="mlx-community/Qwen3-0.6B-8bit",
        explicitly_approved=False,
        gitignore_text=Path(".gitignore").read_text(encoding="utf-8"),
    )

    assert report["decision"]["allowed"] is False
    assert report["decision"]["reason_code"] == "runtime_not_authorized"
    assert "Qwen3" not in report["decision"]["message"]
    assert report["preflight_report"]["decision"]["allowed"] is False
    assert report["model_card"]["license"] == "apache-2.0"


def test_model_download_gate_requires_publish_safe_cache_ignore_policy() -> None:
    report = build_model_download_gate_report(
        model_id="mlx-community/Qwen3-0.6B-8bit",
        explicitly_approved=True,
        gitignore_text="artifacts/\nsecrets/\n",
    )

    assert report["decision"] == {
        "allowed": False,
        "reason_code": "runtime_cache_not_ignored",
        "message": "Runtime model cache paths must be excluded from git.",
    }
    assert report["missing_ignore_patterns"] == [
        "model-cache/",
        "models/",
    ]


def test_model_download_gate_allows_approved_model_with_memory_preflight() -> None:
    report = build_model_download_gate_report(
        model_id="mlx-community/Qwen3-0.6B-8bit",
        explicitly_approved=True,
        gitignore_text=Path(".gitignore").read_text(encoding="utf-8"),
    )

    assert report["schema_version"] == APPROVED_MODEL_CATALOG_SCHEMA_VERSION
    assert report["decision"] == {
        "allowed": True,
        "reason_code": "model_download_gate_passed",
        "message": "Model catalog, approval, memory, and cache policy passed.",
    }
    assert report["model_card"] == {
        "model_id": "mlx-community/Qwen3-0.6B-8bit",
        "source_url": "https://huggingface.co/mlx-community/Qwen3-0.6B-8bit",
        "revision": "11de96878523501bcaa86104e3c186de07ff9068",
        "license": "apache-2.0",
        "library_name": "mlx",
        "pipeline_tag": "text-generation",
        "tags": ["8-bit", "conversational", "mlx", "qwen3", "text-generation"],
        "cache_root": "model-cache/huggingface",
    }
    assert report["preflight_report"]["decision"]["allowed"] is True
    assert report["preflight_report"]["memory_gib"]["estimated_total"] == 4.7
    assert json.loads(json.dumps(report, sort_keys=True)) == report


def test_vllm_mlx_startup_script_runs_model_download_gate() -> None:
    script = Path("scripts/run-vllm-mlx-backend.sh").read_text(encoding="utf-8")

    assert "MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED" in script
    assert "mac_llm_ops_lab.model_catalog" in script
    assert "MODEL_DOWNLOAD_GATE_REPORT" in script
    assert 'PORT="${VLLM_MLX_PORT:-28100}"' in script


def test_model_catalog_docs_describe_approval_and_source_evidence() -> None:
    text = Path("docs/development.md").read_text(encoding="utf-8")

    for required in (
        "Version/source-surface",
        "https://huggingface.co/docs/transformers/en/model_sharing/",
        "https://huggingface.co/docs/datasets/en/cache/",
        "https://huggingface.co/mlx-community/Qwen3-0.6B-8bit",
        "vllm-mlx",
        "MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true",
        "runtime_not_authorized",
        "model-cache/huggingface",
        "estimated_runtime_total_gib: 4.7",
    ):
        assert required in text
