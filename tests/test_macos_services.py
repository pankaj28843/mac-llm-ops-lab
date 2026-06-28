import json
import plistlib
from pathlib import Path

import pytest

from mac_llm_ops_lab.macos_services import (
    MACOS_LAUNCHD_SERVICE_BUNDLE_SCHEMA_VERSION,
    build_macos_launchd_service_bundle,
    main,
    write_macos_launchd_service_bundle,
)


def _repo_dir(tmp_path: Path) -> Path:
    repo_dir = tmp_path / "repo"
    scripts_dir = repo_dir / "scripts"
    scripts_dir.mkdir(parents=True)
    for name in ("run-vllm-mlx-backend.sh", "run-model-backed-api.sh"):
        path = scripts_dir / name
        path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        path.chmod(0o755)
    return repo_dir


def test_launchd_service_bundle_labels_backend_api_logs_and_high_ports(
    tmp_path: Path,
) -> None:
    repo_dir = _repo_dir(tmp_path)
    bundle = build_macos_launchd_service_bundle(
        repo_dir=repo_dir,
        artifact_dir="artifacts/runtime/test-launchd",
        model_id="mlx-community/Qwen3-0.6B-8bit",
        backend_port=28100,
        api_port=28020,
        phoenix_port=26006,
        model_download_approved=False,
    )

    assert bundle["schema_version"] == MACOS_LAUNCHD_SERVICE_BUNDLE_SCHEMA_VERSION
    assert bundle["artifact_dir"] == "artifacts/runtime/test-launchd"
    assert bundle["install_boundary"] == "generate_only_do_not_install"
    assert bundle["ports"] == {"api": 28020, "backend": 28100, "phoenix": 26006}
    assert bundle["plist_files"] == {
        "api": "artifacts/runtime/test-launchd/dev.mac_llm_ops.api.plist",
        "backend": "artifacts/runtime/test-launchd/dev.mac_llm_ops.vllm-mlx.plist",
    }

    backend = bundle["services"]["backend"]
    assert backend["Label"] == "dev.mac_llm_ops.vllm-mlx"
    assert backend["ProgramArguments"] == [
        str(repo_dir / "scripts/run-vllm-mlx-backend.sh")
    ]
    assert backend["WorkingDirectory"] == str(repo_dir)
    assert backend["RunAtLoad"] is False
    assert backend["KeepAlive"] is False
    assert backend["EnvironmentVariables"]["MODEL_ID"] == (
        "mlx-community/Qwen3-0.6B-8bit"
    )
    assert backend["EnvironmentVariables"]["VLLM_MLX_PORT"] == "28100"
    assert backend["EnvironmentVariables"]["MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED"] == "false"
    assert backend["StandardOutPath"].endswith("/backend.out.log")
    assert backend["StandardErrorPath"].endswith("/backend.err.log")

    api = bundle["services"]["api"]
    assert api["Label"] == "dev.mac_llm_ops.api"
    assert api["ProgramArguments"] == [
        str(repo_dir / "scripts/run-model-backed-api.sh")
    ]
    assert api["EnvironmentVariables"]["API_PORT"] == "28020"
    assert api["EnvironmentVariables"]["MAC_LLM_OPS_OPENAI_BASE_URL"] == (
        "http://127.0.0.1:28100/v1"
    )
    assert api["EnvironmentVariables"]["MAC_LLM_OPS_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"] == (
        "http://127.0.0.1:26006/v1/traces"
    )

    assert json.loads(json.dumps(bundle, sort_keys=True)) == bundle
    for plist in bundle["services"].values():
        assert plistlib.loads(plistlib.dumps(plist)) == plist


@pytest.mark.parametrize(
    ("kwargs", "match"),
    (
        ({"backend_port": 8100}, "20000-50000"),
        ({"api_port": 8020}, "20000-50000"),
        ({"phoenix_port": 6006}, "20000-50000"),
        ({"artifact_dir": "../launchd"}, "relative path"),
        ({"artifact_dir": "tmp/launchd"}, "artifacts/runtime"),
    ),
)
def test_launchd_service_bundle_rejects_unsafe_inputs(
    tmp_path: Path,
    kwargs: dict[str, object],
    match: str,
) -> None:
    repo_dir = _repo_dir(tmp_path)
    values: dict[str, object] = {
        "repo_dir": repo_dir,
        "artifact_dir": "artifacts/runtime/test-launchd",
        "model_id": "mlx-community/Qwen3-0.6B-8bit",
        "backend_port": 28100,
        "api_port": 28020,
        "phoenix_port": 26006,
        "model_download_approved": False,
    }
    values.update(kwargs)

    with pytest.raises(ValueError, match=match):
        build_macos_launchd_service_bundle(**values)


def test_launchd_service_bundle_writer_persists_plists_and_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    repo_dir = _repo_dir(tmp_path)

    manifest = write_macos_launchd_service_bundle(
        repo_dir=repo_dir,
        artifact_dir="artifacts/runtime/test-launchd",
        model_id="mlx-community/Qwen3-0.6B-8bit",
        backend_port=28100,
        api_port=28020,
        phoenix_port=26006,
        model_download_approved=True,
    )

    manifest_path = tmp_path / "artifacts/runtime/test-launchd/launchd-manifest.json"
    backend_plist = tmp_path / "artifacts/runtime/test-launchd/dev.mac_llm_ops.vllm-mlx.plist"
    api_plist = tmp_path / "artifacts/runtime/test-launchd/dev.mac_llm_ops.api.plist"
    assert manifest_path.exists()
    assert backend_plist.exists()
    assert api_plist.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert plistlib.loads(backend_plist.read_bytes())["Label"] == "dev.mac_llm_ops.vllm-mlx"
    assert plistlib.loads(api_plist.read_bytes())["Label"] == "dev.mac_llm_ops.api"
    assert (
        manifest["services"]["backend"]["EnvironmentVariables"][
            "MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED"
        ]
        == "true"
    )


def test_launchd_service_bundle_cli_writes_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    repo_dir = _repo_dir(tmp_path)

    exit_code = main(
        [
            "generate",
            "--repo-dir",
            str(repo_dir),
            "--artifact-dir",
            "artifacts/runtime/test-launchd",
            "--model-id",
            "mlx-community/Qwen3-0.6B-8bit",
            "--backend-port",
            "28100",
            "--api-port",
            "28020",
            "--phoenix-port",
            "26006",
            "--model-download-approved",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "artifacts/runtime/test-launchd/launchd-manifest.json").exists()


def test_mac_studio_cluster_docs_describe_launchd_generation() -> None:
    text = Path("docs/mac-studio-cluster.md").read_text(encoding="utf-8")

    for required in (
        "macos-launchd-service-bundle/v1",
        "python -m mac_llm_ops_lab.macos_services generate",
        "launchd-manifest.json",
        "plutil -lint",
        "generate only",
        "does not install or load",
    ):
        assert required in text
