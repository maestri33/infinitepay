import json
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from app.db import session_scope
from app.models.models import Checkout

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_checkouts",
            "description": "Lista ate 50 checkouts recentes com status, cliente, valores e datas.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stats",
            "description": "Estatisticas basicas: total, pagos, pendentes, pagos hoje.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_config",
            "description": "Retorna configuracao da loja: produto, preco, handle, URLs.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_checkouts",
            "description": "Busca checkouts por nome, email, external_id ou slug de fatura.",
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
    {
        "type": "function",
        "function": {
            "name": "get_conversion_stats",
            "description": (
                "Taxa de conversao (pagos/total) por periodo: hoje, ultimos 7 dias, "
                "ultimos 30 dias. Use para analise de tendencias."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_timeline",
            "description": (
                "Linha do tempo dos ultimos 100 eventos (checkouts criados + pagamentos). "
                "Use para entender a sequencia de acontecimentos."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_insights",
            "description": (
                "Dados agregados de clientes: total de clientes distintos, "
                "top compradores (pagos), clientes com checkout pendente, "
                "emails e nomes para analise de perfil."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

SYSTEM_PROMPT = """Você é um assistente de análises financeiras da loja do Pr. Maestri.
O produto vendido é "E-book do Pr. Maestri" (R$ 1,04 via InfinitePay).
Responda SEMPRE em português do Brasil, de forma direta e concisa.
Use as funções disponíveis para consultar dados reais antes de responder.
Apresente valores em reais (R$) com 2 casas decimais.
Se a pergunta envolver "hoje", use a data atual. Se for "semana", considere os últimos 7 dias.
Se for uma pergunta analítica complexa, use multiplas ferramentas para cruzar dados."""

REPORT_PROMPT = """Você é um analista financeiro sênior da loja do Pr. Maestri.
Gere relatórios executivos em português do Brasil.
Analise os dados com profundidade:
- Identifique tendências e padrões nos checkouts
- Compare períodos e calcule taxas de conversão
- Destaque anomalias ou pontos de atenção
- Sugira ações baseadas nos dados
- Segmente clientes quando relevante
Use TODAS as ferramentas disponíveis para cruzar informações.
Formato: markdown com seções claras, use negrito para números importantes."""


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
            created_today = s.execute(
                select(func.count(Checkout.id)).where(
                    Checkout.created_at >= today_start,
                )
            ).scalar()

            return json.dumps(
                {
                    "total_checkouts": total,
                    "pagos": paid,
                    "pendentes": pending,
                    "pagos_hoje": paid_today,
                    "criados_hoje": created_today,
                    "preco_unitario": 104,
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

    elif name == "get_conversion_stats":
        with session_scope() as s:
            today = date.today()
            today_start = datetime.combine(today, datetime.min.time())
            week_start = datetime.combine(today - timedelta(days=7), datetime.min.time())
            month_start = datetime.combine(today - timedelta(days=30), datetime.min.time())

            def conv(start):
                total = s.execute(
                    select(func.count(Checkout.id)).where(Checkout.created_at >= start)
                ).scalar()
                paid = s.execute(
                    select(func.count(Checkout.id)).where(
                        Checkout.created_at >= start, Checkout.is_paid.is_(True)
                    )
                ).scalar()
                rate = round(paid / total * 100, 1) if total else 0.0
                return {"total": total, "pagos": paid, "taxa_conversao_pct": rate}

            return json.dumps(
                {
                    "hoje": conv(today_start),
                    "ultimos_7_dias": conv(week_start),
                    "ultimos_30_dias": conv(month_start),
                },
                ensure_ascii=False,
            )

    elif name == "get_timeline":
        with session_scope() as s:
            rows = (
                s.execute(
                    select(Checkout)
                    .order_by(Checkout.created_at.desc())
                    .limit(100)
                )
                .scalars()
                .all()
            )
            events = []
            for c in rows:
                customer = c.request_payload.get("customer", {})
                name = customer.get("name", "anonimo")
                events.append(
                    {
                        "external_id": c.external_id,
                        "cliente": name,
                        "is_paid": c.is_paid,
                        "criado_em": c.created_at.isoformat() if c.created_at else None,
                        "pago_em": c.updated_at.isoformat() if c.is_paid and c.updated_at else None,
                        "capture_method": c.capture_method,
                    }
                )
            return json.dumps(events, ensure_ascii=False, default=str)

    elif name == "get_customer_insights":
        with session_scope() as s:
            all_rows = (
                s.execute(select(Checkout).order_by(Checkout.created_at.desc()).limit(500))
                .scalars()
                .all()
            )

            customers = {}
            for c in all_rows:
                cust = c.request_payload.get("customer", {})
                name = cust.get("name", "anonimo").strip() or "anonimo"
                email = cust.get("email", "desconhecido").strip() or "desconhecido"
                key = email.lower()
                if key not in customers:
                    customers[key] = {"nome": name, "email": email, "checkouts": 0, "pagos": 0}
                    if c.is_paid:
                        customers[key]["pagos"] += 1
                    customers[key]["checkouts"] += 1
                else:
                    if c.is_paid:
                        customers[key]["pagos"] += 1
                    customers[key]["checkouts"] += 1

            paid_customers = [v for v in customers.values() if v["pagos"] > 0]
            pending_customers = [
                v for v in customers.values() if v["checkouts"] > v["pagos"]
            ]

            return json.dumps(
                {
                    "total_clientes_distintos": len(customers),
                    "clientes_que_pagaram": len(paid_customers),
                    "clientes_com_pendencia": len(pending_customers),
                    "top_compradores": sorted(
                        paid_customers, key=lambda x: x["pagos"], reverse=True
                    )[:10],
                    "clientes_pendentes": sorted(
                        pending_customers, key=lambda x: x["checkouts"] - x["pagos"], reverse=True
                    )[:10],
                },
                ensure_ascii=False,
            )

    return json.dumps({"error": f"função desconhecida: {name}"})
