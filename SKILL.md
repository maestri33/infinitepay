---
name: infinitepay
description: Gerar e acompanhar links de pagamento InfinitePay por CLI `ipay` ou API HTTP local, receber webhooks reais, validar pagamento via `payment_check`, e repassar confirmação para o backend do usuário.
---

# infinitepay — skill de uso

App FastAPI + Typer CLI + SQLite para checkout InfinitePay por link. CLI e API usam a mesma lógica central.

Use esta skill quando o usuário pedir para criar cobrança, gerar link de pagamento, consultar pagamento, configurar `handle`, `redirect_url`, `backend_webhook`, `public_api_url`, ou depurar webhooks/checkouts InfinitePay.

## Regras fundamentais

1. Preço sempre em centavos. R$ 1,00 = `100`. Nunca envie float.
2. `external_id` é o ID do pedido do usuário. Ele vira `order_nsu` na InfinitePay e deve ser único.
3. `public_api_url` só é configurado em `/config/`; nunca aceite no body de checkout.
4. Antes de criar checkout, `public_api_url` precisa estar configurada e validada por `GET {public_api_url}/config/test/?token=...`.
5. Campos de `/config/` viram defaults: `handle`, `price`, `quantity`, `description`, `redirect_url`, `backend_webhook`.
6. Body de checkout prevalece sobre config, exceto `public_api_url`, que é proibido no body.
7. A resposta real de criação da InfinitePay pode ser somente `{"url":"https://checkout.infinitepay.io/..."}`. Isso é sucesso. Só trate como falha se HTTP >= 400, `success:false`, ou ausência de `url`/`checkout_url`.
8. No webhook real, exija `payload.order_nsu == external_id` da rota antes de validar pagamento.

## Bootstrap obrigatório

```bash
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay config set \
  --handle v7m \
  --price 100 \
  --description "Rosa Azul" \
  --redirect-url https://site-do-user.com/pago \
  --backend-webhook https://site-do-user.com/api/ipay \
  --public-api-url https://infinitepay.site-do-user.com
```

A resposta traz `validation_token`. Valide externamente:

```bash
curl 'https://infinitepay.site-do-user.com/config/test/?token=<validation_token>'
```

Só prossiga se:

```bash
curl https://infinitepay.site-do-user.com/health
# {"ok":true,"ready":true}
```

Se alterar `public_api_url`, a validação reseta.

## CLI essencial

```bash
ipay serve --host 0.0.0.0 --port 8000
ipay worker

ipay config show
ipay config set --handle v7m --price 100 --description "Rosa Azul" --redirect-url https://site/pago --backend-webhook https://site/api/ipay --public-api-url https://api-publica
ipay config validate-token
ipay config force-validate  # apenas dev
```

Criar checkout real:

```bash
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay checkout create \
  --external-id pedido-123 \
  --name "Victor Maestri" \
  --email victormaestri@gmail.com \
  --phone +5543996648750 \
  --price 101 \
  --description "Doce de amendoim" \
  --address-json '{"cep":"84050360","street":"Rua Ataulfo Alves","number":"770","neighborhood":"Estrela"}'
```

Retorne o `checkout_url` ao cliente e guarde o `external_id`.

Consultar:

```bash
ipay checkout list
ipay checkout get pedido-123
```

## API endpoints

Base interna: `http://host:8000`.

Rotas:

- `GET /health`: `{ok, ready}`.
- `GET /config/`: mostra config.
- `PATCH /config/`: atualiza config e retorna `validation_token` quando precisa validar.
- `GET /config/test/?token=...`: valida URL pública.
- `POST /checkout/`: cria checkout real na InfinitePay.
- `GET /checkout/`: lista checkouts.
- `GET /checkout/{external_id}/`: retorna `checkout_url` se pendente ou `receipt_url` se pago.
- `POST /webhook/{external_id}/`: entrada da InfinitePay. Não chamar manualmente em produção.
- `GET /test/redirect/`: endpoint interno de teste.
- `POST /test/backend-webhook/{external_id}/`: endpoint interno de teste que grava payload em `webhook_logs`.

Body mínimo de checkout:

```json
{
  "external_id": "pedido-123",
  "customer": {
    "name": "Victor Maestri",
    "phone_number": "+5543996648750",
    "email": "victormaestri@gmail.com"
  }
}
```

Body completo:

```json
{
  "external_id": "pedido-123",
  "handle": "v7m",
  "price": 101,
  "description": "Doce de amendoim",
  "items": [{"quantity":1,"price":101,"description":"Doce de amendoim"}],
  "redirect_url": "https://site.com/pago",
  "backend_webhook": "https://site.com/api/ipay",
  "customer": {"name":"Victor Maestri","email":"victormaestri@gmail.com","phone_number":"+5543996648750"},
  "address": {"cep":"84050360","street":"Rua Ataulfo Alves","neighborhood":"Estrela","number":"770"}
}
```

Nunca inclua `public_api_url` no body.

## Payload real do webhook InfinitePay

```json
{
  "items": [
    {
      "price": 101,
      "quantity": 1,
      "description": "Doce de amendoim",
      "product_reference": null
    }
  ],
  "amount": 101,
  "order_nsu": "pedido-123",
  "paid_amount": 106,
  "receipt_url": "https://recibo.infinitepay.io/a4495b16-c593-4de2-9ff0-83ce89acd0d8",
  "installments": 1,
  "invoice_slug": "VtRJSJkMd",
  "capture_method": "credit_card",
  "transaction_nsu": "a4495b16-c593-4de2-9ff0-83ce89acd0d8"
}
```

Processamento:

1. Logar payload inbound.
2. Validar `order_nsu` contra `{external_id}` da URL.
3. Chamar `payment_check` com `handle`, `order_nsu`, `transaction_nsu`, `slug=invoice_slug`.
4. Se `success:true, paid:true`, marcar checkout como pago.
5. Enfileirar `POST {backend_webhook}/{external_id}/`.

Payload do backend webhook:

```json
{
  "external_id": "pedido-123",
  "paid": true,
  "receipt_url": "https://recibo.infinitepay.io/...",
  "transaction_nsu": "...",
  "invoice_slug": "...",
  "capture_method": "credit_card",
  "installments": 1,
  "amount": 101,
  "paid_amount": 106
}
```

## Produção / proxy

Exponha publicamente apenas:

- `GET /health`
- `GET /config/test/`
- `POST /webhook/{external_id}/`

Mantenha `/checkout/`, `/config/` e `/test/*` internos.

## Playbooks

### Criar cobrança

1. Confirme `ready:true`.
2. Converta valor para centavos.
3. Use `external_id` real e único.
4. Use `ipay checkout create` ou `POST /checkout/`.
5. Entregue só o `checkout_url` ao cliente.

### Consultar pagamento

Use `ipay checkout get <external_id>` ou `GET /checkout/{external_id}/`. Se houver `receipt_url`, o pagamento foi confirmado.

### Debug webhook

Verifique:

- `webhook_logs.kind=create_link`
- `webhook_logs.kind=infinitepay_webhook`
- `webhook_logs.kind=payment_check`
- `outbound_jobs.delivered_at`, `attempts`, `last_error`

### Teste interno sem app final

Configure temporariamente:

```bash
--redirect-url http://10.10.10.120:8000/test/redirect/ \
--backend-webhook http://10.10.10.120:8000/test/backend-webhook
```

O teste de backend webhook grava em `webhook_logs` com `kind=test_backend_webhook`.

## Erros comuns

- `ready:false`: valide `public_api_url` externamente.
- `409`: `external_id` duplicado ou app não pronto.
- `502` na criação: ver resposta em `webhook_logs.kind=create_link`.
- Webhook 400: payload incompleto, `order_nsu` divergente, ou `payment_check success:false`.
- Backend webhook duplicado: pode acontecer em retries; o backend deve ser idempotente por `external_id`/`transaction_nsu`.
