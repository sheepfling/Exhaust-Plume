"""Verify canonical scope markers across Python source, scripts, and tests."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOTS = ("src", "scripts", "tests")


def main(argv: Sequence[str] = ()) -> int:
  """Check markers, optionally applying the tool's safe fixes."""
  if sys.version_info < (3, 11):
    print("scope-markers requires Python 3.11+; marker check skipped on this interpreter")
    return 0
  ####
  parser = argparse.ArgumentParser(
      description="Check canonical #### scope markers in Python source trees.",
  )
  parser.add_argument(
      "--fix",
      action="store_true",
      help="apply scope-marker fixes in place",
  )
  arguments = parser.parse_args(argv)
  command = [sys.executable, "-m", "scope_markers"]
  if arguments.fix:
    command.append("--fix")
  ####
  command.extend(PYTHON_ROOTS)
  return subprocess.run(command, cwd=ROOT, check=False).returncode
####


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
####
