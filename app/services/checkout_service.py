from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.ai import monitor as ai_monitor
from app.ai import receipt as ai_receipt
from app.db import session_scope
from app.exceptions import Conflict, IntegrationError, NotFound, ValidationError
from app.integrations.infinitepay_client import (
    InfinitePayError,
    create_checkout_link,
    payment_check,
)
from app.models.models import Checkout, WebhookLog
from app.services import config_service
from app.utils import validators as v
from app.utils.crypto import encrypt_external_id
from app.workers import outbound_queue as queue


def _log_event(
    sess, *, direction, kind, payload, response=None, status_code=None, external_id=None
):
    entry = WebhookLog(
        direction=direction,
        kind=kind,
        payload=payload or {},
        response=response,
        status_code=status_code,
        external_id=external_id,
    )
    sess.add(entry)
    sess.flush()
    return entry


def _resolve_items(body: dict, cfg: dict) -> list[dict]:
    if body.get("items"):
        return v.normalize_items(body["items"])

    price = body.get("price", cfg.get("price"))
    description = body.get("description", cfg.get("description"))
    quantity = body.get("quantity", cfg.get("quantity") or 1)

    if price is None or not description:
        raise ValidationError(
            "price+description (ou items[]) obrigatórios — informe no body ou salve em /config/"
        )
    return [v.normalize_item({"price": price, "description": description, "quantity": quantity})]


def _resolve_field(body: dict, cfg: dict, key: str, normalizer, *args) -> str:
    val = body.get(key) or cfg.get(key)
    if not val:
        raise ValidationError(f"{key} obrigatório — informe no body ou salve em /config/")
    return normalizer(val, *args)


def create_checkout(body: dict[str, Any]) -> dict:
    cfg = config_service.get_config_dict()

    if "public_api_url" in body:
        raise ValidationError("public_api_url não pode ser informado aqui; altere em /config/.")

    external_id = v.normalize_external_id(body.get("external_id", ""))
    handle = _resolve_field(body, cfg, "handle", v.normalize_handle)
    redirect_url = _resolve_field(body, cfg, "redirect_url", v.normalize_url, "redirect_url")
    public_api_url = cfg["public_api_url"]

    customer = v.normalize_customer(body.get("customer") or {})
    address = v.normalize_address(body.get("address"))
    items = _resolve_items(body, cfg)

    with session_scope() as s:
        existing = s.execute(
            select(Checkout).where(Checkout.external_id == external_id)
        ).scalar_one_or_none()
        if existing is not None:
            raise Conflict(
                f"external_id já existe: {external_id}. "
                f"Faça um GET /checkout/{external_id}/ para conferir.",
                extra={"external_id": external_id},
            )

    ipay_payload: dict[str, Any] = {
        "handle": handle,
        "items": items,
        "order_nsu": external_id,
        "redirect_url": redirect_url,
        "webhook_url": (
            f"{public_api_url}/api/v1/webhook/?external_id={encrypt_external_id(external_id)}"
        ),
        "customer": customer,
    }
    if address:
        ipay_payload["address"] = address

    try:
        response = create_checkout_link(ipay_payload)
    except InfinitePayError as e:
        with session_scope() as s:
            _log_event(
                s,
                direction="outbound",
                kind="create_link",
                payload=ipay_payload,
                response=e.payload,
                status_code=e.status_code,
                external_id=external_id,
            )
        raise IntegrationError(f"Falha ao criar link na InfinitePay: {e}") from e

    checkout_url = response.get("url") or response.get("checkout_url")
    if not checkout_url:
        with session_scope() as s:
            _log_event(
                s,
                direction="outbound",
                kind="create_link",
                payload=ipay_payload,
                response=response,
                status_code=200,
                external_id=external_id,
            )
        raise IntegrationError("InfinitePay não retornou URL de checkout")

    try:
        with session_scope() as s:
            s.add(
                Checkout(
                    external_id=external_id,
                    checkout_url=checkout_url,
                    is_paid=False,
                    request_payload=ipay_payload,
                    response_payload=response,
                )
            )
            _log_event(
                s,
                direction="outbound",
                kind="create_link",
                payload=ipay_payload,
                response=response,
                status_code=200,
                external_id=external_id,
            )
    except IntegrityError:
        raise Conflict(
            f"external_id já existe: {external_id}. "
            f"Faça um GET /checkout/{external_id}/ para conferir.",
            extra={"external_id": external_id},
        ) from None

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
            raise NotFound(f"checkout não encontrado: {external_id}")
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
    external_id = v.normalize_external_id(external_id)
    cfg = config_service.get_config_dict()
    handle = cfg.get("handle")
    backend_webhook = cfg.get("backend_webhook")

    with session_scope() as s:
        _log_event(
            s,
            direction="inbound",
            kind="infinitepay_webhook",
            payload=payload,
            external_id=external_id,
        )

    if not handle:
        raise IntegrationError("handle não configurado")

    transaction_nsu = payload.get("transaction_nsu")
    invoice_slug = payload.get("invoice_slug")
    order_nsu = v.normalize_external_id(str(payload.get("order_nsu") or external_id))
    if order_nsu != external_id:
        raise ValidationError("order_nsu do webhook diverge do external_id da rota")

    if not transaction_nsu or not invoice_slug:
        raise ValidationError("payload de webhook incompleto (faltam transaction_nsu/invoice_slug)")

    with session_scope() as s:
        c = s.execute(
            select(Checkout).where(Checkout.external_id == external_id)
        ).scalar_one_or_none()
        if c is None:
            raise NotFound(f"checkout desconhecido: {external_id}")
        if c.is_paid:
            return {"ok": True, "paid": True, "duplicate": True}

    try:
        check = payment_check(
            handle=handle,
            order_nsu=order_nsu,
            transaction_nsu=transaction_nsu,
            slug=invoice_slug,
        )
    except InfinitePayError as e:
        with session_scope() as s:
            _log_event(
                s,
                direction="outbound",
                kind="payment_check",
                payload={
                    "handle": handle,
                    "order_nsu": order_nsu,
                    "transaction_nsu": transaction_nsu,
                    "slug": invoice_slug,
                },
                response=e.payload,
                status_code=e.status_code,
                external_id=external_id,
            )
        raise IntegrationError(f"Falha ao validar pagamento na InfinitePay: {e}") from e

    with session_scope() as s:
        _log_event(
            s,
            direction="outbound",
            kind="payment_check",
            payload={
                "handle": handle,
                "order_nsu": order_nsu,
                "transaction_nsu": transaction_nsu,
                "slug": invoice_slug,
            },
            response=check,
            external_id=external_id,
        )

    if not check.get("success"):
        raise ValidationError("webhook não pôde ser validado")

    if not check.get("paid"):
        return {"ok": True, "paid": False}

    with session_scope() as s:
        c = s.execute(
            select(Checkout).where(Checkout.external_id == external_id)
        ).scalar_one_or_none()
        if c is None:
            raise NotFound(f"checkout desconhecido: {external_id}")

        if c.is_paid and c.transaction_nsu == transaction_nsu:
            return {"ok": True, "paid": True, "duplicate": True}

        c.is_paid = True
        c.receipt_url = payload.get("receipt_url")
        c.installments = payload.get("installments") or check.get("installments")
        c.invoice_slug = invoice_slug
        c.capture_method = payload.get("capture_method") or check.get("capture_method")
        c.transaction_nsu = transaction_nsu

        # extrair dados antes da sessao fechar (evita DetachedInstanceError)
        _rp = c.request_payload or {}
        _customer = _rp.get("customer", {})
        customer_name = _customer.get("name", "cliente")
        _items = _rp.get("items", [{}])
        product = _items[0].get("description", cfg.get("description", "produto"))
        price = _items[0].get("price", cfg.get("price", 0))
        receipt_url = payload.get("receipt_url") or ""

    if backend_webhook:

        ai_message = ai_receipt.generate_receipt_message(
            customer_name=customer_name,
            product=product,
            price_cents=price,
            receipt_url=receipt_url,
        )

        anomaly = ai_monitor.check_anomaly(external_id, payload)
        if anomaly.get("alert"):
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "anomaly detected: %s — %s", external_id, anomaly.get("reason")
            )
            if anomaly.get("deep_analysis"):
                logger.warning(
                    "anomaly deep analysis: %s — %s",
                    external_id,
                    anomaly.get("deep_analysis"),
                )

        queue.enqueue(
            url=backend_webhook,
            payload={
                "external_id": external_id,
                "paid": True,
                "receipt_url": receipt_url,
                "transaction_nsu": transaction_nsu,
                "invoice_slug": invoice_slug,
                "capture_method": payload.get("capture_method"),
                "installments": payload.get("installments"),
                "amount": payload.get("amount"),
                "paid_amount": payload.get("paid_amount"),
                "customer_name": customer_name,
                "product": product,
                "ai_message": ai_message,
                "ai_anomaly": anomaly,
            },
            external_id=external_id,
        )

    return {"ok": True, "paid": True}
