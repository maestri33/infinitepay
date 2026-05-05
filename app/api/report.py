from fastapi import APIRouter, Query

from app.ai.reporter import generate_report

router = APIRouter()


@router.post("/")
def report_endpoint(kind: str = Query("daily", description="daily, weekly, full")) -> dict:
    """Gera relatório executivo (sempre usa modelo pro avançado).

    - **daily**: resumo de hoje
    - **weekly**: últimos 7 dias
    - **full**: todo o histórico"""
    if kind not in ("daily", "weekly", "full"):
        kind = "daily"
    return generate_report(kind)
