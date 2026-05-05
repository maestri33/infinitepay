import asyncio

from fastapi import APIRouter, Query, Request

from app.schemas.checkout import CheckoutResponse
from app.schemas.error import ErrorResponse
from app.schemas.webhook import WebhookResponse
from app.services import checkout_service
from app.utils.crypto import decrypt_external_id

router = APIRouter()


@router.post(
    "/",
    response_model=WebhookResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Payload invalido"},
        404: {"model": ErrorResponse, "description": "Checkout desconhecido"},
        422: {"model": ErrorResponse, "description": "order_nsu diverge ou campos faltando"},
        502: {"model": ErrorResponse, "description": "Falha na validacao via InfinitePay"},
    },
)
async def infinitepay_webhook(request: Request, external_id: str = Query(...)):
    """Server-to-server webhook da InfinitePay — atualiza status do checkout."""
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


@router.get(
    "/",
    response_model=CheckoutResponse,
)
async def checkout_status(order_nsu: str = Query(...)):
    """Consulta status de um checkout (nao altera nada)."""
    return checkout_service.get_checkout(order_nsu)
