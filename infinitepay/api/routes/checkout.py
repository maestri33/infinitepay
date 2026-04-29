from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from infinitepay.core import checkout as checkout_core

router = APIRouter()


# Snapshot dos defaults de /config/ no momento desta versao do source.
# Sao apenas para popular descricoes/exemplos do OpenAPI; o runtime
# sempre le os valores frescos via core.checkout.get_config_dict().
# Atualize ao mudar o /config/ se quiser refletir o atual aqui.
_CFG_SNAPSHOT_HANDLE = "v7m"
_CFG_SNAPSHOT_PRICE = 100
_CFG_SNAPSHOT_DESCRIPTION = "Rosa Azul"
_CFG_SNAPSHOT_QUANTITY = 1
_CFG_SNAPSHOT_REDIRECT_URL = "http://10.10.10.120/test/redirect"
_CFG_SNAPSHOT_BACKEND_WEBHOOK = "http://10.10.10.120/test/backend-webhook"


class CustomerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, description="Nome completo (>= 2 chars).")
    email: str | None = Field(None, description="Email; normalizado server-side.")
    phone_number: str | None = Field(None, description="Telefone E.164 ou BR sem +55.")


class AddressIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cep: str | None = Field(None, description="CEP (8 digitos, com ou sem hifen).")
    street: str | None = None
    neighborhood: str | None = None
    number: str | int | None = None
    complement: str | None = None


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price: int = Field(..., description="Centavos, > 0.")
    # Field nomeado 'description': uso title= (vira label no Swagger) em vez
    # de description= para evitar a chave 'description' aninhada duas vezes.
    description: str = Field(..., title="Descricao do item")
    quantity: int = Field(1, description="Default 1 quando omitido.")


class CheckoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_id: str | None = Field(
        None,
        description=(
            "ID unico do checkout. Regex [A-Za-z0-9_\\-.]{1,128}. "
            "OBRIGATORIO no body (nao tem fallback em /config/)."
        ),
    )
    handle: str | None = Field(
        None,
        description=(
            f"Handle InfinitePay. Se omitido, usa o valor salvo em "
            f"GET /config/ (atual: {_CFG_SNAPSHOT_HANDLE!r})."
        ),
    )
    price: int | None = Field(
        None,
        description=(
            f"Centavos, > 0. Se omitido, usa o valor salvo em "
            f"GET /config/ (atual: {_CFG_SNAPSHOT_PRICE}). "
            f"Ignorado quando 'items' for enviado."
        ),
    )
    # Field nomeado 'description' do checkout: uso title= em vez de description=
    # para evitar duplicacao visual da chave no OpenAPI.
    description: str | None = Field(
        None,
        title=(
            f"Descricao do checkout (se omitido, usa GET /config/, "
            f"atual: {_CFG_SNAPSHOT_DESCRIPTION!r}). Ignorado se 'items' enviado."
        ),
    )
    quantity: int | None = Field(
        None,
        description=(
            f"Quantidade. Se omitida, usa /config/ (atual: {_CFG_SNAPSHOT_QUANTITY}) "
            f"ou 1 se /config/ tambem estiver vazio. Ignorada quando 'items' enviado."
        ),
    )
    redirect_url: str | None = Field(
        None,
        description=(
            f"URL de redirect pos-pagamento. Se omitida, usa GET /config/ "
            f"(atual: {_CFG_SNAPSHOT_REDIRECT_URL!r})."
        ),
    )
    backend_webhook: str | None = Field(
        None,
        description=(
            f"Webhook do backend para confirmacao de pagamento. Se omitido, usa "
            f"GET /config/ (atual: {_CFG_SNAPSHOT_BACKEND_WEBHOOK!r})."
        ),
    )
    customer: CustomerIn | None = Field(
        None,
        description="Dados do cliente. Sem fallback em /config/.",
    )
    address: AddressIn | None = Field(
        None,
        description="Endereco do cliente. Opcional, sem fallback em /config/.",
    )
    items: list[ItemIn] | None = Field(
        None,
        description=(
            "Lista nao-vazia de itens. Quando presente, sobrescreve "
            "price/description/quantity (do body e do /config/). "
            "Sem fallback em /config/."
        ),
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


_ERR_400 = {"model": ErrorOut, "description": "Body invalido ou campos obrigatorios faltando."}
_ERR_404 = {"model": ErrorOut, "description": "Checkout nao encontrado."}
_ERR_409 = {"model": ErrorOut, "description": "external_id duplicado ou app bloqueado (public_api_url nao validado)."}
_ERR_502 = {"model": ErrorOut, "description": "InfinitePay retornou erro ao criar o link."}
_ERR_503 = {"model": ErrorOut, "description": "App bloqueado pelo middleware bootstrap_lock."}


_POST_DESCRIPTION = """\
Cria link real na InfinitePay.

**Fallbacks de /config/** (consulte `GET /config/` para ver os valores atuais):

| Campo do body         | Tem fallback em /config/? |
|-----------------------|---------------------------|
| `external_id`         | Nao (sempre obrigatorio)  |
| `handle`              | Sim                       |
| `price`               | Sim                       |
| `description`         | Sim                       |
| `quantity`            | Sim (ou 1)                |
| `redirect_url`        | Sim                       |
| `backend_webhook`     | Sim                       |
| `customer`            | Nao                       |
| `address`             | Nao (e opcional)          |
| `items`               | Nao (sobrescreve price/description/quantity quando enviado) |

`public_api_url` e proibido no body (e propriedade do servico, mude por `PATCH /config/`).
"""


@router.post(
    "/",
    summary="Criar checkout",
    description=_POST_DESCRIPTION,
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
