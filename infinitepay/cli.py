"""Typer CLI — calls core logic directly (no HTTP)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from infinitepay.core import checkout as checkout_core
from infinitepay.core import config as cfg_core
from infinitepay.core import queue as queue_core
from infinitepay.db.session import init_db

app = typer.Typer(help="InfinitePay CLI — cria links reais, consulta status local e opera direto no SQLite configurado por IPAY_DB_PATH.")
config_app = typer.Typer(help="Gerenciar configuração global: handle, defaults, redirect_url, backend_webhook e public_api_url.")
checkout_app = typer.Typer(help="Criar, listar e consultar checkouts InfinitePay.")
app.add_typer(config_app, name="config")
app.add_typer(checkout_app, name="checkout")


def _print(data) -> None:
    def default(o):
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False, default=default))


@app.callback()
def _root():
    init_db()


@config_app.command("show")
def config_show():
    """Exibe configuração atual."""
    _print(cfg_core.get_config_dict())


@config_app.command("set")
def config_set(
    handle: Optional[str] = typer.Option(None),
    price: Optional[int] = typer.Option(None, help="em centavos"),
    quantity: Optional[int] = typer.Option(None),
    description: Optional[str] = typer.Option(None),
    redirect_url: Optional[str] = typer.Option(None, help="URL para onde o cliente retorna depois do checkout"),
    backend_webhook: Optional[str] = typer.Option(None, help="URL base do backend que receberá POST /{external_id}/ após pagamento confirmado"),
    public_api_url: Optional[str] = typer.Option(None, help="URL pública desta API; usada para montar webhook_url da InfinitePay"),
):
    """Atualiza defaults e, ao mudar public_api_url, gera novo token de validação."""
    data = {k: v for k, v in {
        "handle": handle,
        "price": price,
        "quantity": quantity,
        "description": description,
        "redirect_url": redirect_url,
        "backend_webhook": backend_webhook,
        "public_api_url": public_api_url,
    }.items() if v is not None}
    if not data:
        typer.echo("nada para atualizar.")
        raise typer.Exit(code=1)
    res = cfg_core.patch_config(data)
    _print(res)


@config_app.command("validate-token")
def config_validate_token():
    """Mostra o token atual de validação do public_api_url (caso pendente)."""
    token = cfg_core.get_validation_token()
    _print({"validation_token": token, "note": "Dispare externamente um GET em {public_api_url}/config/test/?token=<token>"})


@config_app.command("force-validate")
def config_force_validate():
    """Marca public_api_url como validado usando o token local (bypass — só pra dev)."""
    token = cfg_core.get_validation_token()
    if not token:
        typer.echo("nada para validar (já validado ou sem public_api_url)")
        raise typer.Exit(code=1)
    ok = cfg_core.mark_validated(token)
    _print({"validated": ok})


@checkout_app.command("create")
def checkout_create(
    external_id: str = typer.Option(..., "--external-id", help="ID único do pedido; vira order_nsu na InfinitePay"),
    name: str = typer.Option(..., "--name"),
    email: str = typer.Option(..., "--email"),
    phone: str = typer.Option(..., "--phone", help="E.164 ou BR (10-11 dígitos)"),
    price: Optional[int] = typer.Option(None, "--price", help="centavos; sobrescreve config"),
    description: Optional[str] = typer.Option(None, "--description", help="Descrição do item quando não usar --items-json"),
    redirect_url: Optional[str] = typer.Option(None, "--redirect-url", help="Sobrescreve redirect_url da config para este checkout"),
    backend_webhook: Optional[str] = typer.Option(None, "--backend-webhook", help="Sobrescreve backend_webhook da config para este checkout"),
    handle: Optional[str] = typer.Option(None, "--handle", help="Sobrescreve handle da config para este checkout"),
    items_json: Optional[str] = typer.Option(None, "--items-json", help="JSON de items[]; sobrescreve price/description"),
    address_json: Optional[str] = typer.Option(None, "--address-json", help="JSON do endereço"),
):
    """Cria um link real na InfinitePay e salva o checkout localmente."""
    body: dict = {
        "external_id": external_id,
        "customer": {"name": name, "email": email, "phone_number": phone},
    }
    for k, v in [
        ("price", price), ("description", description),
        ("redirect_url", redirect_url), ("backend_webhook", backend_webhook),
        ("handle", handle),
    ]:
        if v is not None:
            body[k] = v
    if items_json:
        body["items"] = json.loads(items_json)
    if address_json:
        body["address"] = json.loads(address_json)
    _print(checkout_core.create_checkout(body))


@checkout_app.command("list")
def checkout_list():
    """Lista checkouts locais, incluindo pendentes e pagos."""
    _print({"items": checkout_core.list_checkouts()})


@checkout_app.command("get")
def checkout_get(external_id: str):
    """Mostra checkout por external_id; retorna checkout_url se pendente ou receipt_url se pago."""
    _print(checkout_core.get_checkout(external_id))


@app.command("worker")
def worker():
    """Roda o worker dedicado de retry do backend_webhook (bloqueante). Use apenas se IPAY_RUN_INLINE_WORKER=false."""
    typer.echo("[worker] iniciando loop...")
    queue_core.run_worker_blocking()


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    reload: bool = typer.Option(False),
):
    """Sobe a API FastAPI local. Em produção, prefira o service infinitepay-api."""
    import uvicorn
    uvicorn.run("infinitepay.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
