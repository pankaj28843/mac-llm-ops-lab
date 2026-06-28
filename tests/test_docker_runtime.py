import tomllib
from pathlib import Path


def _dependency_name(dependency: str) -> str:
    name = dependency
    for delimiter in ("[", "<", ">", "=", "!", "~", ";", " "):
        name = name.split(delimiter, maxsplit=1)[0]
    return name.strip()


def test_docker_entrypoint_runtime_dependencies_are_declared() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    runtime_dependencies = pyproject["project"]["dependencies"]

    assert "uv sync --frozen --no-dev" in dockerfile
    assert "uvicorn" in dockerfile
    assert any(
        _dependency_name(dependency) == "uvicorn" for dependency in runtime_dependencies
    )
    assert any(
        _dependency_name(dependency) == "httpx" for dependency in runtime_dependencies
    )
