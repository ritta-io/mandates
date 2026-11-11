from __future__ import annotations

import base64
import json
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

import pytest

from ritta.mandates import Limits, Mandate, Scope, generate_keypair, sign, verify
from ritta.mandates.keys import Ed25519PrivateKey, Ed25519PublicKey
from ritta.mandates.sdjwt import issue

from .conftest import NOW

KeyPair = tuple[Ed25519PrivateKey, Ed25519PublicKey]

OK_REQUEST: dict[str, Any] = {
    "amount": 120_000,
    "merchant": "MP-123456",
    "category": "pharmacy",
    "remaining": 15_000_000,
    "now": NOW,
}


def _check(token: str, public_key: Ed25519PublicKey, **overrides: Any) -> Any:
    return verify(token, public_key, **{**OK_REQUEST, **overrides})


@pytest.fixture
def token(keypair: KeyPair, make_mandate: Callable[..., Mandate]) -> str:
    return sign(make_mandate(), keypair[0])


def test_ok(token: str, keypair: KeyPair) -> None:
    result = _check(token, keypair[1])
    assert result.ok and result.reason is None


def test_boundaries_are_inclusive(token: str, keypair: KeyPair) -> None:
    assert _check(token, keypair[1], amount=5_000_000, remaining=5_000_000).ok


def test_invalid_signature(token: str) -> None:
    _, other_public = generate_keypair()
    result = _check(token, other_public)
    assert not result.ok and result.reason == "invalid_signature"


def test_expired(token: str, keypair: KeyPair) -> None:
    result = _check(token, keypair[1], now=NOW + timedelta(days=30))
    assert not result.ok and result.reason == "expired"
    assert _check(token, keypair[1], now=NOW + timedelta(days=30, seconds=-1)).ok


def test_amount_over_per_operation(token: str, keypair: KeyPair) -> None:
    result = _check(token, keypair[1], amount=5_000_001)
    assert not result.ok and result.reason == "amount_over_per_operation"


def test_amount_over_remaining(token: str, keypair: KeyPair) -> None:
    result = _check(token, keypair[1], amount=200_000, remaining=199_999)
    assert not result.ok and result.reason == "amount_over_remaining"


def test_merchant_not_allowed(token: str, keypair: KeyPair) -> None:
    result = _check(token, keypair[1], merchant="MP-999")
    assert not result.ok and result.reason == "merchant_not_allowed"


def test_category_not_allowed(token: str, keypair: KeyPair) -> None:
    result = _check(token, keypair[1], category="electronics")
    assert not result.ok and result.reason == "category_not_allowed"


def test_empty_scope_means_any(keypair: KeyPair, make_mandate: Callable[..., Mandate]) -> None:
    token = sign(make_mandate(scope=Scope(merchants=[], categories=[])), keypair[0])
    assert _check(token, keypair[1], merchant="anyone", category="anything").ok


@pytest.mark.parametrize("token", ["", "garbage", "a.b.c~", "a.b.c"])
def test_malformed_token(token: str, keypair: KeyPair) -> None:
    result = _check(token, keypair[1])
    assert not result.ok and result.reason == "malformed"


def test_malformed_claims_with_valid_signature(
    keypair: KeyPair, make_mandate: Callable[..., Mandate]
) -> None:
    claims = make_mandate().to_claims()
    bad_claims: list[dict[str, Any]] = [
        {k: v for k, v in claims.items() if k != "agentmandates:hitl_threshold"},
        {**claims, "agentmandates:limits.total": 15_000_000.0},
        {**claims, "agentmandates:limits.per_operation": "5000000"},
        {**claims, "exp": "tomorrow"},
        {**claims, "agentmandates:state": "pending"},
        {**claims, "agentmandates:limits.currency": "pesos"},
    ]
    for bad in bad_claims:
        result = _check(issue(bad, keypair[0]), keypair[1])
        assert not result.ok and result.reason == "malformed", bad


def test_check_order_reports_first_failure(token: str, keypair: KeyPair) -> None:
    result = _check(
        token,
        keypair[1],
        amount=9_000_000,
        remaining=1,
        merchant="x",
        category="y",
        now=NOW + timedelta(days=60),
    )
    assert result.reason == "expired"


@pytest.mark.parametrize(
    ("overrides", "exc"),
    [
        ({"amount": 0}, ValueError),
        ({"amount": -1}, ValueError),
        ({"amount": 10.0}, TypeError),
        ({"amount": True}, TypeError),
        ({"remaining": -1}, ValueError),
        ({"now": datetime(2026, 1, 1)}, ValueError),
    ],
)
def test_invalid_arguments_raise(
    token: str, keypair: KeyPair, overrides: dict[str, Any], exc: type[Exception]
) -> None:
    with pytest.raises(exc):
        _check(token, keypair[1], **overrides)


def test_deterministic(token: str, keypair: KeyPair) -> None:
    assert _check(token, keypair[1]) == _check(token, keypair[1])


def test_tampered_payload_rejected(token: str, keypair: KeyPair) -> None:
    header_b64, payload_b64, sig_b64 = token[:-1].split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=" * (-len(payload_b64) % 4)))
    payload["agentmandates:limits.per_operation"] = 15_000_000
    raw = json.dumps(payload, separators=(",", ":")).encode()
    forged = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    result = _check(f"{header_b64}.{forged}.{sig_b64}~", keypair[1], amount=10_000_000)
    assert not result.ok and result.reason == "invalid_signature"


def test_currency_is_carried_by_mandate(
    keypair: KeyPair, make_mandate: Callable[..., Mandate]
) -> None:
    limits = Limits(total=10_000_000, per_operation=1_000_000, currency="USDC")
    token = sign(make_mandate(limits=limits), keypair[0])
    assert _check(token, keypair[1], amount=1_000_000).ok
