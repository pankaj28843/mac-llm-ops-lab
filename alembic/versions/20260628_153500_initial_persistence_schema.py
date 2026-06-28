"""initial persistence schema

Revision ID: 20260628_153500
Revises:
Create Date: 2026-06-28 15:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260628_153500"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_catalog",
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("backend", sa.String(length=100), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("license", sa.String(length=100), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "context_window IS NULL OR context_window > 0",
            name="ck_model_catalog_context_window_positive",
        ),
        sa.PrimaryKeyConstraint("model_id", name="pk_model_catalog"),
    )
    op.create_table(
        "node_inventory",
        sa.Column("node_id", sa.String(length=255), nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("chip", sa.String(length=255), nullable=False),
        sa.Column("memory_gib", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "memory_gib > 0",
            name="ck_node_inventory_memory_positive",
        ),
        sa.PrimaryKeyConstraint("node_id", name="pk_node_inventory"),
    )
    op.create_table(
        "inference_runs",
        sa.Column("run_id", sa.String(length=255), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("node_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "prompt_tokens >= 0",
            name="ck_inference_runs_prompt_tokens",
        ),
        sa.CheckConstraint(
            "completion_tokens >= 0",
            name="ck_inference_runs_completion_tokens",
        ),
        sa.ForeignKeyConstraint(
            ["model_id"],
            ["model_catalog.model_id"],
            name="fk_inference_runs_model_id",
        ),
        sa.ForeignKeyConstraint(
            ["node_id"],
            ["node_inventory.node_id"],
            name="fk_inference_runs_node_id",
        ),
        sa.PrimaryKeyConstraint("run_id", name="pk_inference_runs"),
    )
    op.create_table(
        "artifact_pointers",
        sa.Column("artifact_id", sa.String(length=255), nullable=False),
        sa.Column("run_id", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=100), nullable=False),
        sa.Column("uri", sa.String(length=2048), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["inference_runs.run_id"],
            name="fk_artifact_pointers_run_id",
        ),
        sa.PrimaryKeyConstraint("artifact_id", name="pk_artifact_pointers"),
    )
    op.create_table(
        "benchmark_results",
        sa.Column("result_id", sa.String(length=255), nullable=False),
        sa.Column("run_id", sa.String(length=255), nullable=False),
        sa.Column("workload_name", sa.String(length=255), nullable=False),
        sa.Column("requests_per_second", sa.Float(), nullable=False),
        sa.Column("p95_latency_ms", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "requests_per_second >= 0",
            name="ck_benchmark_results_rps_non_negative",
        ),
        sa.CheckConstraint(
            "p95_latency_ms >= 0",
            name="ck_benchmark_results_p95_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["inference_runs.run_id"],
            name="fk_benchmark_results_run_id",
        ),
        sa.PrimaryKeyConstraint("result_id", name="pk_benchmark_results"),
    )


def downgrade() -> None:
    op.drop_table("benchmark_results")
    op.drop_table("artifact_pointers")
    op.drop_table("inference_runs")
    op.drop_table("node_inventory")
    op.drop_table("model_catalog")
