"""Generate public contract schemas, fixtures, and an additive extension manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from exhaust_plume.contracts.capability import (
  ENGINEERING_FLUX_SECTION_CAPABILITY,
  IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
  MODEL_LANE_VISUALIZATION_CAPABILITY,
  SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
  SPATIAL_LOCAL_FIELD_CAPABILITY,
  SPATIAL_PROJECTED_AREA_CAPABILITY,
  SPATIAL_SUPPORT_CAPABILITY,
)
from exhaust_plume.contracts.schema_v1 import PUBLIC_CONTRACT_MODELS, export_public_schemas

from generate_public_contract_fixtures import (
  _axisymmetric_zone_field_fixture,
  _engineering_flux_section_fixture,
  _model_lane_visualization_fixture,
  _plume_flux_section_fixture,
  _projected_area_fixture,
  _ray_fixture,
  _spectral_radiance_image_fixture,
  _signature_fixture,
  _spatial_support_fixture,
  _spatial_local_field_fixture,
  _visual_fixture,
)


MANIFEST_VERSION = 'exhaust-plume-public-contract-extension-v1'
SCHEMA_DIALECT = 'https://json-schema.org/draft/2020-12/schema'
BASE_FREEZE_ID = 'exhaust-plume-public-contract-freeze-v1'
BASE_MANIFEST_SHA256 = '4f91c6891a19f71ea6ff3952801092d345c9908afef47823e557f3a6b790594e'

_EXTENSION_CAPABILITIES = (
  (
    ENGINEERING_FLUX_SECTION_CAPABILITY,
    'engineering_flux_section_v1',
    'engineering_flux_section_result_v1',
  ),
  (
    SPATIAL_SUPPORT_CAPABILITY,
    'spatial_support_v1',
    'spatial_support_result_v1',
  ),
  (
    SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
    'axisymmetric_zone_field_v1',
    'axisymmetric_zone_field_result_v1',
  ),
  (
    SPATIAL_PROJECTED_AREA_CAPABILITY,
    'projected_area_v1',
    'projected_area_result_v1',
  ),
  (
    MODEL_LANE_VISUALIZATION_CAPABILITY,
    'model_lane_visualization_v1',
    'model_lane_visualization_result_v1',
  ),
  (
    IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
    'spectral_radiance_image_v1',
    'spectral_radiance_image_result_v1',
  ),
  (
    SPATIAL_LOCAL_FIELD_CAPABILITY,
    'spatial_local_field_v1',
    'spatial_local_field_result_v1',
  ),
)

_UNRESOLVED_CAPABILITIES = ()

_PENDING_SUPPORT_GATES = (
  (
    IMAGE_SPECTRAL_RADIANCE_CAPABILITY,
    'source-provider-and-observation-validation-pending',
  ),
  (
    SPATIAL_LOCAL_FIELD_CAPABILITY,
    'provider-observation-validation-pending',
  ),
  (
    ENGINEERING_FLUX_SECTION_CAPABILITY,
    'straight-integral-provider-available-measurement-validation-pending',
  ),
)

_EXTENSION_FIXTURE_NAMES = frozenset({
  'spatial_support_result_v1.json',
  'projected_area_result_v1.json',
  'axisymmetric_zone_field_result_v1.json',
  'model_lane_visualization_result_v1.json',
  'spectral_radiance_image_result_v1.json',
  'spatial_local_field_result_v1.json',
  'engineering_flux_section_result_v1.json',
})

_EXTENSION_SCHEMA_IDS = frozenset(
  schema_id
  for _, request_schema_id, result_schema_id in _EXTENSION_CAPABILITIES
  for schema_id in (request_schema_id, result_schema_id)
)
_STANDALONE_SCHEMA_IDS = frozenset({'plume_flux_section_v1'})
_STANDALONE_FIXTURE_NAMES = frozenset({'plume_flux_section_v1.json'})
_EXTENSION_SCHEMA_IDS = _EXTENSION_SCHEMA_IDS | _STANDALONE_SCHEMA_IDS

_FIXTURES: tuple[tuple[str, Any, bool, str | None], ...] = (
  ('visual_sectioned_tube_v1.json', _visual_fixture, True, 'VisualSectionedTubeResult'),
  ('spectral_signature_v1.json', _signature_fixture, True, 'SpectralSignatureResult'),
  ('spectral_ray_transfer_v1.json', _ray_fixture, True, 'SpectralRayTransferResult'),
  ('spatial_support_result_v1.json', _spatial_support_fixture, True, 'SpatialSupportResult'),
  ('projected_area_result_v1.json', _projected_area_fixture, True, 'ProjectedAreaResult'),
  (
    'axisymmetric_zone_field_result_v1.json',
    _axisymmetric_zone_field_fixture,
    True,
    'AxisymmetricZoneFieldResult',
  ),
  (
    'model_lane_visualization_result_v1.json',
    _model_lane_visualization_fixture,
    True,
    'ModelLaneVisualizationResult',
  ),
  (
    'spectral_radiance_image_result_v1.json',
    _spectral_radiance_image_fixture,
    True,
    'SpectralRadianceImageResult',
  ),
  (
    'spatial_local_field_result_v1.json',
    _spatial_local_field_fixture,
    True,
    'SpatialLocalFieldResult',
  ),
  ('plume_flux_section_v1.json', _plume_flux_section_fixture, True, 'PlumeFluxSectionV1'),
  (
    'engineering_flux_section_result_v1.json',
    _engineering_flux_section_fixture,
    True,
    'EngineeringFluxSectionResult',
  ),
)


def _sha256(path: Path) -> str:
  return hashlib.sha256(path.read_bytes()).hexdigest()
####


def _write_fixtures(directory: Path) -> tuple[Path, ...]:
  directory.mkdir(parents=True, exist_ok=True)
  generated: list[Path] = []
  for name, builder, _, _ in _FIXTURES:
    path = directory / name
    path.write_text(builder().model_dump_json(indent=2) + '\n', encoding='utf-8')
    generated.append(path)
  ####
  invalid_visual = _visual_fixture().model_dump(mode='json')
  invalid_visual['sections'][1]['arc_length_m'] = 0.0
  invalid_path = directory / 'invalid_visual_nonmonotonic.json'
  invalid_path.write_text(json.dumps(invalid_visual, indent=2) + '\n', encoding='utf-8')
  generated.append(invalid_path)
  return tuple(generated)
####


def _extension_capabilities() -> list[dict[str, Any]]:
  return [
    {
      'major': identity.major,
      'name': identity.name,
      'request_schema_id': request_schema_id,
      'result_schema_id': result_schema_id,
      'wire_id': identity.wire_id,
    }
    for identity, request_schema_id, result_schema_id in _EXTENSION_CAPABILITIES
  ]
####


def _write_extension_manifest(
    path: Path,
    *,
    schema_directory: Path,
    fixture_directory: Path,
) -> Path:
  schema_records = [
    {
      'file': schema_path.name,
      'model': model.__name__,
      'schema_id': schema_id,
      'sha256': _sha256(schema_path),
    }
    for (schema_id, model), schema_path in zip(
      PUBLIC_CONTRACT_MODELS,
      (schema_directory / f'{schema_id}.schema.json' for schema_id, _ in PUBLIC_CONTRACT_MODELS),
      strict=True,
    )
    if schema_id in _EXTENSION_SCHEMA_IDS
  ]
  fixture_records = [
    {
      'expected_error': None,
      'file': name,
      'model': model,
      'sha256': _sha256(fixture_directory / name),
      'valid': valid,
    }
    for name, _, valid, model in _FIXTURES
    if name in _EXTENSION_FIXTURE_NAMES
  ]
  standalone_fixture_records = [
    {
      'expected_error': None,
      'file': name,
      'model': model,
      'schema_id': 'plume_flux_section_v1',
      'sha256': _sha256(fixture_directory / name),
      'valid': valid,
    }
    for name, _, valid, model in _FIXTURES
    if name in _STANDALONE_FIXTURE_NAMES
  ]
  manifest = {
    'base_freeze': {
      'freeze_id': BASE_FREEZE_ID,
      'manifest_path': 'schemas/public_contract_manifest_v1.json',
      'manifest_sha256': BASE_MANIFEST_SHA256,
    },
    'capabilities': _extension_capabilities(),
    'fixture_generator': 'scripts/generate_public_contract_fixtures.py',
    'fixtures': fixture_records,
    'manifest_version': MANIFEST_VERSION,
    'schema_dialect': SCHEMA_DIALECT,
    'schema_generator': 'src/exhaust_plume/contracts/schema_v1.py',
    'schemas': schema_records,
    'standalone_schema_ids': sorted(_STANDALONE_SCHEMA_IDS),
    'standalone_fixtures': standalone_fixture_records,
    'pending_support_gates': [
      {
        'release_supported': False,
        'status': status,
        'wire_id': identity.wire_id,
      }
      for identity, status in _PENDING_SUPPORT_GATES
    ],
    'unresolved_capabilities': [
      {
        'release_supported': False,
        'status': 'request-result-contract-unresolved',
        'wire_id': identity.wire_id,
      }
      for identity in _UNRESOLVED_CAPABILITIES
    ],
  }
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
  return path
####


def generate_assets(
    *,
    schema_directory: str | Path = 'schemas',
    fixture_directory: str | Path = 'fixtures/contracts',
    manifest_path: str | Path = 'schemas/public_contract_extension_manifest_v1.json',
) -> tuple[Path, ...]:
  """Generate public schemas, fixtures, and the additive extension manifest."""

  schema_root = Path(schema_directory)
  fixture_root = Path(fixture_directory)
  schema_paths = export_public_schemas(schema_root)
  fixture_paths = _write_fixtures(fixture_root)
  manifest = _write_extension_manifest(
    Path(manifest_path),
    schema_directory=schema_root,
    fixture_directory=fixture_root,
  )
  return (*schema_paths, *fixture_paths, manifest)
####


def main() -> None:
  parser = argparse.ArgumentParser(
    description='Generate public plume schemas, fixtures, and additive extension manifest.'
  )
  parser.add_argument('--schema-directory', default='schemas')
  parser.add_argument('--fixture-directory', default='fixtures/contracts')
  parser.add_argument('--manifest', default='schemas/public_contract_extension_manifest_v1.json')
  arguments = parser.parse_args()
  for path in generate_assets(
      schema_directory=arguments.schema_directory,
      fixture_directory=arguments.fixture_directory,
      manifest_path=arguments.manifest,
  ):
    print(path)
  ####
####


if __name__ == '__main__':
  main()
####
