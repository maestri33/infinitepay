from pydantic import BaseModel


class ReportResponse(BaseModel):
    """Relatorio executivo gerado por IA."""

    report: str
    enabled: bool
    kind: str | None = None
    model: str | None = None
    elapsed_ms: int | None = None
    tools_called: list[dict] | None = None
    usage: dict | None = None
