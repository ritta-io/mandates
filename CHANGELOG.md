# Changelog

## Unreleased

## 0.2.0

- Renamed to Ritta: the PyPI distribution and the import package are now `ritta` (was `agentmandates`).
- Claim prefix changed from `agentmandates:` to `ritta:` (e.g. `ritta:limits.total`). Tokens with the old prefix are rejected as `malformed`; see the compatibility note in the spec.
- No functional changes.

## 0.1.0

- `Mandate`, `Limits` and `Scope` models (pydantic v2) with every claim required by the spec; integer amounts only.
- Ed25519 key generation and PEM import/export (`generate_keypair`, `*_to_pem`, `load_*_pem`).
- Mandates signed as SD-JWT (`typ: vc+sd-jwt`, `alg: EdDSA`), no selective disclosure yet.
- Pure `verify()` returning `VerificationResult(ok, reason)`.
- Spec: defined wire format, check order, empty `categories` means "any", verify does not enforce `hitl_threshold`.
- READMEs in Spanish, English and Portuguese. Package ships `py.typed`.
- Project scaffold.
