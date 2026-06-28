from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from mac_llm_ops_lab.persistence.domain import (
    ArtifactPointer,
    BenchmarkResult,
    InferenceRun,
    ModelCatalogEntry,
    NodeInventoryEntry,
)

T = TypeVar("T")


@dataclass
class _PersistenceState:
    models: dict[str, ModelCatalogEntry] = field(default_factory=dict)
    nodes: dict[str, NodeInventoryEntry] = field(default_factory=dict)
    runs: dict[str, InferenceRun] = field(default_factory=dict)
    benchmarks: dict[str, BenchmarkResult] = field(default_factory=dict)
    artifacts: dict[str, ArtifactPointer] = field(default_factory=dict)

    def clone(self) -> _PersistenceState:
        return _PersistenceState(
            models=dict(self.models),
            nodes=dict(self.nodes),
            runs=dict(self.runs),
            benchmarks=dict(self.benchmarks),
            artifacts=dict(self.artifacts),
        )


class _KeyedRepository(Generic[T]):
    def __init__(self, items: dict[str, T]) -> None:
        self._items = items

    async def get(self, item_id: str) -> T | None:
        return self._items.get(item_id)

    async def list(self) -> list[T]:
        return list(self._items.values())


class FakeModelCatalogRepository(_KeyedRepository[ModelCatalogEntry]):
    async def add(self, entry: ModelCatalogEntry) -> None:
        self._items[entry.model_id] = entry


class FakeNodeInventoryRepository(_KeyedRepository[NodeInventoryEntry]):
    async def add(self, entry: NodeInventoryEntry) -> None:
        self._items[entry.node_id] = entry


class FakeInferenceRunRepository(_KeyedRepository[InferenceRun]):
    async def add(self, run: InferenceRun) -> None:
        self._items[run.run_id] = run

    async def list_for_model(self, model_id: str) -> list[InferenceRun]:
        return [run for run in self._items.values() if run.model_id == model_id]


class FakeBenchmarkResultRepository:
    def __init__(self, items: dict[str, BenchmarkResult]) -> None:
        self._items = items

    async def add(self, result: BenchmarkResult) -> None:
        self._items[result.result_id] = result

    async def list_for_run(self, run_id: str) -> list[BenchmarkResult]:
        return [result for result in self._items.values() if result.run_id == run_id]


class FakeArtifactPointerRepository:
    def __init__(self, items: dict[str, ArtifactPointer]) -> None:
        self._items = items

    async def add(self, pointer: ArtifactPointer) -> None:
        self._items[pointer.artifact_id] = pointer

    async def list_for_run(self, run_id: str) -> list[ArtifactPointer]:
        return [pointer for pointer in self._items.values() if pointer.run_id == run_id]


class FakeUnitOfWork:
    def __init__(self) -> None:
        self._committed = _PersistenceState()
        self._working: _PersistenceState | None = None
        self.committed = False

    async def __aenter__(self) -> FakeUnitOfWork:
        self._working = self._committed.clone()
        self.committed = False
        self.models = FakeModelCatalogRepository(self._working.models)
        self.nodes = FakeNodeInventoryRepository(self._working.nodes)
        self.runs = FakeInferenceRunRepository(self._working.runs)
        self.benchmarks = FakeBenchmarkResultRepository(self._working.benchmarks)
        self.artifacts = FakeArtifactPointerRepository(self._working.artifacts)
        return self

    async def __aexit__(self, *args: object) -> None:
        if not self.committed:
            await self.rollback()
        self._working = None

    async def commit(self) -> None:
        if self._working is None:
            raise RuntimeError("FakeUnitOfWork is not active")
        self._committed = self._working.clone()
        self.committed = True

    async def rollback(self) -> None:
        self.committed = False
