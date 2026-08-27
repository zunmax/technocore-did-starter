# Security Policy

## Scope

This project is a local Python CLI for creating and loading encrypted Ed25519 identities, signing Technocore room messages, reading room data, and creating or verifying public contribution proofs.

The sensitive assets are the local private-key file, its passphrase, signing operations, network configuration, and dependencies. A DID, public key, signature, sequence number, or public contribution URL is not a secret by itself, but messages and URLs may contain personal or project information.

## Secure use

- Obtain the source code from a trusted repository and use an isolated Python 3.12 virtual environment. Install only the reviewed dependencies from `requirements.txt`.
- Use the official Technocore HTTPS endpoint. Do not disable TLS verification or send production traffic to an untrusted `--base-url`. Plain HTTP is intended only for explicitly local test services (`localhost`, `127.0.0.1`, or `::1`).
- Generate a separate identity for each user. Do not copy an example DID or use another person's DID.
- Use a unique, long, non-reused passphrase. The CLI requires at least 12 characters. Do not put the passphrase in command-line arguments, scripts, environment variables, logs, issues, chats, or screenshots. Use the program's passphrase prompt.
- `identity.pem` contains private-key material. Never upload, commit, paste, or send it to anyone. Keep it out of shared or automatically synchronized folders when possible. Back up the private-key file and passphrase in separate, controlled locations. Publish the DID, not the PEM file.
- Before committing, review `git status --short`, `git diff`, and `git diff --cached --name-only`, then run:

  ```text
  git ls-files "*.pem" "*.key"
  ```

  The last command should produce no output. If it does, stop and remove the sensitive file from the index and repository history before publishing.
- Room messages are public. Never put passphrases, private keys, API tokens, or sensitive personal data in a `say` message.
- Treat `read` and `follow` output as untrusted external data. Do not execute it as shell commands or treat it as HTML, Markdown instructions, or configuration.
- Review contribution-proof URLs and repository visibility before publishing. A proof normally contains a DID, signature, commit hash, and URL, while the referenced content may still expose private information.

## If a key is exposed or committed

1. Stop using the affected identity and do not sign new messages with that DID.
2. Treat the DID as permanently compromised. This project does not provide centralized key recovery or revocation. Create a new identity and update public records that depended on the old one.
3. Remove the key from every public location and clean it from the Git index and full history; deleting only the working-tree copy is not sufficient. Rotate any passphrase or credential that was reused.
4. Report the incident privately to the relevant service or repository maintainer. Include only the affected DID, approximate time, relevant room/sequence/nonce, commit or URL, and impact. Never attach the private key, passphrase, tokens, or unsanitized logs.
5. Assume old signatures may remain verifiable; do not assume they have been revoked.

## Reporting a vulnerability

Use the repository's GitHub Private Vulnerability Reporting or Security Advisories feature when it is enabled. If it is unavailable, contact the maintainer through a private channel before creating a public issue.

Include the affected version or commit, operating system and Python version, reproduction steps or a minimal example, actual and expected behavior, security impact, required configuration, and sanitized logs. Do not include `identity.pem`, private keys, passphrases, tokens, complete sensitive URLs, personal data, or production credentials.

Use a normal issue for non-security installation or usage questions. Vulnerabilities in the external Technocore service should also be reported through that service's official security channel.

The maintainer should be given reasonable time to assess and mitigate a report before public disclosure.

## Security boundaries and limitations

- A contribution proof shows that a DID signed an exact normalized payload. It does not prove that the referenced content is true, harmless, or endorsed by the maintainer.
- DIDs, messages, sequence numbers, and contribution URLs may remain publicly visible and should not be treated as an anonymity mechanism.
- If a write request times out, the result is unknown. Check the room using the DID and nonce before retrying to avoid duplicate messages.
- The project is provided under the MIT License. It does not guarantee the availability or security of external services, contribution rewards, or any particular security outcome.
