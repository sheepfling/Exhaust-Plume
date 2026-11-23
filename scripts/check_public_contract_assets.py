"""Fail when canonical public schemas, fixtures, or manifest drift."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

# Make this release-facing check executable both through ``scripts/ci.py`` and
# directly from a checkout.  The CI wrapper supplies these paths in
# ``PYTHONPATH``; a direct invocation should not depend on that wrapper.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))

from exhaust_plume.contracts.schema_v1 import PUBLIC_CONTRACT_MODELS  # noqa: E402
from exhaust_plume.contracts.visual_v1 import VisualSectionedTubeResult  # noqa: E402

from generate_public_contract_assets import generate_assets  # noqa: E402


def _assert_same_bytes(expected_root: Path, generated_root: Path, relative_paths: tuple[str, ...]) -> None:
  for relative_path in relative_paths:
    expected = expected_root / relative_path
    generated = generated_root / relative_path
    if expected.read_bytes() != generated.read_bytes():
      raise AssertionError(f'generated public asset differs: {relative_path}')
    ####
  ####
####


def _validate_assets(root: Path) -> None:
  schemas = {
    name: json.loads((root / 'schemas' / f'{name}.schema.json').read_text(encoding='utf-8'))
    for name, _ in PUBLIC_CONTRACT_MODELS
  }
  for schema in schemas.values():
    Draft202012Validator.check_schema(schema)
  ####
  valid_fixtures = (
    (
      'visual_sectioned_tube_v1.json',
      schemas['visual_sectioned_tube_result_v1'],
      VisualSectionedTubeResult,
    ),
    ('spectral_signature_v1.json', schemas['spectral_signature_result_v1'], None),
    ('spectral_ray_transfer_v1.json', schemas['spectral_ray_transfer_result_v1'], None),
  )
  for name, schema, model in valid_fixtures:
    value = json.loads((root / 'fixtures/contracts' / name).read_text(encoding='utf-8'))
    Draft202012Validator(schema).validate(value)
    if model is not None:
      model.model_validate(value)
    ####
  ####
  extension = json.loads(
    (root / 'schemas/public_contract_extension_manifest_v1.json').read_text(encoding='utf-8')
  )
  schema_records = {record['schema_id']: record for record in extension['schemas']}
  result_models = {model.__name__: model for _, model in PUBLIC_CONTRACT_MODELS}
  if not set(extension.get('standalone_schema_ids', ())) <= set(schema_records):
    raise AssertionError('standalone contract schema is missing from the extension schema registry')
  for record in extension['schemas']:
    schema_path = root / 'schemas' / record['file']
    if hashlib.sha256(schema_path.read_bytes()).hexdigest() != record['sha256']:
      raise AssertionError(f'extension schema digest differs: {record["file"]}')
  ####
  for record in extension['fixtures']:
    fixture_path = root / 'fixtures/contracts' / record['file']
    if hashlib.sha256(fixture_path.read_bytes()).hexdigest() != record['sha256']:
      raise AssertionError(f'extension fixture digest differs: {record["file"]}')
    capability = next(
      item
      for item in extension['capabilities']
      if item['result_schema_id'] in schema_records
      and schema_records[item['result_schema_id']]['model'] == record['model']
    )
    value = json.loads(fixture_path.read_text(encoding='utf-8'))
    Draft202012Validator(
      schemas[capability['result_schema_id']]
    ).validate(value)
    result_models[record['model']].model_validate(value)
  ####
  for record in extension.get('standalone_fixtures', ()):
    fixture_path = ROOT / 'fixtures/contracts' / record['file']
    if hashlib.sha256(fixture_path.read_bytes()).hexdigest() != record['sha256']:
      raise AssertionError(f'standalone fixture digest differs: {record["file"]}')
    schema_record = schema_records.get(record['schema_id'])
    if schema_record is None:
      raise AssertionError(f'standalone fixture references an unknown schema: {record["schema_id"]}')
    value = json.loads(fixture_path.read_text(encoding='utf-8'))
    Draft202012Validator(schemas[record['schema_id']]).validate(value)
    result_models[record['model']].model_validate(value)
  ####
  invalid = json.loads(
    (root / 'fixtures/contracts/invalid_visual_nonmonotonic.json').read_text(encoding='utf-8')
  )
  try:
    VisualSectionedTubeResult.model_validate(invalid)
  except ValueError as error:
    if 'strictly increasing' not in str(error):
      raise AssertionError('invalid fixture failed for an unexpected reason') from error
    ####
  else:
    raise AssertionError('invalid visual fixture unexpectedly validated')
  ####
####


def _validate_frozen_base() -> None:
  freeze_path = ROOT / 'schemas/public_contract_freeze_v1.json'
  manifest_path = ROOT / 'schemas/public_contract_manifest_v1.json'
  freeze = json.loads(freeze_path.read_text(encoding='utf-8'))
  manifest_bytes = manifest_path.read_bytes()
  if hashlib.sha256(manifest_bytes).hexdigest() != freeze['source_manifest_sha256']:
    raise AssertionError('accepted v1 public contract manifest digest changed')
  manifest = json.loads(manifest_bytes)
  frozen_ids = [item['wire_id'] for item in freeze['capabilities']]
  manifest_ids = [item['wire_id'] for item in manifest['capabilities']]
  if manifest_ids != frozen_ids:
    raise AssertionError('accepted v1 public contract capability list changed')
  extension_path = ROOT / 'schemas/public_contract_extension_manifest_v1.json'
  extension = json.loads(extension_path.read_text(encoding='utf-8'))
  if extension['base_freeze'] != {
      'freeze_id': freeze['freeze_id'],
      'manifest_path': freeze['source_manifest'],
      'manifest_sha256': freeze['source_manifest_sha256'],
  }:
    raise AssertionError('public contract extension does not bind the accepted v1 freeze')
  ####
####


def main() -> None:
  with tempfile.TemporaryDirectory(prefix='exhaust-plume-assets-') as temporary:
    generated_root = Path(temporary)
    generate_assets(
      schema_directory=generated_root / 'schemas',
      fixture_directory=generated_root / 'fixtures/contracts',
      manifest_path=generated_root / 'schemas/public_contract_extension_manifest_v1.json',
    )
    relative_paths = tuple(
      [f'schemas/{name}.schema.json' for name, _ in PUBLIC_CONTRACT_MODELS]
      + [
        'fixtures/contracts/visual_sectioned_tube_v1.json',
        'fixtures/contracts/spectral_signature_v1.json',
        'fixtures/contracts/spectral_ray_transfer_v1.json',
        'fixtures/contracts/spatial_support_result_v1.json',
        'fixtures/contracts/projected_area_result_v1.json',
        'fixtures/contracts/axisymmetric_zone_field_result_v1.json',
        'fixtures/contracts/model_lane_visualization_result_v1.json',
        'fixtures/contracts/spectral_radiance_image_result_v1.json',
        'fixtures/contracts/spatial_local_field_result_v1.json',
        'fixtures/contracts/plume_flux_section_v1.json',
        'fixtures/contracts/engineering_flux_section_result_v1.json',
        'fixtures/contracts/invalid_visual_nonmonotonic.json',
        'schemas/public_contract_extension_manifest_v1.json',
      ]
    )
    _assert_same_bytes(ROOT, generated_root, relative_paths)
    _validate_assets(generated_root)
    _validate_frozen_base()
  ####
  print('public schemas, fixtures, extension manifest, and frozen baseline are valid')
####


if __name__ == '__main__':
  main()
####
