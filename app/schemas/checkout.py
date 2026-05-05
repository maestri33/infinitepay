from pydantic import BaseModel


class CustomerIn(BaseModel):
    name: str
    email: str
    phone_number: str


class CheckoutCreate(BaseModel):
    external_id: str
    customer: CustomerIn


# ── response schemas ──────────────────────────────────────────────


class CheckoutResponse(BaseModel):
    """Checkout individual — retornado por create, get e list."""

    external_id: str
    is_paid: bool = False
    checkout_url: str | None = None
    receipt_url: str | None = None
    invoice_slug: str | None = None
    transaction_nsu: str | None = None
    capture_method: str | None = None
    installments: int | None = None
    created_at: str | None = None
    updated_at: str | None = None


class CheckoutListResponse(BaseModel):
    """Wrapper para listagem de checkouts."""

    items: list[CheckoutResponse]
