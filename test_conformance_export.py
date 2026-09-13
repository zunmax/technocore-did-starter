import unittest

from export_conformance import build_evidence


class ConformanceExportTests(unittest.TestCase):
    def test_filters_other_senders_and_preserves_signed_fields(self):
        did = "did:key:z6Mks3GkYHmXSXjS639r9399owtxCMpzFexrq6EAziYZnjPk"
        response = {
            "generation": 7,
            "messages": [
                {
                    "seq": 10,
                    "ts": "2026-09-13T00:00:00Z",
                    "from": did,
                    "text": "hello",
                    "nonce": "1234567890123456789",
                    "sig": "signed-value",
                },
                {
                    "seq": 11,
                    "ts": "2026-09-13T00:00:01Z",
                    "from": "did:key:z6Mkother",
                    "text": "other",
                    "nonce": "2",
                    "sig": "other-signature",
                },
            ],
        }
        evidence = build_evidence(
            did,
            "mb-example",
            response,
            implementation="zunmax/technocore-did-starter",
            revision="abc123",
        )
        self.assertEqual(evidence["did"], did)
        self.assertEqual(evidence["mailbox"], "mb-example")
        self.assertFalse(evidence["requireComplete"])
        self.assertEqual(evidence["implementation"], "zunmax/technocore-did-starter")
        self.assertEqual(evidence["revision"], "abc123")
        self.assertEqual(len(evidence["records"]), 1)
        self.assertEqual(
            evidence["records"][0],
            {
                "room": "mb-example",
                "generation": 7,
                "seq": 10,
                "ts": "2026-09-13T00:00:00Z",
                "from": did,
                "text": "hello",
                "nonce": "1234567890123456789",
                "sig": "signed-value",
            },
        )


if __name__ == "__main__":
    unittest.main()
