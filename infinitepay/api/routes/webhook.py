from __future__ import annotations

from fastapi import APIRouter, Request

from infinitepay.core import checkout as checkout_core

router = APIRouter()


@router.post("/{external_id}/", summary="Receber webhook InfinitePay", description="Entrada pública chamada pela InfinitePay. Valida order_nsu contra external_id, chama payment_check e enfileira backend_webhook quando pago.")
async def infinitepay_webhook(external_id: str, request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}
    return checkout_core.handle_infinitepay_webhook(external_id, payload)
