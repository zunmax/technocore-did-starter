from __future__ import annotations

import base64
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from http.client import IncompleteRead
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import call, patch

import technocore_agent as agent
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from urllib.error import HTTPError
from urllib.request import Request


class _Response:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]


class _BrokenResponse(_Response):
    def read(self, limit: int = -1) -> bytes:
        raise IncompleteRead(b"partial")


class _BrokenErrorResponse(HTTPError):
    def read(self, limit: int = -1) -> bytes:
        raise IncompleteRead(b"partial")


class _MalformedRedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(302)
        self.send_header("Location", "http://[::1")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return None


class _RedirectHandler(BaseHTTPRequestHandler):
    target_hits = 0

    def do_GET(self) -> None:
        if self.path == "/target":
            type(self).target_hits += 1
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b"{}")
            return
        self.send_response(302)
        self.send_header("Location", "/target")
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return None


class SignatureAndIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.did = agent.did_from_private_key(self.private_key)
        self.payload = b"lobby|123|hello"
        self.signature = agent.sign_bytes(self.private_key, self.payload)

    def test_did_and_signature_round_trip(self) -> None:
        self.assertEqual(len(self.did), 8 + agent.MULTIBASE_LENGTH)
        self.assertTrue(self.did.startswith("did:key:z6Mk"))
        agent.verify_bytes(self.did, self.signature, self.payload)

    def test_signature_padding_is_rejected(self) -> None:
        with self.assertRaises(agent.ProtocolError):
            agent.verify_bytes(self.did, self.signature + "=", self.payload)

    def test_signature_trailing_bit_alias_is_rejected(self) -> None:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        last_index = alphabet.index(self.signature[-1])
        # The final base64url character carries only two signature bits; change one
        # of its four unused low bits while preserving those significant bits.
        alias_index = (last_index & 0b110000) | ((last_index + 1) & 0b001111)
        self.assertNotEqual(alias_index, last_index)
        alias = self.signature[:-1] + alphabet[alias_index]
        self.assertEqual(
            base64.urlsafe_b64decode(alias + "=="),
            base64.urlsafe_b64decode(self.signature + "=="),
        )
        with self.assertRaises(agent.ProtocolError):
            agent.verify_bytes(self.did, alias, self.payload)

    def test_non_string_signature_is_rejected(self) -> None:
        with self.assertRaises(agent.ProtocolError):
            agent.verify_bytes(self.did, None, self.payload)  # type: ignore[arg-type]

    def test_encrypted_identity_round_trip_and_no_overwrite(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "test-identity.pem"
            passphrase = "a test passphrase 123"
            created_did = agent.create_identity(path, passphrase)
            loaded = agent.load_identity(
                path,
                passphrase.encode("utf-8"),
                allow_prompt=False,
            )
            self.assertEqual(created_did, agent.did_from_private_key(loaded))
            with self.assertRaises(agent.IdentityError):
                agent.create_identity(path, passphrase)
            with self.assertRaises(agent.IdentityError):
                agent.load_identity(
                    path,
                    b"the wrong passphrase",
                    allow_prompt=False,
                )


class URLAndInputBoundaryTests(unittest.TestCase):
    def test_base_url_valid_and_loopback_http_allowed(self) -> None:
        self.assertEqual(
            agent.validate_base_url("https://example.com/"), "https://example.com"
        )
        self.assertEqual(
            agent.validate_base_url("http://127.0.0.1:8080/"),
            "http://127.0.0.1:8080",
        )
        self.assertEqual(
            agent.validate_base_url("http://[0:0:0:0:0:0:0:1]:8080/"),
            "http://[0:0:0:0:0:0:0:1]:8080",
        )

    def test_noncanonical_nonce_is_rejected_before_signing(self) -> None:
        with self.assertRaises(agent.ProtocolError):
            agent.validate_nonce("0123")

    def test_empty_host_is_rejected_for_base_and_artifact_urls(self) -> None:
        for value in ("https://", "https:///path"):
            with self.subTest(value=value):
                with self.assertRaises(agent.ProtocolError):
                    agent.validate_base_url(value)
                with self.assertRaises(agent.ProtocolError):
                    agent.contribution_payload(value, "a" * 40)

    def test_url_controls_whitespace_credentials_and_query_are_rejected(self) -> None:
        invalid_base_urls = (
            "https://example.com/\nnext",
            "https://example.com/%00",
            "https:// example.com",
            "https://user:pass@example.com",
            "https://example.com:bad",
            "https://example.com:99999",
            "https://example.com?format=json",
            "https://example.com#fragment",
            "https://example.com/path",
        )
        for value in invalid_base_urls:
            with self.subTest(value=value):
                with self.assertRaises(agent.ProtocolError):
                    agent.validate_base_url(value)

        invalid_artifacts = (
            "https://user@example.com/path",
            "https://example.com/path?x=1",
            "https://example.com/path#part",
            "https://example.com/path\u200b",
            "https://example.com:bad/path",
        )
        for value in invalid_artifacts:
            with self.subTest(value=value):
                with self.assertRaises(agent.ProtocolError):
                    agent.contribution_payload(value, "a" * 40)

    def test_non_loopback_http_is_rejected(self) -> None:
        with self.assertRaises(agent.ProtocolError):
            agent.validate_base_url("http://example.com")
        with self.assertRaises(agent.ProtocolError):
            agent.contribution_payload("http://127.0.0.1/path", "a" * 40)

    def test_giant_timeout_and_wait_are_protocol_errors(self) -> None:
        giant = 10**10000
        with self.assertRaises(agent.ProtocolError):
            agent.validate_timeout(giant)
        with self.assertRaises(agent.ProtocolError):
            agent.validate_follow_wait(giant)

    def test_non_dict_proof_is_rejected(self) -> None:
        with self.assertRaises(agent.ProtocolError):
            agent.verify_contribution_proof([])  # type: ignore[arg-type]


class NetworkBoundaryTests(unittest.TestCase):
    def test_redirect_is_not_followed(self) -> None:
        _RedirectHandler.target_hits = 0
        server = ThreadingHTTPServer(("127.0.0.1", 0), _RedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/start")
            with self.assertRaises(agent.NetworkError) as context:
                agent.request_json(request, 2)
            self.assertIn("HTTP 302", str(context.exception))
            self.assertEqual(_RedirectHandler.target_hits, 0)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_malformed_redirect_is_network_error(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), _MalformedRedirectHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(f"http://127.0.0.1:{server.server_port}/start")
            with self.assertRaises(agent.NetworkError) as context:
                agent.request_json(request, 2)
            self.assertIn("HTTP 302", str(context.exception))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_bad_json_is_network_error(self) -> None:
        request = Request("https://example.com")
        with patch.object(agent, "urlopen", return_value=_Response(b"not json")):
            with self.assertRaises(agent.NetworkError):
                agent.request_json(request, 2)

    def test_bad_utf8_is_network_error(self) -> None:
        request = Request("https://example.com")
        with patch.object(agent, "urlopen", return_value=_Response(b"\xff")):
            with self.assertRaises(agent.NetworkError):
                agent.request_json(request, 2)

    def test_deep_json_is_network_error(self) -> None:
        request = Request("https://example.com")
        deep_json = ("[" * 2000) + ("]" * 2000)
        with patch.object(agent, "urlopen", return_value=_Response(deep_json.encode())):
            with self.assertRaises(agent.NetworkError):
                agent.request_json(request, 2)

    def test_huge_json_number_is_network_error(self) -> None:
        request = Request("https://example.com")
        huge_number = ('{"value":' + ("9" * 10000) + '}').encode()
        with patch.object(agent, "urlopen", return_value=_Response(huge_number)):
            with self.assertRaises(agent.NetworkError):
                agent.request_json(request, 2)

    def test_broken_response_stream_is_network_error(self) -> None:
        request = Request("https://example.com")
        with patch.object(agent, "urlopen", return_value=_BrokenResponse(b"partial")):
            with self.assertRaises(agent.NetworkError):
                agent.request_json(request, 2)

    def test_broken_http_error_body_is_network_error(self) -> None:
        request = Request("https://example.com")
        error = _BrokenErrorResponse(
            request.full_url,
            502,
            "bad gateway",
            {},
            None,
        )
        with patch.object(agent, "urlopen", side_effect=error):
            with self.assertRaises(agent.NetworkError) as context:
                agent.request_json(request, 2)
        self.assertIn("error response could not be read", str(context.exception))

    def test_nonstandard_json_constant_is_network_error(self) -> None:
        request = Request("https://example.com")
        with patch.object(
            agent,
            "urlopen",
            return_value=_Response(b'{"value":NaN}'),
        ):
            with self.assertRaises(agent.NetworkError):
                agent.request_json(request, 2)

    def test_large_response_is_bounded(self) -> None:
        request = Request("https://example.com")
        body = b"{" + (b"x" * agent.MAX_RESPONSE_BYTES) + b"}"
        with patch.object(agent, "urlopen", return_value=_Response(body)):
            with self.assertRaises(agent.NetworkError):
                agent.request_json(request, 2)


class FollowCursorTests(unittest.TestCase):
    def test_empty_response_with_advanced_cursor_is_not_replayed(self) -> None:
        responses = [
            {"messages": [], "last_seq": 2},
            {"messages": [{"seq": 3}], "last_seq": 3},
        ]
        with patch.object(agent, "read_room", side_effect=responses) as read_room:
            with patch.object(agent.time, "monotonic", return_value=1.0), patch.object(agent.time, "sleep"):
                response = next(
                    agent.follow_room(
                        "lobby",
                        since=1,
                        wait=1,
                        base_url="http://127.0.0.1:1",
                    )
                )
        self.assertEqual(response["last_seq"], 3)
        self.assertEqual(
            [call.kwargs["since"] for call in read_room.call_args_list], [1, 2]
        )


class ProofFileTests(unittest.TestCase):
    def _verify_path(self, path: Path) -> int:
        args = agent.build_parser().parse_args(["verify-proof", str(path)])
        return agent.run_command(args)

    def test_proof_file_size_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_bytes(b"{" + b" " * agent.MAX_PROOF_BYTES + b"}")
            with self.assertRaises(agent.LocalFileError):
                self._verify_path(path)

    def test_proof_file_bad_utf8_is_local_file_error(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_bytes(b"\xff")
            with self.assertRaises(agent.LocalFileError):
                self._verify_path(path)

    def test_proof_file_deep_json_is_local_file_error(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_bytes(("[" * 2000 + "]" * 2000).encode())
            with self.assertRaises(agent.LocalFileError):
                self._verify_path(path)

    def test_proof_file_huge_number_is_local_file_error(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text('{"value":' + "9" * 10000 + "}", encoding="utf-8")
            with self.assertRaises(agent.LocalFileError):
                self._verify_path(path)

    def test_proof_file_nonstandard_json_constant_is_local_file_error(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            path.write_text('{"value":NaN}', encoding="utf-8")
            with self.assertRaises(agent.LocalFileError):
                self._verify_path(path)


class PostedNonceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.did = agent.did_from_private_key(self.private_key)
        self.selected_nonce = "123"
        self.room = "lobby"
        self.text = "hello"

    def _response(self, posted_nonce: object) -> dict[str, object]:
        return {
            "room": self.room,
            "count": 1,
            "last_seq": 7,
            "messages": [{"seq": 7}],
            "posted": {
                "from": self.did,
                "text": self.text,
                "nonce": posted_nonce,
                "seq": 7,
            },
        }

    def _post_with_nonce(self, posted_nonce: object) -> None:
        with patch.object(agent, "request_json", return_value=self._response(posted_nonce)):
            agent.post_signed_message(
                self.private_key,
                self.room,
                self.text,
                nonce=self.selected_nonce,
                base_url="http://127.0.0.1:1",
            )

    def test_integer_nonce_success_path_is_preserved(self) -> None:
        self._post_with_nonce(123)

    def test_fractional_nonce_is_rejected(self) -> None:
        with self.assertRaises(agent.NetworkError):
            self._post_with_nonce(123.0)

    def test_leading_zero_nonce_is_rejected(self) -> None:
        with self.assertRaises(agent.NetworkError):
            self._post_with_nonce("0123")


if __name__ == "__main__":
    unittest.main()
