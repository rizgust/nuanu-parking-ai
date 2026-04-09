FROM python:3.12-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/watchdog/ ./services/watchdog/

RUN uv sync --package watchdog --no-dev

CMD ["uv", "run", "--package", "watchdog", "python", "-m", "watchdog.main"]
