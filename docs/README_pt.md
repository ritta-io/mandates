# Ritta · mandates

[Español](../README.md) · [English](README_en.md) · **Português**

A [Ritta](https://ritta.io) coloca limites na inteligência artificial quando ela gasta o seu dinheiro: você decide quanto um agente pode pagar e em quê, cada pagamento é verificado contra essa regra antes de ser executado, e tudo fica registrado. O dinheiro nunca passa pela Ritta.

Este repositório é a biblioteca open source (Apache 2.0) do **mandato**: a permissão assinada que diz "este agente pode gastar até X, em Y, em nome de Z". É compatível com o [AP2](https://fidoalliance.org/) (Agent Payments Protocol) e é usada com o gateway para pagar com Mercado Pago, Pix e USDC.

```bash
pip install ritta
```

```python
from ritta import Limits, Mandate, Scope, generate_keypair, sign, verify

private_key, public_key = generate_keypair()

mandate = Mandate(
    issuer="did:web:farmacia-central.com.ar",
    subject="agent:compras-01",
    limits=Limits(total=15_000_000, per_operation=5_000_000, currency="ARS"),  # centavos
    scope=Scope(merchants=["MP-123456"], categories=["pharmacy"]),
    hitl_threshold=1_000_000,  # a partir de $10.000 exige aprovação humana (aplicada pelo gateway)
    state="open",
    expires_in_days=30,
)
token = sign(mandate, private_key)  # SD-JWT assinado com Ed25519

result = verify(
    token,
    public_key,
    amount=120_000,          # em centavos; vem do catálogo do comerciante, nunca do modelo
    merchant="MP-123456",
    category="pharmacy",
    remaining=15_000_000,    # saldo não gasto, fornecido pelo ledger do gateway
)
assert result.ok
```

Se o pagamento não for autorizado, `result.ok` é `False` e `result.reason` diz o motivo: `invalid_signature`, `expired`, `amount_over_per_operation`, `amount_over_remaining`, `merchant_not_allowed`, `category_not_allowed` ou `malformed`.

`verify` é pura: não usa rede nem guarda estado. Mesma entrada, mesma saída (passe `now=` para fixar o relógio).

As chaves são exportadas e importadas em PEM com `ritta.mandates.private_key_to_pem`, `public_key_to_pem`, `load_private_key_pem` e `load_public_key_pem`. Nunca guarde uma chave privada no repositório.

Documentação: [ritta.dev](https://ritta.dev). A especificação do formato está em [`spec-mandate.md`](spec-mandate.md) (em espanhol).

## Status

Pré-alfa (0.2.0). Etapa 1 do roadmap: veja [`roadmap.md`](roadmap.md).

## Licença

Apache 2.0.
