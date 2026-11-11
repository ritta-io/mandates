"""Mandate data model.

A mandate authorizes an agent (``sub``) to spend on behalf of an issuer (``iss``)
within limits, a scope and an expiry. Amounts are always integers in the minor unit
of the currency (cents for ARS/BRL, base units for tokens). Floats are rejected.

Claim names follow ``docs/spec-mandate.md``: standard JWT claims (``iss``, ``sub``,
``exp``, ``jti``) plus flat ``ritta:``-prefixed extension claims for what
AP2 does not cover.
"""

from __future__ import annotations

import re
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

# Amounts in minor units. strict=True rejects floats, bools and numeric strings.
PositiveAmount = Annotated[int, Field(strict=True, gt=0)]
NonNegativeAmount = Annotated[int, Field(strict=True, ge=0)]
NonEmptyStr = Annotated[str, StringConstraints(min_length=1, max_length=256)]

# ISO 4217 codes (``ARS``, ``BRL``) and token tickers (``USDC``) share one syntax:
# uppercase, starts with a letter, 3-10 chars. A real ISO 4217 code cannot be told
# apart from a 3-letter token ticker, so no allow-list is enforced here.
CURRENCY_PATTERN = r"^[A-Z][A-Z0-9]{2,9}$"
Currency = Annotated[str, StringConstraints(pattern=CURRENCY_PATTERN)]

_ISSUER_RE = re.compile(r"^(did:[a-z0-9]+:\S+|https://\S+)$")

MandateState = Literal["open", "closed"]

# Claim names (see docs/spec-mandate.md).
CLAIM_TOTAL = "ritta:limits.total"
CLAIM_PER_OPERATION = "ritta:limits.per_operation"
CLAIM_CURRENCY = "ritta:limits.currency"
CLAIM_MERCHANTS = "ritta:scope.merchants"
CLAIM_CATEGORIES = "ritta:scope.categories"
CLAIM_HITL_THRESHOLD = "ritta:hitl_threshold"
CLAIM_STATE = "ritta:state"

REQUIRED_CLAIMS: frozenset[str] = frozenset(
    {
        "iss",
        "sub",
        "exp",
        "jti",
        CLAIM_TOTAL,
        CLAIM_PER_OPERATION,
        CLAIM_CURRENCY,
        CLAIM_MERCHANTS,
        CLAIM_CATEGORIES,
        CLAIM_HITL_THRESHOLD,
        CLAIM_STATE,
    }
)

_FROZEN = ConfigDict(frozen=True, extra="forbid")


class Limits(BaseModel):
    """Spending limits, in the minor unit of ``currency``."""

    model_config = _FROZEN

    total: PositiveAmount
    per_operation: PositiveAmount
    currency: Currency

    @model_validator(mode="after")
    def _per_operation_within_total(self) -> Self:
        if self.per_operation > self.total:
            raise ValueError("per_operation must not exceed total")
        return self


class Scope(BaseModel):
    """Where the agent may spend. An empty list means "any" (discouraged)."""

    model_config = _FROZEN

    merchants: Sequence[NonEmptyStr]
    categories: Sequence[NonEmptyStr]

    @field_validator("merchants", "categories", mode="after")
    @classmethod
    def _as_tuple(cls, value: Sequence[str]) -> tuple[str, ...]:
        # Stored as tuples so the frozen model is really immutable.
        return tuple(value)


class Mandate(BaseModel):
    """A spend mandate. Every field is required; there are no silent defaults.

    The expiry can be given either as ``expires_at`` (timezone-aware datetime) or as
    ``expires_in_days`` (converted to an absolute UTC ``expires_at`` at construction
    time). ``jti`` is generated with :func:`secrets.token_urlsafe` when omitted.
    """

    model_config = _FROZEN

    issuer: NonEmptyStr
    subject: NonEmptyStr
    limits: Limits
    scope: Scope
    hitl_threshold: NonNegativeAmount
    # DECISION NEEDED: a `closed` mandate is bound to a concrete checkout in AP2
    # (CartMandate). The claim that carries that binding (cart hash? order id?) is not
    # defined in the spec yet, so `closed` is accepted but carries no extra data.
    state: MandateState
    expires_at: datetime
    jti: NonEmptyStr = Field(default_factory=lambda: secrets.token_urlsafe(16))

    @model_validator(mode="before")
    @classmethod
    def _resolve_expiry(cls, data: Any) -> Any:
        if not isinstance(data, dict) or "expires_in_days" not in data:
            return data
        data = dict(data)
        days = data.pop("expires_in_days")
        if "expires_at" in data:
            raise ValueError("pass either expires_at or expires_in_days, not both")
        if isinstance(days, bool) or not isinstance(days, int) or days <= 0:
            raise ValueError("expires_in_days must be a positive integer")
        data["expires_at"] = datetime.now(UTC) + timedelta(days=days)
        return data

    @field_validator("issuer")
    @classmethod
    def _issuer_format(cls, value: str) -> str:
        # DECISION NEEDED (from spec): exact `iss` format for SMEs without a DID.
        if not _ISSUER_RE.match(value):
            raise ValueError("issuer must be a DID (did:...) or an https:// URL")
        return value

    @field_validator("expires_at")
    @classmethod
    def _expiry_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must be timezone-aware")
        # JWT `exp` has second precision: normalize so the model round-trips exactly.
        return value.astimezone(UTC).replace(microsecond=0)

    @property
    def exp(self) -> int:
        """Expiry as a JWT NumericDate (seconds since the epoch, UTC)."""
        return int(self.expires_at.timestamp())

    def to_claims(self) -> dict[str, Any]:
        """Serialize to the flat JWT claim set defined in the spec."""
        return {
            "iss": self.issuer,
            "sub": self.subject,
            "exp": self.exp,
            "jti": self.jti,
            CLAIM_TOTAL: self.limits.total,
            CLAIM_PER_OPERATION: self.limits.per_operation,
            CLAIM_CURRENCY: self.limits.currency,
            CLAIM_MERCHANTS: list(self.scope.merchants),
            CLAIM_CATEGORIES: list(self.scope.categories),
            CLAIM_HITL_THRESHOLD: self.hitl_threshold,
            CLAIM_STATE: self.state,
        }

    @classmethod
    def from_claims(cls, claims: dict[str, Any]) -> Mandate:
        """Build a mandate from a claim set. Raises ``ValueError`` if invalid.

        Unknown claims (e.g. ``iat``, ``_sd_alg``) are ignored; missing required
        claims are an error.
        """
        missing = REQUIRED_CLAIMS - claims.keys()
        if missing:
            raise ValueError(f"missing required claims: {sorted(missing)}")
        exp = claims["exp"]
        if isinstance(exp, bool) or not isinstance(exp, int):
            raise ValueError("exp must be an integer NumericDate")
        try:
            expires_at = datetime.fromtimestamp(exp, tz=UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise ValueError("exp out of range") from exc
        return cls.model_validate(
            {
                "issuer": claims["iss"],
                "subject": claims["sub"],
                "jti": claims["jti"],
                "expires_at": expires_at,
                "limits": {
                    "total": claims[CLAIM_TOTAL],
                    "per_operation": claims[CLAIM_PER_OPERATION],
                    "currency": claims[CLAIM_CURRENCY],
                },
                "scope": {
                    "merchants": claims[CLAIM_MERCHANTS],
                    "categories": claims[CLAIM_CATEGORIES],
                },
                "hitl_threshold": claims[CLAIM_HITL_THRESHOLD],
                "state": claims[CLAIM_STATE],
            }
        )
