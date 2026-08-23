"""Exercise the package after installing its built wheel into a fresh environment."""

from __future__ import annotations

import importlib.metadata
import importlib.resources
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import exhaust_plume
from exhaust_plume import ShockBranch, calculatePlumeZones, solve_shock_angle
from exhaust_plume import (
  LookupInterpolationPolicy,
  Pose,
  PrescribedVisualDefinition,
  PrescribedVisualProvider,
  SignatureTableDefinition,
  SignatureTableProvider,
  SpectralSignatureRequest,
  SPECTRAL_RADIANT_INTENSITY_V1,
  VisualMesh,
  VisualSampling,
  VisualSection,
  VisualSectionedTubeRequest,
  build_sectioned_tube_mesh,
  write_signature_result_csv,
  write_signature_result_json,
  write_visual_mesh_json,
  write_visual_obj,
  write_visual_result_json,
)
from exhaust_plume.validation import default_validity_cases, evaluate_validity_matrix
from exhaust_plume.contracts.specs_v1 import VISUAL_SECTIONED_TUBE_V1
from exhaust_plume.log.log import configureLogging
from exhaust_plume.providers import ShockCellAnalyticalProvider
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

  assert exhaust_plume.__version__ == '0.1.0.a1'
  assert distribution.version == '0.1.0a1'
  requirements = tuple(distribution.requires or ())
  unconditional_plot_requirements = tuple(
      requirement for requirement in requirements
      if requirement.split(';', 1)[0].strip().lower().startswith('matplotlib') and 'extra' not in requirement.lower()
  )
  assert not unconditional_plot_requirements, 'Core wheel unexpectedly declares plotting dependencies.'
  assert configureLogging()
  assert LookupInterpolationPolicy.LINEAR.value == 'linear'
  assert ShockCellAnalyticalProvider().descriptor.provider_id == 'shock-cell-analytical'
  assert solve_shock_angle(theta_rad=0.0, mach=3.0, gamma=1.4, branch=ShockBranch.WEAK).beta_rad is not None

  visual_definition = PrescribedVisualDefinition(
      frame_id='source-local',
      sections=(
          VisualSection(
              arc_length_m=0.0,
              center_m=(0.0, 0.0, 0.0),
              section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
              radius_major_m=0.5,
              radius_minor_m=0.25,
          ),
          VisualSection(
              arc_length_m=1.0,
              center_m=(1.0, 0.0, 0.0),
              section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
              radius_major_m=0.6,
              radius_minor_m=0.3,
          ),
      ),
  )
  visual_snapshot = PrescribedVisualProvider().create_session(
      definition=visual_definition,
  ).create_snapshot(
      time_s=0.0,
      source_pose=Pose(
          frame_id='world',
          translation_m=(0.0, 0.0, 0.0),
          rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
      ),
      dynamic_state={},
      ambient_state={},
  )
  visual_result = visual_snapshot.evaluate(
      VISUAL_SECTIONED_TUBE_V1,
      VisualSectionedTubeRequest(
          output_frame_id='source-local',
          sampling=VisualSampling(maximum_section_count=2),
      ),
  )
  assert len(visual_result.sections) == 2
  visual_mesh = build_sectioned_tube_mesh(visual_result, radial_segments=8)
  assert isinstance(visual_mesh, VisualMesh)

  signature_definition = SignatureTableDefinition(
      frame_id='source-local',
      wavelengths_m=(1.0e-6, 2.0e-6),
      direction_cosine_nodes=(-0.5, 0.0, 0.5),
      spectral_radiant_intensity_w_sr_m=(
          (0.5, 1.5),
          (1.0, 2.0),
          (1.5, 2.5),
      ),
  )
  signature_snapshot = SignatureTableProvider().create_session(
      definition=signature_definition,
  ).create_snapshot(
      time_s=0.0,
      source_pose=Pose(
          frame_id='world',
          translation_m=(0.0, 0.0, 0.0),
          rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
      ),
      dynamic_state={},
      ambient_state={},
  )
  signature_result = signature_snapshot.evaluate(
      SPECTRAL_RADIANT_INTENSITY_V1,
      SpectralSignatureRequest(
          direction_frame_id='source-local',
          source_to_observer_directions=((0.0, 1.0, 0.0),),
          wavelengths_m=(1.5e-6,),
      ),
  )
  assert signature_result.spectral_radiant_intensity == ((1.5,),)
  validity_results = evaluate_validity_matrix(default_validity_cases())
  assert len(validity_results) == 15
  assert any(result.validity_status.value == 'outside' for result in validity_results)

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
  visual_cli = shutil.which('exhaust-plume-visualize', path=str(Path(sys.executable).parent))
  signature_cli = shutil.which('exhaust-plume-signature', path=str(Path(sys.executable).parent))
  validity_cli = shutil.which('exhaust-plume-validate', path=str(Path(sys.executable).parent))
  assert visual_cli is not None, 'The installed visual console script was not found.'
  assert signature_cli is not None, 'The installed signature console script was not found.'
  assert validity_cli is not None, 'The installed validity console script was not found.'
  with tempfile.TemporaryDirectory() as working_directory:
    working_path = Path(working_directory)
    write_visual_result_json(visual_result, working_path / 'visual_result.json')
    write_visual_mesh_json(visual_mesh, working_path / 'visual_mesh.json')
    write_visual_obj(visual_mesh, working_path / 'visual_mesh.obj')
    write_signature_result_json(signature_result, working_path / 'signature_result.json')
    write_signature_result_csv(signature_definition, SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=((0.0, 1.0, 0.0),),
      wavelengths_m=(1.5e-6,),
    ), signature_result, working_path / 'signature_result.csv')
    completed = subprocess.run(
      [cli, '--help'],
      cwd=working_directory,
      check=True,
      capture_output=True,
      text=True,
    )
    assert 'usage:' in completed.stdout
    for product_cli in (visual_cli, signature_cli, validity_cli):
      completed = subprocess.run(
        [product_cli, '--help'],
        cwd=working_directory,
        check=True,
        capture_output=True,
        text=True,
      )
      assert 'usage:' in completed.stdout


if __name__ == '__main__':
  main()
