from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ModelCatalogEntry:
    model_id: str
    backend: str
    display_name: str
    source_url: str
    license: str
    tags: tuple[str, ...]
    context_window: int | None
    created_at: datetime


@dataclass(frozen=True)
class NodeInventoryEntry:
    node_id: str
    hostname: str
    chip: str
    memory_gib: int
    role: str
    status: str
    updated_at: datetime


@dataclass(frozen=True)
class InferenceRun:
    run_id: str
    model_id: str
    node_id: str
    status: str
    prompt_tokens: int
    completion_tokens: int
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class BenchmarkResult:
    result_id: str
    run_id: str
    workload_name: str
    requests_per_second: float
    p95_latency_ms: float
    created_at: datetime


@dataclass(frozen=True)
class ArtifactPointer:
    artifact_id: str
    run_id: str
    kind: str
    uri: str
    sha256: str | None
    created_at: datetime
