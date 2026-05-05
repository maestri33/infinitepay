from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    handle: str | None = None
    price: int | None = None
    quantity: int | None = None
    description: str | None = None
    redirect_url: str | None = None
    backend_webhook: str | None = None
    public_api_url: str | None = None


class ConfigResponse(BaseModel):
    """Configuracao atual da loja."""

    handle: str | None = None
    price: int | None = None
    quantity: int = 1
    description: str | None = None
    redirect_url: str | None = None
    backend_webhook: str | None = None
    public_api_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
