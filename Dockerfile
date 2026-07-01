FROM python:3.14-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

FROM base AS api

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["uvicorn", "mac_llm_ops_lab.cli:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS docs

COPY mkdocs.yml ./
COPY docs ./docs

RUN uv sync --frozen --group dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["mkdocs", "serve", "--no-livereload", "-a", "0.0.0.0:8000"]
