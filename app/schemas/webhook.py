from pydantic import BaseModel


class WebhookResponse(BaseModel):
    """Resposta do processamento de webhook da InfinitePay."""

    ok: bool
    paid: bool = False
    duplicate: bool = False
