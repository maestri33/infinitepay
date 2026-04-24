from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from infinitepay.core import checkout as checkout_core

router = APIRouter()


@router.post("/", summary="Criar checkout", description="Cria link real na InfinitePay. Campos omitidos usam defaults de /config/; public_api_url é proibido no body.")
async def create(request: Request) -> dict[str, Any]:
    body = await request.json()
    if not isinstance(body, dict):
        from infinitepay.core.checkout import CheckoutError
        raise CheckoutError("body deve ser objeto JSON", code=400)
    return checkout_core.create_checkout(body)


@router.get("/", summary="Listar checkouts", description="Lista checkouts salvos no SQLite local, ordenados pelos mais recentes.")
def list_all():
    return {"items": checkout_core.list_checkouts()}


@router.get("/{external_id}/", summary="Consultar checkout", description="Retorna checkout_url quando pendente ou receipt_url quando pago.")
def get_one(external_id: str):
    return checkout_core.get_checkout(external_id)
