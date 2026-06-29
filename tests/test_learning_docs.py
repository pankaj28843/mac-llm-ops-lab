import re
from pathlib import Path

import yaml

DOCS_DIR = Path("docs")


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _mkdocs_nav_pages() -> list[str]:
    config = yaml.safe_load(Path("mkdocs.yml").read_text(encoding="utf-8"))
    pages = []
    for item in config["nav"]:
        assert isinstance(item, dict)
        pages.extend(item.values())
    return pages


def test_root_docs_are_short_routers_to_served_docs() -> None:
    required_root_docs = {
        "AGENTS.md": (
            "docs/development.md",
            "docs/operations.md",
            "docs/vision.md",
            "docs/requirements.md",
            "docs/design.md",
        ),
        "vision.md": ("docs/vision.md",),
        "requirements.md": ("docs/requirements.md",),
        "design.md": ("docs/design.md",),
    }

    for path, required_links in required_root_docs.items():
        text = _read(path)
        assert len(text.splitlines()) <= 80
        for required_link in required_links:
            assert required_link in text

    agents_text = _read("AGENTS.md")
    assert "/" + "Users/" not in agents_text
    assert "model-cache/" in agents_text
    assert "artifacts/runtime/" in agents_text
    assert "20000-50000" in agents_text


def test_mkdocs_config_serves_lean_learning_docs_nav() -> None:
    config = yaml.safe_load(Path("mkdocs.yml").read_text(encoding="utf-8"))
    pages = _mkdocs_nav_pages()

    assert config["site_name"] == "Mac LLM Ops Lab"
    assert config["docs_dir"] == "docs"
    assert config["repo_url"] == "https://github.com/pankaj28843/mac-llm-ops-lab"
    assert config["theme"]["name"] == "mkdocs"
    assert pages == [
        "index.md",
        "vision.md",
        "requirements.md",
        "design.md",
        "development.md",
        "operations.md",
        "evidence.md",
        "mac-studio-cluster.md",
        "release-readiness.md",
    ]
    assert len(pages) <= 9
    for page in pages:
        assert (DOCS_DIR / page).exists()


def test_learning_docs_cover_clone_and_run_path_without_private_paths() -> None:
    docs = {
        path.name: path.read_text(encoding="utf-8")
        for path in Path("docs").glob("*.md")
    }

    for required_page in (
        "index.md",
        "vision.md",
        "requirements.md",
        "design.md",
        "development.md",
        "operations.md",
        "evidence.md",
        "mac-studio-cluster.md",
        "release-readiness.md",
    ):
        assert required_page in docs

    combined = "\n".join(docs.values())
    combined_flat = " ".join(combined.split())
    for required in (
        "uv sync",
        "uv run pytest",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "docker compose -f compose.yaml config --format json",
        "uv run mkdocs build --strict",
        "http://localhost:28000",
        "http://localhost:23000",
        "http://localhost:26006",
        "PostgreSQL",
        "Phoenix",
        "OpenTelemetry",
        "Open WebUI",
        "vllm-mlx",
        "mlx-community/Qwen3-0.6B-8bit",
        "Mac Studio",
        "Do not extrapolate",
        "Repository",
        "Unit of Work",
        "mermaid",
        "independent Mac-first learning lab",
        "reference-only background",
        "External references",
    ):
        assert required in combined_flat

    public_learning_docs = "\n".join(
        text for name, text in docs.items() if name != "release-readiness.md"
    )
    forbidden_fragments = (
        "/" + "Users/",
        "Calibre" + " Library",
        "." + "bo" + "oks/",
        "secrets/postgres_password.txt contains",
        "HF_TOKEN",
        "OPENAI_API_KEY=",
    )
    for forbidden in forbidden_fragments:
        assert forbidden not in public_learning_docs

    for stale_branding in (
        "Hands-" + "On LLM Serving",
        "hands-" + "on-llm-serving",
        "hands_" + "on_llm_serving",
        "Mac LLM Ops Lab" + " and Optimization",
        "https://github.com/pankaj28843/" + "mac-llm-ops-lab",
    ):
        assert stale_branding not in public_learning_docs


def test_markdown_local_links_resolve() -> None:
    markdown_files = [
        Path("README.md"),
        Path("AGENTS.md"),
        Path("vision.md"),
        Path("requirements.md"),
        Path("design.md"),
        *sorted(DOCS_DIR.rglob("*.md")),
    ]
    link_pattern = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")

    for path in markdown_files:
        text = path.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(text):
            target = raw_target.split()[0].split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (path.parent / target).resolve()
            assert resolved.exists(), f"{path} links to missing {raw_target}"


def test_readme_points_to_current_native_openwebui_answer_proof() -> None:
    readme = _read("README.md")

    for required in (
        "VLLM_MLX_MAX_TOKENS=512",
        "VLLM_MLX_MAX_REQUEST_TOKENS=1024",
        "VLLM_MLX_REASONING_PARSER=qwen3",
        "VLLM_MLX_DEFAULT_CHAT_TEMPLATE_KWARGS='{\"enable_thinking\": false}'",
        "artifacts/runtime/2026-06-28T195945+0200-open-webui-visible-answer-no-think/",
        "visible assistant answer",
    ):
        assert required in readme

    assert "limited visible answer text" not in readme


def test_readme_points_to_published_docs_and_current_docs_map() -> None:
    readme = _read("README.md")

    for required in (
        "https://pankaj28843.github.io/mac-llm-ops-lab/",
        ".github/workflows/pages.yml",
        "Publish Docs",
        "uv run mkdocs build --strict",
        "make validate",
        "docs/development.md",
        "docs/operations.md",
        "docs/design.md",
        "docs/evidence.md",
        "docs/mac-studio-cluster.md",
        "docs/release-readiness.md",
        "real multi-node proof",
    ):
        assert required in readme


def test_mkdocs_is_declared_as_dev_dependency() -> None:
    pyproject = _read("pyproject.toml")

    assert '"mkdocs>=' in pyproject
