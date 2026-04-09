"""Dashboard service — FastAPI application factory.

Full implementation in Stories 3.1–3.4. This stub provides:
- FastAPI app instance (required for uvicorn CMD)
- /health endpoint (used by Docker health check)
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI(title="Nuanu Parking Dashboard", version="0.1.0")


@app.get("/health")
async def health() -> JSONResponse:
    """Docker health check endpoint."""
    return JSONResponse({"status": "ok"})


# TODO Story 3.1: Add authentication (auth.py, routes/auth.py)
# TODO Story 3.2: Add dashboard route, MQTT subscriber, SSE endpoint
# TODO Story 3.3: Add system health indicator, DEGRADED zone handling
# TODO Story 3.4: Nginx config, end-to-end integration
