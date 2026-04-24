from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from infinitepay.core import checkout as checkout_core

router = APIRouter()


@router.post("/")
async def create(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        from infinitepay.core.checkout import CheckoutError
        raise CheckoutError("body deve ser objeto JSON", code=400)
    return checkout_core.create_checkout(body)


@router.get("/")
def list_all():
    return {"items": checkout_core.list_checkouts()}


@router.get("/{external_id}/")
def get_one(external_id: str):
    return checkout_core.get_checkout(external_id)
