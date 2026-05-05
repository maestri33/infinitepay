from typing import Any

from fastapi import APIRouter

from app.schemas.checkout import CheckoutCreate
from app.services import checkout_service

router = APIRouter()


@router.post("/")
def create(body: CheckoutCreate) -> dict[str, Any]:
    return checkout_service.create_checkout(body.model_dump(exclude_unset=True))


@router.get("/")
def list_all() -> dict[str, Any]:
    return {"items": checkout_service.list_checkouts()}


@router.get("/{external_id}/")
def get_one(external_id: str) -> dict[str, Any]:
    return checkout_service.get_checkout(external_id)
