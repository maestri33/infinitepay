"""Remote Typer CLI that talks to an already-running InfinitePay API."""
from __future__ import annotations

import json
import os
from typing import Optional

import httpx
import typer

app = typer.Typer(
    help="InfinitePay remote CLI - chama uma API InfinitePay existente via HTTP."
)
checkout_app = typer.Typer(
    help="Criar, listar e consultar checkouts pela API remota."
)
app.add_typer(checkout_app, name="checkout")


def _api_url(value: Optional[str]) -> str:
    url = (value or os.environ.get("IPAY_API_URL") or "").strip().rstrip("/")
    if not url:
        raise typer.BadParameter("informe --api-url ou defina IPAY_API_URL")
    if not url.startswith(("http://", "https://")):
        raise typer.BadParameter("api_url deve começar com http:// ou https://")
    return url


def _print(data) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


def _request(method: str, api_url: str, path: str, **kwargs):
    try:
        with httpx.Client(base_url=api_url, timeout=30) as client:
            response = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        typer.echo(f"falha HTTP ao chamar {api_url}: {exc}", err=True)
        raise typer.Exit(code=2)

    try:
        data = response.json()
    except ValueError:
        data = {"raw": response.text}

    if response.status_code >= 400:
        _print({"status_code": response.status_code, "error": data})
        raise typer.Exit(code=1)

    return data


@app.command("health")
def health(
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        help="URL interna da API InfinitePay. Também aceita IPAY_API_URL.",
    ),
):
    """Mostra health/readiness da API remota."""
    _print(_request("GET", _api_url(api_url), "/health"))


@checkout_app.command("create")
def checkout_create(
    external_id: str = typer.Option(
        ...,
        "--external-id",
        help="ID único do pedido; vira order_nsu na InfinitePay.",
    ),
    name: str = typer.Option(..., "--name"),
    email: str = typer.Option(..., "--email"),
    phone: str = typer.Option(..., "--phone", help="E.164 ou BR (10-11 dígitos)"),
    price: Optional[int] = typer.Option(
        None,
        "--price",
        help="Centavos; sobrescreve o default configurado na API principal.",
    ),
    description: Optional[str] = typer.Option(
        None,
        "--description",
        help="Descrição do item quando não usar --items-json.",
    ),
    items_json: Optional[str] = typer.Option(
        None,
        "--items-json",
        help="JSON de items[]; sobrescreve price/description.",
    ),
    address_json: Optional[str] = typer.Option(
        None,
        "--address-json",
        help="JSON do endereço.",
    ),
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        help="URL interna da API InfinitePay. Também aceita IPAY_API_URL.",
    ),
):
    """Cria um checkout pela API remota e imprime o checkout_url."""
    body: dict = {
        "external_id": external_id,
        "customer": {"name": name, "email": email, "phone_number": phone},
    }
    if price is not None:
        body["price"] = price
    if description is not None:
        body["description"] = description
    if items_json:
        body["items"] = json.loads(items_json)
    if address_json:
        body["address"] = json.loads(address_json)

    _print(_request("POST", _api_url(api_url), "/checkout/", json=body))


@checkout_app.command("list")
def checkout_list(
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        help="URL interna da API InfinitePay. Também aceita IPAY_API_URL.",
    ),
):
    """Lista checkouts pela API remota."""
    _print(_request("GET", _api_url(api_url), "/checkout/"))


@checkout_app.command("get")
def checkout_get(
    external_id: str,
    api_url: Optional[str] = typer.Option(
        None,
        "--api-url",
        help="URL interna da API InfinitePay. Também aceita IPAY_API_URL.",
    ),
):
    """Consulta checkout por external_id pela API remota."""
    _print(_request("GET", _api_url(api_url), f"/checkout/{external_id}/"))


if __name__ == "__main__":
    app()
