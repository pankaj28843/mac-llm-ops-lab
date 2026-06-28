from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_alembic_upgrade_and_downgrade_persistence_schema(tmp_path) -> None:
    database_path = tmp_path / "migration.db"
    config = _alembic_config(f"sqlite+aiosqlite:///{database_path}")

    command.upgrade(config, "head")

    sync_engine = create_engine(f"sqlite:///{database_path}")
    try:
        inspector = inspect(sync_engine)
        assert {
            "artifact_pointers",
            "benchmark_results",
            "inference_runs",
            "model_catalog",
            "node_inventory",
        } <= set(inspector.get_table_names())
    finally:
        sync_engine.dispose()

    command.downgrade(config, "base")

    sync_engine = create_engine(f"sqlite:///{database_path}")
    try:
        inspector = inspect(sync_engine)
        assert "model_catalog" not in set(inspector.get_table_names())
    finally:
        sync_engine.dispose()


def test_alembic_env_imports_application_metadata() -> None:
    env_source = Path("alembic/env.py").read_text(encoding="utf-8")

    assert "from mac_llm_ops_lab.persistence.sqlalchemy import Base" in env_source
    assert "target_metadata = Base.metadata" in env_source
    assert 'version_table="mac_llm_ops_alembic_version"' in env_source
    assert "include_name=include_name" in env_source


def _alembic_config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", database_url)
    return config
