from __future__ import annotations

from fastapi import APIRouter, Request

from infinitepay.core import checkout as checkout_core

router = APIRouter()


@router.post("/{external_id}/")
async def infinitepay_webhook(external_id: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    return checkout_core.handle_infinitepay_webhook(external_id, payload)
