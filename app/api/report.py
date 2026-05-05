from fastapi import APIRouter, Query

from app.ai.reporter import generate_report
from app.schemas.report import ReportResponse

router = APIRouter()


@router.post(
    "/",
    response_model=ReportResponse,
)
def report_endpoint(
    kind: str = Query("daily", description="daily, weekly, full"),
) -> ReportResponse:
    """Gera relatorio executivo (sempre usa modelo pro avancado).

    - **daily**: resumo de hoje
    - **weekly**: ultimos 7 dias
    - **full**: todo o historico"""
    if kind not in ("daily", "weekly", "full"):
        kind = "daily"
    return generate_report(kind)
