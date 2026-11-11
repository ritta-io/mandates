"""Ed25519 key generation and PEM import/export.

Thin wrappers over :mod:`cryptography`. This module never logs, prints or embeds key
material in exception messages.
"""

from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

__all__ = [
    "Ed25519PrivateKey",
    "Ed25519PublicKey",
    "generate_keypair",
    "load_private_key_pem",
    "load_public_key_pem",
    "private_key_to_pem",
    "public_key_to_pem",
]


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    """Generate a fresh Ed25519 key pair ``(private_key, public_key)``."""
    private_key = Ed25519PrivateKey.generate()
    return private_key, private_key.public_key()


def private_key_to_pem(private_key: Ed25519PrivateKey, password: bytes | None = None) -> bytes:
    """Export a private key as PKCS#8 PEM, encrypted when ``password`` is given."""
    encryption: serialization.KeySerializationEncryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption,
    )


def public_key_to_pem(public_key: Ed25519PublicKey) -> bytes:
    """Export a public key as SubjectPublicKeyInfo PEM."""
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def load_private_key_pem(data: bytes, password: bytes | None = None) -> Ed25519PrivateKey:
    """Load an Ed25519 private key from PEM. Raises ``TypeError`` for other key types."""
    key = serialization.load_pem_private_key(data, password=password)
    if not isinstance(key, Ed25519PrivateKey):
        raise TypeError("expected an Ed25519 private key")
    return key


def load_public_key_pem(data: bytes) -> Ed25519PublicKey:
    """Load an Ed25519 public key from PEM. Raises ``TypeError`` for other key types."""
    key = serialization.load_pem_public_key(data)
    if not isinstance(key, Ed25519PublicKey):
        raise TypeError("expected an Ed25519 public key")
    return key
