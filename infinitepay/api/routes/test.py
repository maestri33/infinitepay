from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from infinitepay.core.logs import log_event
from infinitepay.db.session import session_scope

router = APIRouter()


@router.get("/redirect/", summary="Redirect de teste", description="Endpoint interno para usar como redirect_url temporário em smoke tests.")
def redirect_probe() -> dict[str, Any]:
    return {"ok": True, "kind": "test_redirect"}


@router.post("/backend-webhook/{external_id}/", summary="Backend webhook de teste", description="Endpoint interno que grava o payload recebido em webhook_logs com kind=test_backend_webhook.")
async def backend_webhook_probe(external_id: str, request: Request) -> dict[str, Any]:
    payload = await request.json()
    with session_scope() as sess:
        log_event(
            sess,
            direction="inbound",
            kind="test_backend_webhook",
            payload=payload if isinstance(payload, dict) else {"payload": payload},
            external_id=external_id,
        )
    return {"ok": True, "external_id": external_id}
