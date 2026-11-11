"""Pure, deterministic verification of a payment request against a signed mandate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import ValidationError

from ritta.mandates.model import Mandate
from ritta.mandates.sdjwt import InvalidSignatureError, MalformedTokenError, decode

RejectionReason = Literal[
    "invalid_signature",
    "expired",
    "amount_over_per_operation",
    "amount_over_remaining",
    "merchant_not_allowed",
    "category_not_allowed",
    "malformed",
]


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of :func:`verify`. ``reason`` is ``None`` iff ``ok`` is ``True``."""

    ok: bool
    reason: RejectionReason | None = None


_OK = VerificationResult(ok=True)


def _reject(reason: RejectionReason) -> VerificationResult:
    return VerificationResult(ok=False, reason=reason)


def _require_int(name: str, value: object, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int in minor units")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def verify(
    token: str,
    public_key: Ed25519PublicKey,
    *,
    amount: int,
    merchant: str,
    category: str,
    remaining: int,
    now: datetime | None = None,
) -> VerificationResult:
    """Check whether a payment of ``amount`` to ``merchant``/``category`` is authorized.

    ``amount`` and ``remaining`` are integers in the mandate currency's minor unit.
    ``remaining`` is the unspent balance, supplied by the caller (the gateway ledger):
    this function keeps no state and makes no network calls. ``now`` defaults to the
    current UTC time; pass it explicitly for fully deterministic results.

    Checks run in this order and the first failure is reported: ``malformed`` /
    ``invalid_signature``, ``expired``, ``amount_over_per_operation``,
    ``amount_over_remaining``, ``merchant_not_allowed``, ``category_not_allowed``.
    An empty merchant or category list in the mandate scope means "any".

    ``hitl_threshold`` is not enforced here: whether to ask a human is a policy
    decision made by the gateway, not a validity check.

    Invalid *arguments* (non-int or non-positive ``amount``, negative ``remaining``,
    naive ``now``) are programming errors and raise ``TypeError``/``ValueError``.
    """
    _require_int("amount", amount, minimum=1)
    _require_int("remaining", remaining, minimum=0)
    if now is None:
        now = datetime.now(UTC)
    elif now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")

    try:
        claims = decode(token, public_key)
    except InvalidSignatureError:
        return _reject("invalid_signature")
    except MalformedTokenError:
        return _reject("malformed")

    try:
        mandate = Mandate.from_claims(claims)
    except (ValidationError, ValueError):
        return _reject("malformed")

    # DECISION NEEDED: for `closed` mandates AP2 binds the amount to a specific
    # checkout; until the binding claim is specified, closed mandates are checked with
    # the same rules as open ones.
    if now >= mandate.expires_at:
        return _reject("expired")
    if amount > mandate.limits.per_operation:
        return _reject("amount_over_per_operation")
    if amount > remaining:
        return _reject("amount_over_remaining")
    if mandate.scope.merchants and merchant not in mandate.scope.merchants:
        return _reject("merchant_not_allowed")
    if mandate.scope.categories and category not in mandate.scope.categories:
        return _reject("category_not_allowed")
    return _OK
