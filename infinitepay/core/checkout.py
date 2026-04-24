"""Checkout business logic (shared by API and CLI)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from infinitepay.core import validators as v
from infinitepay.core import queue
from infinitepay.core.config import get_config_dict, is_ready
from infinitepay.core.infinitepay_client import create_checkout_link, payment_check, InfinitePayError
from infinitepay.core.logs import log_event
from infinitepay.db.models import Checkout
from infinitepay.db.session import session_scope


class CheckoutError(Exception):
    def __init__(self, message: str, code: int = 400, extra: dict | None = None):
        super().__init__(message)
        self.code = code
        self.extra = extra or {}


def _resolve_items(body: dict, cfg: dict) -> list[dict]:
    """Resolve items list: explicit body.items wins, else price+description (body or config)."""
    if body.get("items"):
        return v.normalize_items(body["items"])

    price = body.get("price", cfg.get("price"))
    description = body.get("description", cfg.get("description"))
    quantity = body.get("quantity", cfg.get("quantity") or 1)

    if price is None or not description:
        raise CheckoutError(
            "price+description (ou items[]) obrigatórios — informe no body ou salve em /config/",
            code=400,
        )
    return [v.normalize_item({"price": price, "description": description, "quantity": quantity})]


def _resolve_field(body: dict, cfg: dict, key: str, normalizer, *args) -> str:
    val = body.get(key) or cfg.get(key)
    if not val:
        raise CheckoutError(f"{key} obrigatório — informe no body ou salve em /config/", code=400)
    return normalizer(val, *args)


def create_checkout(body: dict[str, Any]) -> dict:
    """Create a new checkout via InfinitePay and persist it. Returns {external_id, checkout_url}."""
    if not is_ready():
        raise CheckoutError(
            "App bloqueado: public_api_url ausente ou não validado. Configure em /config/.",
            code=409,
        )

    cfg = get_config_dict()

    # public_api_url NEVER comes from body
    if "public_api_url" in body:
        raise CheckoutError("public_api_url não pode ser informado aqui; altere em /config/.", code=400)

    external_id = v.normalize_external_id(body.get("external_id", ""))
    handle = _resolve_field(body, cfg, "handle", v.normalize_handle)
    redirect_url = _resolve_field(body, cfg, "redirect_url", v.normalize_url, "redirect_url")
    backend_webhook = _resolve_field(body, cfg, "backend_webhook", v.normalize_url, "backend_webhook")
    public_api_url = cfg["public_api_url"]

    customer = v.normalize_customer(body.get("customer") or {})
    address = v.normalize_address(body.get("address"))
    items = _resolve_items(body, cfg)

    with session_scope() as s:
        existing = s.execute(
            select(Checkout).where(Checkout.external_id == external_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise CheckoutError(
                f"external_id já existe: {external_id}. Faça um GET /checkout/{external_id}/ para conferir.",
                code=409,
                extra={"external_id": external_id},
            )

    ipay_payload: dict[str, Any] = {
        "handle": handle,
        "items": items,
        "order_nsu": external_id,
        "redirect_url": redirect_url,
        "webhook_url": f"{public_api_url}/webhook/{external_id}/",
        "customer": customer,
    }
    if address:
        ipay_payload["address"] = address

    try:
        response = create_checkout_link(ipay_payload)
    except InfinitePayError as e:
        with session_scope() as s:
            log_event(
                s,
                direction="outbound",
                kind="create_link",
                payload=ipay_payload,
                response=e.payload,
                status_code=e.status_code,
                external_id=external_id,
            )
        raise CheckoutError(
            f"Falha ao criar link na InfinitePay: {e}",
            code=502,
            extra={"infinitepay_response": e.payload},
        )

    checkout_url = response.get("url") or response.get("checkout_url")
    if not checkout_url:
        with session_scope() as s:
            log_event(
                s,
                direction="outbound",
                kind="create_link",
                payload=ipay_payload,
                response=response,
                status_code=200,
                external_id=external_id,
            )
        raise CheckoutError(
            "InfinitePay não retornou URL de checkout",
            code=502,
            extra={"infinitepay_response": response},
        )

    with session_scope() as s:
        s.add(Checkout(
            external_id=external_id,
            checkout_url=checkout_url,
            is_paid=False,
            request_payload=ipay_payload,
            response_payload=response,
        ))
        log_event(
            s,
            direction="outbound",
            kind="create_link",
            payload=ipay_payload,
            response=response,
            status_code=200,
            external_id=external_id,
        )

    return {"external_id": external_id, "checkout_url": checkout_url}


def list_checkouts() -> list[dict]:
    with session_scope() as s:
        rows = s.execute(select(Checkout).order_by(Checkout.created_at.desc())).scalars().all()
        return [_serialize(c) for c in rows]


def get_checkout(external_id: str) -> dict:
    external_id = v.normalize_external_id(external_id)
    with session_scope() as s:
        c = s.execute(
            select(Checkout).where(Checkout.external_id == external_id)
        ).scalar_one_or_none()
        if c is None:
            raise CheckoutError(f"checkout não encontrado: {external_id}", code=404)
        if c.is_paid:
            return {"external_id": c.external_id, "is_paid": True, "receipt_url": c.receipt_url}
        return {"external_id": c.external_id, "is_paid": False, "checkout_url": c.checkout_url}


def _serialize(c: Checkout) -> dict:
    return {
        "external_id": c.external_id,
        "is_paid": c.is_paid,
        "checkout_url": c.checkout_url,
        "receipt_url": c.receipt_url,
        "invoice_slug": c.invoice_slug,
        "transaction_nsu": c.transaction_nsu,
        "capture_method": c.capture_method,
        "installments": c.installments,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def handle_infinitepay_webhook(external_id: str, payload: dict) -> dict:
    """Process incoming InfinitePay webhook. Returns dict; raises CheckoutError -> 400 for invalid.

    Flow per spec:
    1. log payload
    2. call payment_check with {handle, order_nsu, transaction_nsu, slug=invoice_slug}
    3. if success:false -> 400 "webhook não pode ser validado"
    4. else paid -> update checkout + enqueue backend_webhook POST
    """
    external_id = v.normalize_external_id(external_id)
    cfg = get_config_dict()
    handle = cfg.get("handle")
    backend_webhook = cfg.get("backend_webhook")

    with session_scope() as s:
        log_event(
            s,
            direction="inbound",
            kind="infinitepay_webhook",
            payload=payload,
            external_id=external_id,
        )

    if not handle:
        raise CheckoutError("handle não configurado", code=500)

    transaction_nsu = payload.get("transaction_nsu")
    invoice_slug = payload.get("invoice_slug")
    order_nsu = payload.get("order_nsu") or external_id

    if not transaction_nsu or not invoice_slug:
        raise CheckoutError("payload de webhook incompleto (faltam transaction_nsu/invoice_slug)", code=400)

    check = payment_check(
        handle=handle,
        order_nsu=order_nsu,
        transaction_nsu=transaction_nsu,
        slug=invoice_slug,
    )

    with session_scope() as s:
        log_event(
            s,
            direction="outbound",
            kind="payment_check",
            payload={"handle": handle, "order_nsu": order_nsu,
                     "transaction_nsu": transaction_nsu, "slug": invoice_slug},
            response=check,
            external_id=external_id,
        )

    if not check.get("success"):
        raise CheckoutError("webhook não pôde ser validado", code=400, extra={"payment_check": check})

    if not check.get("paid"):
        return {"ok": True, "paid": False}

    with session_scope() as s:
        c = s.execute(
            select(Checkout).where(Checkout.external_id == external_id)
        ).scalar_one_or_none()
        if c is None:
            raise CheckoutError(f"checkout desconhecido: {external_id}", code=404)

        c.is_paid = True
        c.receipt_url = payload.get("receipt_url")
        c.installments = payload.get("installments") or check.get("installments")
        c.invoice_slug = invoice_slug
        c.capture_method = payload.get("capture_method") or check.get("capture_method")
        c.transaction_nsu = transaction_nsu

    if backend_webhook:
        queue.enqueue(
            url=f"{backend_webhook}/{external_id}/",
            payload={
                "external_id": external_id,
                "paid": True,
                "receipt_url": payload.get("receipt_url"),
                "transaction_nsu": transaction_nsu,
                "invoice_slug": invoice_slug,
                "capture_method": payload.get("capture_method"),
                "installments": payload.get("installments"),
                "amount": payload.get("amount"),
                "paid_amount": payload.get("paid_amount"),
            },
            external_id=external_id,
        )

    return {"ok": True, "paid": True}
