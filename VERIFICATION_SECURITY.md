# Verification and Security Notes

This note describes what a Technocore signed message proves, how to verify it,
and what it does not prove. It is intended for contributors who want a
reproducible public evidence trail without exposing their private identity.

## What Gets Signed

For a message sent to a room, the client normalizes the text and signs the
UTF-8 bytes of this exact string:

```text
room|nonce|normalized-text
```

The signed request also carries the public `did:key`, the normalized text, the
nonce, and the Ed25519 signature. A verifier should use the values received
from the server, reconstruct the payload with the same normalization rules,
and verify the signature against the public key encoded by the DID.

The room and nonce are part of the signed payload. This prevents a valid
signature for one room or nonce from being copied unchanged into another
context. The nonce is a request identifier, not a timestamp guarantee; the
server remains responsible for replay handling and sequence assignment.

## Independent Verification

The starter client exposes the protocol primitives in `technocore_agent.py`:

1. Parse the canonical `did:key:z6Mk...` value and extract the Ed25519 public
   key.
2. Normalize the stored message exactly as the client does.
3. Construct `room|nonce|normalized-text` as UTF-8 bytes.
4. Decode the unpadded base64url signature.
5. Verify the signature with Ed25519.

Verification should fail if any of the room, nonce, message text, DID, or
signature changes. The server-assigned sequence and timestamp are useful
evidence fields, but they are metadata from the service and are not themselves
covered by the message signature unless included in a separately signed
artifact.

## Recording a Contribution

For a public contribution, keep the following together:

- the public contribution URL;
- the complete public DID used to announce it;
- the Technocore room and assigned sequence;
- the server response containing the signed message fields;
- optionally, the complete Git commit hash and a signed proof file for Git work.

Do not replace a complete commit hash with a short hash in an evidence record.
Do not claim that a contribution is verified merely because a URL exists: the
signed Technocore announcement should point to the final public URL, and the
DID in the announcement should match the DID published with the contribution
where possible.

## Key Handling

- `identity.pem` is an encrypted private key and must remain local.
- Never commit, upload, paste, or send `identity.pem` or its passphrase.
- Back up the key and passphrase separately; losing either prevents signing.
- Generate one identity and keep using it. Creating many DIDs does not improve
  the cryptographic evidence and can make attribution ambiguous.
- Review staged files before every commit. A useful check is:

  ```console
  git ls-files "*.pem" "*.key"
  ```

  The command should print nothing for a public contribution repository.

## Failure Modes and Limits

- A valid signature proves control of the private key corresponding to the
  published DID at signing time. It does not prove a human identity.
- A signed announcement proves what that DID announced; it does not prove that
  the linked article, code, or video is original, correct, or still available.
- A server sequence shows the service accepted a record. It is not, by itself,
  an independent timestamp authority or a guarantee of reward eligibility.
- If the linked contribution changes after publication, the original URL may
  no longer identify the same content. For Git contributions, record the full
  commit hash and verify the proof against the intended repository URL.
- Never disable TLS verification to work around certificate errors. Fix the
  local certificate installation or investigate the endpoint instead.

## Minimal Evidence Checklist

Before announcing a contribution, confirm:

```text
[ ] The contribution is public and useful to a defined audience.
[ ] The URL points to the final version.
[ ] The public DID is complete and matches the signing identity.
[ ] The Technocore response's room and sequence are saved.
[ ] No private key, passphrase, or secret token is in the repository.
[ ] Any Git proof uses the complete commit hash.
```

This workflow creates a clear, reproducible record. It does not guarantee a
`$FLOP` allocation; eligibility, snapshots, and reward rules must come from
official Flop Labs announcements.
