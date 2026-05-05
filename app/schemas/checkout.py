from pydantic import BaseModel


class CustomerIn(BaseModel):
    name: str | None = None
    email: str | None = None
    phone_number: str | None = None


class AddressIn(BaseModel):
    cep: str | None = None
    street: str | None = None
    neighborhood: str | None = None
    number: str | int | None = None
    complement: str | None = None


class ItemIn(BaseModel):
    price: int
    description: str
    quantity: int = 1


class CheckoutCreate(BaseModel):
    external_id: str | None = None
    handle: str | None = None
    price: int | None = None
    description: str | None = None
    quantity: int | None = None
    redirect_url: str | None = None
    customer: CustomerIn | None = None
    address: AddressIn | None = None
    items: list[ItemIn] | None = None


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
