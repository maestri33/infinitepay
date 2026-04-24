import pytest


def test_normalize_handle_strips_dollar():
    from infinitepay.core import validators as v
    assert v.normalize_handle("$v7m") == "v7m"


def test_normalize_price_requires_positive_int():
    from infinitepay.core import validators as v
    assert v.normalize_price("100") == 100
    with pytest.raises(v.ValidationError):
        v.normalize_price(0)
    with pytest.raises(v.ValidationError):
        v.normalize_price(None)


def test_normalize_cep_strips_non_digits():
    from infinitepay.core import validators as v
    assert v.normalize_cep("12345-678") == "12345678"
    with pytest.raises(v.ValidationError):
        v.normalize_cep("123")


def test_normalize_phone_assumes_br_when_no_plus():
    from infinitepay.core import validators as v
    assert v.normalize_phone("11999887766") == "+5511999887766"
    assert v.normalize_phone("+5511999887766") == "+5511999887766"
    with pytest.raises(v.ValidationError):
        v.normalize_phone("abc")


def test_normalize_url_requires_http():
    from infinitepay.core import validators as v
    assert v.normalize_url("https://x.com/", "u") == "https://x.com"
    with pytest.raises(v.ValidationError):
        v.normalize_url("ftp://x.com", "u")


def test_normalize_customer_address():
    from infinitepay.core import validators as v
    c = v.normalize_customer({"name": "João", "email": "a@b.com", "phone_number": "11999887766"})
    assert c["email"] == "a@b.com"
    a = v.normalize_address({"cep": "12345-678", "street": "R", "neighborhood": "C", "number": "1"})
    assert a["cep"] == "12345678"


def test_normalize_external_id_rejects_bad_chars():
    from infinitepay.core import validators as v
    with pytest.raises(v.ValidationError):
        v.normalize_external_id("a b")
    assert v.normalize_external_id("pedido-1.2_3") == "pedido-1.2_3"
