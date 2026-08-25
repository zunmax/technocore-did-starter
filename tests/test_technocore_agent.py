import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import technocore_agent as agent


class IdentityAndProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.did = agent.did_from_private_key(self.private_key)

    def test_did_round_trip_and_message_signature(self) -> None:
        normalized, payload = agent.message_payload("lobby", "123", " hello\nworld ")
        signature = agent.sign_bytes(self.private_key, payload)

        self.assertEqual(normalized, "hello world")
        agent.verify_bytes(self.did, signature, payload)
        with self.assertRaises(agent.IdentityError):
            agent.verify_bytes(self.did, signature, b"lobby|123|different")

    def test_malformed_signature_is_reported_as_protocol_error(self) -> None:
        with self.assertRaises(agent.ProtocolError):
            agent.verify_bytes(self.did, "!" * agent.SIGNATURE_LENGTH, b"payload")

    def test_identity_is_encrypted_and_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "identity.pem"
            did = agent.create_identity(path, "correct horse battery")
            self.assertEqual(did, agent.did_from_private_key(
                agent.load_identity(path, b"correct horse battery")
            ))
            self.assertIn(b"ENCRYPTED", path.read_bytes())
            with self.assertRaises(agent.IdentityError):
                agent.create_identity(path, "another passphrase")

    def test_validation_rejects_unsafe_urls_and_values(self) -> None:
        with self.assertRaises(agent.ProtocolError):
            agent.validate_base_url("http://example.com")
        with self.assertRaises(agent.ProtocolError):
            agent.contribution_payload("https://example.com/repo#fragment", "a" * 40)
        with self.assertRaises(agent.ProtocolError):
            agent.validate_nonce("not-a-number")


class ContributionProofTests(unittest.TestCase):
    def test_proof_round_trip_and_tamper_detection(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        proof = agent.create_contribution_proof(
            private_key,
            "https://github.com/example/project",
            "A" * 40,
        )
        agent.verify_contribution_proof(proof)

        tampered = dict(proof, commit="B" * 40)
        with self.assertRaises(agent.IdentityError):
            agent.verify_contribution_proof(tampered)

    def test_proof_file_is_public_json_and_not_overwritten(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        proof = agent.create_contribution_proof(
            private_key, "https://github.com/example/project", "a" * 40
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proof.json"
            agent.write_new_json(path, proof)
            self.assertEqual(json.loads(path.read_text()), proof)
            with self.assertRaises(agent.LocalFileError):
                agent.write_new_json(path, proof)


class CliTests(unittest.TestCase):
    def test_parser_requires_a_command_and_supports_public_commands(self) -> None:
        parser = agent.build_parser()
        with self.assertRaises(SystemExit) as version_exit:
            parser.parse_args(["--version"])
        self.assertEqual(version_exit.exception.code, 0)
        args = parser.parse_args([
            "proof", "https://github.com/example/project", "a" * 40
        ])
        self.assertEqual(args.command, "proof")


if __name__ == "__main__":
    unittest.main()
