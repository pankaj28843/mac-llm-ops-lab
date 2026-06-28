from datetime import UTC, datetime

import pytest

from mac_llm_ops_lab.persistence.domain import (
    ArtifactPointer,
    BenchmarkResult,
    InferenceRun,
    ModelCatalogEntry,
    NodeInventoryEntry,
)
from mac_llm_ops_lab.persistence.sqlalchemy import (
    Base,
    SQLAlchemyUnitOfWork,
    create_async_session_factory,
)

NOW = datetime(2026, 6, 28, 12, 0, tzinfo=UTC)


@pytest.mark.anyio
async def test_sqlalchemy_unit_of_work_round_trips_persistence_records(
    tmp_path,
) -> None:
    engine, session_factory = create_async_session_factory(
        f"sqlite+aiosqlite:///{tmp_path / 'roundtrip.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    model = _model()
    node = _node()
    run = _run(model_id=model.model_id, node_id=node.node_id)
    benchmark = _benchmark(run_id=run.run_id)
    artifact = _artifact(run_id=run.run_id)

    try:
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.models.add(model)
            await uow.nodes.add(node)
            await uow.runs.add(run)
            await uow.benchmarks.add(benchmark)
            await uow.artifacts.add(artifact)
            await uow.commit()

        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            assert await uow.models.get(model.model_id) == model
            assert await uow.models.list() == [model]
            assert await uow.nodes.get(node.node_id) == node
            assert await uow.runs.get(run.run_id) == run
            assert await uow.runs.list_for_model(model.model_id) == [run]
            assert await uow.benchmarks.list_for_run(run.run_id) == [benchmark]
            assert await uow.artifacts.list_for_run(run.run_id) == [artifact]
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_sqlalchemy_unit_of_work_rolls_back_without_commit(tmp_path) -> None:
    engine, session_factory = create_async_session_factory(
        f"sqlite+aiosqlite:///{tmp_path / 'rollback.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    try:
        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            await uow.models.add(_model(model_id="rolled-back"))

        async with SQLAlchemyUnitOfWork(session_factory) as uow:
            assert await uow.models.get("rolled-back") is None
            assert await uow.models.list() == []
    finally:
        await engine.dispose()


def test_sqlalchemy_metadata_uses_named_constraints_for_reviewable_migrations() -> None:
    tables = Base.metadata.tables

    assert set(tables) == {
        "artifact_pointers",
        "benchmark_results",
        "inference_runs",
        "model_catalog",
        "node_inventory",
    }
    for table in tables.values():
        assert all(constraint.name for constraint in table.constraints)


@pytest.mark.anyio
async def test_sqlalchemy_uow_uses_a_distinct_session_per_context(tmp_path) -> None:
    engine, session_factory = create_async_session_factory(
        f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}"
    )
    try:
        first_uow = SQLAlchemyUnitOfWork(session_factory)
        second_uow = SQLAlchemyUnitOfWork(session_factory)

        async with first_uow, second_uow:
            assert first_uow.session is not second_uow.session
    finally:
        await engine.dispose()


def _model(model_id: str = "mlx-community/Qwen3-0.6B-8bit") -> ModelCatalogEntry:
    return ModelCatalogEntry(
        model_id=model_id,
        backend="vllm-mlx",
        display_name="Qwen3 0.6B 8-bit MLX",
        source_url="https://huggingface.co/mlx-community/Qwen3-0.6B-8bit",
        license="apache-2.0",
        tags=("mlx", "qwen3", "apple-silicon"),
        context_window=32768,
        created_at=NOW,
    )


def _node() -> NodeInventoryEntry:
    return NodeInventoryEntry(
        node_id="macbook-m3-max",
        hostname="Pankajs-MacBook-Pro.local",
        chip="Apple M3 Max",
        memory_gib=36,
        role="developer",
        status="online",
        updated_at=NOW,
    )


def _run(*, model_id: str, node_id: str) -> InferenceRun:
    return InferenceRun(
        run_id="run-001",
        model_id=model_id,
        node_id=node_id,
        status="succeeded",
        prompt_tokens=9,
        completion_tokens=3,
        started_at=NOW,
        completed_at=NOW,
    )


def _benchmark(*, run_id: str) -> BenchmarkResult:
    return BenchmarkResult(
        result_id="bench-001",
        run_id=run_id,
        workload_name="single-chat-smoke",
        requests_per_second=1.57,
        p95_latency_ms=635.85,
        created_at=NOW,
    )


def _artifact(*, run_id: str) -> ArtifactPointer:
    return ArtifactPointer(
        artifact_id="artifact-001",
        run_id=run_id,
        kind="runtime-evidence",
        uri="artifacts/runtime/2026-06-28T153000+0200-model-backed-api-e2e/",
        sha256=None,
        created_at=NOW,
    )
