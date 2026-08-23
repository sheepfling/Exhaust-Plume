"""Build and exercise a wheel in isolated temporary environments."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


def _venv_python(environment: Path) -> Path:
  """Return the platform-specific Python executable in a virtualenv."""
  if os.name == "nt":
    return environment / "Scripts" / "python.exe"
  ####
  return environment / "bin" / "python"
####


def main() -> int:
  """Build one wheel, install it fresh, and run the installed smoke test."""
  environment = os.environ.copy()
  environment.pop("PYTHONPATH", None)
  with TemporaryDirectory(prefix="exhaust-plume-wheel-") as temporary:
    root = Path(temporary)
    wheel_directory = root / "wheel"
    wheel_directory.mkdir()
    built = subprocess.run(
        [
          sys.executable,
          "-m",
          "build",
          "--wheel",
          "--outdir",
          str(wheel_directory),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    if built.returncode:
      return built.returncode
    ####
    wheels = tuple(wheel_directory.glob("*.whl"))
    if len(wheels) != 1:
      print(f"expected one built wheel, found {len(wheels)}", file=sys.stderr)
      return 1
    ####

    environment_directory = root / "venv"
    created = subprocess.run(
        [sys.executable, "-m", "venv", str(environment_directory)],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    if created.returncode:
      return created.returncode
    ####
    python = _venv_python(environment_directory)
    for command in (
        [python, "-m", "pip", "install", "--upgrade", "pip"],
        [python, "-m", "pip", "install", str(wheels[0])],
    ):
      installed = subprocess.run(command, cwd=ROOT, env=environment, check=False)
      if installed.returncode:
        return installed.returncode
      ####
    ####

    return subprocess.run(
        [python, str(ROOT / "tests" / "installed_smoke.py")],
        cwd=root,
        env=environment,
        check=False,
    ).returncode
  ####
####


if __name__ == "__main__":
  raise SystemExit(main())
####
