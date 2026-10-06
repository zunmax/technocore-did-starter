# Thin launcher for technocore_agent.py: Windows getpass reads the console
# via msvcrt even when stdin is redirected, so supply the passphrase from
# the TC_PASS environment variable instead.
import os
import sys
import runpy

import getpass

_passphrase = os.environ["TC_PASS"]
getpass.getpass = lambda prompt="": _passphrase

sys.argv = ["technocore_agent.py"] + sys.argv[1:]
runpy.run_path(os.path.join(os.path.dirname(os.path.abspath(__file__)), "technocore_agent.py"), run_name="__main__")
