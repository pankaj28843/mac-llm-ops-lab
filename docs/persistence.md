# Persistence

The persistence boundary stores model catalog records, Mac node inventory,
inference run metadata, benchmark summaries, and runtime artifact pointers.

The application uses plain domain dataclasses plus Repository and Unit of Work
ports. FastAPI request handlers do not import SQLAlchemy or Alembic adapters;
service code should receive a UoW and work through repositories.

## Modules

- `mac_llm_ops_lab.persistence.domain`: persistence domain records.
- `mac_llm_ops_lab.persistence.ports`: async repository and Unit of Work
  protocols.
- `mac_llm_ops_lab.persistence.fakes`: in-memory fake repositories and UoW
  for fast tests.
- `mac_llm_ops_lab.persistence.sqlalchemy`: SQLAlchemy async records,
  repositories, session factory, and UoW.
- `alembic/`: reviewed schema migrations.

## Local Migration

The Alembic environment imports application metadata from
`mac_llm_ops_lab.persistence.sqlalchemy.Base`. It uses a project-specific
version table named `mac_llm_ops_alembic_version` because the local Compose PostgreSQL
database may also contain service-owned migration metadata from Phoenix.

Run migrations against the local Compose PostgreSQL service with:

```bash
POSTGRES_PASSWORD_VALUE="$(tr -d '\n' < secrets/postgres_password.txt)"
DATABASE_URL="postgresql+asyncpg://llm_serving:${POSTGRES_PASSWORD_VALUE}@127.0.0.1:${POSTGRES_HOST_PORT:-5432}/llm_serving" \
  uv run alembic upgrade head
```

Do not echo `DATABASE_URL`; it contains the local database password. The
`secrets/` directory is ignored and must stay out of git.

## Runtime Proof

The first local PostgreSQL persistence proof is saved under:

```text
artifacts/runtime/2026-06-28T154545+0200-postgres-persistence/
```

It includes:

- Postgres container state and `pg_isready`.
- Alembic upgrade to revision `20260628_153500`.
- Confirmation that `mac_llm_ops_alembic_version` contains the project migration
  revision.
- Confirmation that `model_catalog`, `node_inventory`, `inference_runs`,
  `benchmark_results`, and `artifact_pointers` exist.
- A sample insert/read through `SQLAlchemyUnitOfWork`.

The proof is publish-safe because raw runtime files live under ignored
`artifacts/runtime/` and the local password is not written into evidence files.
