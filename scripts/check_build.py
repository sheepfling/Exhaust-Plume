"""Build and exercise a wheel in isolated temporary environments."""

from __future__ import annotations

import argparse
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


def main(argv: list[str] | None = None) -> int:
  """Build one wheel, install it fresh, and run the installed smoke test.

  The default path retains isolated build and online dependency-upgrade
  semantics.  ``--offline`` is an explicit reproducibility path for runners
  that already have the build and runtime dependencies installed: it uses
  the current environment's build backend, a system-site-packages venv, and
  no-index/no-deps wheel installation.
  """
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
    '--offline',
    action='store_true',
    help='use locally installed build/runtime packages without contacting an index',
  )
  arguments = parser.parse_args(argv)
  environment = os.environ.copy()
  environment.pop("PYTHONPATH", None)
  with TemporaryDirectory(prefix="exhaust-plume-wheel-") as temporary:
    root = Path(temporary)
    wheel_directory = root / "wheel"
    wheel_directory.mkdir()
    build_command = [
      sys.executable,
      "-m",
      "build",
      "--wheel",
      "--outdir",
      str(wheel_directory),
    ]
    if arguments.offline:
      build_command.append('--no-isolation')
    built = subprocess.run(
        build_command,
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
    venv_command = [sys.executable, "-m", "venv"]
    if arguments.offline:
      venv_command.append('--system-site-packages')
    venv_command.append(str(environment_directory))
    created = subprocess.run(
        venv_command,
        cwd=ROOT,
        env=environment,
        check=False,
    )
    if created.returncode:
      return created.returncode
    ####
    python = _venv_python(environment_directory)
    install_commands = []
    if not arguments.offline:
      install_commands.append([python, "-m", "pip", "install", "--upgrade", "pip"])
    wheel_install = [python, "-m", "pip", "install"]
    if arguments.offline:
      wheel_install.extend(["--no-index", "--no-deps"])
    wheel_install.append(str(wheels[0]))
    install_commands.append(wheel_install)
    for command in install_commands:
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
