import pytest


def _bootstrap():
    from infinitepay.core import config as cfg
    from infinitepay.db.session import init_db
    init_db()
    res = cfg.patch_config({
        "handle": "v7m",
        "price": 100,
        "description": "Padrão",
        "redirect_url": "https://site.com/pago",
        "backend_webhook": "https://site.com/api",
        "public_api_url": "https://my.public.api",
    })
    cfg.mark_validated(res["validation_token"])


def test_create_checkout_uses_config_defaults(monkeypatch):
    _bootstrap()
    from infinitepay.core import checkout as co

    captured = {}

    def fake_create(payload):
        captured["payload"] = payload
        return {"success": True, "url": "https://checkout.ipay/abc"}

    monkeypatch.setattr("infinitepay.core.checkout.create_checkout_link", fake_create)

    out = co.create_checkout({
        "external_id": "pedido-1",
        "customer": {"name": "João", "email": "a@b.com", "phone_number": "11999887766"},
    })
    assert out == {"external_id": "pedido-1", "checkout_url": "https://checkout.ipay/abc"}
    p = captured["payload"]
    assert p["handle"] == "v7m"
    assert p["items"] == [{"quantity": 1, "price": 100, "description": "Padrão"}]
    assert p["order_nsu"] == "pedido-1"
    assert p["webhook_url"] == "https://my.public.api/webhook/pedido-1/"


def test_create_checkout_duplicate_external_id(monkeypatch):
    _bootstrap()
    from infinitepay.core import checkout as co
    monkeypatch.setattr(
        "infinitepay.core.checkout.create_checkout_link",
        lambda p: {"success": True, "url": "https://x/y"},
    )
    body = {
        "external_id": "p-dup",
        "customer": {"name": "João", "email": "a@b.com", "phone_number": "11999887766"},
    }
    co.create_checkout(body)
    with pytest.raises(co.CheckoutError) as exc:
        co.create_checkout(body)
    assert exc.value.code == 409


def test_create_checkout_blocked_when_not_ready(monkeypatch):
    from infinitepay.core import checkout as co
    from infinitepay.db.session import init_db
    init_db()
    with pytest.raises(co.CheckoutError) as exc:
        co.create_checkout({"external_id": "x",
                            "customer": {"name": "João", "email": "a@b.com", "phone_number": "11999887766"}})
    assert exc.value.code == 409


def test_get_returns_checkout_url_when_unpaid(monkeypatch):
    _bootstrap()
    from infinitepay.core import checkout as co
    monkeypatch.setattr(
        "infinitepay.core.checkout.create_checkout_link",
        lambda p: {"success": True, "url": "https://x/y"},
    )
    co.create_checkout({
        "external_id": "p1",
        "customer": {"name": "João", "email": "a@b.com", "phone_number": "11999887766"},
    })
    got = co.get_checkout("p1")
    assert got == {"external_id": "p1", "is_paid": False, "checkout_url": "https://x/y"}


def test_webhook_flow_pays_and_enqueues_backend(monkeypatch):
    _bootstrap()
    from infinitepay.core import checkout as co
    from infinitepay.core import queue
    from infinitepay.db.models import OutboundJob
    from infinitepay.db.session import session_scope
    from sqlalchemy import select

    monkeypatch.setattr(
        "infinitepay.core.checkout.create_checkout_link",
        lambda p: {"success": True, "url": "https://x/y"},
    )
    co.create_checkout({
        "external_id": "p2",
        "customer": {"name": "João", "email": "a@b.com", "phone_number": "11999887766"},
    })

    monkeypatch.setattr(
        "infinitepay.core.checkout.payment_check",
        lambda **kw: {"success": True, "paid": True, "amount": 100, "paid_amount": 106,
                      "installments": 1, "capture_method": "credit_card"},
    )

    payload = {
        "invoice_slug": "VtRJSJkMd",
        "amount": 100, "paid_amount": 106,
        "installments": 1, "capture_method": "credit_card",
        "transaction_nsu": "tx-uuid",
        "order_nsu": "p2",
        "receipt_url": "https://recibo/p2",
        "items": [],
    }
    res = co.handle_infinitepay_webhook("p2", payload)
    assert res == {"ok": True, "paid": True}

    with session_scope() as s:
        jobs = s.execute(select(OutboundJob)).scalars().all()
        assert len(jobs) == 1
        assert jobs[0].url == "https://site.com/api/p2/"
        assert jobs[0].payload["paid"] is True
        assert jobs[0].payload["receipt_url"] == "https://recibo/p2"

    # Checkout is updated
    got = co.get_checkout("p2")
    assert got["is_paid"] is True
    assert got["receipt_url"] == "https://recibo/p2"


def test_webhook_invalid_returns_400(monkeypatch):
    _bootstrap()
    from infinitepay.core import checkout as co
    monkeypatch.setattr(
        "infinitepay.core.checkout.create_checkout_link",
        lambda p: {"success": True, "url": "https://x/y"},
    )
    co.create_checkout({
        "external_id": "p3",
        "customer": {"name": "João", "email": "a@b.com", "phone_number": "11999887766"},
    })

    monkeypatch.setattr(
        "infinitepay.core.checkout.payment_check",
        lambda **kw: {"success": False},
    )
    payload = {"invoice_slug": "s", "transaction_nsu": "t", "order_nsu": "p3"}
    with pytest.raises(co.CheckoutError) as exc:
        co.handle_infinitepay_webhook("p3", payload)
    assert exc.value.code == 400
