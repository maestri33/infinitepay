import json
from datetime import date, datetime

from sqlalchemy import func, select

from app.db import session_scope
from app.models.models import Checkout

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_checkouts",
            "description": "Lista checkouts com status, cliente, valores e datas.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Retorna estatisticas: total, pagos, pendentes, pagos hoje.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_config",
            "description": "Retorna configuracao: handle, preco, descricao do produto, URLs.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_checkouts",
            "description": "Busca checkouts por nome, email, external_id ou slug.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Termo de busca (nome, email, external_id)",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

SYSTEM_PROMPT = """Você é um assistente de análises financeiras da loja do Pr. Maestri.
O produto vendido é "E-book do Pr. Maestri" (R$ 1,04 via InfinitePay).
Responda SEMPRE em português do Brasil, de forma direta e concisa.
Use as funções disponíveis para consultar dados reais antes de responder.
Apresente valores em reais (R$) com 2 casas decimais.
Se a pergunta envolver "hoje", use a data atual. Se for "semana", considere os últimos 7 dias."""


def _serialize_checkout(c: Checkout) -> dict:
    return {
        "external_id": c.external_id,
        "is_paid": c.is_paid,
        "checkout_url": c.checkout_url,
        "receipt_url": c.receipt_url,
        "invoice_slug": c.invoice_slug,
        "transaction_nsu": c.transaction_nsu,
        "capture_method": c.capture_method,
        "installments": c.installments,
        "customer": c.request_payload.get("customer", {}),
        "items": c.request_payload.get("items", []),
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def execute_tool(name: str, args: dict) -> str:
    if name == "list_checkouts":
        with session_scope() as s:
            rows = (
                s.execute(select(Checkout).order_by(Checkout.created_at.desc()).limit(50))
                .scalars()
                .all()
            )
            return json.dumps(
                [_serialize_checkout(r) for r in rows], ensure_ascii=False, default=str
            )

    elif name == "get_stats":
        with session_scope() as s:
            total = s.execute(select(func.count(Checkout.id))).scalar()
            paid = s.execute(
                select(func.count(Checkout.id)).where(Checkout.is_paid.is_(True))
            ).scalar()
            pending = total - paid

            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            paid_today = s.execute(
                select(func.count(Checkout.id)).where(
                    Checkout.is_paid.is_(True),
                    Checkout.updated_at >= today_start,
                )
            ).scalar()

            return json.dumps(
                {
                    "total_checkouts": total,
                    "pagos": paid,
                    "pendentes": pending,
                    "pagos_hoje": paid_today,
                    "preco_unitario": 104,  # centavos
                },
                ensure_ascii=False,
            )

    elif name == "get_config":
        from app.services import config_service

        cfg = config_service.get_config_dict()
        return json.dumps(
            {
                "produto": cfg.get("description"),
                "preco_centavos": cfg.get("price"),
                "preco_reais": f"{cfg.get('price', 0) / 100:.2f}" if cfg.get("price") else "N/A",
                "handle": cfg.get("handle"),
                "public_api_url": cfg.get("public_api_url"),
            },
            ensure_ascii=False,
        )

    elif name == "search_checkouts":
        query = (args.get("query") or "").lower()
        with session_scope() as s:
            all_rows = (
                s.execute(select(Checkout).order_by(Checkout.created_at.desc()).limit(200))
                .scalars()
                .all()
            )
            matches = []
            for c in all_rows:
                customer = c.request_payload.get("customer", {})
                searchable = json.dumps(
                    [
                        c.external_id or "",
                        c.invoice_slug or "",
                        c.transaction_nsu or "",
                        customer.get("name", ""),
                        customer.get("email", ""),
                    ]
                ).lower()
                if query in searchable:
                    matches.append(_serialize_checkout(c))
            return json.dumps(matches[:20], ensure_ascii=False, default=str)

    return json.dumps({"error": f"função desconhecida: {name}"})
