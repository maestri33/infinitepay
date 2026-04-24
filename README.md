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

### Auditoria do webhook

Quando um pagamento real funciona, a sequência esperada em `webhook_logs` é:

1. `kind=create_link`: checkout criado na InfinitePay, com `webhook_url` apontando para `public_api_url`.
2. `kind=infinitepay_webhook`: payload recebido da InfinitePay.
3. `kind=payment_check`: validação feita contra `https://api.infinitepay.io/invoices/public/checkout/payment_check`.
4. `kind=test_backend_webhook` ou log do seu backend real: confirmação repassada ao destino configurado em `backend_webhook`.

Na LXC principal, consulte por Python/SQLAlchemy:

```bash
cd /opt/infinitepay
IPAY_DB_PATH=/var/lib/infinitepay/app.db /opt/infinitepay/.venv/bin/python - <<'PY'
from sqlalchemy import select
from infinitepay.db.models import WebhookLog, OutboundJob
from infinitepay.db.session import session_scope

external_id = "pedido-123"
with session_scope() as s:
    logs = s.execute(
        select(WebhookLog)
        .where(WebhookLog.external_id == external_id)
        .order_by(WebhookLog.id)
    ).scalars().all()
    for row in logs:
        print(row.id, row.direction, row.kind, row.created_at, row.payload, row.response)

    jobs = s.execute(
        select(OutboundJob)
        .where(OutboundJob.external_id == external_id)
        .order_by(OutboundJob.id)
    ).scalars().all()
    for job in jobs:
        print(job.id, job.url, job.attempts, job.delivered_at, job.last_error)
PY
```

Status codes importantes:

- `200 {"ok":true,"paid":true}`: webhook validado, checkout marcado como pago e backend webhook enfileirado.
- `200 {"ok":true,"paid":false}`: InfinitePay confirmou o webhook, mas `payment_check` ainda não indica pago.
- `400 {"detail":"payload de webhook incompleto..."}`: faltou `transaction_nsu` ou `invoice_slug`.
- `400 {"detail":"order_nsu do webhook diverge..."}`: URL e payload não pertencem ao mesmo pedido.
- `400 {"detail":"webhook não pôde ser validado"}`: `payment_check` retornou `success:false`.
- `404 {"detail":"checkout desconhecido..."}`: a InfinitePay chamou um `external_id` que não existe no SQLite local.

O `backend_webhook` é assíncrono. Se o destino responder `2xx`, `outbound_jobs.delivered_at` é preenchido. Se responder erro ou der timeout, `last_error` guarda o motivo e o worker tenta de novo com backoff.

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

## CLI remota em outra LXC

A CLI `ipay` nativa fala direto com o SQLite local, então ela deve ser usada na LXC principal. Para operar de outra LXC sem copiar banco nem liberar `/config/`, use `ipay-remote`.

`ipay-remote` chama a API principal por HTTP interno e implementa somente:

- `health`
- `checkout create`
- `checkout list`
- `checkout get`

Configuração continua exclusiva da LXC principal.

### Instalar na LXC remota

Na outra LXC:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/maestri33/infinitepay/main/install_cli.sh) http://10.10.10.120:8000
```

O instalador cria `/opt/infinitepay-remote`, instala o pacote em venv e gera `/usr/local/bin/ipay-remote` com `IPAY_API_URL` apontando para a API principal.

Se preferir instalar a partir de clone local:

```bash
git clone https://github.com/maestri33/infinitepay.git /tmp/infinitepay
cd /tmp/infinitepay
bash deploy/install-remote-cli.sh http://10.10.10.120:8000
```

Também dá para usar sem wrapper:

```bash
export IPAY_API_URL=http://10.10.10.120:8000
ipay-remote health
```

### Usar a CLI remota

```bash
ipay-remote health
```

Criar cobrança real pela API principal:

```bash
ipay-remote checkout create \
  --external-id pedido-123 \
  --name "Victor Maestri" \
  --email victormaestri@gmail.com \
  --phone +5543996648750 \
  --price 101 \
  --description "Doce de amendoim" \
  --address-json '{"cep":"84050360","street":"Rua Ataulfo Alves","number":"770","neighborhood":"Estrela"}'
```

Listar e consultar:

```bash
ipay-remote checkout list
ipay-remote checkout get pedido-123
```

Se `price` e `description` forem omitidos, a API principal usa os defaults configurados na LXC nativa. O webhook público e o `backend_webhook` continuam sendo processados pela LXC principal; a LXC remota só pede a criação/consulta via HTTP.

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

## Nginx / exposição pública

A API pode escutar internamente em `0.0.0.0:8000`, mas a internet não precisa acessar tudo. Em produção, exponha apenas os endpoints que a InfinitePay ou o monitoramento externo precisam chamar:

- `GET /health`: health público simples.
- `GET /config/test/`: validação externa do `public_api_url`.
- `POST /webhook/{external_id}/`: webhook real da InfinitePay.

Mantenha internos:

- `/checkout/`: cria cobranças reais; deve ficar atrás do seu backend, VPN, SSH, automação interna ou CLI.
- `/config/`: altera handle, preço, URLs e validação; nunca exponha publicamente sem autenticação.
- `/test/*`: smoke tests internos; não há motivo para expor.

### Apontamento do proxy

No Nginx Proxy Manager, crie um Proxy Host para o domínio público, por exemplo `infinitepay.seudominio.com`, apontando para o LXC que roda a API:

```text
Forward Hostname / IP: 10.10.10.120
Forward Port: 8000
Scheme: http
SSL: Let's Encrypt ativo
Force SSL: ativo
```

Na aba Advanced, deixe o `location /` negando tudo e libere somente os paths abaixo. O exemplo inclui os headers que o NPM costuma gerar; se o seu template já injeta esses headers via `include conf.d/include/proxy.conf`, mantenha o include.

```nginx
# default: nega tudo que nao foi liberado explicitamente
location / {
  return 404;
}

# health publico - apenas GET
location = /health {
  limit_except GET { deny all; }
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection $http_connection;
  proxy_http_version 1.1;
  include conf.d/include/proxy.conf;
}

# validacao do public_api_url - apenas GET
location = /config/test/ {
  limit_except GET { deny all; }
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection $http_connection;
  proxy_http_version 1.1;
  include conf.d/include/proxy.conf;
}

# webhook da InfinitePay - apenas POST
location ~ ^/webhook/[A-Za-z0-9_\-.]+/?$ {
  limit_except POST { deny all; }
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
  proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  proxy_set_header X-Forwarded-Proto $scheme;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection $http_connection;
  proxy_http_version 1.1;
  include conf.d/include/proxy.conf;
}
```

Depois de editar, teste e recarregue o Nginx. Em NPM rodando dentro de Docker:

```bash
docker exec nginx-proxy-manager-npm-1 nginx -t
docker exec nginx-proxy-manager-npm-1 nginx -s reload
```

### Respostas públicas esperadas

Com `public_api_url` já validada:

```bash
curl -i https://infinitepay.seudominio.com/health
# HTTP/2 200
# {"ok":true,"ready":true}
```

Antes de validar, `ready` será `false`:

```json
{"ok":true,"ready":false}
```

Validação externa do domínio:

```bash
curl -i 'https://infinitepay.seudominio.com/config/test/?token=<validation_token>'
# HTTP/2 200
# {"ok":true,"validated":true}
```

Token errado ou URL ainda não configurada:

```bash
# HTTP/2 400
{"detail":"token inválido ou public_api_url não configurado"}
```

Rotas não expostas devem responder pelo proxy, não pela aplicação:

```bash
curl -i https://infinitepay.seudominio.com/checkout/
# HTTP/2 404
```

Método errado em rota exposta deve ser bloqueado pelo Nginx:

```bash
curl -i -X POST https://infinitepay.seudominio.com/health
# HTTP/2 403
```

Webhook real bem processado pela InfinitePay:

```bash
# POST /webhook/pedido-123/
# HTTP/2 200
{"ok":true,"paid":true}
```

Webhook com `order_nsu` diferente do `{external_id}` da URL:

```bash
# HTTP/2 400
{
  "detail":"order_nsu do webhook diverge do external_id da rota",
  "external_id":"pedido-correto",
  "order_nsu":"outro-pedido"
}
```

### Webhook interno do seu backend

O `backend_webhook` não é chamado pela InfinitePay nem precisa ser público para ela. Ele é chamado por esta aplicação depois que o webhook da InfinitePay foi validado com `payment_check`.

Se você configurar:

```bash
--backend-webhook https://app.seudominio.com/api/ipay
```

então, para `external_id=pedido-123`, esta aplicação fará:

```text
POST https://app.seudominio.com/api/ipay/pedido-123/
```

com payload:

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

O backend deve responder `2xx` para marcar o job como entregue. Qualquer resposta não-2xx ou timeout fica em `outbound_jobs.last_error` e será retentada com backoff exponencial. O backend deve ser idempotente por `external_id` e/ou `transaction_nsu`, porque retries podem repetir a entrega.

Para teste sem o app final, use o webhook interno local:

```bash
--backend-webhook http://10.10.10.120:8000/test/backend-webhook
```

Ele grava o payload em `webhook_logs` com `kind=test_backend_webhook` e responde:

```json
{"ok":true,"external_id":"pedido-123"}
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
