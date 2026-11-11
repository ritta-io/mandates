# CLAUDE.md — mandates

Este archivo es la memoria de trabajo de Claude Code en este repo. Leelo entero antes de tocar código.

## Qué es el proyecto (en una oración)

> Nombre: **Ritta** (ritta.io, docs en ritta.dev). Repo: https://github.com/ritta-io/mandates. Paquete en PyPI: `ritta`. Publicar en PyPI solo desde un tag `v*` (release de GitHub → `.github/workflows/publish.yml`), nunca a mano ni desde una rama.

El producto le pone límites a la inteligencia artificial cuando gasta plata: el dueño define hasta cuánto puede pagar un agente y en qué, cada pago se verifica contra esa regla antes de ejecutarse, y todo queda registrado de forma auditable. La plata nunca pasa por nosotros: pasa por Mercado Pago, Pix o una wallet del cliente.

## Qué es ESTE repo

`mandates` es la **librería open source (Apache 2.0)** del formato de mandato y su verificación, más el SDK de cliente en Python. Es la capa de adquisición: lo que un desarrollador instala con `pip install ritta` para que su agente pueda pedir permiso de gasto de forma estándar.

Lo que vive acá:
- `ritta.mandates`: modelo de mandato, firma, verificación, serialización. Compatible con **AP2 v0.2** (Agent Payments Protocol, hoy en la FIDO Alliance): el mandato es una credencial verificable **SD-JWT**, con estados `open` (presupuesto + restricciones) y `closed` (monto atado a un checkout concreto).
- `ritta.client`: cliente HTTP y herramientas MCP para hablar con un el gateway (`create_mandate`, `quote`, `request_payment`, `get_receipt`).
- `docs/`: spec del mandato en español, inglés y portugués.

Lo que NO vive acá (vive en `gateway`, repo privado): el motor de políticas, los rieles de pago (Mercado Pago, x402, Pix), el ledger, el audit log, el panel, la facturación.

## Stack y convenciones

- Python 3.12. Gestor: `uv`. Empaquetado con `pyproject.toml` (hatchling). Nombre del paquete en PyPI: `ritta`.
- Tipado estricto: `mypy --strict` pasa siempre. Modelos con `pydantic` v2.
- Firma y verificación: `cryptography` (Ed25519 por defecto) y SD-JWT según el borrador IETF `draft-ietf-oauth-selective-disclosure-jwt`. No inventar criptografía: usar primitivas estándar.
- Tests con `pytest` + `hypothesis` para propiedades (un mandato nunca se verifica con firma inválida, vencido, o con monto mayor al restante).
- Lint y formato: `ruff`. Commits en inglés, estilo Conventional Commits (`feat:`, `fix:`, `docs:`). Código, nombres y comentarios en inglés; documentación de usuario en español, inglés y portugués.
- Sin dependencias pesadas. Nada de frameworks web en este repo.

## Reglas no negociables

1. **El modelo de lenguaje nunca decide monto, moneda ni destinatario.** Esos datos salen del mandato firmado y del catálogo del comercio. El agente solo elige un `product_id` o una intención. Cualquier API que acepte un monto libre proveniente del agente está mal diseñada y no se mergea.
2. **Nada de secretos en el código ni en los tests.** Claves de prueba se generan en el test. Nunca commitear `.env`, tokens de Mercado Pago, claves privadas.
3. **Un mandato tiene siempre:** emisor (quién autoriza), sujeto (qué agente), límites (monto total, monto por operación, moneda), alcance (comercios o categorías permitidas), vencimiento, nonce, y firma. Si falta uno, el constructor falla.
4. **Verificación es pura y determinista:** misma entrada, misma salida, sin red. La verificación de un mandato no llama a ningún servicio externo.
5. **Compatibilidad AP2 primero.** Si hay que elegir entre un diseño propio y uno que mapea limpio a AP2/Verifiable Credentials, se elige AP2. Lo que no cubre AP2 va en extensiones con prefijo `ritta:`.
6. **Idempotencia:** toda operación que pueda repetirse lleva `idempotency_key`.
7. **Montos en enteros** (centavos/unidad mínima) con moneda ISO 4217 o identificador de token. Nunca `float`.

## Cómo trabajamos con Claude Code

- Antes de implementar algo, leé `docs/spec-mandate.md` y los tests existentes. Si la spec no cubre el caso, primero se actualiza la spec, después el código.
- Trabajá en ramas `feat/...` o `fix/...`. Un PR por cambio. Los PR llevan descripción en inglés y, si cambia la spec, una línea en `CHANGELOG.md`.
- Definición de terminado: `uv run pytest` verde, `uv run mypy --strict src` sin errores, `uv run ruff check .` limpio, docs actualizadas en los tres idiomas si cambió la API pública.
- Cuando no estés seguro de una decisión de diseño que afecte la compatibilidad con AP2, Mercado Pago o x402: no asumas, dejá un comentario `# DECISION NEEDED:` y pará.
- No agregues funcionalidad que no esté en la etapa actual del roadmap (ver `docs/roadmap.md`). Menos es más.

## Comandos

```bash
uv sync                      # instalar dependencias
uv run pytest -q             # tests
uv run mypy --strict src     # tipos
uv run ruff check . && uv run ruff format .   # lint y formato
uv build                     # construir el paquete
```

## Estado actual

Etapa 1 del roadmap. Objetivo de la etapa: esquema de mandato compatible con AP2 v0.2 (SD-JWT), firma y verificación en Python, README en tres idiomas, tests de propiedades. Ver `docs/roadmap.md`.
