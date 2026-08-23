"""Run Pyright using the interpreter that owns the development tools."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
  """Run the repository's configured Pyright check."""
  return subprocess.run(
      [sys.executable, "-m", "pyright"],
      cwd=ROOT,
      check=False,
  ).returncode
####


if __name__ == "__main__":
  raise SystemExit(main())
####
