# infinitepay

Integração com a InfinitePay (checkout via link) — **FastAPI + Typer CLI**, ambas usando a mesma lógica central. Persistência em **SQLite**. Fila de retry para o webhook do seu backend também em SQLite (sem Redis).

## Instalação

```bash
cd ~/Desktop/infinitepay
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
```

DB e diretório ficam em `~/.infinitepay/app.db` (sobrescreva com `IPAY_DB_PATH`).

## Bootstrap (obrigatório antes de usar)

Toda rota (exceto `/health`, `/config/*`) fica **bloqueada com 503** até o `public_api_url` ser configurado **e validado**.

1. Configure os defaults + a URL pública desta API:

```bash
ipay config set \
  --handle v7m \
  --price 100 \
  --description "Venda padrão" \
  --redirect-url https://seusite.com/pago \
  --backend-webhook https://seusite.com/api/ipay \
  --public-api-url https://minha-api-publica.com
```

A resposta traz um `validation_token`. Agora um serviço **externo** deve bater:

```
GET https://minha-api-publica.com/config/test/?token=<validation_token>
```

Se chegar, a API marca como validado e libera o resto. Em dev dá pra usar `ipay config force-validate`.

2. Altere qualquer campo depois com outro `ipay config set ...` ou `PATCH /config/`. Mudar `public_api_url` reinicia o ciclo de validação.

## Uso via API

```bash
ipay serve --reload
```

- `GET /config/` · `PATCH /config/`
- `GET /config/test/?token=...`
- `POST /checkout/` — cria checkout (body merge com config)
- `GET  /checkout/` — lista
- `GET  /checkout/{external_id}/` — retorna `checkout_url` ou `receipt_url` conforme `is_paid`
- `POST /webhook/{external_id}/` — recebe webhook da InfinitePay

### Body do POST /checkout/

```json
{
  "external_id": "pedido-123",
  "price": 1000,
  "description": "Camiseta",
  "customer": {"name": "João Silva", "email": "joao@email.com", "phone_number": "+5511999887766"},
  "address": {"cep": "12345-678", "street": "Rua X", "neighborhood": "Centro", "number": "10"}
}
```

- Campos ausentes no body caem nos valores do `/config/`.
- `public_api_url` **nunca** pode vir no body.
- Pra múltiplos produtos, mande `items: [...]` (sobrescreve `price`/`description`).
- `external_id` duplicado → 409.

## Uso via CLI

```bash
ipay config show
ipay checkout create --external-id pedido-123 \
  --name "João" --email joao@email.com --phone +5511999887766
ipay checkout list
ipay checkout get pedido-123
ipay worker     # processa fila de retries do backend_webhook
```

## Fluxo do webhook (entrada da InfinitePay)

1. Recebe `POST /webhook/{external_id}/` → loga o payload.
2. Chama `POST https://api.infinitepay.io/invoices/public/checkout/payment_check` com `{handle, order_nsu, transaction_nsu, slug=invoice_slug}`.
3. Se `success:false` → responde **400** (InfinitePay re-enviará).
4. Se `success:true, paid:true` → atualiza checkout (`is_paid`, `receipt_url`, `transaction_nsu`, `invoice_slug`, `capture_method`, `installments`) e **enfileira** um POST para `backend_webhook/{external_id}/` com `{paid:true, ...}`. Retries exponenciais (1m→24h).

## Logs

Tudo fica em `webhook_logs` (SQLite): payloads de entrada, chamadas para `/checkout/links`, `/payment_check`, e disparos de `backend_webhook`.

## Deploy em LXC (systemd)

Dentro do container (Debian/Ubuntu) como root:

```bash
# copie o repo pro container (rsync, scp, git clone...) e:
cd /caminho/do/repo && bash deploy/install-lxc.sh
```

O script cria usuário `infinitepay`, venv em `/opt/infinitepay/.venv`, SQLite em `/var/lib/infinitepay/app.db`, env em `/etc/infinitepay/env`, e sobe o service `infinitepay-api` no systemd (porta 8000).

**Worker**: por padrão o worker de retry roda **inline** no processo da API (via lifespan asyncio). Se quiser escalar/separar, edite `/etc/infinitepay/env` → `IPAY_RUN_INLINE_WORKER=false` e habilite o service dedicado:

```bash
systemctl enable --now infinitepay-worker
```

⚠️ Só rode **um** worker (inline OU dedicado). Os dois ao mesmo tempo podem disparar entregas duplicadas.

Logs: `journalctl -u infinitepay-api -f`.

### Docker (alternativa)

```bash
docker build -t infinitepay .
docker run -d --name ipay -p 8000:8000 -v ipay-data:/data infinitepay
```

## Testes

```bash
pip install -e '.[dev]'
pytest -q
```

## Variáveis de ambiente

- `IPAY_DB_PATH` — path do SQLite (default `~/.infinitepay/app.db`)
- `IPAY_INFINITEPAY_BASE_URL` — default `https://api.infinitepay.io`
- `IPAY_HTTP_TIMEOUT` — segundos (default 15)
- `IPAY_WORKER_POLL_SECONDS` — default 5
- `IPAY_RUN_INLINE_WORKER` — default `true`; `false` se usar o service dedicado
