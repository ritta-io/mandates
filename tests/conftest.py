from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from ritta.mandates import Limits, Mandate, Scope, generate_keypair
from ritta.mandates.keys import Ed25519PrivateKey, Ed25519PublicKey

# Fixed clock so tests are deterministic.
NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="session")
def keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    # Test keys are generated at runtime; nothing secret is stored in the repo.
    return generate_keypair()


@pytest.fixture(scope="session")
def make_mandate() -> Callable[..., Mandate]:
    def factory(**overrides: Any) -> Mandate:
        fields: dict[str, Any] = {
            "issuer": "did:web:farmacia-central.com.ar",
            "subject": "agent:compras-01",
            "limits": Limits(total=15_000_000, per_operation=5_000_000, currency="ARS"),
            "scope": Scope(merchants=["MP-123456"], categories=["pharmacy"]),
            "hitl_threshold": 1_000_000,
            "state": "open",
            "expires_at": NOW + timedelta(days=30),
        }
        fields.update(overrides)
        # An override of None drops the field (e.g. to use expires_in_days instead).
        return Mandate(**{k: v for k, v in fields.items() if v is not None})

    return factory
