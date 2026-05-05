from fastapi import APIRouter

from app.api.checkout import router as checkout_router
from app.api.config import router as config_router
from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router

router = APIRouter()
router.include_router(health_router)
router.include_router(checkout_router, prefix="/checkout")
router.include_router(config_router, prefix="/config")
router.include_router(webhooks_router, prefix="/webhook")
