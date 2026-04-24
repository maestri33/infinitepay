from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from infinitepay.core import queue
from infinitepay.core.checkout import CheckoutError
from infinitepay.core.config import is_ready
from infinitepay.core.validators import ValidationError
from infinitepay.db.session import init_db
from infinitepay.settings import settings

from infinitepay.api.routes import config as config_routes
from infinitepay.api.routes import checkout as checkout_routes
from infinitepay.api.routes import webhook as webhook_routes

# Paths that work even if public_api_url is not yet validated.
UNLOCKED_PATHS = {
    "/health",
    "/config/",
    "/config",
    "/config/test/",
    "/config/test",
    "/docs",
    "/openapi.json",
    "/redoc",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop = asyncio.Event()
    worker_task = None
    if settings.run_inline_worker:
        worker_task = asyncio.create_task(queue.run_worker_loop(stop))
    try:
        yield
    finally:
        stop.set()
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except (asyncio.CancelledError, Exception):
                pass


def create_app() -> FastAPI:
    app = FastAPI(title="InfinitePay Integration", lifespan=lifespan)

    @app.middleware("http")
    async def bootstrap_lock(request: Request, call_next):
        path = request.url.path
        if path in UNLOCKED_PATHS or path.startswith("/config/"):
            return await call_next(request)
        if not is_ready():
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "App bloqueado: configure public_api_url via PATCH /config/ e valide-o antes.",
                },
            )
        return await call_next(request)

    @app.exception_handler(CheckoutError)
    async def _checkout_err(_req, exc: CheckoutError):
        return JSONResponse(status_code=exc.code, content={"detail": str(exc), **exc.extra})

    @app.exception_handler(ValidationError)
    async def _validation_err(_req, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        return {"ok": True, "ready": is_ready()}

    app.include_router(config_routes.router, prefix="/config", tags=["config"])
    app.include_router(checkout_routes.router, prefix="/checkout", tags=["checkout"])
    app.include_router(webhook_routes.router, prefix="/webhook", tags=["webhook"])
    return app


app = create_app()
