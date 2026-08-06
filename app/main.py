"""FastAPI application entry-point with lifespan management, middleware, and operational probes."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import docker
import docker.errors
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.api.schemas import HealthResponse
from app.api.websocket import ws_router
from app.core.config import settings
from app.core.logging_config import setup_logging
from app.core.metrics import get_metrics_text
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.services.concurrency import limiter

# Configure structured logging on startup
setup_logging(debug=settings.debug, json_format=not settings.debug)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook.

    On startup, verifies Docker Engine connectivity and performs best-effort
    pre-pulling for all configured language images.
    """
    logger.info("Starting %s v%s", settings.app_title, settings.app_version)

    # ── Docker health-check ──────────────────────────────────────────────
    client = None
    try:
        client = docker.from_env()
        client.ping()
        logger.info("Docker Engine is reachable and responsive")
    except Exception as exc:
        logger.warning(
            "Docker Engine is NOT reachable at startup — sandbox executions will fail "
            "until the daemon becomes available. (%s)",
            exc,
        )

    # ── Pre-pull images (best-effort) ────────────────────────────────────
    if client is not None:
        images = [settings.image_python, settings.image_c, settings.image_javascript]
        for img in images:
            try:
                client.images.get(img)
                logger.info("Image %s already present locally", img)
            except docker.errors.ImageNotFound:
                logger.info("Image %s not found; attempting background pre-pull...", img)
                try:
                    client.images.pull(img)
                    logger.info("Successfully pre-pulled image: %s", img)
                except Exception as exc:
                    logger.warning("Failed to pre-pull %s: %s", img, exc)
            except Exception as exc:
                logger.warning("Error inspecting image %s: %s", img, exc)

    yield  # ── application serves traffic here ──

    logger.info("Shutting down %s", settings.app_title)


def create_app() -> FastAPI:
    """Application factory configuring routers, middleware, and operational endpoints."""
    app = FastAPI(
        title=settings.app_title,
        description=settings.app_description,
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Middleware chain (evaluated bottom to top) ────────────────────────
    # 1. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Rate Limiting (evaluated for /api/ routes)
    app.add_middleware(
        RateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
    )

    # 3. Request Correlation ID
    app.add_middleware(RequestIDMiddleware)

    # ── Routers ──────────────────────────────────────────────────────────
    app.include_router(router)
    app.include_router(ws_router)

    # ── Operational Probes ───────────────────────────────────────────────
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["meta"],
        summary="Service health and readiness probe",
    )
    async def health():
        """Readiness probe checking Docker connectivity, container limits, and images."""
        docker_connected = False
        images_status = {
            "python": False,
            "c": False,
            "javascript": False,
        }

        try:
            client = docker.from_env()
            client.ping()
            docker_connected = True

            img_map = {
                "python": settings.image_python,
                "c": settings.image_c,
                "javascript": settings.image_javascript,
            }
            for lang, img_tag in img_map.items():
                try:
                    client.images.get(img_tag)
                    images_status[lang] = True
                except Exception:
                    images_status[lang] = False
        except Exception:
            docker_connected = False

        status_str = "ok" if docker_connected else "degraded"

        return HealthResponse(
            status=status_str,
            version=settings.app_version,
            docker_connected=docker_connected,
            images_available=images_status,
            active_executions=limiter.active_count,
            max_concurrent=limiter.max_concurrent,
        )

    @app.get(
        "/metrics",
        tags=["meta"],
        summary="Prometheus operational metrics scrape endpoint",
        response_class=Response,
    )
    async def metrics():
        """Expose operational metrics in Prometheus text exposition format."""
        content = get_metrics_text()
        return Response(content=content, media_type="text/plain; version=0.0.4")

    return app


app = create_app()
