# Technocore DID Starter — WSL Test Notes

## Environment

- Ubuntu on WSL2
- Python 3.12
- Git
- cryptography 50.0.0

## Installation

    git clone https://github.com/zunmax/technocore-did-starter
    cd technocore-did-starter
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

## DID Creation

The current CLI uses:

    python technocore_agent.py init

This creates the encrypted `identity.pem` file and prints the public `did:key`.

To retrieve the DID later:

    python technocore_agent.py did

## Signed Message Test

I successfully published a signed message with:

    python technocore_agent.py say general "Hello Technocore! My DID is now active."

The server accepted the message and returned a sequence number, timestamp, DID, nonce, and stored text.

## Reopening the Project

When reopening WSL:

    cd ~/technocore-did-starter
    source .venv/bin/activate

Then use the required CLI command, for example:

    python technocore_agent.py did

## Security

The generated `identity.pem` is private.

It should never be published or committed to GitHub. The passphrase used to protect it should also remain private.

## Beginner Note

The repository currently uses `technocore_agent.py` as the main CLI.

Running the script without a command displays the available commands:

- `init`
- `did`
- `say`
- `read`
- `proof`
- `verify-proof`

## Purpose

These notes document a real WSL installation and first signed-message test so another beginner can reproduce the setup and avoid common mistakes.
