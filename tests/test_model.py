from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ritta.mandates import Limits, Mandate, Scope

REQUIRED_FIELDS = ["issuer", "subject", "limits", "scope", "hitl_threshold", "state", "expires_at"]


@pytest.mark.parametrize("field", REQUIRED_FIELDS)
def test_constructor_fails_when_required_field_missing(
    make_mandate: Callable[..., Mandate], field: str
) -> None:
    base = make_mandate().model_dump()
    del base[field]
    with pytest.raises(ValidationError):
        Mandate(**base)


def test_expires_in_days_becomes_absolute_utc(make_mandate: Callable[..., Mandate]) -> None:
    before = datetime.now(UTC).replace(microsecond=0)
    mandate = make_mandate(expires_at=None, expires_in_days=30)
    after = datetime.now(UTC)
    assert mandate.expires_at.tzinfo == UTC
    assert before + timedelta(days=30) <= mandate.expires_at <= after + timedelta(days=30)
    assert mandate.expires_at.microsecond == 0


def test_expires_at_normalized_to_utc(make_mandate: Callable[..., Mandate]) -> None:
    local = datetime(2026, 3, 1, 9, 0, 0, 123, tzinfo=timezone(timedelta(hours=-3)))
    mandate = make_mandate(expires_at=local)
    assert mandate.expires_at == datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
    assert mandate.expires_at.tzinfo == UTC


@pytest.mark.parametrize("days", [0, -1, 1.5, True, "30"])
def test_invalid_expires_in_days(make_mandate: Callable[..., Mandate], days: object) -> None:
    with pytest.raises(ValidationError):
        make_mandate(expires_at=None, expires_in_days=days)


def test_naive_expiry_rejected(make_mandate: Callable[..., Mandate]) -> None:
    with pytest.raises(ValidationError):
        make_mandate(expires_at=datetime(2030, 1, 1))


def test_both_expiry_forms_rejected(make_mandate: Callable[..., Mandate]) -> None:
    with pytest.raises(ValidationError):
        make_mandate(expires_in_days=3)


def test_jti_generated_and_unique(make_mandate: Callable[..., Mandate]) -> None:
    a, b = make_mandate(), make_mandate()
    assert a.jti and b.jti and a.jti != b.jti
    assert make_mandate(jti="fixed").jti == "fixed"


@pytest.mark.parametrize("value", [100.0, "100", True, 0, -5])
def test_amounts_must_be_positive_ints(value: object) -> None:
    with pytest.raises(ValidationError):
        Limits(total=value, per_operation=1, currency="ARS")  # type: ignore[arg-type]


def test_per_operation_cannot_exceed_total() -> None:
    with pytest.raises(ValidationError):
        Limits(total=100, per_operation=101, currency="ARS")


@pytest.mark.parametrize("currency", ["ARS", "BRL", "USDC", "USD"])
def test_valid_currencies(currency: str) -> None:
    assert Limits(total=1, per_operation=1, currency=currency).currency == currency


@pytest.mark.parametrize("currency", ["", "ar", "ars", "A", "1AR", "TOOLONGTOKEN", "US D"])
def test_invalid_currencies(currency: str) -> None:
    with pytest.raises(ValidationError):
        Limits(total=1, per_operation=1, currency=currency)


@pytest.mark.parametrize("issuer", ["acme", "http://acme.com", "did:", ""])
def test_invalid_issuer(make_mandate: Callable[..., Mandate], issuer: str) -> None:
    with pytest.raises(ValidationError):
        make_mandate(issuer=issuer)


def test_negative_hitl_threshold_rejected(make_mandate: Callable[..., Mandate]) -> None:
    with pytest.raises(ValidationError):
        make_mandate(hitl_threshold=-1)


def test_invalid_state_rejected(make_mandate: Callable[..., Mandate]) -> None:
    with pytest.raises(ValidationError):
        make_mandate(state="pending")


def test_scope_rejects_empty_ids() -> None:
    with pytest.raises(ValidationError):
        Scope(merchants=[""], categories=[])


def test_scope_rejects_bare_string_and_stores_tuples() -> None:
    with pytest.raises(ValidationError):
        Scope(merchants="MP-1", categories=[])
    scope = Scope(merchants=["MP-1"], categories=["pharmacy"])
    assert scope.merchants == ("MP-1",) and scope.categories == ("pharmacy",)


def test_mandate_is_immutable(make_mandate: Callable[..., Mandate]) -> None:
    mandate = make_mandate()
    with pytest.raises(ValidationError):
        mandate.subject = "agent:other"


def test_claims_round_trip(make_mandate: Callable[..., Mandate]) -> None:
    mandate = make_mandate()
    claims = mandate.to_claims()
    assert claims["agentmandates:limits.total"] == 15_000_000
    assert claims["agentmandates:state"] == "open"
    assert Mandate.from_claims(claims) == mandate


def test_from_claims_missing_claim(make_mandate: Callable[..., Mandate]) -> None:
    claims = make_mandate().to_claims()
    del claims["jti"]
    with pytest.raises(ValueError, match="jti"):
        Mandate.from_claims(claims)
