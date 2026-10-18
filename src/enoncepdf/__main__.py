"""``python -m enoncepdf``: the command line of cli.py."""

import sys

from enoncepdf.cli import main

__all__: list[str] = []

sys.exit(main())
