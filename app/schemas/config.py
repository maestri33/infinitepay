from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    handle: str | None = None
    price: int | None = None
    quantity: int | None = None
    description: str | None = None
    redirect_url: str | None = None
    backend_webhook: str | None = None
    public_api_url: str | None = None
