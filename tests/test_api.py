def test_health_and_lock_flow(monkeypatch):
    from fastapi.testclient import TestClient
    from infinitepay.api.main import create_app

    app = create_app()
    with TestClient(app) as c:
        assert c.get("/health").json()["ready"] is False

        # checkout blocked
        r = c.post("/checkout/", json={})
        assert r.status_code == 503

        # configure + validate
        r = c.patch("/config/", json={
            "handle": "v7m",
            "price": 100,
            "description": "x",
            "redirect_url": "https://a.com/p",
            "backend_webhook": "https://a.com/api",
            "public_api_url": "https://my.api",
        })
        token = r.json()["validation_token"]
        r = c.get(f"/config/test/?token={token}")
        assert r.status_code == 200
        assert c.get("/health").json()["ready"] is True

        # missing customer -> 400
        r = c.post("/checkout/", json={"external_id": "p1"})
        assert r.status_code == 400

        # mock infinitepay + full flow
        monkeypatch.setattr(
            "infinitepay.core.checkout.create_checkout_link",
            lambda p: {"success": True, "url": "https://checkout.ipay/x"},
        )
        r = c.post("/checkout/", json={
            "external_id": "p1",
            "customer": {"name": "João", "email": "a@b.com", "phone_number": "11999887766"},
        })
        assert r.status_code == 200, r.text
        assert r.json()["checkout_url"] == "https://checkout.ipay/x"

        r = c.get("/checkout/p1/")
        assert r.json() == {"external_id": "p1", "is_paid": False, "checkout_url": "https://checkout.ipay/x"}
