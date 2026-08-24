from __future__ import annotations

import argparse
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import technocore_agent as agent
import technocore_curl_say as fallback


class CurlFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.args = argparse.Namespace(
            room="lobby",
            text="hello from the fallback",
            key=Path("identity.pem"),
            nonce="123456789",
            base_url="https://technocore.chat",
            timeout=30.0,
        )

    def _successful_run(
        self,
        command: list[str],
        *,
        input: bytes,
        **_: object,
    ) -> subprocess.CompletedProcess[bytes]:
        request = json.loads(input.decode("utf-8"))
        posted = {
            "seq": 42,
            "ts": "2026-08-24T16:06:59Z",
            "from": request["did"],
            "text": request["text"],
            "nonce": int(request["nonce"]),
            "untrusted_extra": "must not be printed",
        }
        response = {
            "room": "lobby",
            "count": 1,
            "last_seq": 42,
            "messages": [posted],
            "posted": posted,
        }
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(response).encode("utf-8"),
            stderr=b"",
        )

    @patch.object(fallback.shutil, "which", return_value=r"C:\Windows\curl.exe")
    @patch.object(fallback.agent, "load_identity")
    @patch.object(fallback.subprocess, "run")
    def test_signs_locally_and_sends_public_envelope_on_stdin(
        self,
        run: Mock,
        load_identity: Mock,
        _which: Mock,
    ) -> None:
        load_identity.return_value = self.private_key
        run.side_effect = self._successful_run

        result = fallback.post_with_curl(self.args)

        self.assertEqual(result["room"], "lobby")
        self.assertEqual(result["posted"]["seq"], 42)
        self.assertNotIn("untrusted_extra", result["posted"])
        run.assert_called_once()
        command = run.call_args.args[0]
        request_body = json.loads(run.call_args.kwargs["input"].decode("utf-8"))
        command_text = " ".join(command)
        self.assertIn("--http1.1", command)
        self.assertIn("--tls-max", command)
        self.assertIn("@-", command)
        self.assertNotIn(request_body["did"], command_text)
        self.assertNotIn(request_body["sig"], command_text)

        normalized, payload = agent.message_payload(
            self.args.room, self.args.nonce, self.args.text
        )
        self.assertEqual(request_body["text"], normalized)
        agent.verify_bytes(request_body["did"], request_body["sig"], payload)

    @patch.object(fallback.shutil, "which", return_value=r"C:\Windows\curl.exe")
    @patch.object(fallback.agent, "load_identity")
    @patch.object(fallback.subprocess, "run")
    def test_transport_failure_is_not_retried(
        self,
        run: Mock,
        load_identity: Mock,
        _which: Mock,
    ) -> None:
        load_identity.return_value = self.private_key
        run.return_value = subprocess.CompletedProcess(
            ["curl.exe"], 28, stdout=b"", stderr=b"operation timed out"
        )

        with self.assertRaisesRegex(agent.NetworkError, "outcome may be unknown"):
            fallback.post_with_curl(self.args)

        run.assert_called_once()

    @patch.object(fallback.shutil, "which", return_value=None)
    def test_requires_curl_exe(self, _which: Mock) -> None:
        with self.assertRaisesRegex(agent.NetworkError, "curl.exe was not found"):
            fallback.post_with_curl(self.args)


if __name__ == "__main__":
    unittest.main()
