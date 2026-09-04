#!/usr/bin/env python3
"""Create a Technocore DID, publish signed messages, and prove contributions."""

from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import ipaddress
import json
import math
import os
import re
import sys
import time
import unicodedata
from collections.abc import Callable, Iterator
from http.client import InvalidURL
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

APP_VERSION = "1.0.0"
DEFAULT_BASE_URL = "https://technocore.chat"
DEFAULT_KEY_PATH = Path("identity.pem")
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_FOLLOW_WAIT_SECONDS = 10.0
MIN_FOLLOW_INTERVAL_SECONDS = 0.5
MAX_MESSAGE_CHARS = 4096
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
MAX_ERROR_RESPONSE_BYTES = 16 * 1024
MAX_PROOF_BYTES = 256 * 1024
MULTICODEC_ED25519 = b"\xed\x01"
MULTIBASE_LENGTH = 48
SIGNATURE_LENGTH = 86

BASE58BTC_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
BASE58BTC_INDEX = {
    character: index for index, character in enumerate(BASE58BTC_ALPHABET)
}
INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Zl", "Zp"})
NAME_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{0,47}")
NONCE_PATTERN = re.compile(r"[0-9]{1,19}")
SIGNATURE_PATTERN = re.compile(rf"[A-Za-z0-9_-]{{{SIGNATURE_LENGTH}}}")
COMMIT_PATTERN = re.compile(r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})")


class IdentityError(ValueError):
    """The local identity cannot be created, loaded, or verified."""


class ProtocolError(ValueError):
    """An input does not satisfy the published Technocore protocol."""


class NetworkError(RuntimeError):
    """A Technocore HTTP request failed or returned an invalid response."""


class LocalFileError(RuntimeError):
    """A local public artifact could not be read or written safely."""


class _NoRedirectHandler(HTTPRedirectHandler):
    """Disable urllib's automatic redirect handling for every request."""

    def redirect_request(
        self,
        request: Request,
        file_object: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def urlopen(
    request: Request,
    data: bytes | None = None,
    timeout: Any = None,
) -> Any:
    """Open a request without allowing urllib to follow redirects."""
    if data is None:
        return _NO_REDIRECT_OPENER.open(request, timeout=timeout)
    return _NO_REDIRECT_OPENER.open(request, data=data, timeout=timeout)


def base58btc_encode(data: bytes) -> str:
    """Encode bytes with the base58btc alphabet, preserving leading zeroes."""
    zeroes = len(data) - len(data.lstrip(b"\x00"))
    number = int.from_bytes(data, "big")
    encoded = ""
    while number:
        number, remainder = divmod(number, 58)
        encoded = BASE58BTC_ALPHABET[remainder] + encoded
    return "1" * zeroes + encoded


def base58btc_decode(value: str) -> bytes:
    """Decode a base58btc string, rejecting characters outside its alphabet."""
    number = 0
    for character in value:
        try:
            digit = BASE58BTC_INDEX[character]
        except KeyError as error:
            raise ProtocolError(
                f"invalid base58btc character: {character!r}"
            ) from error
        number = number * 58 + digit
    decoded = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    zeroes = len(value) - len(value.lstrip("1"))
    return b"\x00" * zeroes + decoded


def did_from_private_key(private_key: Ed25519PrivateKey) -> str:
    """Derive the public did:key identifier for an Ed25519 private key."""
    public_key = private_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    multibase = "z" + base58btc_encode(MULTICODEC_ED25519 + public_key)
    if len(multibase) != MULTIBASE_LENGTH or not multibase.startswith("z6Mk"):
        raise IdentityError("generated an invalid Ed25519 did:key")
    return "did:key:" + multibase


def public_key_from_did(did: str) -> Ed25519PublicKey:
    """Parse a canonical Ed25519 did:key into a verification key."""
    prefix = "did:key:"
    if not isinstance(did, str) or not did.startswith(prefix):
        raise ProtocolError("DID must start with 'did:key:z6Mk'")
    multibase = did[len(prefix) :]
    if len(multibase) != MULTIBASE_LENGTH or not multibase.startswith("z6Mk"):
        raise ProtocolError(
            "DID must be the canonical 48-character Ed25519 multibase form"
        )
    decoded = base58btc_decode(multibase[1:])
    if len(decoded) != 34 or not decoded.startswith(MULTICODEC_ED25519):
        raise ProtocolError("DID must contain an ed25519-pub key")
    try:
        return Ed25519PublicKey.from_public_bytes(decoded[2:])
    except ValueError as error:
        raise ProtocolError("DID contains an invalid Ed25519 public key") from error


def normalize_message(text: str) -> str:
    """Mirror the server's single-line sweep before signing a message."""
    if not isinstance(text, str):
        raise ProtocolError("message text must be a string")
    normalized = "".join(
        " " if unicodedata.category(character) in INVISIBLE_CATEGORIES else character
        for character in text
    ).strip()
    if not normalized:
        raise ProtocolError("message has no visible text after normalization")
    if len(normalized) > MAX_MESSAGE_CHARS:
        raise ProtocolError(
            f"message has {len(normalized)} characters; maximum is {MAX_MESSAGE_CHARS}"
        )
    return normalized


def terminal_safe_detail(value: Any) -> str:
    """Replace terminal control and formatting characters in an error detail."""
    return "".join(
        " " if unicodedata.category(character) in INVISIBLE_CATEGORIES else character
        for character in str(value)
    ).strip()


def validate_name(value: str, label: str = "room") -> str:
    """Validate a Technocore room or identifier name."""
    if not isinstance(value, str) or NAME_PATTERN.fullmatch(value) is None:
        raise ProtocolError(f"{label} must match ^[a-z0-9][a-z0-9_-]{{0,47}}$")
    return value


def validate_nonce(value: str | int) -> str:
    """Return a nonce string accepted by the signed-write protocol."""
    nonce = str(value)
    if NONCE_PATTERN.fullmatch(nonce) is None:
        raise ProtocolError("nonce must contain 1-19 ASCII digits")
    return nonce


def _posted_nonce_matches(posted_nonce: Any, selected_nonce: str) -> bool:
    """Accept only the canonical decimal representation of the nonce we sent."""
    if isinstance(posted_nonce, bool):
        return False
    if isinstance(posted_nonce, int):
        return str(posted_nonce) == selected_nonce
    if isinstance(posted_nonce, str):
        return (
            posted_nonce == selected_nonce
            and (posted_nonce == "0" or not posted_nonce.startswith("0"))
        )
    return False


def next_nonce() -> str:
    """Create a high-resolution wall-clock nonce within the 19-digit limit."""
    return validate_nonce(time.time_ns())


def sign_bytes(private_key: Ed25519PrivateKey, payload: bytes) -> str:
    """Return an unpadded base64url Ed25519 signature."""
    encoded = (
        base64.urlsafe_b64encode(private_key.sign(payload)).decode("ascii").rstrip("=")
    )
    if SIGNATURE_PATTERN.fullmatch(encoded) is None:
        raise IdentityError("generated an invalid Ed25519 signature encoding")
    return encoded


def verify_bytes(did: str, signature: str, payload: bytes) -> None:
    """Verify a canonical base64url Ed25519 signature against a did:key."""
    if (
        not isinstance(signature, str)
        or SIGNATURE_PATTERN.fullmatch(signature) is None
    ):
        raise ProtocolError("signature must contain 86 unpadded base64url characters")
    try:
        raw_signature = base64.b64decode(
            signature + "==", altchars=b"-_", validate=True
        )
        canonical_signature = (
            base64.urlsafe_b64encode(raw_signature).decode("ascii").rstrip("=")
        )
    except (binascii.Error, UnicodeError, ValueError) as error:
        raise ProtocolError("signature is not valid base64url") from error
    if canonical_signature != signature:
        raise ProtocolError("signature must use canonical base64url encoding")
    try:
        public_key_from_did(did).verify(raw_signature, payload)
    except InvalidSignature as error:
        raise IdentityError("signature does not match the DID and payload") from error


def message_payload(room: str, nonce: str | int, text: str) -> tuple[str, bytes]:
    """Build the normalized message and exact signed payload."""
    valid_room = validate_name(room)
    valid_nonce = validate_nonce(nonce)
    normalized = normalize_message(text)
    return normalized, f"{valid_room}|{valid_nonce}|{normalized}".encode()


def create_identity(
    path: Path,
    passphrase: str,
) -> str:
    """Create one encrypted private key without overwriting an existing identity."""
    path = path.expanduser().resolve()
    if path.exists():
        raise IdentityError(f"refusing to overwrite existing identity: {path}")
    if not isinstance(passphrase, str) or len(passphrase) < 12:
        raise IdentityError("identity passphrase must contain at least 12 characters")
    encoded_passphrase = passphrase.encode("utf-8")
    private_key = Ed25519PrivateKey.generate()
    try:
        private_bytes = private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(encoded_passphrase),
        )
        path.parent.mkdir(parents=True, exist_ok=True)
    except (OSError, ValueError) as error:
        raise IdentityError(
            f"cannot prepare encrypted identity {path}: {error}"
        ) from error

    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created = True
        with os.fdopen(descriptor, "wb") as key_file:
            descriptor = None
            key_file.write(private_bytes)
            key_file.flush()
            os.fsync(key_file.fileno())
        os.chmod(path, 0o600)
    except FileExistsError as error:
        raise IdentityError(
            f"refusing to overwrite existing identity: {path}"
        ) from error
    except OSError as error:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        cleanup_failed = False
        if created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True
        detail = f"cannot write encrypted identity {path}: {error}"
        if cleanup_failed:
            detail += f"; remove the incomplete file manually: {path}"
        raise IdentityError(detail) from error
    return did_from_private_key(private_key)


def load_identity(
    path: Path,
    passphrase: bytes | None = None,
    *,
    allow_prompt: bool = True,
    password_prompt: Callable[[str], str] = getpass.getpass,
) -> Ed25519PrivateKey:
    """Load an Ed25519 identity, prompting only when an encrypted key requires it."""
    resolved = path.expanduser().resolve()
    try:
        private_bytes = resolved.read_bytes()
    except OSError as error:
        raise IdentityError(f"cannot read identity {resolved}: {error}") from error
    password = passphrase
    if password is None:
        try:
            loaded = serialization.load_pem_private_key(private_bytes, password=None)
        except TypeError:
            if not allow_prompt:
                raise IdentityError(
                    "identity is encrypted and no passphrase was provided"
                ) from None
            entered = password_prompt(f"Passphrase for {resolved}: ")
            password = entered.encode("utf-8")
            loaded = _load_pem_key(private_bytes, password)
        except UnsupportedAlgorithm as error:
            raise IdentityError(
                f"identity uses unsupported encryption or key data: {resolved}"
            ) from error
        except ValueError as error:
            raise IdentityError(
                f"identity is not a valid PEM private key: {resolved}"
            ) from error
        else:
            raise IdentityError(
                "unencrypted private keys are not supported; create an encrypted identity"
            )
    else:
        loaded = _load_pem_key(private_bytes, password)
    if not isinstance(loaded, Ed25519PrivateKey):
        raise IdentityError("identity must contain an Ed25519 private key")
    return loaded


def _load_pem_key(private_bytes: bytes, password: bytes) -> Any:
    try:
        return serialization.load_pem_private_key(private_bytes, password=password)
    except UnsupportedAlgorithm as error:
        raise IdentityError(
            "identity uses unsupported encryption or key data"
        ) from error
    except (ValueError, TypeError) as error:
        raise IdentityError(
            "incorrect passphrase or invalid encrypted identity"
        ) from error


def _reject_unsafe_url_text(value: str, label: str) -> None:
    """Reject URL text that clients may interpret inconsistently."""
    for index, character in enumerate(value):
        if character == "%" and (
            index + 2 >= len(value)
            or re.fullmatch(r"[0-9A-Fa-f]{2}", value[index + 1 : index + 3]) is None
        ):
            raise ProtocolError(f"{label} contains an invalid percent escape")
    for component in (value, unquote(value)):
        for character in component:
            if (
                character.isspace()
                or not character.isprintable()
                or unicodedata.category(character) in INVISIBLE_CATEGORIES
            ):
                raise ProtocolError(
                    f"{label} must not contain whitespace or invisible characters"
                )


def _validate_url(
    value: str,
    *,
    label: str,
    allow_loopback_http: bool = False,
    allow_query: bool = False,
    allow_path: bool = True,
) -> Any:
    """Parse and validate a URL before handing it to urllib/http.client."""
    if not isinstance(value, str) or not value:
        raise ProtocolError(f"{label} must be a non-empty URL")
    if value != value.strip():
        raise ProtocolError(f"{label} must not contain surrounding whitespace")
    _reject_unsafe_url_text(value, label)
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
    except ValueError as error:
        raise ProtocolError(f"{label} is malformed") from error
    scheme = parsed.scheme.lower()
    if not scheme or not parsed.netloc or not hostname:
        raise ProtocolError(f"{label} must contain a host")
    if parsed.username is not None or parsed.password is not None:
        raise ProtocolError(f"{label} must not contain embedded credentials")
    if not allow_query and "?" in value:
        raise ProtocolError(f"{label} must not contain a query")
    if "#" in value:
        raise ProtocolError(f"{label} must not contain a fragment")
    if not allow_path and parsed.path not in {"", "/"}:
        raise ProtocolError(f"{label} must not contain a path")
    if "\\" in parsed.netloc or "\\" in parsed.path:
        raise ProtocolError(f"{label} contains an invalid path or host")

    authority = parsed.netloc
    if ":" in hostname:
        if not authority.startswith("[") or "]" not in authority:
            raise ProtocolError(f"{label} contains an invalid host")
        closing_bracket = authority.find("]")
        if closing_bracket != authority.rfind("]"):
            raise ProtocolError(f"{label} contains an invalid host")
        suffix = authority[closing_bracket + 1 :]
        if suffix and not suffix.startswith(":"):
            raise ProtocolError(f"{label} contains an invalid host")
    elif any(character in authority for character in "[]"):
        raise ProtocolError(f"{label} contains an invalid host")
    if authority.endswith(":"):
        raise ProtocolError(f"{label} contains an invalid port")
    try:
        _ = parsed.port
    except ValueError as error:
        raise ProtocolError(f"{label} contains an invalid port") from error
    try:
        if ":" in hostname:
            if "%" in hostname:
                raise ValueError("IPv6 zone identifiers are not allowed")
            ipaddress.IPv6Address(hostname)
        else:
            ascii_hostname = hostname.encode("idna").decode("ascii")
            if len(ascii_hostname) > 253 or any(
                not label_part
                or len(label_part) > 63
                or label_part.startswith("-")
                or label_part.endswith("-")
                or not re.fullmatch(r"[A-Za-z0-9-]+", label_part)
                for label_part in ascii_hostname.split(".")
            ):
                raise ValueError("invalid hostname")
    except (UnicodeError, ValueError) as error:
        raise ProtocolError(f"{label} contains an invalid host") from error

    if scheme != "https":
        loopback = hostname.lower() in {"localhost", "127.0.0.1", "::1"}
        if not (allow_loopback_http and scheme == "http" and loopback):
            raise ProtocolError(
                f"{label} must use HTTPS, except for an explicit loopback test server"
            )
    return parsed


def validate_base_url(base_url: str) -> str:
    """Require HTTPS except for explicit loopback development servers."""
    _validate_url(
        base_url,
        label="base URL",
        allow_loopback_http=True,
        allow_path=False,
    )
    return base_url.rstrip("/")


def validate_timeout(timeout: float) -> float:
    """Return a finite, positive HTTP timeout."""
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ProtocolError("timeout must be a finite number greater than zero")
    try:
        selected = float(timeout)
    except (OverflowError, ValueError) as error:
        raise ProtocolError("timeout must be a finite number greater than zero") from error
    if not math.isfinite(selected) or selected <= 0:
        raise ProtocolError("timeout must be a finite number greater than zero")
    return selected


def validate_follow_wait(wait: float) -> float:
    """Return a valid positive Technocore long-poll interval."""
    if isinstance(wait, bool) or not isinstance(wait, (int, float)):
        raise ProtocolError(
            "follow wait must be greater than zero and at most 10 seconds"
        )
    try:
        selected = float(wait)
    except (OverflowError, ValueError) as error:
        raise ProtocolError(
            "follow wait must be greater than zero and at most 10 seconds"
        ) from error
    if not math.isfinite(selected) or not 0 < selected <= 10:
        raise ProtocolError(
            "follow wait must be greater than zero and at most 10 seconds"
        )
    return selected


def request_json(
    request: Request,
    timeout: float,
    *,
    is_write: bool = False,
) -> dict[str, Any]:
    """Execute one bounded HTTP request and require a UTF-8 JSON object response."""
    selected_timeout = validate_timeout(timeout)
    timeout_detail = "Technocore request timed out"
    if is_write:
        timeout_detail = (
            "Technocore write timed out; its outcome is unknown, so read the room and "
            "check your DID and nonce before retrying"
        )
    try:
        with urlopen(request, timeout=selected_timeout) as response:
            raw_body = response.read(MAX_RESPONSE_BYTES + 1)
    except InvalidURL as error:
        raise NetworkError("Technocore request URL was invalid") from error
    except HTTPError as error:
        raw_error = error.read(MAX_ERROR_RESPONSE_BYTES + 1)
        truncated = len(raw_error) > MAX_ERROR_RESPONSE_BYTES
        body = (
            raw_error[:MAX_ERROR_RESPONSE_BYTES]
            .decode("utf-8", errors="replace")
            .strip()
        )
        if truncated:
            body += "…"
        detail = terminal_safe_detail(body or error.reason or "no response body")
        detail = detail or "no response body"
        raise NetworkError(f"Technocore returned HTTP {error.code}: {detail}") from None
    except URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise NetworkError(timeout_detail) from error
        raise NetworkError(
            f"could not reach Technocore: {terminal_safe_detail(error.reason)}"
        ) from error
    except TimeoutError as error:
        raise NetworkError(timeout_detail) from error
    except OSError as error:
        raise NetworkError(
            f"Technocore request failed: {terminal_safe_detail(error)}"
        ) from error
    if len(raw_body) > MAX_RESPONSE_BYTES:
        raise NetworkError(
            f"Technocore response exceeded the {MAX_RESPONSE_BYTES}-byte safety limit"
        )
    try:
        body = raw_body.decode("utf-8")
    except UnicodeDecodeError as error:
        raise NetworkError(
            "Technocore returned a response that was not valid UTF-8"
        ) from error
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, ValueError, UnicodeError, RecursionError) as error:
        raise NetworkError("Technocore returned a non-JSON response") from error
    if not isinstance(payload, dict):
        raise NetworkError("Technocore returned JSON that was not an object")
    return payload


def validate_room_response(response: dict[str, Any], expected_room: str) -> None:
    """Require the stable room fields published by the Technocore API."""
    if response.get("room") != expected_room:
        raise NetworkError("Technocore returned data for a different room")
    count = response.get("count")
    last_seq = response.get("last_seq")
    messages = response.get("messages")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise NetworkError("Technocore returned an invalid room count")
    if isinstance(last_seq, bool) or not isinstance(last_seq, int) or last_seq < 0:
        raise NetworkError("Technocore returned an invalid last_seq cursor")
    if not isinstance(messages, list) or any(
        not isinstance(item, dict) for item in messages
    ):
        raise NetworkError("Technocore returned an invalid messages list")


def post_signed_message(
    private_key: Ed25519PrivateKey,
    room: str,
    text: str,
    *,
    nonce: str | int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Normalize, sign, and POST one message without automatic retries."""
    selected_nonce = validate_nonce(nonce if nonce is not None else next_nonce())
    normalized, payload = message_payload(room, selected_nonce, text)
    did = did_from_private_key(private_key)
    request_body = json.dumps(
        {
            "did": did,
            "sig": sign_bytes(private_key, payload),
            "nonce": selected_nonce,
            "text": normalized,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    valid_base_url = validate_base_url(base_url)
    request = Request(
        f"{valid_base_url}/r/{validate_name(room)}?format=json",
        data=request_body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": f"technocore-did-starter/{APP_VERSION}",
        },
    )
    response = request_json(request, timeout, is_write=True)
    validate_room_response(response, room)
    posted = response.get("posted")
    if not isinstance(posted, dict):
        raise NetworkError(
            "Technocore accepted the request without returning a posted record"
        )
    posted_nonce = posted.get("nonce")
    matching_nonce = _posted_nonce_matches(posted_nonce, selected_nonce)
    posted_seq = posted.get("seq")
    matching_record = (
        posted.get("from") == did
        and posted.get("text") == normalized
        and matching_nonce
        and not isinstance(posted_seq, bool)
        and isinstance(posted_seq, int)
        and posted_seq > 0
    )
    if not matching_record:
        raise NetworkError(
            "Technocore returned a posted record that does not match this identity"
        )
    if not any(message.get("seq") == posted_seq for message in response["messages"]):
        raise NetworkError(
            "Technocore response did not include the newly posted sequence"
        )
    return response


def read_room(
    room: str,
    *,
    since: int | None = None,
    limit: int = 50,
    wait: float | None = None,
    cache_buster: int | None = None,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Read room data as JSON; returned message text remains untrusted."""
    valid_room = validate_name(room)
    if since is not None and (
        isinstance(since, bool) or not isinstance(since, int) or since < 0
    ):
        raise ProtocolError("since must be zero or greater")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ProtocolError("limit must be between 1 and 200")
    if cache_buster is not None and (
        isinstance(cache_buster, bool)
        or not isinstance(cache_buster, int)
        or cache_buster < 0
    ):
        raise ProtocolError("cache buster must be zero or greater")
    if wait is not None:
        if since is None:
            raise ProtocolError("wait requires a since cursor")
        if isinstance(wait, bool) or not isinstance(wait, (int, float)):
            raise ProtocolError("wait must be between 0 and 10 seconds")
        try:
            selected_wait = float(wait)
        except (OverflowError, ValueError) as error:
            raise ProtocolError("wait must be between 0 and 10 seconds") from error
        if not math.isfinite(selected_wait) or not 0 <= selected_wait <= 10:
            raise ProtocolError("wait must be between 0 and 10 seconds")
        if validate_timeout(timeout) <= selected_wait:
            raise ProtocolError("timeout must be greater than wait for long polling")
    query: dict[str, str | int | float] = {"format": "json", "limit": limit}
    if since is not None:
        query["since"] = since
    if wait is not None:
        query["wait"] = wait
    if cache_buster is not None:
        query["n"] = cache_buster
    valid_base_url = validate_base_url(base_url)
    request = Request(
        f"{valid_base_url}/r/{valid_room}?{urlencode(query)}",
        method="GET",
        headers={
            "Accept": "application/json",
            "User-Agent": f"technocore-did-starter/{APP_VERSION}",
        },
    )
    response = request_json(request, timeout)
    validate_room_response(response, valid_room)
    return response


def follow_room(
    room: str,
    *,
    since: int,
    limit: int = 50,
    wait: float = DEFAULT_FOLLOW_WAIT_SECONDS,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> Iterator[dict[str, Any]]:
    """Continuously yield non-empty room responses while advancing the cursor."""
    selected_wait = validate_follow_wait(wait)
    cursor = since
    cache_buster = 0
    while True:
        request_started = time.monotonic()
        response = read_room(
            room,
            since=cursor,
            limit=limit,
            wait=selected_wait,
            cache_buster=cache_buster,
            base_url=base_url,
            timeout=timeout,
        )
        cache_buster += 1
        next_cursor = response["last_seq"]
        if next_cursor < cursor:
            raise NetworkError("Technocore moved the room cursor backwards")
        if response["messages"]:
            if next_cursor <= cursor:
                raise NetworkError(
                    "Technocore returned messages without advancing last_seq"
                )
            cursor = next_cursor
            yield response
        elif next_cursor > cursor:
            # A deployment may advance its cursor while returning no retained rows.
            # Keep following from that cursor instead of replaying an empty window.
            cursor = next_cursor
        elapsed = time.monotonic() - request_started
        if elapsed < MIN_FOLLOW_INTERVAL_SECONDS:
            time.sleep(MIN_FOLLOW_INTERVAL_SECONDS - elapsed)


def contribution_payload(artifact_url: str, commit: str) -> bytes:
    """Build a deterministic payload linking a DID to one published revision."""
    if not isinstance(artifact_url, str) or not isinstance(commit, str):
        raise ProtocolError("artifact URL and commit must be strings")
    _validate_url(
        artifact_url,
        label="artifact URL",
        allow_loopback_http=False,
        allow_query=False,
        allow_path=True,
    )
    if COMMIT_PATTERN.fullmatch(commit) is None:
        raise ProtocolError(
            "commit must be a complete 40- or 64-character hexadecimal revision"
        )
    record = {
        "artifact_url": artifact_url,
        "commit": commit.lower(),
        "schema": "technocore-contribution-v1",
    }
    canonical = json.dumps(
        record, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return canonical.encode("utf-8")


def create_contribution_proof(
    private_key: Ed25519PrivateKey,
    artifact_url: str,
    commit: str,
) -> dict[str, str]:
    """Sign a public artifact URL and immutable hexadecimal revision."""
    payload = contribution_payload(artifact_url, commit)
    return {
        "schema": "technocore-contribution-proof-v1",
        "did": did_from_private_key(private_key),
        "artifact_url": artifact_url,
        "commit": commit.lower(),
        "signature": sign_bytes(private_key, payload),
    }


def verify_contribution_proof(proof: dict[str, Any]) -> None:
    """Validate a contribution proof's shape and Ed25519 signature."""
    if not isinstance(proof, dict):
        raise ProtocolError("contribution proof must contain an object")
    if proof.get("schema") != "technocore-contribution-proof-v1":
        raise ProtocolError("unsupported contribution proof schema")
    required = ("did", "artifact_url", "commit", "signature")
    if any(not isinstance(proof.get(field), str) for field in required):
        raise ProtocolError("contribution proof is missing required string fields")
    payload = contribution_payload(proof["artifact_url"], proof["commit"])
    verify_bytes(proof["did"], proof["signature"], payload)


def write_new_json(path: Path, payload: dict[str, Any]) -> None:
    """Write public proof JSON without overwriting an existing file."""
    resolved = path.expanduser().resolve()
    serialized = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    descriptor: int | None = None
    created = False
    try:
        descriptor = os.open(resolved, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        created = True
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            descriptor = None
            output.write(serialized)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as error:
        raise LocalFileError(
            f"refusing to overwrite existing file: {resolved}"
        ) from error
    except OSError as error:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        cleanup_failed = False
        if created:
            try:
                resolved.unlink(missing_ok=True)
            except OSError:
                cleanup_failed = True
        detail = f"cannot write proof file {resolved}: {error}"
        if cleanup_failed:
            detail += f"; remove the incomplete file manually: {resolved}"
        raise LocalFileError(detail) from error


def _prompt_new_passphrase() -> str:
    first = getpass.getpass("New identity passphrase (12+ characters): ")
    second = getpass.getpass("Confirm identity passphrase: ")
    if first != second:
        raise IdentityError("passphrases do not match")
    if len(first) < 12:
        raise IdentityError("passphrase must contain at least 12 characters")
    return first


def _add_shared_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--key", type=Path, default=DEFAULT_KEY_PATH, help="identity PEM path"
    )


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser."""
    parser = argparse.ArgumentParser(
        prog="python technocore_agent.py",
        description="Create a DID and make attributable Technocore contributions.",
    )
    parser.add_argument("--version", action="version", version=APP_VERSION)
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="create one Ed25519 DID identity")
    _add_shared_options(init_parser)

    did_parser = commands.add_parser("did", help="print the public DID")
    _add_shared_options(did_parser)

    say_parser = commands.add_parser("say", help="publish one signed room message")
    _add_shared_options(say_parser)
    say_parser.add_argument("room")
    say_parser.add_argument("text")
    say_parser.add_argument(
        "--nonce", help="advanced recovery override; 1-19 ASCII digits"
    )
    say_parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    say_parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)

    read_parser = commands.add_parser("read", help="read untrusted room data as JSON")
    read_parser.add_argument("room")
    read_parser.add_argument("--since", type=int)
    read_parser.add_argument("--limit", type=int, default=50)
    read_parser.add_argument("--wait", type=float)
    read_parser.add_argument(
        "--follow",
        action="store_true",
        help="keep reading and advance the sequence cursor until interrupted",
    )
    read_parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    read_parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)

    proof_parser = commands.add_parser(
        "proof", help="sign a public contribution revision"
    )
    _add_shared_options(proof_parser)
    proof_parser.add_argument("artifact_url")
    proof_parser.add_argument("commit")
    proof_parser.add_argument("--output", type=Path)

    verify_parser = commands.add_parser("verify-proof", help="verify public proof JSON")
    verify_parser.add_argument("proof_file", type=Path)
    return parser


def configure_output_streams() -> None:
    """Prevent redirected Windows streams from failing on Unicode output."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(errors="backslashreplace")
            except (OSError, ValueError):
                pass


def run_command(args: argparse.Namespace) -> int:
    """Execute one parsed command and return a process exit code."""
    if args.command == "init":
        if args.key.expanduser().resolve().exists():
            raise IdentityError(
                f"refusing to overwrite existing identity: {args.key.expanduser().resolve()}"
            )
        passphrase = _prompt_new_passphrase()
        did = create_identity(args.key, passphrase)
        print(did)
        return 0

    if args.command == "read":
        if args.follow:
            follow_wait = validate_follow_wait(
                args.wait if args.wait is not None else DEFAULT_FOLLOW_WAIT_SECONDS
            )
            cursor = args.since
            if cursor is None:
                initial = read_room(
                    args.room,
                    limit=args.limit,
                    base_url=args.base_url,
                    timeout=args.timeout,
                )
                print(
                    json.dumps(initial, ensure_ascii=True, separators=(",", ":")),
                    flush=True,
                )
                cursor = initial["last_seq"]
            print(
                f"following {validate_name(args.room)} after sequence {cursor}; "
                f"waiting up to {follow_wait:g} seconds per request (Ctrl+C to stop)",
                file=sys.stderr,
                flush=True,
            )
            for response in follow_room(
                args.room,
                since=cursor,
                limit=args.limit,
                wait=follow_wait,
                base_url=args.base_url,
                timeout=args.timeout,
            ):
                print(
                    json.dumps(response, ensure_ascii=True, separators=(",", ":")),
                    flush=True,
                )
            return 0
        response = read_room(
            args.room,
            since=args.since,
            limit=args.limit,
            wait=args.wait,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        print(json.dumps(response, ensure_ascii=True, indent=2))
        return 0

    if args.command == "verify-proof":
        proof_path = args.proof_file.expanduser().resolve()
        try:
            with proof_path.open("rb") as proof_file:
                proof_bytes = proof_file.read(MAX_PROOF_BYTES + 1)
        except (OSError, UnicodeError, ValueError, RecursionError) as error:
            raise LocalFileError(f"cannot read proof JSON: {error}") from error
        if len(proof_bytes) > MAX_PROOF_BYTES:
            raise LocalFileError(
                f"proof JSON exceeded the {MAX_PROOF_BYTES}-byte safety limit"
            )
        try:
            proof_text = proof_bytes.decode("utf-8")
            proof = json.loads(proof_text)
        except (UnicodeError, ValueError, RecursionError) as error:
            raise LocalFileError(f"cannot read proof JSON: {error}") from error
        if not isinstance(proof, dict):
            raise ProtocolError("proof JSON must contain an object")
        verify_contribution_proof(proof)
        print(f"valid proof for {proof['did']}")
        return 0

    if (
        args.command == "proof"
        and args.output
        and args.output.expanduser().resolve().exists()
    ):
        raise LocalFileError(
            f"refusing to overwrite existing file: {args.output.expanduser().resolve()}"
        )

    private_key = load_identity(args.key)
    if args.command == "did":
        print(did_from_private_key(private_key))
        return 0
    if args.command == "say":
        response = post_signed_message(
            private_key,
            args.room,
            args.text,
            nonce=args.nonce,
            base_url=args.base_url,
            timeout=args.timeout,
        )
        print(json.dumps(response, ensure_ascii=True, indent=2))
        return 0
    if args.command == "proof":
        proof = create_contribution_proof(private_key, args.artifact_url, args.commit)
        if args.output:
            write_new_json(args.output, proof)
            print(args.output.expanduser().resolve())
        else:
            print(json.dumps(proof, ensure_ascii=True, indent=2, sort_keys=True))
        return 0
    raise ProtocolError(f"unsupported command: {args.command}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    configure_output_streams()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run_command(args)
    except (IdentityError, LocalFileError, NetworkError, ProtocolError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (EOFError, KeyboardInterrupt):
        print("cancelled", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
