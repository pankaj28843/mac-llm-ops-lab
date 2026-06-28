from datetime import UTC, datetime
from pathlib import Path

import pytest

from mac_llm_ops_lab.persistence.domain import (
    ArtifactPointer,
    BenchmarkResult,
    InferenceRun,
    ModelCatalogEntry,
    NodeInventoryEntry,
)
from mac_llm_ops_lab.persistence.fakes import FakeUnitOfWork

NOW = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_fake_unit_of_work_commits_model_node_run_and_artifacts() -> None:
    uow = FakeUnitOfWork()
    model = ModelCatalogEntry(
        model_id="mlx-community/Qwen3-0.6B-8bit",
        backend="vllm-mlx",
        display_name="Qwen3 0.6B 8-bit MLX",
        source_url="https://huggingface.co/mlx-community/Qwen3-0.6B-8bit",
        license="apache-2.0",
        tags=("mlx", "qwen3", "apple-silicon"),
        context_window=32768,
        created_at=NOW,
    )
    node = NodeInventoryEntry(
        node_id="macbook-m3-max",
        hostname="Pankajs-MacBook-Pro.local",
        chip="Apple M3 Max",
        memory_gib=36,
        role="developer",
        status="online",
        updated_at=NOW,
    )
    run = InferenceRun(
        run_id="run-001",
        model_id=model.model_id,
        node_id=node.node_id,
        status="succeeded",
        prompt_tokens=9,
        completion_tokens=3,
        started_at=NOW,
        completed_at=NOW,
    )
    benchmark = BenchmarkResult(
        result_id="bench-001",
        run_id=run.run_id,
        workload_name="single-chat-smoke",
        requests_per_second=1.57,
        p95_latency_ms=635.85,
        created_at=NOW,
    )
    artifact = ArtifactPointer(
        artifact_id="artifact-001",
        run_id=run.run_id,
        kind="runtime-evidence",
        uri="artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/",
        sha256=None,
        created_at=NOW,
    )

    async with uow:
        await uow.models.add(model)
        await uow.nodes.add(node)
        await uow.runs.add(run)
        await uow.benchmarks.add(benchmark)
        await uow.artifacts.add(artifact)
        await uow.commit()

    async with uow:
        assert await uow.models.get(model.model_id) == model
        assert await uow.models.list() == [model]
        assert await uow.nodes.get(node.node_id) == node
        assert await uow.runs.get(run.run_id) == run
        assert await uow.runs.list_for_model(model.model_id) == [run]
        assert await uow.benchmarks.list_for_run(run.run_id) == [benchmark]
        assert await uow.artifacts.list_for_run(run.run_id) == [artifact]


@pytest.mark.anyio
async def test_fake_unit_of_work_rolls_back_uncommitted_writes() -> None:
    uow = FakeUnitOfWork()
    model = ModelCatalogEntry(
        model_id="uncommitted-model",
        backend="vllm-mlx",
        display_name="Uncommitted",
        source_url="https://example.invalid/model",
        license="unknown",
        tags=(),
        context_window=None,
        created_at=NOW,
    )

    async with uow:
        await uow.models.add(model)

    async with uow:
        assert await uow.models.get(model.model_id) is None
        assert await uow.models.list() == []


def test_api_handlers_do_not_import_database_adapters() -> None:
    app_source = Path("src/mac_llm_ops_lab/app.py").read_text(encoding="utf-8")

    assert "sqlalchemy" not in app_source
    assert "alembic" not in app_source
    assert "persistence.sqlalchemy" not in app_source
