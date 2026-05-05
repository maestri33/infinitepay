from fastapi import APIRouter

from app.schemas.checkout import CheckoutCreate, CheckoutListResponse, CheckoutResponse
from app.schemas.error import ErrorResponse
from app.services import checkout_service

router = APIRouter()


@router.post(
    "/",
    response_model=CheckoutResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Campos obrigatorios ausentes"},
        409: {"model": ErrorResponse, "description": "external_id ja existe"},
        422: {"model": ErrorResponse, "description": "Validacao de campos"},
        502: {"model": ErrorResponse, "description": "Falha na InfinitePay"},
    },
)
def create(body: CheckoutCreate) -> CheckoutResponse:
    """Cria um link de pagamento InfinitePay.

    Campos como handle, price, description e redirect_url usam os defaults
    de /config/ quando nao informados no body.
    """
    return checkout_service.create_checkout(body.model_dump(exclude_unset=True))


@router.get(
    "/",
    response_model=CheckoutListResponse,
)
def list_all() -> CheckoutListResponse:
    """Lista todos os checkouts, do mais recente ao mais antigo."""
    return {"items": checkout_service.list_checkouts()}


@router.get(
    "/{external_id}/",
    response_model=CheckoutResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Checkout nao encontrado"},
    },
)
def get_one(external_id: str) -> CheckoutResponse:
    """Consulta um checkout pelo external_id.

    Se pago, retorna receipt_url. Senao, retorna checkout_url para pagamento.
    """
    return checkout_service.get_checkout(external_id)
