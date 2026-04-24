# infinitepay

Integração com a InfinitePay para checkout por link. O projeto entrega uma API FastAPI, uma CLI `ipay`, SQLite para estado local e uma fila de retry para notificar o backend do usuário depois que a InfinitePay confirma o pagamento.

O fluxo foi validado com pagamento real: criação de link, webhook público, `payment_check`, atualização do checkout e entrega do backend webhook.

## Instalação local

```bash
cd ~/Desktop/infinitepay
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

O banco padrão fica em `~/.infinitepay/app.db`. Em produção use `IPAY_DB_PATH=/var/lib/infinitepay/app.db` ou outro caminho persistente.

## Conceitos

- `price` sempre é inteiro em centavos. R$ 1,00 = `100`.
- `external_id` é o ID único do pedido no seu sistema. Ele vira `order_nsu` na InfinitePay.
- `public_api_url` é a URL pública desta API, usada para receber o webhook da InfinitePay.
- `backend_webhook` é a URL do seu backend; depois do pagamento confirmado, o app faz `POST {backend_webhook}/{external_id}/`.
- `redirect_url` é para onde o cliente volta depois do checkout.
- A criação de checkout só é liberada depois que `public_api_url` for validada externamente.

## Bootstrap

Configure os defaults e gere o token de validação:

```bash
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay config set \
  --handle v7m \
  --price 100 \
  --description "Rosa Azul" \
  --redirect-url https://seusite.com/pago \
  --backend-webhook https://seusite.com/api/ipay \
  --public-api-url https://infinitepay.seudominio.com
```

A resposta inclui `validation_token`. Valide a URL pública a partir de fora do container:

```bash
curl 'https://infinitepay.seudominio.com/config/test/?token=<validation_token>'
```

Depois disso:

```bash
curl https://infinitepay.seudominio.com/health
# {"ok":true,"ready":true}
```

Alterar `public_api_url` sempre reseta a validação.

## API

Rode localmente:

```bash
ipay serve --host 0.0.0.0 --port 8000
```

### `GET /health`

Retorna `{ok, ready}`. `ready=false` indica que `public_api_url` ainda não foi validada.

### `GET /config/`

Mostra a configuração atual.

### `PATCH /config/`

Atualiza qualquer subconjunto de config.

```bash
curl -X PATCH http://127.0.0.1:8000/config/ \
  -H 'Content-Type: application/json' \
  -d '{
    "handle":"v7m",
    "price":100,
    "description":"Rosa Azul",
    "redirect_url":"https://seusite.com/pago",
    "backend_webhook":"https://seusite.com/api/ipay",
    "public_api_url":"https://infinitepay.seudominio.com"
  }'
```

### `GET /config/test/?token=...`

Valida `public_api_url`. Essa rota precisa estar acessível publicamente por HTTPS.

### `POST /checkout/`

Cria link real na InfinitePay. Campos omitidos caem nos defaults de `/config/`.

```bash
curl -X POST http://127.0.0.1:8000/checkout/ \
  -H 'Content-Type: application/json' \
  -d '{
    "external_id":"pedido-123",
    "price":101,
    "description":"Doce de amendoim",
    "customer": {
      "name":"Victor Maestri",
      "phone_number":"+5543996648750",
      "email":"victormaestri@gmail.com"
    },
    "address": {
      "cep":"84050360",
      "street":"Rua Ataulfo Alves",
      "number":"770",
      "neighborhood":"Estrela"
    }
  }'
```

Resposta esperada:

```json
{"external_id":"pedido-123","checkout_url":"https://checkout.infinitepay.io/v7m?..."}
```

A API pública da InfinitePay pode responder apenas `{"url":"..."}` na criação do link. Isso é sucesso. `success:false` explícito é tratado como erro.

### `GET /checkout/`

Lista checkouts locais.

### `GET /checkout/{external_id}/`

Retorna pendente ou pago:

```json
{"external_id":"pedido-123","is_paid":false,"checkout_url":"https://checkout.infinitepay.io/..."}
```

```json
{"external_id":"pedido-123","is_paid":true,"receipt_url":"https://recibo.infinitepay.io/..."}
```

### `POST /webhook/{external_id}/`

Entrada chamada pela InfinitePay. Não chame manualmente em produção.

Payload real recebido da InfinitePay:

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

O app valida que `payload.order_nsu == {external_id}` da rota antes de chamar `payment_check`. Se divergir, responde `400`.

Fluxo interno:

1. Loga payload inbound em `webhook_logs`.
2. Chama `POST https://api.infinitepay.io/invoices/public/checkout/payment_check` com `handle`, `order_nsu`, `transaction_nsu` e `slug=invoice_slug`.
3. Se `success:false`, responde `400` para a InfinitePay tentar novamente.
4. Se `success:true, paid:true`, marca o checkout como pago e enfileira o backend webhook.

Payload enviado ao `backend_webhook`:

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

## CLI

Configuração:

```bash
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay config show
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay config validate-token
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay config set \
  --handle v7m \
  --price 100 \
  --description "Rosa Azul" \
  --redirect-url https://seusite.com/pago \
  --backend-webhook https://seusite.com/api/ipay \
  --public-api-url https://infinitepay.seudominio.com
```

Criar cobrança:

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

Consultar:

```bash
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay checkout list
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay checkout get pedido-123
```

Worker dedicado, se não usar worker inline:

```bash
IPAY_DB_PATH=/var/lib/infinitepay/app.db ipay worker
```

## Endpoints internos de teste

Essas rotas existem para smoke test local e para testar o disparo de backend webhook sem depender do app final:

- `GET /test/redirect/` retorna `{"ok":true,"kind":"test_redirect"}`.
- `POST /test/backend-webhook/{external_id}/` grava o payload recebido em `webhook_logs` com `kind=test_backend_webhook`.

Use como `redirect_url` e `backend_webhook` temporários:

```bash
--redirect-url http://10.10.10.120:8000/test/redirect/ \
--backend-webhook http://10.10.10.120:8000/test/backend-webhook
```

Não é necessário expor `/test/*` publicamente.

## Proxy publico recomendado

Para produção, exponha apenas:

- `GET /health`
- `GET /config/test/`
- `POST /webhook/{external_id}/`

Mantenha `/checkout/`, `/config/` e `/test/*` acessíveis apenas na rede interna ou via operação controlada.

Exemplo de proxy host Nginx Proxy Manager customizado:

```nginx
location = /health {
  limit_except GET { deny all; }
  include conf.d/include/proxy.conf;
}

location = /config/test/ {
  limit_except GET { deny all; }
  include conf.d/include/proxy.conf;
}

location ~ ^/webhook/[A-Za-z0-9_\-.]+/?$ {
  limit_except POST { deny all; }
  include conf.d/include/proxy.conf;
}

location / {
  return 404;
}
```

## Deploy em LXC com systemd

Dentro do container Debian/Ubuntu, como root:

```bash
cd /root/infinitepay
bash deploy/install-lxc.sh
systemctl status infinitepay-api --no-pager -l
```

O script cria:

- usuario de sistema `infinitepay`
- app em `/opt/infinitepay`
- venv em `/opt/infinitepay/.venv`
- banco em `/var/lib/infinitepay/app.db`
- env em `/etc/infinitepay/env`
- servico `infinitepay-api` na porta `8000`
- servico opcional `infinitepay-worker`

Por padrão, o worker de retry roda inline no processo da API. Para usar worker dedicado, defina no `/etc/infinitepay/env`:

```bash
IPAY_RUN_INLINE_WORKER=false
```

Depois habilite:

```bash
systemctl enable --now infinitepay-worker
```

Use apenas um worker: inline ou dedicado.

Logs:

```bash
journalctl -u infinitepay-api -f
```

## Variáveis de ambiente

- `IPAY_DB_PATH`: caminho do SQLite. Default: `~/.infinitepay/app.db`.
- `IPAY_INFINITEPAY_BASE_URL`: default `https://api.infinitepay.io`.
- `IPAY_HTTP_TIMEOUT`: timeout HTTP em segundos. Default: `15`.
- `IPAY_WORKER_POLL_SECONDS`: intervalo do worker. Default: `5`.
- `IPAY_RUN_INLINE_WORKER`: default `true`; use `false` se habilitar `infinitepay-worker`.

## Troubleshooting

| Sintoma | Causa provável | Ação |
|---|---|---|
| `ready:false` | `public_api_url` ainda não validada | `ipay config validate-token` e `GET /config/test/?token=...` pela URL pública |
| `409` ao criar checkout | `external_id` duplicado ou app bloqueado | `ipay checkout get <external_id>` e `ipay config show` |
| `502` na criação | InfinitePay recusou ou não retornou URL | Ver `webhook_logs` com `kind=create_link` |
| Pagamento não vira pago | Webhook não chegou ou `payment_check` falhou | Ver `kind=infinitepay_webhook` e `kind=payment_check` |
| Backend não recebeu | Retry pendente ou URL errada | Ver `outbound_jobs.last_error`, `attempts`, `delivered_at` |

Os logs ficam em `webhook_logs`; retries ficam em `outbound_jobs`.
