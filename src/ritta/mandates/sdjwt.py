"""Minimal SD-JWT issuance and verification (draft-ietf-oauth-selective-disclosure-jwt).

Wire format
-----------
A mandate is serialized as an SD-JWT in compact form::

    <issuer-signed JWT>~

* The issuer-signed JWT is a compact JWS (RFC 7515) with header
  ``{"alg": "EdDSA", "typ": "vc+sd-jwt"}``, signed with Ed25519 (RFC 8037).
* The payload carries ``"_sd_alg": "sha-256"`` plus the mandate claims.
* The trailing ``~`` is the SD-JWT separator with **zero disclosures** and no
  Key Binding JWT.

Design decision (v0.1.0): no real selective disclosure yet
----------------------------------------------------------
Every claim is visible in the JWT payload; no ``_sd`` digests and no disclosures are
emitted. The output is still a well-formed SD-JWT, so adding disclosures later only
means moving claims into ``_sd`` digests and appending ``<disclosure>~`` segments,
without changing the header, the signature scheme or the envelope.

Because this version cannot process disclosures, the verifier fails closed: a token
carrying disclosures, a Key Binding JWT, ``_sd`` digests or ``...`` array entries is
rejected as malformed rather than partially trusted.

Base64url segments are decoded strictly (URL-safe alphabet, no padding, canonical
encoding), so two different strings never verify as the same token.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from ritta.mandates.model import Mandate

# DECISION NEEDED: the current SD-JWT VC draft (draft-ietf-oauth-sd-jwt-vc) renamed
# the media type to `dc+sd-jwt` and requires a `vct` claim. We emit `vc+sd-jwt` and no
# `vct` as specified for v0.1.0; which one AP2 v0.2 verifiers expect must be confirmed.
TYP = "vc+sd-jwt"
ALG = "EdDSA"
SD_ALG = "sha-256"
SEPARATOR = "~"

_B64URL_RE = re.compile(r"^[A-Za-z0-9_-]*$")


class SdJwtError(ValueError):
    """Base error for SD-JWT decoding failures."""


class MalformedTokenError(SdJwtError):
    """The token is not a well-formed SD-JWT this version can process."""


class InvalidSignatureError(SdJwtError):
    """The issuer signature does not verify against the given public key."""


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(segment: str) -> bytes:
    if not segment or not _B64URL_RE.match(segment) or len(segment) % 4 == 1:
        raise MalformedTokenError("invalid base64url segment")
    try:
        data = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
    except (binascii.Error, ValueError) as exc:
        raise MalformedTokenError("invalid base64url segment") from exc
    # Reject non-canonical encodings (non-zero trailing bits): otherwise a modified
    # character could decode to the same bytes and still verify.
    if _b64url_encode(data) != segment:
        raise MalformedTokenError("non-canonical base64url segment")
    return data


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MalformedTokenError("duplicate JSON member")
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise MalformedTokenError("non-finite number in JSON")


def _json_object(data: bytes) -> dict[str, Any]:
    try:
        value = json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise MalformedTokenError("invalid JSON") from exc
    if not isinstance(value, dict):
        raise MalformedTokenError("JSON value is not an object")
    return value


def _json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )


def _contains_sd_digests(value: Any) -> bool:
    if isinstance(value, dict):
        return "_sd" in value or any(_contains_sd_digests(v) for v in value.values())
    if isinstance(value, list):
        return any(
            (isinstance(v, dict) and set(v) == {"..."}) or _contains_sd_digests(v) for v in value
        )
    return False


def issue(claims: dict[str, Any], private_key: Ed25519PrivateKey) -> str:
    """Issue an SD-JWT (no disclosures) over ``claims``."""
    if "_sd" in claims or "_sd_alg" in claims:
        raise ValueError("claims must not contain reserved SD-JWT members")
    header = {"alg": ALG, "typ": TYP}
    payload = {"_sd_alg": SD_ALG, **claims}
    signing_input = f"{_b64url_encode(_json_bytes(header))}.{_b64url_encode(_json_bytes(payload))}"
    signature = private_key.sign(signing_input.encode("ascii"))
    return f"{signing_input}.{_b64url_encode(signature)}{SEPARATOR}"


def decode(token: str, public_key: Ed25519PublicKey) -> dict[str, Any]:
    """Verify the issuer signature and return the claims (without ``_sd_alg``).

    Raises :class:`MalformedTokenError` or :class:`InvalidSignatureError`.
    Pure: no network, no clock, no state.
    """
    if not isinstance(token, str) or not token.isascii():
        raise MalformedTokenError("token must be an ASCII string")
    parts = token.split(SEPARATOR)
    if len(parts) != 2 or parts[1] != "":
        raise MalformedTokenError("disclosures and key binding are not supported")
    segments = parts[0].split(".")
    if len(segments) != 3:
        raise MalformedTokenError("issuer JWT must have three segments")
    header_b64, payload_b64, signature_b64 = segments

    header = _json_object(_b64url_decode(header_b64))
    if header.get("alg") != ALG or header.get("typ") != TYP or "crit" in header:
        raise MalformedTokenError("unsupported JWT header")

    payload_bytes = _b64url_decode(payload_b64)
    signature = _b64url_decode(signature_b64)
    try:
        public_key.verify(signature, f"{header_b64}.{payload_b64}".encode("ascii"))
    except InvalidSignature as exc:
        raise InvalidSignatureError("signature does not verify") from exc

    claims = _json_object(payload_bytes)
    if claims.pop("_sd_alg", SD_ALG) != SD_ALG:
        raise MalformedTokenError("unsupported _sd_alg")
    if _contains_sd_digests(claims):
        raise MalformedTokenError("selectively disclosable claims are not supported")
    return claims


def sign(mandate: Mandate, private_key: Ed25519PrivateKey) -> str:
    """Sign a mandate and return it as an SD-JWT string."""
    return issue(mandate.to_claims(), private_key)
