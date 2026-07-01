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
    path = scripts_dir / "run-vllm-mlx-backend.sh"
    path.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    path.chmod(0o755)
    return repo_dir


def test_launchd_service_bundle_labels_only_backend_logs_and_high_ports(
    tmp_path: Path,
) -> None:
    repo_dir = _repo_dir(tmp_path)
    bundle = build_macos_launchd_service_bundle(
        repo_dir=repo_dir,
        artifact_dir="artifacts/runtime/test-launchd",
        model_id="mlx-community/Qwen3-0.6B-8bit",
        backend_port=28100,
        model_download_approved=False,
    )

    assert bundle["schema_version"] == MACOS_LAUNCHD_SERVICE_BUNDLE_SCHEMA_VERSION
    assert bundle["artifact_dir"] == "artifacts/runtime/test-launchd"
    assert bundle["install_boundary"] == "generate_only_do_not_install"
    assert bundle["ports"] == {"backend": 28100}
    assert bundle["plist_files"] == {
        "backend": "artifacts/runtime/test-launchd/dev.mac_llm_ops.vllm-mlx.plist",
    }
    assert set(bundle["services"]) == {"backend"}

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
    assert (
        backend["EnvironmentVariables"]["MAC_LLM_OPS_MODEL_DOWNLOAD_APPROVED"]
        == "false"
    )
    assert backend["StandardOutPath"].endswith("/backend.out.log")
    assert backend["StandardErrorPath"].endswith("/backend.err.log")

    assert json.loads(json.dumps(bundle, sort_keys=True)) == bundle
    for plist in bundle["services"].values():
        assert plistlib.loads(plistlib.dumps(plist)) == plist


@pytest.mark.parametrize(
    ("kwargs", "match"),
    (
        ({"backend_port": 8100}, "20000-50000"),
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
        model_download_approved=True,
    )

    manifest_path = tmp_path / "artifacts/runtime/test-launchd/launchd-manifest.json"
    backend_plist = (
        tmp_path / "artifacts/runtime/test-launchd/dev.mac_llm_ops.vllm-mlx.plist"
    )
    assert manifest_path.exists()
    assert backend_plist.exists()
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest
    assert (
        plistlib.loads(backend_plist.read_bytes())["Label"]
        == "dev.mac_llm_ops.vllm-mlx"
    )
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
            "--model-download-approved",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "artifacts/runtime/test-launchd/launchd-manifest.json").exists()


def test_mac_studio_cluster_docs_keep_launchd_generation_internal() -> None:
    text = Path("docs/mac-studio-cluster.md").read_text(encoding="utf-8")

    for internal in (
        "macos-launchd-service-bundle/v1",
        "python -m mac_llm_ops_lab.macos_services generate",
        "launchd-manifest.json",
        "plutil -lint",
    ):
        assert internal not in text

    for required in (
        "private Mac Studio LAN",
        "native `vllm-mlx` backend",
        "OpenAI-compatible API surface",
    ):
        assert required in text
