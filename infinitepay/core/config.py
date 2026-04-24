"""Config singleton management + public_api_url validation flow."""
from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy.orm import Session

from infinitepay.db.models import Config
from infinitepay.db.session import session_scope
from infinitepay.core import validators as v


class ConfigError(Exception):
    pass


PUBLIC_FIELDS = (
    "handle", "price", "quantity", "description",
    "redirect_url", "backend_webhook", "public_api_url",
    "public_api_url_validated", "created_at", "updated_at",
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


def is_ready() -> bool:
    """True if public_api_url is set AND validated."""
    with session_scope() as s:
        cfg = _get_or_create(s)
        return bool(cfg.public_api_url and cfg.public_api_url_validated)


def patch_config(data: dict[str, Any]) -> dict:
    """Update mutable config fields. Returns the current config dict.

    Special handling:
    - public_api_url: normalizes, stores, resets validated=False, generates token.
    """
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
            url = v.normalize_url(data["public_api_url"], "public_api_url")
            cfg.public_api_url = url
            cfg.public_api_url_validated = False
            cfg.public_api_url_validation_token = secrets.token_urlsafe(24)

        s.flush()
        return {f: getattr(cfg, f) for f in PUBLIC_FIELDS} | {
            "validation_token": cfg.public_api_url_validation_token if not cfg.public_api_url_validated else None
        }


def get_validation_token() -> str | None:
    with session_scope() as s:
        cfg = _get_or_create(s)
        if cfg.public_api_url_validated:
            return None
        return cfg.public_api_url_validation_token


def mark_validated(token: str) -> bool:
    with session_scope() as s:
        cfg = _get_or_create(s)
        if not cfg.public_api_url or not cfg.public_api_url_validation_token:
            return False
        if not secrets.compare_digest(token, cfg.public_api_url_validation_token):
            return False
        cfg.public_api_url_validated = True
        return True
