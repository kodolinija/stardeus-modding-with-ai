"""Stardeus modding workspace tools. Run through tools/stardeus (or tools\\stardeus.cmd on Windows)."""
import sys
from pathlib import Path

if sys.version_info < (3, 10):
    sys.exit("The workspace tools need Python 3.10 or newer: https://www.python.org/downloads/")

sys.path.insert(0, str(Path(__file__).resolve().parent))

from stardeuslib.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
