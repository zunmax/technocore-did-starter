"""Tests for technocore_agent core: base58, DID, normalization, signing, identity.

Run: python -m pytest test_technocore_agent.py -v
No network access is required - every test is offline.
"""
import os

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from technocore_agent import (
    IdentityError,
    ProtocolError,
    base58btc_decode,
    base58btc_encode,
    contribution_payload,
    create_identity,
    did_from_private_key,
    message_payload,
    normalize_message,
    public_key_from_did,
    sign_bytes,
    validate_base_url,
    validate_name,
    validate_nonce,
    verify_bytes,
    verify_contribution_proof,
)


def make_key():
    return Ed25519PrivateKey.generate()


# ---------------------------------------------------------------- base58btc
def test_base58_roundtrip():
    for data in (b"hello", b"\x00\x00abc", b"\x00", bytes(range(256)), b""):
        assert base58btc_decode(base58btc_encode(data)) == data


def test_base58_preserves_leading_zeros():
    enc = base58btc_encode(b"\x00\x00\x01")
    assert enc.startswith("11")          # leading zero bytes -> leading '1's
    assert base58btc_decode(enc) == b"\x00\x00\x01"


def test_base58_rejects_ambiguous_chars():
    with pytest.raises(ProtocolError):
        base58btc_decode("0OIl")


# ---------------------------------------------------------------- did:key
def test_did_from_key_shape():
    did = did_from_private_key(make_key())
    assert did.startswith("did:key:z6Mk")
    assert len(did) == len("did:key:") + 48


def test_did_roundtrip_to_public_key():
    key = make_key()
    did = did_from_private_key(key)
    pub = key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    decoded = public_key_from_did(did).public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    assert decoded == pub


def test_did_rejects_bad_multibase():
    with pytest.raises(ProtocolError):
        public_key_from_did("did:key:z" + "1" * 47)      # wrong length
    with pytest.raises(ProtocolError):
        public_key_from_did("did:key:z6Lk" + "a" * 44)   # wrong multibase prefix
    with pytest.raises(ProtocolError):
        public_key_from_did("did:key:z6Mk0OIl" + "a" * 40)  # ambiguous b58 chars


# ---------------------------------------------------------------- normalize
def test_normalize_replaces_invisible_with_spaces_and_strips():
    assert normalize_message("  a\nb\tc ") == "a b c"


def test_normalize_rejects_empty_after_sweep():
    with pytest.raises(ProtocolError):
        normalize_message("\n\t \n")


def test_normalize_rejects_over_4096():
    with pytest.raises(ProtocolError):
        normalize_message("x" * 4097)


def test_normalize_keeps_unicode():
    assert normalize_message("приват ключ") == "приват ключ"


# ---------------------------------------------------------------- validation
def test_validate_name():
    assert validate_name("lobby") == "lobby"
    with pytest.raises(ProtocolError):
        validate_name("-bad")
    with pytest.raises(ProtocolError):
        validate_name("UPPER")


def test_validate_nonce_bounds():
    assert validate_nonce(1) == "1"
    assert validate_nonce("9" * 19) == "9" * 19
    with pytest.raises(ProtocolError):
        validate_nonce("9" * 20)
    with pytest.raises(ProtocolError):
        validate_nonce("12a")


# ---------------------------------------------------------------- sign/verify
def test_sign_bytes_canonical_encoding():
    key = make_key()
    sig = sign_bytes(key, b"payload")
    assert len(sig) == 86
    assert "=" not in sig
    assert sig[-1] in "AQgw"      # canonical: low 4 bits of the last byte are zero


def test_verify_roundtrip_and_tamper():
    key = make_key()
    did = did_from_private_key(key)
    payload = b"room|123|text"
    sig = sign_bytes(key, payload)
    verify_bytes(did, sig, payload)                     # must not raise
    with pytest.raises(IdentityError):
        verify_bytes(did, sig, b"room|124|text")        # tampered payload


def test_message_payload_exact_bytes():
    norm, payload = message_payload("lobby", 42, "hello world")
    assert norm == "hello world"
    assert payload == b"lobby|42|hello world"


# ---------------------------------------------------------------- identity file
def test_create_identity_roundtrip(tmp_path):
    path = tmp_path / "identity.pem"
    did = create_identity(path, "passphrase-12-chars")
    assert did.startswith("did:key:z6Mk")
    pem = path.read_bytes()
    assert b"BEGIN ENCRYPTED PRIVATE KEY" in pem
    loaded = serialization.load_pem_private_key(pem, password=b"passphrase-12-chars")
    assert did_from_private_key(loaded) == did


def test_create_identity_refuses_overwrite(tmp_path):
    path = tmp_path / "identity.pem"
    create_identity(path, "passphrase-12-chars")
    with pytest.raises(IdentityError):
        create_identity(path, "another-pass-12")


def test_create_identity_rejects_short_passphrase(tmp_path):
    with pytest.raises(IdentityError):
        create_identity(tmp_path / "identity.pem", "short")


# ---------------------------------------------------------------- base url
def test_validate_base_url_https_only():
    assert validate_base_url("https://technocore.chat") == "https://technocore.chat"
    assert validate_base_url("http://localhost:8080") == "http://localhost:8080"
    with pytest.raises(ProtocolError):
        validate_base_url("http://example.com")            # non-loopback http
    with pytest.raises(ProtocolError):
        validate_base_url("https://x.com/path?query=1")    # query
    with pytest.raises(ProtocolError):
        validate_base_url("https://user:pass@x.com")       # credentials


# ---------------------------------------------------------------- contribution proof
def test_contribution_proof_roundtrip_and_tamper():
    key = make_key()
    did = did_from_private_key(key)
    proof = {
        "schema": "technocore-contribution-proof-v1",
        "did": did,
        "artifact_url": "https://github.com/org/repo/commit/" + "a" * 40,
        "commit": "a" * 40,
        "signature": sign_bytes(key, contribution_payload(
            "https://github.com/org/repo/commit/" + "a" * 40, "a" * 40)),
    }
    verify_contribution_proof(proof)                       # must not raise
    proof["commit"] = "b" * 40
    with pytest.raises(Exception):
        verify_contribution_proof(proof)                   # tampered revision
