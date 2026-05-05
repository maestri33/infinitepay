from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    deep: bool = False  # true = força pro model para análise profunda
