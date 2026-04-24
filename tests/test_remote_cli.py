from typer.testing import CliRunner


class _FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "fake"

    def json(self):
        return self._payload


class _FakeClient:
    calls = []

    def __init__(self, base_url, timeout):
        self.base_url = base_url
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def request(self, method, path, **kwargs):
        self.calls.append((self.base_url, self.timeout, method, path, kwargs))
        if method == "POST":
            return _FakeResponse(200, {"external_id": "pedido-1", "checkout_url": "https://checkout"})
        return _FakeResponse(200, {"ok": True, "ready": True})


def test_remote_health_uses_env_api_url(monkeypatch):
    from infinitepay import remote_cli

    _FakeClient.calls = []
    monkeypatch.setattr(remote_cli.httpx, "Client", _FakeClient)
    monkeypatch.setenv("IPAY_API_URL", "http://10.10.10.120:8000/")

    result = CliRunner().invoke(remote_cli.app, ["health"])

    assert result.exit_code == 0
    assert '"ready": true' in result.stdout
    assert _FakeClient.calls[0][:4] == ("http://10.10.10.120:8000", 30, "GET", "/health")


def test_remote_checkout_create_posts_expected_payload(monkeypatch):
    from infinitepay import remote_cli

    _FakeClient.calls = []
    monkeypatch.setattr(remote_cli.httpx, "Client", _FakeClient)

    result = CliRunner().invoke(
        remote_cli.app,
        [
            "checkout",
            "create",
            "--api-url",
            "http://10.10.10.120:8000",
            "--external-id",
            "pedido-1",
            "--name",
            "Victor Maestri",
            "--email",
            "victormaestri@gmail.com",
            "--phone",
            "+5543996648750",
            "--price",
            "101",
            "--description",
            "Doce de amendoim",
            "--address-json",
            '{"cep":"84050360","street":"Rua Ataulfo Alves","number":"770","neighborhood":"Estrela"}',
        ],
    )

    assert result.exit_code == 0
    _, _, method, path, kwargs = _FakeClient.calls[0]
    assert method == "POST"
    assert path == "/checkout/"
    assert kwargs["json"] == {
        "external_id": "pedido-1",
        "customer": {
            "name": "Victor Maestri",
            "email": "victormaestri@gmail.com",
            "phone_number": "+5543996648750",
        },
        "price": 101,
        "description": "Doce de amendoim",
        "address": {
            "cep": "84050360",
            "street": "Rua Ataulfo Alves",
            "number": "770",
            "neighborhood": "Estrela",
        },
    }
