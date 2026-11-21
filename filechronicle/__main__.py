"""Executable entry point when invoked as python -m filechronicle."""

import sys
from filechronicle.cli import main

if __name__ == "__main__":
    sys.exit(main())
