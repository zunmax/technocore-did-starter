import unittest

from technocore_agent import ProtocolError, verify_bytes


class SignatureCanonicalityTests(unittest.TestCase):
    DID = "did:key:z6MktNvQh9uSK3Hwxh2c9iCQZs3Q3kgXWhNEhcP4n7fvQWdr"
    PAYLOAD = b"gauntlet|9007199254740993001|hello"
    SIGNATURE = (
        "7x4LHPXWJBlqBIP614Rx0PNkdmWrkfjTSYmqLZ9EK0I"
        "JFdZbZZ43bpnNl7-D0Dychqlzko2Z7oToqIjvj-O7CQ"
    )

    def test_accepts_canonical_unpadded_signature(self) -> None:
        verify_bytes(self.DID, self.SIGNATURE, self.PAYLOAD)

    def test_rejects_padded_signature_before_verification(self) -> None:
        with self.assertRaisesRegex(
            ProtocolError, "86 unpadded base64url characters"
        ):
            verify_bytes(self.DID, self.SIGNATURE + "==", self.PAYLOAD)


if __name__ == "__main__":
    unittest.main()
