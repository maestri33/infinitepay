import json

from app.ai.client import ai_enabled, get_client


def check_anomaly(external_id: str, payload: dict) -> dict:
    """Verifica anomalias no pagamento. Retorna {alert: bool, reason: str}."""
    if not ai_enabled():
        return {"alert": False, "reason": "ai disabled"}

    client = get_client()
    try:
        system_msg = (
            "Analise este pagamento e detecte anomalias. "
            "Responda SOMENTE com JSON valido: "
            '{"alert": false, "reason": ""} ou '
            '{"alert": true, "reason": "motivo curto em pt-BR"}. '
            "Anomalias: valor suspeito, dados inconsistentes, "
            "nome estranho, email invalido aparente."
        )
        user_msg = (
            f"external_id: {external_id}\n"
            f"payload: {json.dumps(payload, default=str)}"
        )
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            max_tokens=100,
            temperature=0.1,
        )
        result = json.loads(response.choices[0].message.content or "{}")
        return {"alert": result.get("alert", False), "reason": result.get("reason", "")}
    except Exception:
        return {"alert": False, "reason": "ai check failed"}
