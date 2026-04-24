def test_bootstrap_lock_flow():
    from infinitepay.core import config as cfg
    from infinitepay.db.session import init_db
    init_db()
    assert cfg.is_ready() is False

    res = cfg.patch_config({
        "handle": "v7m",
        "price": 100,
        "description": "x",
        "redirect_url": "https://a.com/pago",
        "backend_webhook": "https://a.com/api",
        "public_api_url": "https://my.public.api",
    })
    token = res["validation_token"]
    assert token
    assert cfg.is_ready() is False

    assert cfg.mark_validated("wrong") is False
    assert cfg.mark_validated(token) is True
    assert cfg.is_ready() is True

    # Changing public_api_url resets validation
    res2 = cfg.patch_config({"public_api_url": "https://other.api"})
    assert res2["validation_token"]
    assert cfg.is_ready() is False
