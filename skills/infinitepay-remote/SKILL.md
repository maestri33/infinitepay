---
name: infinitepay-remote
description: Usar a API InfinitePay já instalada em outra LXC por CLI remota `ipay-remote`, sem editar configuração; cria, lista e consulta checkouts via HTTP interno.
---

# infinitepay-remote

Use esta skill quando o usuário quiser operar checkouts InfinitePay a partir de outra LXC/VM/host, sem acesso ao SQLite e sem editar `/config/`.

## Modelo

- A LXC principal roda `infinitepay-api` e guarda config/SQLite.
- A LXC remota instala somente `ipay-remote`.
- `ipay-remote` chama a API principal por HTTP interno (`IPAY_API_URL`).
- Configuração (`handle`, `public_api_url`, `redirect_url`, `backend_webhook`) continua sendo feita apenas na LXC principal.

## Instalação em outra LXC

Na LXC remota:

```bash
git clone https://github.com/maestri33/infinitepay.git /tmp/infinitepay
cd /tmp/infinitepay
bash deploy/install-remote-cli.sh http://10.10.10.120:8000
```

O instalador cria:

- clone em `/opt/infinitepay-remote`
- venv em `/opt/infinitepay-remote/.venv`
- wrapper `/usr/local/bin/ipay-remote`
- `IPAY_API_URL` fixo no wrapper

Alternativa sem wrapper:

```bash
export IPAY_API_URL=http://10.10.10.120:8000
ipay-remote health
```

## Comandos

Health:

```bash
ipay-remote health
```

Criar checkout:

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

Listar:

```bash
ipay-remote checkout list
```

Consultar:

```bash
ipay-remote checkout get pedido-123
```

## Regras

1. Não use `ipay-remote` para `/config/`; essa CLI não implementa config por desenho.
2. Use `external_id` único e real do sistema chamador.
3. Valores continuam em centavos.
4. Se `price`/`description` forem omitidos, a API principal usa os defaults já configurados.
5. A URL remota deve ser interna e confiável, por exemplo `http://10.10.10.120:8000`; não precisa passar pelo proxy público.
6. Se a API responder erro, a CLI imprime `status_code` e o JSON retornado.

## Respostas

Criação bem-sucedida:

```json
{
  "external_id": "pedido-123",
  "checkout_url": "https://checkout.infinitepay.io/v7m?..."
}
```

Consulta pendente:

```json
{
  "external_id": "pedido-123",
  "is_paid": false,
  "checkout_url": "https://checkout.infinitepay.io/..."
}
```

Consulta paga:

```json
{
  "external_id": "pedido-123",
  "is_paid": true,
  "receipt_url": "https://recibo.infinitepay.io/..."
}
```

## Troubleshooting

- `ready:false` no `health`: valide `public_api_url` na LXC principal.
- `409`: `external_id` duplicado; use `ipay-remote checkout get <external_id>`.
- `502`: InfinitePay recusou ou não retornou URL; veja logs na LXC principal.
- Timeout/conexão recusada: teste `curl http://10.10.10.120:8000/health` a partir da LXC remota.
