from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any

import pytest

from ritta.mandates import Mandate, sign
from ritta.mandates.keys import Ed25519PrivateKey, Ed25519PublicKey
from ritta.mandates.sdjwt import (
    InvalidSignatureError,
    MalformedTokenError,
    decode,
    issue,
)

KeyPair = tuple[Ed25519PrivateKey, Ed25519PublicKey]


def _b64(data: dict[str, Any]) -> str:
    raw = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64_decode(segment: str) -> Any:
    return json.loads(base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4)))


def _forge(header: dict[str, Any], payload: dict[str, Any], key: Ed25519PrivateKey) -> str:
    signing_input = f"{_b64(header)}.{_b64(payload)}"
    sig = base64.urlsafe_b64encode(key.sign(signing_input.encode())).rstrip(b"=").decode()
    return f"{signing_input}.{sig}~"


def test_format(keypair: KeyPair, make_mandate: Callable[..., Mandate]) -> None:
    token = sign(make_mandate(), keypair[0])
    assert token.endswith("~") and token.count("~") == 1
    header_b64, payload_b64, _ = token[:-1].split(".")
    assert _b64_decode(header_b64) == {"alg": "EdDSA", "typ": "vc+sd-jwt"}
    payload = _b64_decode(payload_b64)
    assert payload["_sd_alg"] == "sha-256"
    assert "_sd" not in payload


def test_round_trip(keypair: KeyPair, make_mandate: Callable[..., Mandate]) -> None:
    mandate = make_mandate()
    claims = decode(sign(mandate, keypair[0]), keypair[1])
    assert "_sd_alg" not in claims
    assert Mandate.from_claims(claims) == mandate


def test_wrong_key(keypair: KeyPair, make_mandate: Callable[..., Mandate]) -> None:
    from ritta.mandates import generate_keypair

    _, other_public = generate_keypair()
    with pytest.raises(InvalidSignatureError):
        decode(sign(make_mandate(), keypair[0]), other_public)


@pytest.mark.parametrize(
    "header",
    [
        {"alg": "none", "typ": "vc+sd-jwt"},
        {"alg": "HS256", "typ": "vc+sd-jwt"},
        {"alg": "EdDSA", "typ": "JWT"},
        {"alg": "EdDSA", "typ": "vc+sd-jwt", "crit": ["exp"]},
    ],
)
def test_rejects_unsupported_headers(keypair: KeyPair, header: dict[str, Any]) -> None:
    with pytest.raises(MalformedTokenError):
        decode(_forge(header, {"iss": "x"}, keypair[0]), keypair[1])


def test_rejects_disclosures_and_key_binding(keypair: KeyPair) -> None:
    token = issue({"iss": "x"}, keypair[0])
    with pytest.raises(MalformedTokenError):
        decode(token + "WyJzYWx0IiwgImsiLCAidiJd~", keypair[1])
    with pytest.raises(MalformedTokenError):
        decode(token + "eyJ.kb.jwt", keypair[1])
    with pytest.raises(MalformedTokenError):
        decode(token[:-1], keypair[1])  # plain JWT without the SD-JWT separator


def test_rejects_sd_digests_in_payload(keypair: KeyPair) -> None:
    header = {"alg": "EdDSA", "typ": "vc+sd-jwt"}
    for payload in ({"_sd": ["abc"]}, {"a": [{"...": "abc"}]}, {"_sd_alg": "sha-512"}):
        with pytest.raises(MalformedTokenError):
            decode(_forge(header, payload, keypair[0]), keypair[1])


def test_rejects_duplicate_members(keypair: KeyPair) -> None:
    header_b64 = _b64({"alg": "EdDSA", "typ": "vc+sd-jwt"})
    raw = b'{"iss":"a","iss":"b"}'
    payload_b64 = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    signing_input = f"{header_b64}.{payload_b64}"
    sig = base64.urlsafe_b64encode(keypair[0].sign(signing_input.encode())).rstrip(b"=").decode()
    with pytest.raises(MalformedTokenError):
        decode(f"{signing_input}.{sig}~", keypair[1])


def test_rejects_non_canonical_base64(keypair: KeyPair) -> None:
    token = issue({"iss": "x"}, keypair[0])
    jwt = token[:-1]
    # 64-byte signature -> 86 chars; the last char carries 4 unused bits.
    last = jwt[-1]
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    twin = alphabet[alphabet.index(last) ^ 1]
    with pytest.raises(MalformedTokenError):
        decode(jwt[:-1] + twin + "~", keypair[1])


def test_issue_rejects_reserved_claims(keypair: KeyPair) -> None:
    with pytest.raises(ValueError):
        issue({"_sd": []}, keypair[0])


@pytest.mark.parametrize("token", ["", "~", "a.b~", "a.b.c.d~", "é.b.c~", "!!.!!.!!~"])
def test_garbage(keypair: KeyPair, token: str) -> None:
    with pytest.raises(MalformedTokenError):
        decode(token, keypair[1])
