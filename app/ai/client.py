from openai import OpenAI

from app.config import get_settings


def get_client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.deepseek_api_key, base_url="https://api.deepseek.com")


def ai_enabled() -> bool:
    s = get_settings()
    return s.deepseek_ai_features_enabled and bool(s.deepseek_api_key)


def get_model() -> str:
    """Modelo rápido/barato para tarefas simples (tool calling, classificacao, geracao)."""
    return get_settings().deepseek_model


def get_pro_model() -> str:
    """Modelo avancado para analise profunda, reports, raciocinio multi-step."""
    return get_settings().deepseek_pro_model
