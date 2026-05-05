from fastapi import APIRouter

from app.ai.analytics import ask as run_ask
from app.schemas.ask import AskRequest

router = APIRouter()


@router.post("/")
def ask_endpoint(body: AskRequest) -> dict:
    """Pergunte sobre seus checkouts em linguagem natural (requer DeepSeek API key)."""
    return run_ask(body.question)
