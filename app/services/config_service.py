from typing import Any

from sqlalchemy.orm import Session

from app.db import session_scope
from app.models.models import Config
from app.utils import validators as v


PUBLIC_FIELDS = (
    "handle",
    "price",
    "quantity",
    "description",
    "redirect_url",
    "backend_webhook",
    "public_api_url",
    "created_at",
    "updated_at",
)


def _get_or_create(sess: Session) -> Config:
    cfg = sess.get(Config, 1)
    if cfg is None:
        cfg = Config(id=1)
        sess.add(cfg)
        sess.flush()
    return cfg


def get_config_dict() -> dict:
    with session_scope() as s:
        cfg = _get_or_create(s)
        return {f: getattr(cfg, f) for f in PUBLIC_FIELDS}


def patch_config(data: dict[str, Any]) -> dict:
    with session_scope() as s:
        cfg = _get_or_create(s)

        if "handle" in data and data["handle"] is not None:
            cfg.handle = v.normalize_handle(data["handle"])
        if "price" in data and data["price"] is not None:
            cfg.price = v.normalize_price(data["price"])
        if "quantity" in data and data["quantity"] is not None:
            cfg.quantity = v.normalize_quantity(data["quantity"])
        if "description" in data and data["description"] is not None:
            cfg.description = v.normalize_description(data["description"])
        if "redirect_url" in data and data["redirect_url"] is not None:
            cfg.redirect_url = v.normalize_url(data["redirect_url"], "redirect_url")
        if "backend_webhook" in data and data["backend_webhook"] is not None:
            cfg.backend_webhook = v.normalize_url(data["backend_webhook"], "backend_webhook")
        if "public_api_url" in data and data["public_api_url"] is not None:
            cfg.public_api_url = v.normalize_url(data["public_api_url"], "public_api_url")

        s.flush()
        return {f: getattr(cfg, f) for f in PUBLIC_FIELDS}
