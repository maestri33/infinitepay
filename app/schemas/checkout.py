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
