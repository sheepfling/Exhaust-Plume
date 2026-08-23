"""Fail when canonical public schemas, fixtures, or manifest drift."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator

from exhaust_plume.contracts.schema_v1 import PUBLIC_CONTRACT_MODELS
from exhaust_plume.contracts.visual_v1 import VisualSectionedTubeResult

from generate_public_contract_assets import generate_assets


ROOT = Path(__file__).resolve().parents[1]


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


def main() -> None:
  with tempfile.TemporaryDirectory(prefix='exhaust-plume-assets-') as temporary:
    generated_root = Path(temporary)
    generate_assets(
      schema_directory=generated_root / 'schemas',
      fixture_directory=generated_root / 'fixtures/contracts',
      manifest_path=generated_root / 'schemas/public_contract_manifest_v1.json',
    )
    relative_paths = tuple(
      [f'schemas/{name}.schema.json' for name, _ in PUBLIC_CONTRACT_MODELS]
      + [
        'fixtures/contracts/visual_sectioned_tube_v1.json',
        'fixtures/contracts/spectral_signature_v1.json',
        'fixtures/contracts/spectral_ray_transfer_v1.json',
        'fixtures/contracts/invalid_visual_nonmonotonic.json',
        'schemas/public_contract_manifest_v1.json',
      ]
    )
    _assert_same_bytes(ROOT, generated_root, relative_paths)
    _validate_assets(generated_root)
  ####
  print('canonical public schemas, fixtures, and manifest are deterministic and valid')
####


if __name__ == '__main__':
  main()
####
