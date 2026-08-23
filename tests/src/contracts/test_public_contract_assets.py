from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys

import pytest

from exhaust_plume.contracts import (
  PUBLIC_CONTRACT_MODELS,
  SpectralSignatureResult,
  VersionedSpectralRayTransferResult,
  VisualSectionedTubeResult,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_ROOT = ROOT / 'fixtures' / 'contracts'
SCHEMA_ROOT = ROOT / 'schemas'


def _generated_asset_paths(root: Path) -> tuple[Path, ...]:
  return tuple(
    [root / 'schemas' / f'{name}.schema.json' for name, _ in PUBLIC_CONTRACT_MODELS]
    + [
      root / 'fixtures/contracts/visual_sectioned_tube_v1.json',
      root / 'fixtures/contracts/spectral_signature_v1.json',
      root / 'fixtures/contracts/spectral_ray_transfer_v1.json',
      root / 'fixtures/contracts/invalid_visual_nonmonotonic.json',
      root / 'schemas/public_contract_manifest_v1.json',
    ]
  )
####


def test_checked_in_schemas_match_model_generation() -> None:
  for name, model in PUBLIC_CONTRACT_MODELS:
    schema_path = SCHEMA_ROOT / f'{name}.schema.json'
    assert schema_path.exists()
    assert json.loads(schema_path.read_text(encoding='utf-8')) == model.model_json_schema()
  ####
####


def test_checked_in_valid_fixtures_round_trip() -> None:
  VisualSectionedTubeResult.model_validate_json(
    (FIXTURE_ROOT / 'visual_sectioned_tube_v1.json').read_text(encoding='utf-8')
  )
  SpectralSignatureResult.model_validate_json(
    (FIXTURE_ROOT / 'spectral_signature_v1.json').read_text(encoding='utf-8')
  )
  VersionedSpectralRayTransferResult.model_validate_json(
    (FIXTURE_ROOT / 'spectral_ray_transfer_v1.json').read_text(encoding='utf-8')
  )
####


def test_checked_in_invalid_fixture_is_rejected() -> None:
  with pytest.raises(ValueError, match='strictly increasing'):
    VisualSectionedTubeResult.model_validate_json(
      (FIXTURE_ROOT / 'invalid_visual_nonmonotonic.json').read_text(encoding='utf-8')
    )
  ####
####


def test_manifest_records_one_capability_registry_and_asset_digests() -> None:
  manifest = json.loads(
    (SCHEMA_ROOT / 'public_contract_manifest_v1.json').read_text(encoding='utf-8')
  )
  assert manifest['schema_dialect'] == 'https://json-schema.org/draft/2020-12/schema'
  assert len(manifest['capabilities']) == 9
  assert {record['wire_id'] for record in manifest['capabilities']} == {
    'plume.visual.sectioned-tube@1',
    'plume.signature.spectral-radiant-intensity@1',
    'plume.optical.spectral-ray-transfer@1',
    'plume.engineering.flux-section@1',
    'plume.spatial.support@1',
    'plume.spatial.local-field@1',
    'plume.spatial.axisymmetric-zone-field@1',
    'plume.spatial.projected-area@1',
    'plume.image.spectral-radiance@1',
  }
  for record in (*manifest['schemas'], *manifest['fixtures']):
    asset_path = ROOT / ('schemas' if record['file'].endswith('.schema.json') else 'fixtures/contracts') / record['file']
    assert hashlib.sha256(asset_path.read_bytes()).hexdigest() == record['sha256']
  ####
####


def test_checked_in_v1_assets_match_the_0_1_0a1_wire_baseline() -> None:
  recorded = {}
  for line in (ROOT / 'docs/release_gate_0.1.0a1.sha256').read_text(encoding='utf-8').splitlines():
    digest, relative_path = line.split(maxsplit=1)
    if relative_path.startswith(('schemas/', 'fixtures/contracts/')):
      recorded[relative_path] = digest
    ####
  ####
  assert recorded
  for relative_path, digest in recorded.items():
    assert hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest() == digest
  ####
####


def test_two_clean_generation_runs_are_byte_identical(tmp_path: Path) -> None:
  generated_roots = (tmp_path / 'first', tmp_path / 'second')
  environment = os.environ.copy()
  environment['PYTHONPATH'] = os.pathsep.join((str(ROOT / 'src'), str(ROOT / 'scripts')))
  for generated_root in generated_roots:
    subprocess.run(
      (
        sys.executable,
        'scripts/generate_public_contract_assets.py',
        '--schema-directory',
        str(generated_root / 'schemas'),
        '--fixture-directory',
        str(generated_root / 'fixtures/contracts'),
        '--manifest',
        str(generated_root / 'schemas/public_contract_manifest_v1.json'),
      ),
      cwd=ROOT,
      env=environment,
      check=True,
      capture_output=True,
      text=True,
    )
  ####
  first_paths = _generated_asset_paths(generated_roots[0])
  second_paths = _generated_asset_paths(generated_roots[1])
  assert all(first.read_bytes() == second.read_bytes() for first, second in zip(first_paths, second_paths, strict=True))
####
