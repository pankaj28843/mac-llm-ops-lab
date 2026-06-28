from pathlib import Path


def test_persistence_docs_describe_migration_and_runtime_evidence() -> None:
    docs_path = Path("docs/persistence.md")

    assert docs_path.exists()
    text = docs_path.read_text(encoding="utf-8")

    for required in (
        "SQLAlchemy",
        "Alembic",
        "mac_llm_ops_alembic_version",
        "DATABASE_URL",
        "artifacts/runtime/2026-06-28T154545+0200-postgres-persistence/",
        "Repository",
        "Unit of Work",
        "PostgreSQL",
    ):
        assert required in text
