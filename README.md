# Ritta · mandates

**Español** · [English](docs/README_en.md) · [Português](docs/README_pt.md)

[Ritta](https://ritta.io) le pone límites a la inteligencia artificial cuando gasta tu plata: vos decís hasta cuánto puede pagar un agente y en qué, cada pago se verifica contra esa regla antes de ejecutarse, y todo queda registrado. La plata nunca pasa por Ritta.

Este repo es la librería open source (Apache 2.0) del **mandato**: el permiso firmado que dice "este agente puede gastar hasta X, en Y, en nombre de Z". Es compatible con [AP2](https://fidoalliance.org/) (Agent Payments Protocol) y se usa con el gateway para pagar con Mercado Pago, Pix y USDC.

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
    hitl_threshold=1_000_000,  # desde $10.000 se pide aprobación humana (lo aplica el gateway)
    state="open",
    expires_in_days=30,
)
token = sign(mandate, private_key)  # SD-JWT firmado con Ed25519

result = verify(
    token,
    public_key,
    amount=120_000,          # en centavos; sale del catálogo del comercio, nunca del modelo
    merchant="MP-123456",
    category="pharmacy",
    remaining=15_000_000,    # saldo sin gastar, lo aporta el ledger del gateway
)
assert result.ok
```

Si el pago no está autorizado, `result.ok` es `False` y `result.reason` dice por qué: `invalid_signature`, `expired`, `amount_over_per_operation`, `amount_over_remaining`, `merchant_not_allowed`, `category_not_allowed` o `malformed`.

`verify` es pura: no usa red ni guarda estado. Misma entrada, misma salida (pasá `now=` para fijar el reloj).

Las claves se exportan e importan en PEM con `ritta.mandates.private_key_to_pem`, `public_key_to_pem`, `load_private_key_pem` y `load_public_key_pem`. Nunca guardes una clave privada en el repositorio.

Documentación: [ritta.dev](https://ritta.dev). La especificación del formato está en [`docs/spec-mandate.md`](docs/spec-mandate.md).

## Estado

Pre-alpha (0.2.0). Etapa 1 del roadmap: ver [`docs/roadmap.md`](docs/roadmap.md).

## Licencia

Apache 2.0.
