from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from infinitepay.core import config as cfg_core

router = APIRouter()


class ConfigPatch(BaseModel):
    handle: str | None = None
    price: int | None = None
    quantity: int | None = None
    description: str | None = None
    redirect_url: str | None = None
    backend_webhook: str | None = None
    public_api_url: str | None = None


def _serialize(d: dict) -> dict:
    out = dict(d)
    for k in ("created_at", "updated_at"):
        if out.get(k) is not None and hasattr(out[k], "isoformat"):
            out[k] = out[k].isoformat()
    return out


@router.get("/", summary="Mostrar configuração", description="Retorna os defaults usados para criar checkouts e o estado de validação da public_api_url.")
def get_config():
    return _serialize(cfg_core.get_config_dict())


@router.patch("/", summary="Atualizar configuração", description="Atualiza defaults. Alterar public_api_url gera token novo e bloqueia checkouts até validação externa.")
def patch_config(body: ConfigPatch):
    data = body.model_dump(exclude_unset=True)
    result = cfg_core.patch_config(data)
    result = _serialize(result)
    # hint for public_api_url validation flow
    if result.get("public_api_url") and not result.get("public_api_url_validated"):
        token = result.get("validation_token")
        result["next_step"] = (
            f"Dispare externamente um GET em {result['public_api_url']}/config/test/?token={token} "
            "para validar. Enquanto não validar, demais endpoints ficam bloqueados."
        )
    return result


@router.get("/test/", summary="Validar public_api_url", description="Endpoint público chamado externamente para provar que a URL pública chega nesta API.")
def validate_public_url(token: str = Query(...)):
    ok = cfg_core.mark_validated(token)
    if not ok:
        raise HTTPException(status_code=400, detail="token inválido ou public_api_url não configurado")
    return {"ok": True, "validated": True}
