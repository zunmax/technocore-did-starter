"""Conformance tests: this client vs. the Technocore server's canonical string.

Why this file exists
--------------------
`technocore_agent.py` signs a canonical string:

    room|nonce|swept-text

The server verifies a signature over *its own* reconstruction of that same
string. If the two disagree by a single byte, every signed write this client
makes is rejected -- and the failure surfaces as a signature error, not as a
text-normalization error, so it is disproportionately painful to debug.

Unit tests that check this client only against itself cannot catch that class
of bug: a wrong-but-self-consistent sweep passes them all. So the reference
implementation below is mirrored from the server's own published signer
(flop-labs/technocore-chat, `scripts/sign.py`) and kept deliberately
standalone -- it must not import helpers from `technocore_agent`, or it would
inherit the very defect it exists to detect.

Reference rules pinned here:
  * sweep: characters in Unicode categories Cc, Cf, Cs, Co, Zl, Zp become
    U+0020, then leading/trailing whitespace is stripped
  * text that is empty after the sweep is refused
  * swept text is capped at 4096 characters
  * nonce must match ^[0-9]{1,19}$ -- ASCII digits only
  * canonical string is f"{room}|{nonce}|{swept}", signed as UTF-8
  * signature is unpadded base64url of the raw 64-byte Ed25519 signature
  * did:key is "did:key:z" + base58btc(0xED 0x01 || raw 32-byte public key)

NFC is deliberately *not* applied; see TestDocumentedNonNormalization for the
rationale and the assertion that pins it.

Run:  python -m pytest tests/test_server_conformance.py -v
"""

from __future__ import annotations

import base64
import hashlib
import re
import unicodedata

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import technocore_agent as tc

# --------------------------------------------------------------------------
# Reference implementation, mirrored from the server's scripts/sign.py.
# --------------------------------------------------------------------------

REF_INVISIBLE_CATEGORIES = ("Cc", "Cf", "Cs", "Co", "Zl", "Zp")
REF_MAX_TEXT_CHARS = 4096
REF_NONCE_RE = re.compile(r"[0-9]{1,19}")
REF_BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
REF_MULTICODEC_ED25519 = b"\xed\x01"


def ref_sweep(text: str) -> str:
    """The server's single-line sweep: invisibles to space, then strip."""
    cleaned = "".join(
        " " if unicodedata.category(ch) in REF_INVISIBLE_CATEGORIES else ch
        for ch in text
    ).strip()
    if not cleaned:
        raise ValueError("no visible text after sweep")
    if len(cleaned) > REF_MAX_TEXT_CHARS:
        raise ValueError("text over cap")
    return cleaned


def ref_canonical(room: str, nonce: str, text: str) -> str:
    if not REF_NONCE_RE.fullmatch(nonce):
        raise ValueError("nonce must be 1-19 ASCII digits")
    return f"{room}|{nonce}|{ref_sweep(text)}"


def ref_signature(key: Ed25519PrivateKey, canonical: str) -> str:
    raw = key.sign(canonical.encode("utf-8"))
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def ref_base58btc(payload: bytes) -> str:
    zeros = len(payload) - len(payload.lstrip(b"\x00"))
    number = int.from_bytes(payload, "big")
    out = ""
    while number:
        number, rem = divmod(number, 58)
        out = REF_BASE58_ALPHABET[rem] + out
    return "1" * zeros + out


def ref_did(key: Ed25519PrivateKey) -> str:
    raw = key.public_key().public_bytes_raw()
    return "did:key:z" + ref_base58btc(REF_MULTICODEC_ED25519 + raw)


# --------------------------------------------------------------------------
# Fixed key, so vectors are reproducible across machines and CI runs.
# --------------------------------------------------------------------------

KEY = Ed25519PrivateKey.from_private_bytes(
    hashlib.sha256(b"technocore-conformance-vector").digest()
)
DID = tc.did_from_private_key(KEY)
ROOM = "agents"

# (id, nonce, raw text) -- each entry exercises a different sweep edge.
TEXT_VECTORS = [
    ("plain_ascii", "1", "hello world"),
    ("zero_width_space", "2", "hello\u200bworld"),
    ("rtl_override", "3", "safe\u202egnp.exe"),
    ("tab_and_newline", "4", "a\tb\nc"),
    ("surrounding_whitespace", "5", "   padded   "),
    ("bom_mid_string", "6", "a\ufeffb"),
    ("nbsp_is_kept", "7", "a\u00a0b"),
    ("ideographic_space_is_kept", "8", "a\u3000b"),
    ("astral_emoji", "9", "ship it \U0001f680"),
    ("cyrillic_confusable", "10", "p\u0430ypal"),
    ("combining_accent", "11", "cafe\u0301"),
    ("precomposed_accent", "12", "caf\u00e9"),
    ("pipe_inside_text", "13", "a|b|c"),
    ("line_separator", "14", "a\u2028b"),
    ("soft_hyphen", "15", "a\u00adb"),
    ("at_length_cap", "16", "x" * REF_MAX_TEXT_CHARS),
]

IDS = [vector[0] for vector in TEXT_VECTORS]


class TestCanonicalStringMatchesServer:
    """The byte-for-byte agreement that every signed write depends on."""

    @pytest.mark.parametrize("_id,nonce,text", TEXT_VECTORS, ids=IDS)
    def test_canonical_string_matches_reference(self, _id, nonce, text):
        _, payload = tc.message_payload(ROOM, nonce, text)
        assert payload.decode("utf-8") == ref_canonical(ROOM, nonce, text)

    @pytest.mark.parametrize("_id,nonce,text", TEXT_VECTORS, ids=IDS)
    def test_signature_matches_reference(self, _id, nonce, text):
        _, payload = tc.message_payload(ROOM, nonce, text)
        assert tc.sign_bytes(KEY, payload) == ref_signature(
            KEY, ref_canonical(ROOM, nonce, text)
        )

    @pytest.mark.parametrize("_id,nonce,text", TEXT_VECTORS, ids=IDS)
    def test_client_signature_verifies_over_server_payload(self, _id, nonce, text):
        """End-to-end property: the server's own bytes must verify."""
        _, payload = tc.message_payload(ROOM, nonce, text)
        signature = tc.sign_bytes(KEY, payload)
        server_bytes = ref_canonical(ROOM, nonce, text).encode("utf-8")
        tc.verify_bytes(DID, signature, server_bytes)


class TestDidDerivation:
    def test_did_matches_reference(self):
        assert tc.did_from_private_key(KEY) == ref_did(KEY)

    def test_did_is_stable_vector(self):
        """Pinned so any encoding regression shows up directly in the diff."""
        assert DID == "did:key:z6MkpDgEKrhqMwD7QdJPPhDFxmN6XP1NfKb7ZZGsAH5oU7if"

    def test_multibase_length_and_prefix(self):
        assert DID.startswith("did:key:z6Mk")
        assert len(DID.split(":")[-1]) == 48

    def test_round_trip_through_public_key(self):
        recovered = tc.public_key_from_did(DID).public_bytes_raw()
        assert recovered == KEY.public_key().public_bytes_raw()


class TestSweepAgreement:
    @pytest.mark.parametrize(
        "codepoint,is_swept",
        [
            ("\u200b", True),   # ZERO WIDTH SPACE       Cf
            ("\u202e", True),   # RIGHT-TO-LEFT OVERRIDE Cf
            ("\ufeff", True),   # BOM / ZWNBSP           Cf
            ("\u00ad", True),   # SOFT HYPHEN            Cf
            ("\u2028", True),   # LINE SEPARATOR         Zl
            ("\u2029", True),   # PARAGRAPH SEPARATOR    Zp
            ("\t", True),       # TAB                    Cc
            ("\n", True),       # LINE FEED              Cc
            ("\u00a0", False),  # NO-BREAK SPACE         Zs -- kept
            ("\u3000", False),  # IDEOGRAPHIC SPACE      Zs -- kept
            ("a", False),       # LATIN SMALL LETTER A   Ll
        ],
    )
    def test_category_membership_matches_reference(self, codepoint, is_swept):
        category = unicodedata.category(codepoint)
        assert (category in tc.INVISIBLE_CATEGORIES) is is_swept
        assert (category in REF_INVISIBLE_CATEGORIES) is is_swept

    def test_invisible_category_set_is_identical(self):
        assert set(tc.INVISIBLE_CATEGORIES) == set(REF_INVISIBLE_CATEGORIES)

    def test_text_cap_matches_reference(self):
        assert tc.MAX_MESSAGE_CHARS == REF_MAX_TEXT_CHARS


class TestRejectionsMatchServer:
    """Both sides must refuse the same inputs, for the same reasons."""

    @pytest.mark.parametrize(
        "text",
        ["", "   ", "\u200b", "\t\n", "\u200b\u202e", "x" * (REF_MAX_TEXT_CHARS + 1)],
    )
    def test_both_reject_unsignable_text(self, text):
        with pytest.raises(tc.ProtocolError):
            tc.message_payload(ROOM, "1", text)
        with pytest.raises(ValueError):
            ref_canonical(ROOM, "1", text)

    @pytest.mark.parametrize(
        "nonce",
        [
            "\u0661\u0662\u0663",  # Arabic-Indic digits: str.isdigit() is True
            "\uff11",              # FULLWIDTH DIGIT ONE
            "1_2",
            "-1",
            "1.0",
            " 1",
            "1 ",
            "",
            "9" * 20,              # 20 digits: one past the cap
            "0x10",
        ],
    )
    def test_both_reject_non_conforming_nonce(self, nonce):
        with pytest.raises(tc.ProtocolError):
            tc.message_payload(ROOM, nonce, "hello")
        with pytest.raises(ValueError):
            ref_canonical(ROOM, nonce, "hello")

    @pytest.mark.parametrize("nonce", ["0", "1", "9" * 19])
    def test_both_accept_boundary_nonces(self, nonce):
        _, payload = tc.message_payload(ROOM, nonce, "hello")
        assert payload.decode("utf-8") == ref_canonical(ROOM, nonce, "hello")


class TestDocumentedNonNormalization:
    """NFC is intentionally NOT applied. Pinned so it cannot drift silently.

    "cafe\\u0301" and "caf\\u00e9" render identically but sign differently.
    Applying NFC client-side would break verification, because the server signs
    the bytes it was given. Agreement -- not canonicalization -- is what matters.
    """

    def test_combining_and_precomposed_sign_differently(self):
        _, combining = tc.message_payload(ROOM, "1", "cafe\u0301")
        _, precomposed = tc.message_payload(ROOM, "1", "caf\u00e9")
        assert combining != precomposed
        assert combining.decode("utf-8") == ref_canonical(ROOM, "1", "cafe\u0301")
        assert precomposed.decode("utf-8") == ref_canonical(ROOM, "1", "caf\u00e9")

    def test_nfc_would_have_collapsed_them(self):
        assert unicodedata.normalize("NFC", "cafe\u0301") == "caf\u00e9"


class TestTamperDetection:
    """A mismatched payload must raise IdentityError, never verify silently."""

    def test_modified_text_fails(self):
        _, payload = tc.message_payload(ROOM, "1", "hello world")
        signature = tc.sign_bytes(KEY, payload)
        _, other = tc.message_payload(ROOM, "1", "hello world!")
        with pytest.raises(tc.IdentityError):
            tc.verify_bytes(DID, signature, other)

    def test_replayed_nonce_fails(self):
        _, payload = tc.message_payload(ROOM, "1", "hello world")
        signature = tc.sign_bytes(KEY, payload)
        _, other = tc.message_payload(ROOM, "2", "hello world")
        with pytest.raises(tc.IdentityError):
            tc.verify_bytes(DID, signature, other)

    def test_cross_room_replay_fails(self):
        _, payload = tc.message_payload("agents", "1", "hello world")
        signature = tc.sign_bytes(KEY, payload)
        _, other = tc.message_payload("lobby", "1", "hello world")
        with pytest.raises(tc.IdentityError):
            tc.verify_bytes(DID, signature, other)

    def test_signature_from_different_key_fails(self):
        _, payload = tc.message_payload(ROOM, "1", "hello world")
        other_key = Ed25519PrivateKey.from_private_bytes(
            hashlib.sha256(b"a-different-key").digest()
        )
        signature = tc.sign_bytes(other_key, payload)
        with pytest.raises(tc.IdentityError):
            tc.verify_bytes(DID, signature, payload)

    @pytest.mark.parametrize(
        "signature",
        ["", "abc", "A" * 85, "A" * 87, "A" * 86 + "=", "+" * 86, "/" * 86],
    )
    def test_malformed_signature_is_refused_before_verifying(self, signature):
        _, payload = tc.message_payload(ROOM, "1", "hello world")
        with pytest.raises(tc.ProtocolError):
            tc.verify_bytes(DID, signature, payload)
