"""Tests pour les fonctions d'identité crypto."""

import pytest
from pathlib import Path
from technocore_agent import (
    create_identity,
    load_identity,
    did_from_private_key,
    IdentityError,
    base58btc_encode,
    base58btc_decode,
)


def test_base58btc_encode_decode():
    """Base58btc encoding et decoding doivent être inverses."""
    original = b"hello world"
    encoded = base58btc_encode(original)
    decoded = base58btc_decode(encoded)
    assert decoded == original


def test_base58btc_with_leading_zeros():
    """Leading zeroes doivent être préservées."""
    data = b"\x00\x00\x01\x02"
    encoded = base58btc_encode(data)
    decoded = base58btc_decode(encoded)
    assert decoded == data


def test_create_identity_basic(tmp_path):
    """Créer une identité produit un fichier PEM valide."""
    key_path = tmp_path / "test_identity.pem"
    passphrase = "my-test-passphrase-123"
    
    did = create_identity(key_path, passphrase)
    
    assert key_path.exists()
    assert did.startswith("did:key:z6Mk")
    assert len(did) == 56


def test_create_identity_refuses_overwrite(tmp_path):
    """Créer une identité doit refuser de écraser un fichier existant."""
    key_path = tmp_path / "test_identity.pem"
    passphrase = "my-test-passphrase-123"
    
    create_identity(key_path, passphrase)
    
    with pytest.raises(IdentityError, match="refusing to overwrite"):
        create_identity(key_path, passphrase)


def test_create_identity_short_passphrase(tmp_path):
    """Les passphrases courtes doivent être rejetées."""
    key_path = tmp_path / "test_identity.pem"
    short_passphrase = "short"
    
    with pytest.raises(IdentityError, match="at least 12 characters"):
        create_identity(key_path, short_passphrase)


def test_load_identity_valid(tmp_path):
    """Charger une identité valide doit fonctionner."""
    key_path = tmp_path / "test_identity.pem"
    passphrase = "my-test-passphrase-123"
    
    original_did = create_identity(key_path, passphrase)
    loaded_key = load_identity(key_path, passphrase=passphrase.encode())
    loaded_did = did_from_private_key(loaded_key)
    
    assert original_did == loaded_did


def test_load_identity_wrong_passphrase(tmp_path):
    """Charger avec la mauvaise passphrase doit échouer."""
    key_path = tmp_path / "test_identity.pem"
    correct = "my-test-passphrase-123"
    wrong = "wrong-passphrase-456"
    
    create_identity(key_path, correct)
    
    with pytest.raises(IdentityError, match="incorrect passphrase"):
        load_identity(key_path, passphrase=wrong.encode())


def test_did_format():
    """Le format DID doit être canonique."""
    from technocore_agent import Ed25519PrivateKey
    
    private_key = Ed25519PrivateKey.generate()
    did = did_from_private_key(private_key)
    
    assert did.startswith("did:key:z6Mk")
    assert len(did) == 56
