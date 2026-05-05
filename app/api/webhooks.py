import asyncio

from fastapi import APIRouter, Query, Request
from fastapi.responses import RedirectResponse

from app.services import checkout_service
from app.utils.crypto import decrypt_external_id

router = APIRouter()


@router.post("/")
async def infinitepay_webhook(request: Request, external_id: str = Query(...)):
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


@router.get("/")
async def infinitepay_redirect(
    order_nsu: str = Query(...),
    transaction_nsu: str = Query(...),
    slug: str = Query(...),
    receipt_url: str = Query(""),
    capture_method: str = Query(""),
    transaction_id: str = Query(""),
):
    payload = {
        "transaction_nsu": transaction_nsu,
        "invoice_slug": slug,
        "order_nsu": order_nsu,
        "receipt_url": receipt_url,
        "capture_method": capture_method,
        "transaction_id": transaction_id,
    }
    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(
        None, checkout_service.handle_infinitepay_webhook, order_nsu, payload
    )
    if result.get("paid"):
        return RedirectResponse(url=receipt_url or f"/checkout/{order_nsu}/")
    return RedirectResponse(url=f"/checkout/{order_nsu}/")
