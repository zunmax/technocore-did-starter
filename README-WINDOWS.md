# Windows: passphrase from redirected stdin

## The bug

On Windows, `getpass.getpass()` reads the console through `msvcrt` even when
stdin is redirected. So the documented non-interactive flow

    python technocore_agent.py init < passphrase.txt

hangs forever: `init` waits on the console while the passphrase sits in the
redirected pipe. The same affects `did`, `say` and `proof` for encrypted
identities (they prompt via `load_identity`).

## The fix (two options)

### Option A - launcher wrapper (zero upstream changes)

`run_starter.py` monkey-patches `getpass.getpass` to return the passphrase
from the `TC_PASS` environment variable, then runs the CLI:

    set TC_PASS=<your passphrase>
    python run_starter.py init

### Option B - upstream patch (recommended)

`windows-getpass.patch` adds a `_read_passline()` helper: when stdin is not a
TTY, the passphrase is read from stdin instead of the console. Interactive
behavior is unchanged; piped/CI flows work on every OS.

    git apply windows-getpass.patch

After applying: `init < passphrase.txt` consumes two lines (passphrase twice,
for the confirmation prompt), exactly as the interactive flow asks twice.

## Security notes

- Reading a passphrase from a pipe is marginally weaker than a console prompt
  (the pipe contents may be visible to the parent process); the TTY path is
  unchanged, so interactive users keep the msvcrt prompt.
- Never put the passphrase in shell history or image layers; prefer a secret
  manager feeding the pipe.
