# Model Catalog And Download Gate

Real model downloads are governed by a tracked catalog plus an explicit local
approval flag. This keeps public repo state clean while still letting the lab
run a small Apple Silicon model when the operator chooses to do so.

## Source Surface

Version/source-surface:

- Local `docsearch` tenant `transformers`, page
  `https://huggingface.co/docs/transformers/en/model_sharing/`, for Hugging
  Face model repositories, revisions, gating, and model cards.
- Local `docsearch` tenant `datasets`, page
  `https://huggingface.co/docs/datasets/en/cache/`, for `HF_HOME` and
  `HF_HUB_CACHE` cache behavior.
- Primary Hugging Face model API for
  `https://huggingface.co/mlx-community/Qwen3-0.6B-8bit`, checked on
  2026-06-28.
- Primary `vllm-mlx` GitHub/PyPI metadata, checked on 2026-06-28.

Current approved local model:

```text
model_id: mlx-community/Qwen3-0.6B-8bit
backend_id: vllm-mlx
revision: 11de96878523501bcaa86104e3c186de07ff9068
license: apache-2.0
library: mlx
pipeline: text-generation
tags: 8-bit, conversational, mlx, qwen3, text-generation
cache_root: model-cache/huggingface
estimated_runtime_total_gib: 4.7
```

The cache root is intentionally under ignored `model-cache/`. Do not commit
model weights, cache metadata, raw benchmark payloads, traces, local reports,
or generated runtime artifacts.

## Approval Flow

The model download gate is CPU-safe and does not download a model:

```bash
uv run python -m mac_llm_ops_lab.model_catalog mlx-community/Qwen3-0.6B-8bit
```

Without approval it exits non-zero and returns `runtime_not_authorized`.

To approve a local run or download, set the approval flag and save the report
under ignored runtime artifacts:

```bash
MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true \
MODEL_DOWNLOAD_GATE_REPORT=artifacts/runtime/vllm-mlx-model-download-gate.json \
uv run python -m mac_llm_ops_lab.model_catalog mlx-community/Qwen3-0.6B-8bit
```

`scripts/run-vllm-mlx-backend.sh` invokes this same gate before starting
`vllm-mlx serve`. The script defaults `MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=false`, so
future starts cannot silently download or run a cataloged model without an
operator decision.

## Completion Boundary

This gate satisfies the catalog/download-approval part of slice 10. It does not
complete fuller benchmark qualification or Mac Studio cluster proof.
