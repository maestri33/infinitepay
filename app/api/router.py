from fastapi import APIRouter

from app.api.checkout import router as checkout_router
from app.api.config import router as config_router
from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router

router = APIRouter(prefix="/api/v1")
router.include_router(health_router, tags=["health"])
router.include_router(checkout_router, prefix="/checkout", tags=["checkout"])
router.include_router(config_router, prefix="/config", tags=["config"])
router.include_router(webhooks_router, prefix="/webhook", tags=["webhook"])
