"""Exercise the package after installing its built wheel into a fresh environment."""

from __future__ import annotations

import importlib.metadata
import importlib.resources
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import exhaust_plume
from exhaust_plume import calculatePlumeZones
from exhaust_plume.log.log import configureLogging
from exhaust_plume.util.physical_constants import PASCAL_PER_ATM


def _walk_resources(resource: Any) -> Iterator[Any]:
  for child in resource.iterdir():
    if child.is_dir():
      yield from _walk_resources(child)
    else:
      yield child


def _resource_from_parts(root: Any, parts: tuple[str, ...]) -> Any:
  resource = root
  for part in parts:
    resource = resource.joinpath(part)
  return resource


def main() -> None:
  distribution = importlib.metadata.distribution('exhaust-plume')
  package_name = exhaust_plume.__name__
  package_root = importlib.resources.files(package_name)
  package_resources = tuple(_walk_resources(package_root))
  assert package_resources, 'The installed package contains no discoverable resources.'

  distribution_files = tuple(distribution.files or ())
  assert distribution_files, 'The installed distribution has no file manifest.'
  for distribution_file in distribution_files:
    parts = tuple(distribution_file.parts)
    if parts and parts[0] == package_name:
      resource = _resource_from_parts(package_root, parts[1:])
      assert resource.is_file(), f'Package manifest entry is not readable: {distribution_file}'
      resource.read_bytes()

  python_resources = tuple(resource for resource in package_resources if resource.name.endswith('.py'))
  assert python_resources, 'The installed package contains no Python modules.'
  checkout_marker = str(Path(__file__).resolve().parents[1])
  for resource in python_resources:
    source = resource.read_bytes()
    assert checkout_marker.encode() not in source, f'Embedded checkout path found in {resource}.'
    compile(source, str(resource), 'exec')
  assert any(resource.name.endswith('.yaml') for resource in package_resources), 'Packaged YAML resources were not discovered.'

  assert exhaust_plume.__version__ == '0.1.0.a0'
  assert distribution.version == '0.1.0a0'
  assert importlib.util.find_spec('matplotlib') is None, 'Core wheel unexpectedly installs plotting dependencies.'
  assert configureLogging()

  zones, details = calculatePlumeZones(
      nozzle_mach=4.13,
      nozzle_total_temperature=2000.,
      nozzle_total_pressure=69. * PASCAL_PER_ATM,
      nozzle_radius=1.,
      atmospheric_pressure=PASCAL_PER_ATM,
      gamma=1.33,
      num_expansion_lines=2,
      num_compression_lines=1,
      num_plumes=1,
  )
  assert zones and details

  cli = shutil.which('exhaust-plume', path=str(Path(sys.executable).parent))
  assert cli is not None, 'The installed console script was not found.'
  with tempfile.TemporaryDirectory() as working_directory:
    completed = subprocess.run(
        [cli, '--help'],
        cwd=working_directory,
        check=True,
        capture_output=True,
        text=True,
    )
  assert 'usage:' in completed.stdout


if __name__ == '__main__':
  main()
