from fastapi import APIRouter

from app.ai.analytics import ask as run_ask
from app.schemas.ask import AskRequest

router = APIRouter()


@router.post("/")
def ask_endpoint(body: AskRequest) -> dict:
    """Pergunte sobre seus checkouts em linguagem natural.

    Use `deep: true` para análises complexas (tendências, padrões, relatórios).
    O modelo pro é usado automaticamente para perguntas analíticas."""
    return run_ask(body.question, deep=body.deep)
