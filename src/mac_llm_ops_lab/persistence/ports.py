from collections.abc import AsyncContextManager
from typing import Protocol

from mac_llm_ops_lab.persistence.domain import (
    ArtifactPointer,
    BenchmarkResult,
    InferenceRun,
    ModelCatalogEntry,
    NodeInventoryEntry,
)


class ModelCatalogRepository(Protocol):
    async def add(self, entry: ModelCatalogEntry) -> None: ...

    async def get(self, model_id: str) -> ModelCatalogEntry | None: ...

    async def list(self) -> list[ModelCatalogEntry]: ...


class NodeInventoryRepository(Protocol):
    async def add(self, entry: NodeInventoryEntry) -> None: ...

    async def get(self, node_id: str) -> NodeInventoryEntry | None: ...

    async def list(self) -> list[NodeInventoryEntry]: ...


class InferenceRunRepository(Protocol):
    async def add(self, run: InferenceRun) -> None: ...

    async def get(self, run_id: str) -> InferenceRun | None: ...

    async def list_for_model(self, model_id: str) -> list[InferenceRun]: ...


class BenchmarkResultRepository(Protocol):
    async def add(self, result: BenchmarkResult) -> None: ...

    async def list_for_run(self, run_id: str) -> list[BenchmarkResult]: ...


class ArtifactPointerRepository(Protocol):
    async def add(self, pointer: ArtifactPointer) -> None: ...

    async def list_for_run(self, run_id: str) -> list[ArtifactPointer]: ...


class UnitOfWork(AsyncContextManager["UnitOfWork"], Protocol):
    models: ModelCatalogRepository
    nodes: NodeInventoryRepository
    runs: InferenceRunRepository
    benchmarks: BenchmarkResultRepository
    artifacts: ArtifactPointerRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
