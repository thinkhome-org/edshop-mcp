FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable --no-cache

FROM python:3.12-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY --from=builder /app/.venv /app/.venv
RUN useradd --uid 10001 --create-home app
USER 10001
EXPOSE 8000
ENTRYPOINT ["edshop-mcp"]
CMD ["--transport", "http", "--host", "0.0.0.0"]
