import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import technocore_agent as agent


class MessageReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        self.receipt = agent.create_message_receipt(
            self.private_key,
            "lobby",
            "  portable\nreceipt  ",
            nonce="123456789",
        )

    def test_create_and_verify_receipt(self) -> None:
        self.assertEqual(self.receipt["schema"], agent.MESSAGE_RECEIPT_SCHEMA)
        self.assertEqual(self.receipt["room"], "lobby")
        self.assertEqual(self.receipt["nonce"], "123456789")
        self.assertEqual(self.receipt["text"], "portable receipt")
        self.assertEqual(
            self.receipt["did"],
            "did:key:z6MkehRgf7yJbgaGfYsdoAsKdBPE3dj2CYhowQdcjqSJgvVd",
        )
        self.assertEqual(
            self.receipt["signature"],
            "XBNhaonw5m5xB-35AlgpeUTkZJCqmsvuIGZ_0dmB9TMS5PWYydcbfSonqXZIxRrp"
            "AApI-tmOTGsoG9PNSRfGBQ",
        )
        agent.verify_message_receipt(self.receipt)

    def test_rejects_tampered_signed_fields(self) -> None:
        other_did = agent.did_from_private_key(Ed25519PrivateKey.generate())
        tampered_values = {
            "did": other_did,
            "room": "technocore",
            "nonce": "123456790",
            "text": "portable receipt changed",
            "signature": (
                ("A" if self.receipt["signature"][0] != "A" else "B")
                + self.receipt["signature"][1:]
            ),
        }
        for field, value in tampered_values.items():
            with self.subTest(field=field):
                changed = copy.deepcopy(self.receipt)
                changed[field] = value
                with self.assertRaises((agent.IdentityError, agent.ProtocolError)):
                    agent.verify_message_receipt(changed)

    def test_rejects_text_that_is_not_already_normalized(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["text"] = "portable\nreceipt"
        with self.assertRaisesRegex(agent.ProtocolError, "already be normalized"):
            agent.verify_message_receipt(changed)

    def test_rejects_wrong_schema_and_missing_fields(self) -> None:
        changed = copy.deepcopy(self.receipt)
        changed["schema"] = "unknown-receipt-v1"
        with self.assertRaisesRegex(agent.ProtocolError, "unsupported"):
            agent.verify_message_receipt(changed)

        changed = copy.deepcopy(self.receipt)
        del changed["signature"]
        with self.assertRaisesRegex(agent.ProtocolError, "missing required"):
            agent.verify_message_receipt(changed)

    def test_timeout_preserves_receipt_before_network_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "message-receipt.json"

            def simulated_timeout(request, timeout, *, is_write=False):
                self.assertTrue(receipt_path.exists())
                raise agent.NetworkError("simulated timeout")

            with patch.object(
                agent,
                "request_json",
                side_effect=simulated_timeout,
            ):
                with self.assertRaisesRegex(agent.NetworkError, "simulated timeout"):
                    agent.post_signed_message(
                        self.private_key,
                        "lobby",
                        "timeout evidence",
                        nonce="234567890",
                        receipt_path=receipt_path,
                    )
            saved = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["nonce"], "234567890")
            agent.verify_message_receipt(saved)

    def test_existing_receipt_blocks_network_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "existing.json"
            receipt_path.write_text("do not replace", encoding="utf-8")
            with patch.object(agent, "request_json") as request:
                with self.assertRaisesRegex(
                    agent.LocalFileError, "refusing to overwrite"
                ):
                    agent.post_signed_message(
                        self.private_key,
                        "lobby",
                        "must not post",
                        nonce="345678901",
                        receipt_path=receipt_path,
                    )
            request.assert_not_called()
            self.assertEqual(receipt_path.read_text(encoding="utf-8"), "do not replace")

    def test_post_uses_exact_receipt_signature(self) -> None:
        captured_body = {}

        def fake_request(request, timeout, *, is_write=False):
            captured_body.update(json.loads(request.data.decode("utf-8")))
            posted = {
                "seq": 42,
                "ts": "2026-08-26T00:00:00Z",
                "from": captured_body["did"],
                "text": captured_body["text"],
                "nonce": int(captured_body["nonce"]),
            }
            return {
                "room": "lobby",
                "count": 1,
                "last_seq": 42,
                "messages": [posted],
                "posted": posted,
            }

        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "message-receipt.json"
            with patch.object(agent, "request_json", side_effect=fake_request):
                response = agent.post_signed_message(
                    self.private_key,
                    "lobby",
                    "successful receipt",
                    nonce="456789012",
                    receipt_path=receipt_path,
                )
            saved = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(captured_body["sig"], saved["signature"])
            self.assertEqual(response["posted"]["seq"], 42)
            agent.verify_message_receipt(saved)

    def test_verify_message_receipt_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "message-receipt.json"
            agent.write_new_json(receipt_path, self.receipt)
            output = io.StringIO()
            with redirect_stdout(output):
                result = agent.main(["verify-message-receipt", str(receipt_path)])
            self.assertEqual(result, 0)
            self.assertIn("valid message receipt for did:key:z6Mk", output.getvalue())


if __name__ == "__main__":
    unittest.main()
