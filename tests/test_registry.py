import argparse
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import technocore_agent as agent


class DidRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        self.did = agent.did_from_private_key(self.key)
        self.fingerprint = agent.did_registry_fingerprint(self.did)

    def test_fingerprint_is_stable_and_lowercase(self) -> None:
        self.assertEqual(len(self.fingerprint), 16)
        self.assertRegex(self.fingerprint, r"^[0-9a-f]{16}$")
        self.assertEqual(
            self.fingerprint,
            agent.did_registry_fingerprint(self.did),
        )

    @patch.object(agent, "request_text", return_value=(404, "404 no note"))
    def test_missing_registration_is_reported(self, _request_text) -> None:
        status = agent.read_did_registration(self.did)

        self.assertEqual(status["state"], "missing")
        self.assertEqual(status["fingerprint"], self.fingerprint)

    @patch.object(agent, "request_text")
    def test_registered_value_is_read_after_the_untrusted_banner(self, request_text) -> None:
        request_text.return_value = (
            200,
            f"!! UNTRUSTED CONTENT\n\n{self.did}\n# budget: 1 of 2 reads left",
        )

        status = agent.read_did_registration(self.did)

        self.assertEqual(status["state"], "registered")
        self.assertEqual(status["value"], self.did)

    @patch.object(agent, "request_text")
    @patch.object(agent, "read_did_registration")
    def test_capacity_full_is_retryable(self, read_registration, request_text) -> None:
        read_registration.return_value = {
            "did": self.did,
            "fingerprint": self.fingerprint,
            "registry_url": f"https://technocore.chat/kv/did/{self.fingerprint}",
            "state": "missing",
        }
        request_text.return_value = (400, "400 note limit reached (5120 is the cap)")

        result = agent.register_did(self.key)

        self.assertEqual(result["state"], "capacity_full")
        self.assertTrue(result["retryable"])

    @patch.object(agent, "request_text", return_value=(200, "stored"))
    @patch.object(agent, "read_did_registration")
    def test_success_is_verified_by_reading_back(self, read_registration, _request_text) -> None:
        missing = {
            "did": self.did,
            "fingerprint": self.fingerprint,
            "registry_url": f"https://technocore.chat/kv/did/{self.fingerprint}",
            "state": "missing",
        }
        verified = {**missing, "state": "registered", "value": self.did}
        read_registration.side_effect = [missing, verified]

        result = agent.register_did(self.key)

        self.assertEqual(result["state"], "registered")
        self.assertEqual(read_registration.call_count, 2)

    def test_passphrase_file_loads_without_prompting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            key_path = root / "identity.pem"
            passphrase_path = root / "passphrase"
            passphrase = "this-is-a-long-test-passphrase"
            expected_did = agent.create_identity(key_path, passphrase)
            passphrase_path.write_text(passphrase + "\n", encoding="utf-8")
            args = argparse.Namespace(key=key_path, passphrase_file=passphrase_path)

            loaded = agent.load_command_identity(args)

            self.assertEqual(agent.did_from_private_key(loaded), expected_did)


if __name__ == "__main__":
    unittest.main()
