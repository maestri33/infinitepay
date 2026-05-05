import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.router import router as api_router
from app.config import get_settings
from app.db import init_db
from app.exceptions import DomainError
from app.utils.logging import configure_logging
from app.workers import outbound_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    stop = asyncio.Event()
    worker_task = None
    if get_settings().run_inline_worker:
        worker_task = asyncio.create_task(outbound_queue.run_worker_loop(stop))
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
    configure_logging()

    tags_metadata = [
        {
            "name": "health",
            "description": "Health check e readiness probe.",
        },
        {
            "name": "checkout",
            "description": "Criacao, listagem e consulta de links de pagamento InfinitePay.",
        },
        {
            "name": "config",
            "description": "Configuracao global: handle, precos padrao, URLs de webhook.",
        },
        {
            "name": "webhook",
            "description": "Recebimento de webhooks server-to-server da InfinitePay.",
        },
        {
            "name": "ai",
            "description": (
                "Perguntas em linguagem natural sobre checkouts e relatorios (DeepSeek AI)."
            ),
        },
    ]

    app = FastAPI(
        title="infinitepay API",
        version="1.0.0",
        description="Checkout integration with InfinitePay.",
        contact={
            "name": "InfinitePay Team",
        },
        license_info={
            "name": "MIT",
        },
        openapi_tags=tags_metadata,
        summary="Integracao com InfinitePay — criacao de checkouts, webhooks e analise AI.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def _domain_err(_req, exc: DomainError):
        return JSONResponse(status_code=exc.code, content={"detail": str(exc), **exc.extra})

    app.include_router(health_router, tags=["health"])
    app.include_router(api_router)
    return app


app = create_app()
