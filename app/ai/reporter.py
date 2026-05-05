import json
import time

from app.ai.client import ai_enabled, get_client, get_pro_model
from app.ai.tools import REPORT_PROMPT, TOOLS, execute_tool


def generate_report(kind: str = "daily") -> dict:
    """Gera relatorio executivo usando pro model.

    Args:
        kind: "daily" (hoje), "weekly" (7 dias), "full" (geral)
    """
    if not ai_enabled():
        return {"report": "AI features desabilitadas.", "enabled": False}

    kind_prompts = {
        "daily": "Gere um relatorio EXECUTIVO das vendas de HOJE.",
        "weekly": "Gere um relatorio EXECUTIVO das vendas dos ULTIMOS 7 DIAS.",
        "full": "Gere um relatorio EXECUTIVO completo das vendas (todo o historico).",
    }

    question = kind_prompts.get(kind, kind_prompts["daily"])
    question += (
        " Use TODAS as ferramentas disponiveis para cruzar dados. "
        "Inclua: resumo, metricas principais, taxa de conversao, "
        "clientes, tendencias, anomalias e recomendacoes. "
        "Seja DIRETO e ANALITICO. Destaque numeros importantes com negrito (**)."
    )

    model = get_pro_model()
    client = get_client()
    messages = [
        {"role": "system", "content": REPORT_PROMPT},
        {"role": "user", "content": question},
    ]

    t0 = time.time()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=TOOLS,
        temperature=0.3,
    )
    msg = response.choices[0].message

    tool_calls_executed = []
    while msg.tool_calls:
        messages.append(msg)
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            result = execute_tool(tc.function.name, args)
            tool_calls_executed.append({"tool": tc.function.name, "args": args})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.3,
        )
        msg = response.choices[0].message

    elapsed_ms = int((time.time() - t0) * 1000)

    return {
        "report": msg.content or "(sem resposta)",
        "enabled": True,
        "kind": kind,
        "model": model,
        "elapsed_ms": elapsed_ms,
        "tools_called": tool_calls_executed,
        "usage": {
            "prompt_tokens": response.usage.prompt_tokens if response.usage else None,
            "completion_tokens": response.usage.completion_tokens if response.usage else None,
        },
    }
