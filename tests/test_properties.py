"""Property-based tests: invariants that must hold for every mandate and request."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from ritta.mandates import Limits, Mandate, Scope, generate_keypair, sign, verify

# One key pair for the whole module, generated at runtime (no secrets in the repo).
PRIVATE_KEY, PUBLIC_KEY = generate_keypair()

MAX_AMOUNT = 10**15
ids = st.text(st.characters(codec="utf-8"), min_size=1, max_size=16)
times = st.datetimes(
    min_value=datetime(2000, 1, 1), max_value=datetime(2100, 1, 1), timezones=st.just(UTC)
)


@st.composite
def limits(draw: st.DrawFn) -> Limits:
    total = draw(st.integers(1, MAX_AMOUNT))
    per_operation = draw(st.integers(1, total))
    currency = draw(st.sampled_from(["ARS", "BRL", "USD", "USDC", "EURC"]))
    return Limits(total=total, per_operation=per_operation, currency=currency)


@st.composite
def mandates(draw: st.DrawFn) -> Mandate:
    return Mandate(
        issuer=draw(st.sampled_from(["did:web:acme.com.ar", "https://acme.com.br"])),
        subject=draw(ids),
        limits=draw(limits()),
        scope=Scope(
            merchants=draw(st.lists(ids, max_size=3)),
            categories=draw(st.lists(ids, max_size=3)),
        ),
        hitl_threshold=draw(st.integers(0, MAX_AMOUNT)),
        state=draw(st.sampled_from(["open", "closed"])),
        expires_at=draw(times),
    )


def _in_scope(mandate: Mandate, data: st.DataObject) -> tuple[str, str]:
    merchant = data.draw(
        st.sampled_from(mandate.scope.merchants) if mandate.scope.merchants else ids
    )
    category = data.draw(
        st.sampled_from(mandate.scope.categories) if mandate.scope.categories else ids
    )
    return merchant, category


@given(mandate=mandates(), data=st.data())
def test_amount_over_per_operation_never_ok(mandate: Mandate, data: st.DataObject) -> None:
    token = sign(mandate, PRIVATE_KEY)
    amount = data.draw(st.integers(mandate.limits.per_operation + 1, 2 * MAX_AMOUNT + 1))
    merchant, category = _in_scope(mandate, data)
    result = verify(
        token,
        PUBLIC_KEY,
        amount=amount,
        merchant=merchant,
        category=category,
        remaining=data.draw(st.integers(0, 4 * MAX_AMOUNT)),
        now=data.draw(times),
    )
    assert not result.ok


@given(mandate=mandates(), data=st.data())
def test_expired_mandate_never_ok(mandate: Mandate, data: st.DataObject) -> None:
    token = sign(mandate, PRIVATE_KEY)
    now = mandate.expires_at + timedelta(seconds=data.draw(st.integers(0, 10**9)))
    merchant, category = _in_scope(mandate, data)
    amount = data.draw(st.integers(1, mandate.limits.per_operation))
    result = verify(
        token,
        PUBLIC_KEY,
        amount=amount,
        merchant=merchant,
        category=category,
        remaining=mandate.limits.total,
        now=now,
    )
    assert not result.ok
    assert result.reason == "expired"


@given(mandate=mandates(), data=st.data())
def test_any_altered_character_never_ok(mandate: Mandate, data: st.DataObject) -> None:
    token = sign(mandate, PRIVATE_KEY)
    index = data.draw(st.integers(0, len(token) - 1))
    replacement = data.draw(st.characters(codec="utf-8").filter(lambda c: c != token[index]))
    tampered = token[:index] + replacement + token[index + 1 :]
    merchant, category = _in_scope(mandate, data)
    result = verify(
        tampered,
        PUBLIC_KEY,
        amount=1,
        merchant=merchant,
        category=category,
        remaining=mandate.limits.total,
        now=mandate.expires_at - timedelta(seconds=1),
    )
    assert not result.ok


@given(mandate=mandates(), data=st.data())
def test_any_altered_byte_never_ok(mandate: Mandate, data: st.DataObject) -> None:
    raw = bytearray(sign(mandate, PRIVATE_KEY).encode("ascii"))
    index = data.draw(st.integers(0, len(raw) - 1))
    raw[index] ^= data.draw(st.integers(1, 255))
    tampered = raw.decode("latin-1")
    result = verify(
        tampered,
        PUBLIC_KEY,
        amount=1,
        merchant=mandate.scope.merchants[0] if mandate.scope.merchants else "m",
        category=mandate.scope.categories[0] if mandate.scope.categories else "c",
        remaining=mandate.limits.total,
        now=mandate.expires_at - timedelta(seconds=1),
    )
    assert not result.ok


@given(mandate=mandates(), data=st.data())
def test_valid_request_within_limits_is_ok(mandate: Mandate, data: st.DataObject) -> None:
    # Sanity check for the negative properties above: in-limit requests do verify.
    token = sign(mandate, PRIVATE_KEY)
    amount = data.draw(st.integers(1, mandate.limits.per_operation))
    merchant, category = _in_scope(mandate, data)
    result = verify(
        token,
        PUBLIC_KEY,
        amount=amount,
        merchant=merchant,
        category=category,
        remaining=data.draw(st.integers(amount, 4 * MAX_AMOUNT)),
        now=mandate.expires_at - timedelta(seconds=data.draw(st.integers(1, 10**9))),
    )
    assert result.ok, result.reason


@given(mandate=mandates())
def test_other_key_never_ok(mandate: Mandate) -> None:
    _, other_public = generate_keypair()
    result = verify(
        sign(mandate, PRIVATE_KEY),
        other_public,
        amount=1,
        merchant=mandate.scope.merchants[0] if mandate.scope.merchants else "m",
        category=mandate.scope.categories[0] if mandate.scope.categories else "c",
        remaining=mandate.limits.total,
        now=mandate.expires_at - timedelta(seconds=1),
    )
    assert result.reason == "invalid_signature"
