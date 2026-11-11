# Ritta · mandates

[Español](../README.md) · **English** · [Português](README_pt.md)

[Ritta](https://ritta.io) puts limits on AI when it spends your money: you decide how much an agent may pay and on what, every payment is checked against that rule before it runs, and everything is recorded. The money never goes through Ritta.

This repo is the open source (Apache 2.0) library for the **mandate**: the signed permission that says "this agent may spend up to X, on Y, on behalf of Z". It is compatible with [AP2](https://fidoalliance.org/) (Agent Payments Protocol) and is used with the gateway to pay with Mercado Pago, Pix and USDC.

```bash
pip install ritta
```

```python
from ritta import Limits, Mandate, Scope, generate_keypair, sign, verify

private_key, public_key = generate_keypair()

mandate = Mandate(
    issuer="did:web:farmacia-central.com.ar",
    subject="agent:compras-01",
    limits=Limits(total=15_000_000, per_operation=5_000_000, currency="ARS"),  # cents
    scope=Scope(merchants=["MP-123456"], categories=["pharmacy"]),
    hitl_threshold=1_000_000,  # from $10,000 a human must approve (enforced by the gateway)
    state="open",
    expires_in_days=30,
)
token = sign(mandate, private_key)  # SD-JWT signed with Ed25519

result = verify(
    token,
    public_key,
    amount=120_000,          # in cents; comes from the merchant catalog, never from the model
    merchant="MP-123456",
    category="pharmacy",
    remaining=15_000_000,    # unspent balance, supplied by the gateway ledger
)
assert result.ok
```

If the payment is not authorized, `result.ok` is `False` and `result.reason` says why: `invalid_signature`, `expired`, `amount_over_per_operation`, `amount_over_remaining`, `merchant_not_allowed`, `category_not_allowed` or `malformed`.

`verify` is pure: no network, no state. Same input, same output (pass `now=` to pin the clock).

Keys are exported and imported as PEM with `ritta.mandates.private_key_to_pem`, `public_key_to_pem`, `load_private_key_pem` and `load_public_key_pem`. Never store a private key in the repository.

Documentation: [ritta.dev](https://ritta.dev). The format specification is in [`spec-mandate.md`](spec-mandate.md) (Spanish).

## Status

Pre-alpha (0.2.0). Stage 1 of the roadmap: see [`roadmap.md`](roadmap.md).

## License

Apache 2.0.
