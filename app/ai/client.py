from openai import OpenAI

from app.config import get_settings


def get_client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.deepseek_api_key, base_url="https://api.deepseek.com")


def ai_enabled() -> bool:
    s = get_settings()
    return s.deepseek_ai_features_enabled and bool(s.deepseek_api_key)


def get_model() -> str:
    return get_settings().deepseek_model
