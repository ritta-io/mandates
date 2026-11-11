# Especificación del mandato Ritta (borrador v0, implementado en 0.2.0)

Un **mandato** es una credencial verificable (SD-JWT) que autoriza a un agente a gastar dentro de límites. Mapea a AP2 v0.2; lo que AP2 no cubre va en claims con prefijo `ritta:`.

## Claims obligatorios

Los nombres son literales y planos: `ritta:limits.total` es un único claim, no un objeto anidado.

> **Compatibilidad.** La versión 0.1.0 usaba el prefijo `agentmandates:`. Desde 0.2.0 el prefijo es `ritta:` y un verificador 0.2.0 **no acepta** mandatos con el prefijo anterior: los rechaza como `malformed` porque les faltan los claims obligatorios. No se ofrece migración porque 0.1.0 no tuvo usuarios externos.

| Claim | Tipo | Significado |
|---|---|---|
| `iss` | DID o URL | Quién autoriza (persona o empresa). Hoy se acepta `did:<método>:...` o `https://...` |
| `sub` | string | Identificador del agente autorizado |
| `ritta:limits.total` | int | Monto total autorizado, en unidad mínima (> 0) |
| `ritta:limits.per_operation` | int | Tope por operación (> 0 y ≤ `total`) |
| `ritta:limits.currency` | string | ISO 4217 (`ARS`, `BRL`) o token (`USDC`). Sintaxis: `^[A-Z][A-Z0-9]{2,9}$` |
| `ritta:scope.merchants` | lista | IDs de comercio permitidos (vacío = cualquiera, desaconsejado) |
| `ritta:scope.categories` | lista | Categorías permitidas (vacío = cualquiera, desaconsejado) |
| `ritta:hitl_threshold` | int | Monto a partir del cual se exige aprobación humana (≥ 0) |
| `exp` | timestamp | Vencimiento (NumericDate, segundos UTC) |
| `jti` | string | Nonce único (anti-replay) |
| `ritta:state` | `open` / `closed` | Abierto (presupuesto) o cerrado (atado a un checkout) |

Los montos son enteros JSON. Un número con decimales (aunque sea `100.0`) o un string hace que el mandato sea `malformed`.

## Formato (SD-JWT)

El mandato firmado es un SD-JWT en forma compacta: `<JWT firmado por el emisor>~`.

- Header: `{"alg": "EdDSA", "typ": "vc+sd-jwt"}`. Firma Ed25519.
- Payload: `"_sd_alg": "sha-256"` más los claims de la tabla.
- El `~` final es el separador de SD-JWT con cero disclosures y sin Key Binding JWT.

En 0.1.0 no hay divulgación selectiva: todos los claims son visibles. El formato ya es SD-JWT válido, así que agregar disclosures después no rompe el sobre. Mientras tanto, un verificador 0.1.0 rechaza como `malformed` cualquier token con disclosures, Key Binding JWT, digests `_sd`, header con `crit`, miembros JSON duplicados o base64url no canónico.

## Verificación

`verify(token, public_key, *, amount, merchant, category, remaining, now=None)` devuelve `ok` solo si: la firma es válida, `now < exp`, `amount <= per_operation`, `amount <= remaining`, `merchant` y `category` están dentro del scope. Es pura: no consulta red. El saldo `remaining` lo aporta el gateway (ledger); la librería recibe el valor.

Si falla, devuelve la primera razón en este orden: `malformed` / `invalid_signature`, `expired`, `amount_over_per_operation`, `amount_over_remaining`, `merchant_not_allowed`, `category_not_allowed`.

- `amount` y `remaining` son enteros en la unidad mínima de la moneda del mandato. Argumentos inválidos (`amount <= 0`, `remaining < 0`, no enteros, `now` sin zona horaria) son errores de programación y lanzan excepción.
- `hitl_threshold` no lo aplica `verify`: pedir aprobación humana es una decisión de política del gateway.

## Pendientes (DECISION NEEDED)

- Formato exacto de `iss` para pymes argentinas sin DID (¿`did:web` del gateway + CUIT?).
- Mapeo de `ritta:scope.categories` a MCC de tarjetas.
- `typ`: el borrador actual de SD-JWT VC usa `dc+sd-jwt` (antes `vc+sd-jwt`) y exige el claim `vct`. Confirmar qué esperan los verificadores AP2 v0.2.
- Mandato `closed`: qué claim lo ata al checkout (CartMandate de AP2). Hoy se verifica igual que uno `open`.
- Vinculación del agente (holder binding, claim `cnf` + Key Binding JWT): no implementada.
