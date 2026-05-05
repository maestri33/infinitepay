import json
import logging

from app.ai.client import ai_enabled, get_client, get_model, get_pro_model

logger = logging.getLogger(__name__)


def check_anomaly(external_id: str, payload: dict) -> dict:
    """Triagem rapida com flash. Retorna {alert: bool, reason: str}."""
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
            model=get_model(),
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            max_tokens=100,
            temperature=0.1,
        )
        result = json.loads(response.choices[0].message.content or "{}")
        alert = result.get("alert", False)
        reason = result.get("reason", "")

        if alert:
            deep = _deep_analysis(external_id, payload, reason)
            return {
                "alert": True,
                "reason": reason,
                "deep_analysis": deep,
            }

        return {"alert": False, "reason": ""}
    except Exception:
        return {"alert": False, "reason": "ai check failed"}


def _deep_analysis(external_id: str, payload: dict, flash_reason: str) -> str:
    """Analise profunda com pro quando flash detecta anomalia."""
    try:
        client = get_client()
        system_msg = (
            "Voce e um especialista em prevencao a fraudes em pagamentos. "
            "Um sistema de triagem rapida flagou este pagamento como suspeito. "
            "Analise profundamente o payload e explique: "
            "1) Qual o risco real (baixo/medio/alto)? "
            "2) Que padrao especifico de fraude pode ser? "
            "3) Que acao recomenda (ignorar, revisar manualmente, cancelar)? "
            "Responda em pt-BR, maximo 4 frases, tom profissional."
        )
        user_msg = (
            f"Motivo do alerta inicial: {flash_reason}\n"
            f"external_id: {external_id}\n"
            f"payload: {json.dumps(payload, default=str)}"
        )
        response = client.chat.completions.create(
            model=get_pro_model(),
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=250,
            temperature=0.3,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("deep anomaly analysis failed: %s", exc)
        return ""
