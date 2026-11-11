"""Mandate model, signing (SD-JWT, Ed25519) and pure verification."""

from ritta.mandates.keys import (
    generate_keypair,
    load_private_key_pem,
    load_public_key_pem,
    private_key_to_pem,
    public_key_to_pem,
)
from ritta.mandates.model import Limits, Mandate, Scope
from ritta.mandates.sdjwt import sign
from ritta.mandates.verify import RejectionReason, VerificationResult, verify

__all__ = [
    "Limits",
    "Mandate",
    "RejectionReason",
    "Scope",
    "VerificationResult",
    "generate_keypair",
    "load_private_key_pem",
    "load_public_key_pem",
    "private_key_to_pem",
    "public_key_to_pem",
    "sign",
    "verify",
]
