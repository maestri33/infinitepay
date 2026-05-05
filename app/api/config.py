from fastapi import APIRouter

from app.schemas.config import ConfigResponse, ConfigUpdate
from app.schemas.error import ErrorResponse
from app.services import config_service

router = APIRouter()


def _serialize(d: dict) -> dict:
    out = dict(d)
    for k in ("created_at", "updated_at"):
        if out.get(k) is not None and hasattr(out[k], "isoformat"):
            out[k] = out[k].isoformat()
    return out


@router.get(
    "/",
    response_model=ConfigResponse,
)
def get_config() -> ConfigResponse:
    """Retorna a configuracao atual: handle, precos padrao, URLs de webhook."""
    return _serialize(config_service.get_config_dict())


@router.patch(
    "/",
    response_model=ConfigResponse,
    responses={
        422: {"model": ErrorResponse, "description": "Validacao de campos"},
    },
)
def patch_config(body: ConfigUpdate) -> ConfigResponse:
    """Atualiza campos da configuracao (partial update).

    Envie apenas os campos que deseja alterar.
    Campos omitidos mantem o valor atual.
    """
    data = body.model_dump(exclude_unset=True)
    return _serialize(config_service.patch_config(data))
