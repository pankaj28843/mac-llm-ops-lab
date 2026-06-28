from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    select,
)
from sqlalchemy import String as SQLString
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from mac_llm_ops_lab.persistence.domain import (
    ArtifactPointer,
    BenchmarkResult,
    InferenceRun,
    ModelCatalogEntry,
    NodeInventoryEntry,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    pass


class ModelCatalogRecord(Base):
    __tablename__ = "model_catalog"
    __table_args__ = (
        CheckConstraint(
            "context_window IS NULL OR context_window > 0",
            name="ck_model_catalog_context_window_positive",
        ),
    )

    model_id: Mapped[str] = mapped_column(SQLString(255), primary_key=True)
    backend: Mapped[str] = mapped_column(SQLString(100), nullable=False)
    display_name: Mapped[str] = mapped_column(SQLString(255), nullable=False)
    source_url: Mapped[str] = mapped_column(SQLString(1024), nullable=False)
    license: Mapped[str] = mapped_column(SQLString(100), nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    @classmethod
    def from_domain(cls, entry: ModelCatalogEntry) -> ModelCatalogRecord:
        return cls(
            model_id=entry.model_id,
            backend=entry.backend,
            display_name=entry.display_name,
            source_url=entry.source_url,
            license=entry.license,
            tags=list(entry.tags),
            context_window=entry.context_window,
            created_at=entry.created_at,
        )

    def to_domain(self) -> ModelCatalogEntry:
        return ModelCatalogEntry(
            model_id=self.model_id,
            backend=self.backend,
            display_name=self.display_name,
            source_url=self.source_url,
            license=self.license,
            tags=tuple(self.tags),
            context_window=self.context_window,
            created_at=_as_utc(self.created_at),
        )


class NodeInventoryRecord(Base):
    __tablename__ = "node_inventory"
    __table_args__ = (
        CheckConstraint("memory_gib > 0", name="ck_node_inventory_memory_positive"),
    )

    node_id: Mapped[str] = mapped_column(SQLString(255), primary_key=True)
    hostname: Mapped[str] = mapped_column(SQLString(255), nullable=False)
    chip: Mapped[str] = mapped_column(SQLString(255), nullable=False)
    memory_gib: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(SQLString(100), nullable=False)
    status: Mapped[str] = mapped_column(SQLString(100), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    @classmethod
    def from_domain(cls, entry: NodeInventoryEntry) -> NodeInventoryRecord:
        return cls(
            node_id=entry.node_id,
            hostname=entry.hostname,
            chip=entry.chip,
            memory_gib=entry.memory_gib,
            role=entry.role,
            status=entry.status,
            updated_at=entry.updated_at,
        )

    def to_domain(self) -> NodeInventoryEntry:
        return NodeInventoryEntry(
            node_id=self.node_id,
            hostname=self.hostname,
            chip=self.chip,
            memory_gib=self.memory_gib,
            role=self.role,
            status=self.status,
            updated_at=_as_utc(self.updated_at),
        )


class InferenceRunRecord(Base):
    __tablename__ = "inference_runs"
    __table_args__ = (
        CheckConstraint("prompt_tokens >= 0", name="ck_inference_runs_prompt_tokens"),
        CheckConstraint(
            "completion_tokens >= 0",
            name="ck_inference_runs_completion_tokens",
        ),
    )

    run_id: Mapped[str] = mapped_column(SQLString(255), primary_key=True)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_catalog.model_id", name="fk_inference_runs_model_id"),
        nullable=False,
    )
    node_id: Mapped[str] = mapped_column(
        ForeignKey("node_inventory.node_id", name="fk_inference_runs_node_id"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(SQLString(100), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @classmethod
    def from_domain(cls, run: InferenceRun) -> InferenceRunRecord:
        return cls(
            run_id=run.run_id,
            model_id=run.model_id,
            node_id=run.node_id,
            status=run.status,
            prompt_tokens=run.prompt_tokens,
            completion_tokens=run.completion_tokens,
            started_at=run.started_at,
            completed_at=run.completed_at,
        )

    def to_domain(self) -> InferenceRun:
        return InferenceRun(
            run_id=self.run_id,
            model_id=self.model_id,
            node_id=self.node_id,
            status=self.status,
            prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens,
            started_at=_as_utc(self.started_at),
            completed_at=_as_utc(self.completed_at),
        )


class BenchmarkResultRecord(Base):
    __tablename__ = "benchmark_results"
    __table_args__ = (
        CheckConstraint(
            "requests_per_second >= 0",
            name="ck_benchmark_results_rps_non_negative",
        ),
        CheckConstraint(
            "p95_latency_ms >= 0",
            name="ck_benchmark_results_p95_non_negative",
        ),
    )

    result_id: Mapped[str] = mapped_column(SQLString(255), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("inference_runs.run_id", name="fk_benchmark_results_run_id"),
        nullable=False,
    )
    workload_name: Mapped[str] = mapped_column(SQLString(255), nullable=False)
    requests_per_second: Mapped[float] = mapped_column(Float, nullable=False)
    p95_latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    @classmethod
    def from_domain(cls, result: BenchmarkResult) -> BenchmarkResultRecord:
        return cls(
            result_id=result.result_id,
            run_id=result.run_id,
            workload_name=result.workload_name,
            requests_per_second=result.requests_per_second,
            p95_latency_ms=result.p95_latency_ms,
            created_at=result.created_at,
        )

    def to_domain(self) -> BenchmarkResult:
        return BenchmarkResult(
            result_id=self.result_id,
            run_id=self.run_id,
            workload_name=self.workload_name,
            requests_per_second=self.requests_per_second,
            p95_latency_ms=self.p95_latency_ms,
            created_at=_as_utc(self.created_at),
        )


class ArtifactPointerRecord(Base):
    __tablename__ = "artifact_pointers"

    artifact_id: Mapped[str] = mapped_column(SQLString(255), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("inference_runs.run_id", name="fk_artifact_pointers_run_id"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(SQLString(100), nullable=False)
    uri: Mapped[str] = mapped_column(SQLString(2048), nullable=False)
    sha256: Mapped[str | None] = mapped_column(SQLString(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    @classmethod
    def from_domain(cls, pointer: ArtifactPointer) -> ArtifactPointerRecord:
        return cls(
            artifact_id=pointer.artifact_id,
            run_id=pointer.run_id,
            kind=pointer.kind,
            uri=pointer.uri,
            sha256=pointer.sha256,
            created_at=pointer.created_at,
        )

    def to_domain(self) -> ArtifactPointer:
        return ArtifactPointer(
            artifact_id=self.artifact_id,
            run_id=self.run_id,
            kind=self.kind,
            uri=self.uri,
            sha256=self.sha256,
            created_at=_as_utc(self.created_at),
        )


class SQLAlchemyModelCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: ModelCatalogEntry) -> None:
        await self._session.merge(ModelCatalogRecord.from_domain(entry))

    async def get(self, model_id: str) -> ModelCatalogEntry | None:
        record = await self._session.get(ModelCatalogRecord, model_id)
        return record.to_domain() if record else None

    async def list(self) -> list[ModelCatalogEntry]:
        records = await self._session.scalars(
            select(ModelCatalogRecord).order_by(ModelCatalogRecord.model_id)
        )
        return [record.to_domain() for record in records]


class SQLAlchemyNodeInventoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, entry: NodeInventoryEntry) -> None:
        await self._session.merge(NodeInventoryRecord.from_domain(entry))

    async def get(self, node_id: str) -> NodeInventoryEntry | None:
        record = await self._session.get(NodeInventoryRecord, node_id)
        return record.to_domain() if record else None

    async def list(self) -> list[NodeInventoryEntry]:
        records = await self._session.scalars(
            select(NodeInventoryRecord).order_by(NodeInventoryRecord.node_id)
        )
        return [record.to_domain() for record in records]


class SQLAlchemyInferenceRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: InferenceRun) -> None:
        await self._session.merge(InferenceRunRecord.from_domain(run))

    async def get(self, run_id: str) -> InferenceRun | None:
        record = await self._session.get(InferenceRunRecord, run_id)
        return record.to_domain() if record else None

    async def list_for_model(self, model_id: str) -> list[InferenceRun]:
        records = await self._session.scalars(
            select(InferenceRunRecord)
            .where(InferenceRunRecord.model_id == model_id)
            .order_by(InferenceRunRecord.started_at, InferenceRunRecord.run_id)
        )
        return [record.to_domain() for record in records]


class SQLAlchemyBenchmarkResultRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, result: BenchmarkResult) -> None:
        await self._session.merge(BenchmarkResultRecord.from_domain(result))

    async def list_for_run(self, run_id: str) -> list[BenchmarkResult]:
        records = await self._session.scalars(
            select(BenchmarkResultRecord)
            .where(BenchmarkResultRecord.run_id == run_id)
            .order_by(BenchmarkResultRecord.created_at, BenchmarkResultRecord.result_id)
        )
        return [record.to_domain() for record in records]


class SQLAlchemyArtifactPointerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, pointer: ArtifactPointer) -> None:
        await self._session.merge(ArtifactPointerRecord.from_domain(pointer))

    async def list_for_run(self, run_id: str) -> list[ArtifactPointer]:
        records = await self._session.scalars(
            select(ArtifactPointerRecord)
            .where(ArtifactPointerRecord.run_id == run_id)
            .order_by(
                ArtifactPointerRecord.created_at,
                ArtifactPointerRecord.artifact_id,
            )
        )
        return [record.to_domain() for record in records]


class SQLAlchemyUnitOfWork:
    def __init__(self, session_factory: Callable[[], AsyncSession]) -> None:
        self._session_factory = session_factory
        self.committed = False

    async def __aenter__(self) -> SQLAlchemyUnitOfWork:
        self.session = self._session_factory()
        self.committed = False
        self.models = SQLAlchemyModelCatalogRepository(self.session)
        self.nodes = SQLAlchemyNodeInventoryRepository(self.session)
        self.runs = SQLAlchemyInferenceRunRepository(self.session)
        self.benchmarks = SQLAlchemyBenchmarkResultRepository(self.session)
        self.artifacts = SQLAlchemyArtifactPointerRepository(self.session)
        return self

    async def __aexit__(self, *args: object) -> None:
        if not self.committed:
            await self.rollback()
        await self.session.close()

    async def commit(self) -> None:
        await self.session.commit()
        self.committed = True

    async def rollback(self) -> None:
        await self.session.rollback()
        self.committed = False


def create_async_session_factory(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
