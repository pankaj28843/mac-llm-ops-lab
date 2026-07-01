import argparse
import json
import plistlib
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath

MACOS_LAUNCHD_SERVICE_BUNDLE_SCHEMA_VERSION = "macos-launchd-service-bundle/v2"
BACKEND_LABEL = "dev.mac_llm_ops.vllm-mlx"


def build_macos_launchd_service_bundle(
    *,
    repo_dir: str | Path,
    artifact_dir: str,
    model_id: str,
    backend_port: int,
    model_download_approved: bool,
    backend_host: str = "127.0.0.1",
) -> dict[str, object]:
    normalized_repo_dir = _validated_repo_dir(repo_dir)
    normalized_artifact_dir = _validated_artifact_dir(artifact_dir)
    normalized_model_id = _non_empty_string(model_id, field_name="model_id")
    ports = {
        "backend": _validated_high_port(backend_port, field_name="backend_port"),
    }
    artifact_root = Path.cwd() / normalized_artifact_dir
    backend_script = _validated_script(
        normalized_repo_dir / "scripts/run-vllm-mlx-backend.sh",
        field_name="backend_script",
    )

    backend_plist = _build_launchd_plist(
        label=BACKEND_LABEL,
        program_arguments=(backend_script,),
        working_directory=normalized_repo_dir,
        environment={
            "MODEL_ID": normalized_model_id,
            "SERVED_MODEL_NAME": normalized_model_id,
            "VLLM_MLX_HOST": _non_empty_string(
                backend_host,
                field_name="backend_host",
            ),
            "VLLM_MLX_PORT": str(ports["backend"]),
            "HF_HOME": str(normalized_repo_dir / "model-cache/huggingface"),
            "MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED": _bool_env(model_download_approved),
            "MODEL_DOWNLOAD_GATE_REPORT": (
                f"{normalized_artifact_dir}/vllm-mlx-model-download-gate.json"
            ),
        },
        stdout_path=artifact_root / "backend.out.log",
        stderr_path=artifact_root / "backend.err.log",
    )

    return {
        "schema_version": MACOS_LAUNCHD_SERVICE_BUNDLE_SCHEMA_VERSION,
        "artifact_dir": normalized_artifact_dir,
        "install_boundary": "generate_only_do_not_install",
        "ports": ports,
        "plist_files": {
            "backend": f"{normalized_artifact_dir}/{BACKEND_LABEL}.plist",
        },
        "services": {
            "backend": backend_plist,
        },
    }


def write_macos_launchd_service_bundle(
    *,
    repo_dir: str | Path,
    artifact_dir: str,
    model_id: str,
    backend_port: int,
    model_download_approved: bool,
    backend_host: str = "127.0.0.1",
) -> dict[str, object]:
    bundle = build_macos_launchd_service_bundle(
        repo_dir=repo_dir,
        artifact_dir=artifact_dir,
        model_id=model_id,
        backend_port=backend_port,
        model_download_approved=model_download_approved,
        backend_host=backend_host,
    )
    artifact_root = Path.cwd() / str(bundle["artifact_dir"])
    artifact_root.mkdir(parents=True, exist_ok=True)

    for service_name, plist_path in bundle["plist_files"].items():
        plist = bundle["services"][service_name]
        (Path.cwd() / plist_path).write_bytes(plistlib.dumps(plist, sort_keys=True))

    manifest_path = artifact_root / "launchd-manifest.json"
    manifest_path.write_text(
        json.dumps(bundle, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return bundle


def _build_launchd_plist(
    *,
    label: str,
    program_arguments: Sequence[Path],
    working_directory: Path,
    environment: Mapping[str, str],
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, object]:
    return {
        "EnvironmentVariables": {
            _non_empty_string(key, field_name="environment key"): _non_empty_string(
                value,
                field_name=f"environment.{key}",
            )
            for key, value in sorted(environment.items())
        },
        "KeepAlive": False,
        "Label": _non_empty_string(label, field_name="label"),
        "ProgramArguments": [
            _absolute_path(value, field_name="program_argument").as_posix()
            for value in program_arguments
        ],
        "RunAtLoad": False,
        "StandardErrorPath": _absolute_path(
            stderr_path,
            field_name="stderr_path",
        ).as_posix(),
        "StandardOutPath": _absolute_path(
            stdout_path,
            field_name="stdout_path",
        ).as_posix(),
        "WorkingDirectory": _absolute_path(
            working_directory,
            field_name="working_directory",
        ).as_posix(),
    }


def _validated_repo_dir(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError("repo_dir must be an absolute path")
    if not path.exists() or not path.is_dir():
        raise ValueError("repo_dir must exist and be a directory")
    return path


def _validated_script(value: Path, *, field_name: str) -> Path:
    path = _absolute_path(value, field_name=field_name)
    if not path.exists() or not path.is_file():
        raise ValueError(f"{field_name} must exist")
    return path


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


def _absolute_path(value: str | Path, *, field_name: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{field_name} must be an absolute path")
    return path


def _validated_high_port(value: object, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if not 20000 <= value <= 50000:
        raise ValueError(f"{field_name} must stay in the 20000-50000 range")
    return value


def _bool_env(value: bool) -> str:
    if not isinstance(value, bool):
        raise ValueError("model_download_approved must be a boolean")
    return "true" if value else "false"


def _non_empty_string(value: object, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")
    return value


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate macOS launchd service manifests for local LLM serving.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    generate = subparsers.add_parser(
        "generate",
        help="Write launchd plist files and a manifest under artifacts/runtime/.",
    )
    generate.add_argument("--repo-dir", type=Path, required=True)
    generate.add_argument("--artifact-dir", required=True)
    generate.add_argument("--model-id", required=True)
    generate.add_argument("--backend-port", type=int, default=28100)
    generate.add_argument("--backend-host", default="127.0.0.1")
    generate.add_argument(
        "--model-download-approved",
        action="store_true",
        help="Set MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED=true in the backend plist.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.subcommand == "generate":
        write_macos_launchd_service_bundle(
            repo_dir=args.repo_dir,
            artifact_dir=args.artifact_dir,
            model_id=args.model_id,
            backend_port=args.backend_port,
            backend_host=args.backend_host,
            model_download_approved=args.model_download_approved,
        )
        return 0
    parser.error(f"unsupported subcommand: {args.subcommand}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
