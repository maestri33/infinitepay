from fastapi import APIRouter

from app.ai.analytics import ask as run_ask
from app.schemas.ask import AskRequest, AskResponse

router = APIRouter()


@router.post(
    "/",
    response_model=AskResponse,
)
def ask_endpoint(body: AskRequest) -> AskResponse:
    """Pergunte sobre seus checkouts em linguagem natural.

    Use `deep: true` para analises complexas (tendencias, padroes, relatorios).
    O modelo pro e usado automaticamente para perguntas analiticas."""
    return run_ask(body.question, deep=body.deep)
