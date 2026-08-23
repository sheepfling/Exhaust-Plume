"""Generate the canonical public v1 schemas, fixtures, and asset manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from exhaust_plume.contracts.capability import CANONICAL_CAPABILITY_IDENTITIES
from exhaust_plume.contracts.ray_transfer_v1 import SPECTRAL_RAY_TRANSFER_CAPABILITY
from exhaust_plume.contracts.schema_v1 import PUBLIC_CONTRACT_MODELS, export_public_schemas
from exhaust_plume.contracts.signature_v1 import SPECTRAL_RADIANT_INTENSITY_CAPABILITY
from exhaust_plume.contracts.visual_v1 import VISUAL_SECTIONED_TUBE_CAPABILITY

from generate_public_contract_fixtures import (
  _ray_fixture,
  _signature_fixture,
  _visual_fixture,
)


MANIFEST_VERSION = 'exhaust-plume-public-contract-manifest-v1'
SCHEMA_DIALECT = 'https://json-schema.org/draft/2020-12/schema'

_FIXTURES: tuple[tuple[str, Any, bool, str | None], ...] = (
  ('visual_sectioned_tube_v1.json', _visual_fixture, True, 'VisualSectionedTubeResult'),
  ('spectral_signature_v1.json', _signature_fixture, True, 'SpectralSignatureResult'),
  ('spectral_ray_transfer_v1.json', _ray_fixture, True, 'SpectralRayTransferResult'),
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


def _capability_manifest() -> list[dict[str, Any]]:
  primary_schemas = {
    VISUAL_SECTIONED_TUBE_CAPABILITY.wire_id: (
      'visual_sectioned_tube_v1',
      'visual_sectioned_tube_result_v1',
    ),
    SPECTRAL_RADIANT_INTENSITY_CAPABILITY.wire_id: (
      'spectral_signature_v1',
      'spectral_signature_result_v1',
    ),
    SPECTRAL_RAY_TRANSFER_CAPABILITY.wire_id: (
      'spectral_ray_transfer_v1',
      'spectral_ray_transfer_result_v1',
    ),
  }
  records: list[dict[str, Any]] = []
  for identity in CANONICAL_CAPABILITY_IDENTITIES:
    request_schema, result_schema = primary_schemas.get(identity.wire_id, (None, None))
    records.append({
      'major': identity.major,
      'name': identity.name,
      'request_schema_id': request_schema,
      'result_schema_id': result_schema,
      'wire_id': identity.wire_id,
    })
  ####
  return records
####


def _write_manifest(
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
  ]
  fixture_records.append({
    'expected_error': 'strictly increasing',
    'file': 'invalid_visual_nonmonotonic.json',
    'model': 'VisualSectionedTubeResult',
    'sha256': _sha256(fixture_directory / 'invalid_visual_nonmonotonic.json'),
    'valid': False,
  })
  manifest = {
    'capabilities': _capability_manifest(),
    'fixture_generator': 'scripts/generate_public_contract_fixtures.py',
    'fixtures': fixture_records,
    'manifest_version': MANIFEST_VERSION,
    'schema_dialect': SCHEMA_DIALECT,
    'schema_generator': 'src/exhaust_plume/contracts/schema_v1.py',
    'schemas': schema_records,
  }
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
  return path
####


def generate_assets(
    *,
    schema_directory: str | Path = 'schemas',
    fixture_directory: str | Path = 'fixtures/contracts',
    manifest_path: str | Path = 'schemas/public_contract_manifest_v1.json',
) -> tuple[Path, ...]:
  """Generate every canonical public asset and return written paths."""

  schema_root = Path(schema_directory)
  fixture_root = Path(fixture_directory)
  schema_paths = export_public_schemas(schema_root)
  fixture_paths = _write_fixtures(fixture_root)
  manifest = _write_manifest(
    Path(manifest_path),
    schema_directory=schema_root,
    fixture_directory=fixture_root,
  )
  return (*schema_paths, *fixture_paths, manifest)
####


def main() -> None:
  parser = argparse.ArgumentParser(description='Generate canonical public plume schemas, fixtures, and manifest.')
  parser.add_argument('--schema-directory', default='schemas')
  parser.add_argument('--fixture-directory', default='fixtures/contracts')
  parser.add_argument('--manifest', default='schemas/public_contract_manifest_v1.json')
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
