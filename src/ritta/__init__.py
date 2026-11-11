"""Ritta: signed spend mandates for AI agents."""

from ritta.mandates import (
    Limits,
    Mandate,
    Scope,
    VerificationResult,
    generate_keypair,
    sign,
    verify,
)

__version__ = "0.2.0"

__all__ = [
    "Limits",
    "Mandate",
    "Scope",
    "VerificationResult",
    "__version__",
    "generate_keypair",
    "sign",
    "verify",
]
