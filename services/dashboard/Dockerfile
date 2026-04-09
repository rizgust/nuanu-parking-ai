FROM python:3.12-slim

# Install UV and curl (for health check)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/dashboard/ ./services/dashboard/

RUN uv sync --package dashboard --no-dev

CMD ["uv", "run", "--package", "dashboard", "uvicorn", "dashboard.main:app", "--host", "0.0.0.0", "--port", "8000"]
