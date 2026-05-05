from fastapi import APIRouter

from app.schemas.config import ConfigUpdate
from app.services import config_service

router = APIRouter()


def _serialize(d: dict) -> dict:
    out = dict(d)
    for k in ("created_at", "updated_at"):
        if out.get(k) is not None and hasattr(out[k], "isoformat"):
            out[k] = out[k].isoformat()
    return out


@router.get("/")
def get_config():
    return _serialize(config_service.get_config_dict())


@router.patch("/")
def patch_config(body: ConfigUpdate):
    data = body.model_dump(exclude_unset=True)
    return _serialize(config_service.patch_config(data))
