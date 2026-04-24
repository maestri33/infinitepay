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

app = typer.Typer(help="InfinitePay CLI — espelha a API e opera direto no SQLite local.")
config_app = typer.Typer(help="Gerenciar configuração global (valores default para checkouts).")
checkout_app = typer.Typer(help="Gerenciar checkouts.")
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
    redirect_url: Optional[str] = typer.Option(None),
    backend_webhook: Optional[str] = typer.Option(None),
    public_api_url: Optional[str] = typer.Option(None),
):
    """Atualiza um ou mais campos do /config/."""
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
    external_id: str = typer.Option(..., "--external-id"),
    name: str = typer.Option(..., "--name"),
    email: str = typer.Option(..., "--email"),
    phone: str = typer.Option(..., "--phone", help="E.164 ou BR (10-11 dígitos)"),
    price: Optional[int] = typer.Option(None, "--price", help="centavos; sobrescreve config"),
    description: Optional[str] = typer.Option(None, "--description"),
    redirect_url: Optional[str] = typer.Option(None, "--redirect-url"),
    backend_webhook: Optional[str] = typer.Option(None, "--backend-webhook"),
    handle: Optional[str] = typer.Option(None, "--handle"),
    items_json: Optional[str] = typer.Option(None, "--items-json", help="JSON de items[]; sobrescreve price/description"),
    address_json: Optional[str] = typer.Option(None, "--address-json", help="JSON do endereço"),
):
    """Cria um checkout na InfinitePay."""
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
    _print({"items": checkout_core.list_checkouts()})


@checkout_app.command("get")
def checkout_get(external_id: str):
    _print(checkout_core.get_checkout(external_id))


@app.command("worker")
def worker():
    """Roda o worker de retry do backend_webhook (bloqueante)."""
    typer.echo("[worker] iniciando loop...")
    queue_core.run_worker_blocking()


@app.command("serve")
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    reload: bool = typer.Option(False),
):
    """Sobe FastAPI (uvicorn)."""
    import uvicorn
    uvicorn.run("infinitepay.api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
