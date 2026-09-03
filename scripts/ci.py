"""Run the same repository checks locally and in GitHub Actions."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ci_commands(python: str = sys.executable) -> tuple[tuple[str, ...], ...]:
  """Return the ordered, platform-independent CI commands."""
  return (
      (python, "-m", "pytest", "-q"),
      (python, "-m", "scripts.test_lanes", "--check"),
      (python, "-m", "ruff", "check", "src", "scripts", "tests"),
      (python, "-m", "scripts.check_scope_markers"),
      (python, "-m", "scripts.check_rumdl"),
      (python, "-m", "scripts.check_pyright"),
      (python, "scripts/check_public_contract_assets.py"),
      (python, "-m", "scripts.check_build"),
  )
####


def run_command(command: Sequence[str]) -> int:
  """Run one check from the repository root with source imports enabled."""
  environment = os.environ.copy()
  source_path = str(ROOT / "src")
  existing_pythonpath = environment.get("PYTHONPATH")
  environment["PYTHONPATH"] = os.pathsep.join(
      path for path in (source_path, existing_pythonpath) if path
  )
  try:
    completed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
  except OSError as error:
    print(f"CI command could not start: {' '.join(command)}: {error}", file=sys.stderr)
    return 1
  ####
  return completed.returncode
####


def main(argv: Sequence[str] = ()) -> int:
  """Run each CI command in order, stopping at the first failure."""
  parser = argparse.ArgumentParser(
      description="Run the repository checks in the same order as CI.",
  )
  parser.parse_args(argv)
  for command in ci_commands():
    print(f"$ {' '.join(command)}")
    return_code = run_command(command)
    if return_code:
      return return_code
    ####
  ####
  return 0
####


if __name__ == "__main__":
  raise SystemExit(main(sys.argv[1:]))
####
