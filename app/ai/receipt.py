from app.ai.client import ai_enabled, get_client


def generate_receipt_message(
    customer_name: str, product: str, price_cents: int, receipt_url: str
) -> str:
    """Gera mensagem de confirmação personalizada."""
    if not ai_enabled():
        return f"Pagamento confirmado: {product} - R$ {price_cents / 100:.2f}"

    client = get_client()
    price_reais = price_cents / 100
    try:
        system_msg = (
            "Gere mensagem curta de confirmacao de pagamento em pt-BR. "
            "Seja amigavel mas profissional. Maximo 2 frases. "
            "Inclua nome do cliente, produto e valor. "
            "NAO inclua links."
        )
        user_msg = (
            f"Cliente: {customer_name}\n"
            f"Produto: {product}\n"
            f"Valor: R$ {price_reais:.2f}"
        )
        response = client.chat.completions.create(
            model="deepseek-v4-flash",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=150,
            temperature=0.7,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception:
        return (
            f"Oi {customer_name}! "
            f"Seu pagamento de R$ {price_reais:.2f} "
            f"pelo {product} foi confirmado."
        )
