from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Resposta de erro padrao."""

    detail: str
