from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from ritta.mandates.keys import (
    generate_keypair,
    load_private_key_pem,
    load_public_key_pem,
    private_key_to_pem,
    public_key_to_pem,
)


def test_pem_round_trip() -> None:
    private_key, public_key = generate_keypair()
    loaded_private = load_private_key_pem(private_key_to_pem(private_key))
    loaded_public = load_public_key_pem(public_key_to_pem(public_key))
    signature = loaded_private.sign(b"msg")
    loaded_public.verify(signature, b"msg")
    public_key.verify(signature, b"msg")


def test_encrypted_private_key_round_trip() -> None:
    private_key, public_key = generate_keypair()
    password = b"test-password-generated-in-test"
    pem = private_key_to_pem(private_key, password=password)
    assert b"ENCRYPTED" in pem
    with pytest.raises(TypeError):
        load_private_key_pem(pem)
    loaded = load_private_key_pem(pem, password=password)
    public_key.verify(loaded.sign(b"msg"), b"msg")


def test_rejects_non_ed25519_keys() -> None:
    other = ec.generate_private_key(ec.SECP256R1())
    private_pem = other.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = other.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    with pytest.raises(TypeError):
        load_private_key_pem(private_pem)
    with pytest.raises(TypeError):
        load_public_key_pem(public_pem)
