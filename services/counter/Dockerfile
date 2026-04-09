FROM python:3.12-slim

# Install UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy workspace root and required packages
COPY pyproject.toml .
COPY shared/ ./shared/
COPY services/counter/ ./services/counter/

# Install counter dependencies (no dev deps in production image)
RUN uv sync --package counter --no-dev

# Pre-download YOLOv8n model weights at build time
# This avoids runtime internet dependency
RUN uv run --package counter python -c "from ultralytics import YOLO; YOLO('yolov8n.pt')"

CMD ["uv", "run", "--package", "counter", "python", "-m", "counter.main"]
