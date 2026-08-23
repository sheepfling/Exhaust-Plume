"""Run the repository Markdown policy with the active development environment."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_FILES = ("README.md",)


def _rumdl_command() -> str:
  """Find the rumdl executable beside the active Python interpreter."""
  executable = shutil.which("rumdl")
  if executable is not None:
    return executable
  ####
  for name in ("rumdl", "rumdl.exe"):
    sibling = Path(sys.executable).with_name(name)
    if sibling.exists():
      return str(sibling)
    ####
  ####
  raise FileNotFoundError(
      "rumdl is not installed; install the development dependencies with "
      '`python -m pip install -e ".[dev]"`'
  )
####


def main(argv: Sequence[str] = ()) -> int:
  """Check the tracked Markdown entry points, optionally applying fixes."""
  parser = argparse.ArgumentParser(description="Check repository Markdown with rumdl.")
  parser.add_argument("--fix", action="store_true", help="apply rumdl's safe fixes")
  arguments = parser.parse_args(argv)
  command = [_rumdl_command(), "check"]
  if arguments.fix:
    command.append("--fix")
  ####
  command.extend(MARKDOWN_FILES)
  return subprocess.run(command, cwd=ROOT, check=False).returncode
####


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
####
