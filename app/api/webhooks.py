import asyncio

from fastapi import APIRouter, Query, Request

from app.services import checkout_service
from app.utils.crypto import decrypt_external_id

router = APIRouter()


@router.post("/")
async def infinitepay_webhook(external_id: str = Query(...), request: Request):
    external_id = decrypt_external_id(external_id)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, checkout_service.handle_infinitepay_webhook, external_id, payload
    )
