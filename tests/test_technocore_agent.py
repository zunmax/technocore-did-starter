import contextlib
import io
import unittest

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import technocore_agent as agent


class SignedMessageVerificationTests(unittest.TestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        self.did = agent.did_from_private_key(self.private_key)
        self.room = "builders"
        self.nonce = "1724512345678901234"
        self.text = "A signed\nTechnocore message"
        self.normalized, payload = agent.message_payload(
            self.room, self.nonce, self.text
        )
        self.signature = agent.sign_bytes(self.private_key, payload)

    def test_valid_message_round_trip(self):
        verified_text = agent.verify_signed_message(
            self.room, self.did, self.nonce, self.text, self.signature
        )

        self.assertEqual(verified_text, "A signed Technocore message")

    def test_rejects_tampered_message_fields(self):
        tampered_values = (
            ("another-room", self.nonce, self.text),
            (self.room, "1724512345678901235", self.text),
            (self.room, self.nonce, self.text + "!"),
        )

        for room, nonce, text in tampered_values:
            with self.subTest(room=room, nonce=nonce, text=text):
                with self.assertRaises(agent.IdentityError):
                    agent.verify_signed_message(
                        room, self.did, nonce, text, self.signature
                    )

    def test_rejects_signature_from_another_did(self):
        other_did = agent.did_from_private_key(Ed25519PrivateKey.generate())

        with self.assertRaises(agent.IdentityError):
            agent.verify_signed_message(
                self.room, other_did, self.nonce, self.text, self.signature
            )

    def test_cli_reports_valid_message(self):
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = agent.main(
                [
                    "verify-message",
                    self.room,
                    self.did,
                    self.nonce,
                    self.text,
                    self.signature,
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn(f"valid message from {self.did}", output.getvalue())

    def test_cli_returns_error_for_tampered_text(self):
        stderr = io.StringIO()

        with contextlib.redirect_stderr(stderr):
            exit_code = agent.main(
                [
                    "verify-message",
                    self.room,
                    self.did,
                    self.nonce,
                    "tampered",
                    self.signature,
                ]
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("signature does not match", stderr.getvalue())


class ExistingProtocolTests(unittest.TestCase):
    def test_contribution_proof_round_trip(self):
        private_key = Ed25519PrivateKey.generate()
        proof = agent.create_contribution_proof(
            private_key,
            "https://github.com/example/technocore-tool",
            "a" * 40,
        )

        agent.verify_contribution_proof(proof)

    def test_did_rejects_invalid_base58(self):
        with self.assertRaises(agent.ProtocolError):
            agent.public_key_from_did("did:key:z6Mk" + "0" * 44)


if __name__ == "__main__":
    unittest.main()
