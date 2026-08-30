"""Regression test for the identity.pem permission warning (PR #15).

Standard-library unittest only, matching this starter repo's minimal
dependency footprint -- no pytest in requirements.txt.
"""
import io
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from technocore_agent import load_identity


def _make_key_file(mode: int) -> Path:
    """Write a syntactically-loadable dummy key file with the given mode.

    load_identity's permission check runs before the key bytes are parsed,
    so the file content only needs to exist -- it does not need to be a
    real Ed25519 key for this test, since we only assert on the warning
    written to stderr, not on successful key parsing.
    """
    fd, path_str = tempfile.mkstemp(suffix=".pem")
    os.close(fd)
    path = Path(path_str)
    path.write_bytes(b"not a real key, only used for permission-check tests")
    path.chmod(mode)
    return path


class TestIdentityPermissionWarning(unittest.TestCase):
    def _load_and_capture_stderr(self, path: Path) -> str:
        captured = io.StringIO()
        with patch("sys.stderr", captured):
            try:
                load_identity(path)
            except Exception:
                # load_identity will fail past the permission check since
                # the file is not a real key -- that is expected and fine,
                # the permission-warning branch runs and writes to stderr
                # before the real parse failure occurs.
                pass
        return captured.getvalue()

    def test_warns_on_posix_when_group_other_readable(self):
        path = _make_key_file(0o644)
        try:
            with patch("os.name", "posix"):
                stderr_output = self._load_and_capture_stderr(path)
            self.assertIn("group/other", stderr_output)
            self.assertIn("chmod 600", stderr_output)
        finally:
            path.unlink(missing_ok=True)

    def test_silent_on_posix_when_owner_only(self):
        path = _make_key_file(0o600)
        try:
            with patch("os.name", "posix"):
                stderr_output = self._load_and_capture_stderr(path)
            self.assertNotIn("group/other", stderr_output)
        finally:
            path.unlink(missing_ok=True)

    def test_silent_on_windows_regardless_of_mode(self):
        # Windows synthesizes POSIX-style mode bits from its own ACL, and a
        # normal Windows file commonly reports as 0o666 -- which would
        # false-positive under a POSIX-style check. This asserts the
        # Windows branch is skipped entirely, matching the real-world
        # os.name == "nt", S_IMODE == 0o666 case reported against PR #15.
        path = _make_key_file(0o666)
        try:
            with patch("os.name", "nt"):
                stderr_output = self._load_and_capture_stderr(path)
            self.assertNotIn("group/other", stderr_output)
        finally:
            path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
