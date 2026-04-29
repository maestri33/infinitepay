from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from infinitepay.core import checkout as checkout_core

router = APIRouter()


class CustomerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, description="Nome completo (>= 2 chars).")
    email: str | None = Field(None, description="Email; normalizado server-side.")
    phone_number: str | None = Field(None, description="Telefone E.164 ou BR sem +55.")


class AddressIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cep: str | None = Field(None, description="CEP (8 dígitos, com ou sem hífen).")
    street: str | None = None
    neighborhood: str | None = None
    number: str | int | None = None
    complement: str | None = None


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: int = Field(..., description="Centavos, > 0.")
    description: str
    quantity: int = Field(1, description="Default 1 quando omitido.")


class CheckoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str | None = Field(
        None,
        description="ID único do checkout. Regex [A-Za-z0-9_\\-.]{1,128}. Obrigatório (sem default global).",
    )
    handle: str | None = Field(None, description="Handle InfinitePay; usa /config/ se omitido.")
    price: int | None = Field(None, description="Centavos; usa /config/ se omitido.")
    description: str | None = Field(None, description="Descrição; usa /config/ se omitido.")
    quantity: int | None = Field(None, description="Default 1.")
    redirect_url: str | None = Field(None, description="URL de redirect; usa /config/ se omitido.")
    backend_webhook: str | None = Field(None, description="Webhook do backend; usa /config/ se omitido.")
    customer: CustomerIn | None = None
    address: AddressIn | None = None
    items: list[ItemIn] | None = Field(
        None, description="Lista não-vazia. Quando presente, sobrescreve price/description/quantity."
    )


class CheckoutCreatedOut(BaseModel):
    external_id: str
    checkout_url: str


class CheckoutDetailOut(BaseModel):
    external_id: str
    is_paid: bool
    checkout_url: str | None = None
    receipt_url: str | None = None


class CheckoutListItem(BaseModel):
    external_id: str
    is_paid: bool
    checkout_url: str | None = None
    receipt_url: str | None = None
    invoice_slug: str | None = None
    transaction_nsu: str | None = None
    capture_method: str | None = None
    installments: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CheckoutListOut(BaseModel):
    items: list[CheckoutListItem]


class ErrorOut(BaseModel):
    detail: str


_ERR_400 = {"model": ErrorOut, "description": "Body inválido ou campos obrigatórios faltando."}
_ERR_404 = {"model": ErrorOut, "description": "Checkout não encontrado."}
_ERR_409 = {"model": ErrorOut, "description": "external_id duplicado ou app bloqueado (public_api_url não validado)."}
_ERR_502 = {"model": ErrorOut, "description": "InfinitePay retornou erro ao criar o link."}
_ERR_503 = {"model": ErrorOut, "description": "App bloqueado pelo middleware bootstrap_lock."}


@router.post(
    "/",
    summary="Criar checkout",
    description="Cria link real na InfinitePay. Campos omitidos usam defaults de /config/; public_api_url é proibido no body.",
    response_model=CheckoutCreatedOut,
    operation_id="checkout_create",
    responses={400: _ERR_400, 409: _ERR_409, 502: _ERR_502, 503: _ERR_503},
)
def create(body: CheckoutCreate) -> dict[str, Any]:
    return checkout_core.create_checkout(body.model_dump(exclude_unset=True))


@router.get(
    "/",
    summary="Listar checkouts",
    description="Lista checkouts salvos no SQLite local, ordenados pelos mais recentes.",
    response_model=CheckoutListOut,
    operation_id="checkout_list",
)
def list_all() -> dict[str, Any]:
    return {"items": checkout_core.list_checkouts()}


@router.get(
    "/{external_id}/",
    summary="Consultar checkout",
    description="Retorna checkout_url quando pendente ou receipt_url quando pago.",
    response_model=CheckoutDetailOut,
    operation_id="checkout_get",
    responses={400: _ERR_400, 404: _ERR_404, 503: _ERR_503},
)
def get_one(external_id: str) -> dict[str, Any]:
    return checkout_core.get_checkout(external_id)
