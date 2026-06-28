import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

CLUSTER_EVIDENCE_MANIFEST_SCHEMA_VERSION = "cluster-evidence-manifest/v1"
NODE_EVIDENCE_REPORT_SCHEMA_VERSION = "mac-studio-node-evidence/v1"
REQUIRED_NODE_EVIDENCE_LABELS = (
    "api_log",
    "backend_log",
    "phoenix_spans",
    "metrics",
)
REQUIRED_NODE_REPORT_EVIDENCE_LABELS = (
    "api_log",
    "backend_log",
    "metrics",
    "node_evidence",
    "phoenix_spans",
)
NODE_REPORT_EVIDENCE_SUFFIXES = {
    "api_log": ".log",
    "backend_log": ".log",
    "metrics": ".json",
    "node_evidence": ".json",
    "phoenix_spans": ".json",
}


@dataclass(frozen=True)
class ClusterNode:
    node_id: str
    hostname: str
    api_base_url: str
    backend_base_url: str
    backend_id: str
    chip: str
    memory_gib: int
    models: tuple[str, ...]
    queue_depth: int
    ready: bool
    healthy: bool
    capabilities: tuple[str, ...]
    ports: Mapping[str, int]

    def to_inventory_record(self) -> dict[str, object]:
        node = register_cluster_node(self)
        return {
            "node_id": node.node_id,
            "hostname": node.hostname,
            "api_base_url": node.api_base_url,
            "backend_base_url": node.backend_base_url,
            "backend_id": node.backend_id,
            "chip": node.chip,
            "memory_gib": node.memory_gib,
            "models": list(node.models),
            "queue_depth": node.queue_depth,
            "ready": node.ready,
            "healthy": node.healthy,
            "capabilities": list(node.capabilities),
            "ports": dict(sorted(node.ports.items())),
        }


@dataclass(frozen=True)
class RoutingDecision:
    node_id: str
    backend_id: str
    model_id: str
    api_base_url: str | None
    reason: str
    fallback: bool

    def to_record(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "backend_id": self.backend_id,
            "model_id": self.model_id,
            "api_base_url": self.api_base_url,
            "reason": self.reason,
            "fallback": self.fallback,
        }


def register_cluster_node(node: ClusterNode) -> ClusterNode:
    return ClusterNode(
        node_id=_non_empty_string(node.node_id, field_name="node_id"),
        hostname=_non_empty_string(node.hostname, field_name="hostname"),
        api_base_url=_validated_high_port_url(
            node.api_base_url,
            field_name="api_base_url",
        ),
        backend_base_url=_validated_high_port_url(
            node.backend_base_url,
            field_name="backend_base_url",
        ),
        backend_id=_non_empty_string(node.backend_id, field_name="backend_id"),
        chip=_non_empty_string(node.chip, field_name="chip"),
        memory_gib=_positive_int(node.memory_gib, field_name="memory_gib"),
        models=_non_empty_strings(node.models, field_name="models"),
        queue_depth=_non_negative_int(node.queue_depth, field_name="queue_depth"),
        ready=_bool(node.ready, field_name="ready"),
        healthy=_bool(node.healthy, field_name="healthy"),
        capabilities=_non_empty_strings(
            node.capabilities,
            field_name="capabilities",
        ),
        ports=_validated_high_ports(node.ports),
    )


def route_to_model(
    nodes: Sequence[ClusterNode],
    *,
    model_id: str,
) -> RoutingDecision:
    requested_model = _non_empty_string(model_id, field_name="model_id")
    registered_nodes = [register_cluster_node(node) for node in nodes]
    candidates = [
        node
        for node in registered_nodes
        if node.healthy and node.ready and requested_model in node.models
    ]
    if not candidates:
        return RoutingDecision(
            node_id="local-fallback",
            backend_id="fake",
            model_id=requested_model,
            api_base_url=None,
            reason="no_healthy_registered_node",
            fallback=True,
        )

    selected = min(candidates, key=lambda node: (node.queue_depth, node.node_id))
    return RoutingDecision(
        node_id=selected.node_id,
        backend_id=selected.backend_id,
        model_id=requested_model,
        api_base_url=selected.api_base_url,
        reason="least_queue_depth",
        fallback=False,
    )


def build_cluster_evidence_manifest(
    *,
    git_sha: str,
    command: Sequence[str],
    artifact_dir: str,
    nodes: Sequence[ClusterNode],
    route_decisions: Sequence[RoutingDecision],
    node_evidence: Mapping[str, Mapping[str, str]],
) -> dict[str, object]:
    normalized_artifact_dir = _validated_artifact_dir(artifact_dir)
    normalized_nodes = [register_cluster_node(node) for node in nodes]
    if not normalized_nodes:
        raise ValueError("nodes must contain at least one node")
    normalized_decisions = [
        _validated_route_decision(decision) for decision in route_decisions
    ]
    if not normalized_decisions:
        raise ValueError("route_decisions must contain at least one decision")

    node_ids = {node.node_id for node in normalized_nodes}
    for decision in normalized_decisions:
        if not decision.fallback and decision.node_id not in node_ids:
            raise ValueError("route_decisions must reference registered nodes")

    return {
        "schema_version": CLUSTER_EVIDENCE_MANIFEST_SCHEMA_VERSION,
        "git_sha": _non_empty_string(git_sha, field_name="git_sha"),
        "command": _validated_command(command),
        "artifact_dir": normalized_artifact_dir,
        "requires_real_multi_node_proof": True,
        "nodes": [node.to_inventory_record() for node in normalized_nodes],
        "route_decisions": [decision.to_record() for decision in normalized_decisions],
        "node_evidence": _validated_node_evidence(
            node_evidence,
            node_ids=node_ids,
            artifact_dir=normalized_artifact_dir,
        ),
    }


def build_node_evidence_report(
    *,
    node: ClusterNode,
    git_sha: str,
    command: Sequence[str],
    artifact_dir: str,
    macos_version: str,
    model_id: str,
    model_revision: str,
    health_urls: Mapping[str, str],
    phoenix_url: str,
    evidence_files: Mapping[str, str],
) -> dict[str, object]:
    normalized_node = register_cluster_node(node)
    normalized_model_id = _non_empty_string(model_id, field_name="model_id")
    if normalized_model_id not in normalized_node.models:
        raise ValueError("model_id must be listed in node.models")

    normalized_artifact_dir = _validated_artifact_dir(artifact_dir)
    return {
        "schema_version": NODE_EVIDENCE_REPORT_SCHEMA_VERSION,
        "git_sha": _non_empty_string(git_sha, field_name="git_sha"),
        "artifact_dir": normalized_artifact_dir,
        "command": _validated_command(command),
        "requires_real_multi_node_proof": True,
        "node": normalized_node.to_inventory_record(),
        "host": {
            "hostname": normalized_node.hostname,
            "chip": normalized_node.chip,
            "memory_gib": normalized_node.memory_gib,
            "macos_version": _non_empty_string(
                macos_version,
                field_name="macos_version",
            ),
        },
        "backend": {
            "backend_id": normalized_node.backend_id,
            "model_id": normalized_model_id,
            "model_revision": _non_empty_string(
                model_revision,
                field_name="model_revision",
            ),
        },
        "service_endpoints": {
            "api_base_url": normalized_node.api_base_url,
            "backend_base_url": normalized_node.backend_base_url,
            "health_urls": _validated_health_urls(health_urls),
            "phoenix_url": _validated_high_port_url(
                phoenix_url,
                field_name="phoenix_url",
            ),
        },
        "evidence_files": _validated_node_report_evidence_files(
            evidence_files,
            artifact_dir=normalized_artifact_dir,
        ),
    }


def write_node_evidence_report(
    *,
    output_path: str,
    node: ClusterNode,
    git_sha: str,
    command: Sequence[str],
    artifact_dir: str,
    macos_version: str,
    model_id: str,
    model_revision: str,
    health_urls: Mapping[str, str],
    phoenix_url: str,
    evidence_files: Mapping[str, str],
) -> dict[str, object]:
    report = build_node_evidence_report(
        node=node,
        git_sha=git_sha,
        command=command,
        artifact_dir=artifact_dir,
        macos_version=macos_version,
        model_id=model_id,
        model_revision=model_revision,
        health_urls=health_urls,
        phoenix_url=phoenix_url,
        evidence_files=evidence_files,
    )
    normalized_output_path = _validated_evidence_path(
        output_path,
        artifact_dir=report["artifact_dir"],
        field_name="output_path",
        expected_suffix=".json",
    )
    if report["evidence_files"]["node_evidence"] != normalized_output_path:
        raise ValueError("output_path must match evidence_files.node_evidence")

    output = Path(normalized_output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report


def _validated_route_decision(decision: RoutingDecision) -> RoutingDecision:
    return RoutingDecision(
        node_id=_non_empty_string(decision.node_id, field_name="decision.node_id"),
        backend_id=_non_empty_string(
            decision.backend_id,
            field_name="decision.backend_id",
        ),
        model_id=_non_empty_string(decision.model_id, field_name="decision.model_id"),
        api_base_url=(
            None
            if decision.api_base_url is None
            else _validated_high_port_url(
                decision.api_base_url, field_name="decision.api_base_url"
            )
        ),
        reason=_non_empty_string(decision.reason, field_name="decision.reason"),
        fallback=_bool(decision.fallback, field_name="decision.fallback"),
    )


def _validated_node_evidence(
    node_evidence: Mapping[str, Mapping[str, str]],
    *,
    node_ids: set[str],
    artifact_dir: str,
) -> list[dict[str, object]]:
    evidence_node_ids = set(node_evidence)
    if evidence_node_ids != node_ids:
        raise ValueError("node_evidence must contain exactly one entry per node")

    normalized = []
    for node_id in sorted(node_ids):
        files = dict(node_evidence[node_id])
        missing = [
            label for label in REQUIRED_NODE_EVIDENCE_LABELS if label not in files
        ]
        if missing:
            raise ValueError(
                "node_evidence is missing required labels: " + ", ".join(missing),
            )
        normalized.append(
            {
                "node_id": node_id,
                "files": {
                    label: _validated_evidence_path(
                        files[label],
                        artifact_dir=artifact_dir,
                        field_name=f"node_evidence.{node_id}.{label}",
                        expected_suffix=".log" if label.endswith("_log") else ".json",
                    )
                    for label in REQUIRED_NODE_EVIDENCE_LABELS
                },
            }
        )
    return normalized


def _validated_node_report_evidence_files(
    evidence_files: Mapping[str, str],
    *,
    artifact_dir: str,
) -> dict[str, str]:
    files = dict(evidence_files)
    missing = [
        label for label in REQUIRED_NODE_REPORT_EVIDENCE_LABELS if label not in files
    ]
    if missing:
        raise ValueError(
            "evidence_files is missing required labels: " + ", ".join(missing),
        )

    return {
        label: _validated_evidence_path(
            files[label],
            artifact_dir=artifact_dir,
            field_name=f"evidence_files.{label}",
            expected_suffix=NODE_REPORT_EVIDENCE_SUFFIXES[label],
        )
        for label in REQUIRED_NODE_REPORT_EVIDENCE_LABELS
    }


def _validated_evidence_path(
    value: str,
    *,
    artifact_dir: str,
    field_name: str,
    expected_suffix: str,
) -> str:
    path = _relative_path(value, field_name=field_name)
    try:
        path.relative_to(PurePosixPath(artifact_dir))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be inside artifact_dir") from exc
    if path.suffix != expected_suffix:
        raise ValueError(f"{field_name} must end with {expected_suffix}")
    return path.as_posix()


def _validated_artifact_dir(value: str) -> str:
    path = _relative_path(value, field_name="artifact_dir")
    if len(path.parts) < 3 or path.parts[:2] != ("artifacts", "runtime"):
        raise ValueError("artifact_dir must be under artifacts/runtime/")
    return path.as_posix()


def _relative_path(value: str, *, field_name: str) -> PurePosixPath:
    text = _non_empty_string(value, field_name=field_name)
    path = PurePosixPath(text)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"{field_name} must be a relative path without traversal")
    return path


def _validated_command(command: Sequence[str]) -> list[str]:
    normalized = list(command)
    if not normalized or any(
        not isinstance(part, str) or not part.strip() for part in normalized
    ):
        raise ValueError("command must contain non-empty strings")
    return normalized


def _validated_high_ports(ports: Mapping[str, int]) -> dict[str, int]:
    normalized = dict(ports)
    if not normalized:
        raise ValueError("ports must be non-empty")
    for name, port in normalized.items():
        _non_empty_string(name, field_name="port name")
        if not isinstance(port, int) or isinstance(port, bool):
            raise ValueError("ports must map names to integer port values")
        if not 20000 <= port <= 50000:
            raise ValueError("ports must stay in the 20000-50000 range")
    return dict(sorted(normalized.items()))


def _validated_health_urls(health_urls: Mapping[str, str]) -> dict[str, str]:
    normalized = dict(health_urls)
    if not normalized:
        raise ValueError("health_urls must be non-empty")
    return {
        _non_empty_string(name, field_name="health URL name"): _validated_high_port_url(
            value,
            field_name=f"health_urls.{name}",
        )
        for name, value in sorted(normalized.items())
    }


def _validated_high_port_url(value: str, *, field_name: str) -> str:
    text = _validated_url(value, field_name=field_name)
    parsed = urlparse(text)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field_name} must include a valid port") from exc
    if port is None:
        raise ValueError(f"{field_name} must include an explicit high port")
    if not 20000 <= port <= 50000:
        raise ValueError(f"{field_name} port must stay in the 20000-50000 range")
    return text


def _validated_url(value: str, *, field_name: str) -> str:
    text = _non_empty_string(value, field_name=field_name)
    if not (text.startswith("http://") or text.startswith("https://")):
        raise ValueError(f"{field_name} must be an HTTP URL")
    return text


def _non_empty_strings(values: Sequence[str], *, field_name: str) -> tuple[str, ...]:
    if isinstance(values, str) or not values:
        raise ValueError(f"{field_name} must contain at least one value")
    return tuple(_non_empty_string(value, field_name=field_name) for value in values)


def _non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value


def _positive_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _non_negative_int(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")
    return value


def _bool(value: object, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _parse_key_value_pairs(
    values: Sequence[str],
    *,
    field_name: str,
    integer_values: bool = False,
) -> dict[str, int] | dict[str, str]:
    parsed: dict[str, int] | dict[str, str] = {}
    for value in values:
        key, separator, raw_value = value.partition("=")
        if not separator:
            raise ValueError(f"{field_name} entries must use name=value")
        key = _non_empty_string(key, field_name=f"{field_name} name")
        raw_value = _non_empty_string(raw_value, field_name=f"{field_name}.{key}")
        if integer_values:
            try:
                parsed[key] = int(raw_value)
            except ValueError as exc:
                raise ValueError(f"{field_name}.{key} must be an integer") from exc
        else:
            parsed[key] = raw_value
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mac Studio cluster evidence helpers.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    node_evidence = subparsers.add_parser(
        "node-evidence",
        help="Write a per-node evidence report under artifacts/runtime/.",
    )
    node_evidence.add_argument("--node-id", required=True)
    node_evidence.add_argument("--hostname", required=True)
    node_evidence.add_argument("--api-base-url", required=True)
    node_evidence.add_argument("--backend-base-url", required=True)
    node_evidence.add_argument("--backend-id", required=True)
    node_evidence.add_argument("--chip", required=True)
    node_evidence.add_argument("--memory-gib", type=int, required=True)
    node_evidence.add_argument("--model-id", required=True)
    node_evidence.add_argument("--model-revision", required=True)
    node_evidence.add_argument("--macos-version", required=True)
    node_evidence.add_argument("--capability", action="append", required=True)
    node_evidence.add_argument("--port", action="append", required=True)
    node_evidence.add_argument("--health-url", action="append", required=True)
    node_evidence.add_argument("--phoenix-url", required=True)
    node_evidence.add_argument("--git-sha", required=True)
    node_evidence.add_argument("--command", action="append", required=True)
    node_evidence.add_argument("--artifact-dir", required=True)
    node_evidence.add_argument("--api-log", required=True)
    node_evidence.add_argument("--backend-log", required=True)
    node_evidence.add_argument("--phoenix-spans", required=True)
    node_evidence.add_argument("--metrics", required=True)
    node_evidence.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand == "node-evidence":
        ports = _parse_key_value_pairs(
            args.port,
            field_name="port",
            integer_values=True,
        )
        health_urls = _parse_key_value_pairs(
            args.health_url,
            field_name="health-url",
        )
        evidence_files = {
            "node_evidence": args.output,
            "api_log": args.api_log,
            "backend_log": args.backend_log,
            "phoenix_spans": args.phoenix_spans,
            "metrics": args.metrics,
        }
        node = ClusterNode(
            node_id=args.node_id,
            hostname=args.hostname,
            api_base_url=args.api_base_url,
            backend_base_url=args.backend_base_url,
            backend_id=args.backend_id,
            chip=args.chip,
            memory_gib=args.memory_gib,
            models=(args.model_id,),
            queue_depth=0,
            ready=True,
            healthy=True,
            capabilities=tuple(args.capability),
            ports=ports,
        )
        write_node_evidence_report(
            output_path=args.output,
            node=node,
            git_sha=args.git_sha,
            command=args.command,
            artifact_dir=args.artifact_dir,
            macos_version=args.macos_version,
            model_id=args.model_id,
            model_revision=args.model_revision,
            health_urls=health_urls,
            phoenix_url=args.phoenix_url,
            evidence_files=evidence_files,
        )
        return 0
    parser.error(f"unsupported subcommand: {args.subcommand}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
