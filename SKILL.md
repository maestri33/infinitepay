---
name: infinitepay
description: Gerar e acompanhar links de pagamento InfinitePay (checkout) via CLI `ipay` ou API HTTP local. Use quando o usuário pedir para criar cobrança, gerar link de pagamento, consultar status de um pedido, configurar handle/redirect/webhook da integração InfinitePay, ou inspecionar checkouts já criados.
---

# infinitepay — skill de uso

App local (FastAPI + Typer CLI, SQLite) que embala a API pública da InfinitePay. CLI e API chamam a **mesma lógica** — escolha conforme contexto:

- **CLI (`ipay`)** — operações locais, scripts, debugging, configuração inicial
- **API HTTP** — integração com backend do usuário, webhooks, automações externas

Os dois compartilham o mesmo SQLite (`$IPAY_DB_PATH`, default `~/.infinitepay/app.db`).

---

## Regras fundamentais

1. **Preços em centavos.** R$ 10,00 = `1000`. Nunca envie float.
2. **`external_id` é o ID do pedido no sistema do usuário.** Vira `order_nsu` na InfinitePay. Deve ser único — duplicado retorna 409.
3. **`public_api_url` só pode ser alterada via `/config/`.** Nunca aceite no body de criação de checkout. É a URL pública desta própria API (onde a InfinitePay mandará webhooks).
4. **Bootstrap lock.** Enquanto `public_api_url` não estiver configurada **e validada**, todas as rotas (exceto `/health`, `/config/*`) retornam **503**. Valide antes de tentar criar checkout.
5. **Config como default.** Campos salvos em `/config/` (`handle`, `price`, `description`, `redirect_url`, `backend_webhook`) são usados quando omitidos no body do checkout. Body sempre prevalece sobre config.
6. **Não invente campos.** Schema da InfinitePay é fechado: `handle`, `items[]`, `order_nsu`, `redirect_url`, `webhook_url`, `customer`, `address`.

---

## Fluxo de configuração inicial (obrigatório)

Antes de qualquer checkout:

```bash
ipay config set \
  --handle SEU_HANDLE \
  --price 100 \
  --description "Default" \
  --redirect-url https://site-do-user.com/pago \
  --backend-webhook https://site-do-user.com/api/ipay \
  --public-api-url https://url-publica-desta-api.com
```

A resposta traz `validation_token`. A URL pública **precisa** ser validada por uma chamada externa:

```
GET {public_api_url}/config/test/?token={validation_token}
```

Só então o app libera `POST /checkout/`. Em dev, `ipay config force-validate` pula essa etapa.

**Ao alterar `public_api_url`, a validação é resetada** — repita o fluxo.

---

## CLI — comandos essenciais

```bash
ipay serve --host 0.0.0.0 --port 8000    # sobe FastAPI (uvicorn)
ipay worker                               # roda fila de retry do backend_webhook (se separado)

ipay config show
ipay config set --handle X --price 100 ... [--public-api-url https://...]
ipay config validate-token       # mostra token pendente
ipay config force-validate       # apenas dev

ipay checkout create \
  --external-id pedido-123 \
  --name "João Silva" \
  --email joao@email.com \
  --phone +5511999887766 \
  [--price 1500] [--description "Camiseta"] \
  [--items-json '[{"quantity":1,"price":1500,"description":"X"}]'] \
  [--address-json '{"cep":"12345678","street":"R","neighborhood":"C","number":"1"}']

ipay checkout list
ipay checkout get pedido-123
```

`ipay checkout create` retorna `{"external_id": "...", "checkout_url": "https://..."}` — envie o `checkout_url` ao cliente.

---

## API — endpoints

Base: `http://host:8000` (ou `public_api_url` externamente).

### `GET /health` → `{ok, ready}`
`ready=false` indica que o bootstrap lock está ativo.

### `GET /config/` · `PATCH /config/`
Body PATCH aceita qualquer subconjunto dos campos. Exemplo:
```json
PATCH /config/
{"handle":"v7m","price":100,"public_api_url":"https://api.ex.com"}
```
Se alterou `public_api_url`, a resposta traz `validation_token` e `next_step`.

### `GET /config/test/?token=...`
Valida `public_api_url`. Dispare **externamente** (CURL de outra máquina, serviço de monitoramento, etc.) para provar que a URL pública realmente chega neste app.

### `POST /checkout/`
Body mínimo (os demais campos caem no `/config/`):
```json
{
  "external_id": "pedido-123",
  "customer": {
    "name": "João Silva",
    "email": "joao@email.com",
    "phone_number": "+5511999887766"
  }
}
```
Body completo:
```json
{
  "external_id": "pedido-123",
  "handle": "v7m",
  "price": 1500,
  "description": "Camiseta azul",
  "items": [{"quantity":1,"price":1500,"description":"Camiseta azul"}],
  "redirect_url": "https://site.com/pago",
  "backend_webhook": "https://site.com/api/ipay",
  "customer": {"name":"João","email":"a@b.com","phone_number":"+5511999887766"},
  "address": {"cep":"12345678","street":"R","neighborhood":"C","number":"1","complement":"Ap 1"}
}
```
Resposta 200: `{"external_id":"pedido-123","checkout_url":"https://checkout.infinitepay.io/..."}`.

Erros relevantes:
- `400` campo inválido / faltando obrigatório
- `409` `external_id` duplicado **ou** app não está pronto (`public_api_url` não validada)
- `502` InfinitePay devolveu erro / `success:false`
- `503` bootstrap lock

### `GET /checkout/` → lista todos
### `GET /checkout/{external_id}/`
- não pago → `{"external_id","is_paid":false,"checkout_url":"..."}`
- pago → `{"external_id","is_paid":true,"receipt_url":"..."}`

### `POST /webhook/{external_id}/` (ENTRADA — **NÃO chamar**)
Endpoint chamado **pela InfinitePay**. Ao receber:
1. Loga payload.
2. Chama `payment_check` da InfinitePay com `{handle, order_nsu, transaction_nsu, slug=invoice_slug}`.
3. `success:false` → responde **400** (InfinitePay tentará de novo).
4. `success:true, paid:true` → atualiza checkout (`is_paid`, `receipt_url`, `installments`, `invoice_slug`, `capture_method`, `transaction_nsu`) e enfileira `POST backend_webhook/{external_id}/` com `{paid:true, ...}`. Retries exponenciais 1m→24h.

---

## Padrões de uso (playbooks)

### Criar cobrança e retornar link para o cliente
1. Se o usuário mencionar valor em reais, converta para centavos (`R$ 1,50` → `150`).
2. Normalize telefone (se só dígitos BR, o app adiciona `+55`; se já tiver `+`, mantém).
3. CEP: aceite com ou sem hífen (o app normaliza).
4. `external_id`: use o ID do pedido do usuário; se não informado, peça.
5. Chame `POST /checkout/` ou `ipay checkout create`.
6. Devolva **apenas** o `checkout_url` ao cliente final. Guarde o `external_id` internamente.

### Consultar status
`GET /checkout/{external_id}/` — a presença de `receipt_url` indica pagamento confirmado; `checkout_url` indica pendente. **Não chame `payment_check` diretamente**; é o webhook interno que dispara isso.

### Configurar integração pela primeira vez
1. `PATCH /config/` com tudo + `public_api_url`.
2. Instrua o usuário (ou ferramenta de monitoramento) a bater o `GET /config/test/?token=...` da máquina externa dele — prova que a URL chega até nós.
3. `GET /health` deve retornar `ready:true`.

### Trocar domínio / apontar pra nova URL pública
Um `PATCH /config/ {"public_api_url":"..."}` invalida a atual. Refaça validação antes de novas cobranças.

---

## O que evitar

- Criar checkout sem validar `public_api_url` → falha com 409/503.
- Enviar `public_api_url` no body de `POST /checkout/` → rejeitado.
- Criar checkout com `external_id` já usado antes → 409. Se realmente for retentativa, primeiro `GET /checkout/{external_id}/` pra ver se já tem link; reuse.
- Chamar `payment_check` da InfinitePay manualmente — é o handler de webhook que faz.
- Rodar inline worker **e** worker dedicado ao mesmo tempo (pode duplicar entregas para o `backend_webhook`). Escolha um.
- Assumir centavos quando o usuário disse "reais" — confirme e converta.

---

## Troubleshooting rápido

| Sintoma | Causa provável | Ação |
|---|---|---|
| 503 em todas as rotas | `public_api_url` não validada | `GET /config/` → ver `public_api_url_validated`, disparar `/config/test/?token=...` |
| 409 ao criar checkout | `external_id` duplicado OU app não pronto | `GET /checkout/{external_id}/` pra confirmar |
| 502 na criação | InfinitePay recusou | Ver logs: `webhook_logs` com `kind=create_link` |
| Pagamento não atualiza | Webhook não chegou OU `payment_check` falhou | Ver logs inbound `kind=infinitepay_webhook` e outbound `kind=payment_check` |
| Backend do user não foi notificado | Retry em curso ou URL errada | Ver `outbound_jobs.last_error` |

Logs ficam na tabela `webhook_logs`; jobs de retry em `outbound_jobs`. Acesso direto via SQLite: `sqlite3 $IPAY_DB_PATH`.
