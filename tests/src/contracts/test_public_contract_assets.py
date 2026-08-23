from __future__ import annotations

import json
from pathlib import Path

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


def test_checked_in_schemas_match_model_generation() -> None:
  for name, model in PUBLIC_CONTRACT_MODELS:
    schema_path = SCHEMA_ROOT / f'{name}.schema.json'
    assert schema_path.exists()
    assert json.loads(schema_path.read_text(encoding='utf-8')) == model.model_json_schema()


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


def test_checked_in_invalid_fixture_is_rejected() -> None:
  with pytest.raises(ValueError, match='strictly increasing'):
    VisualSectionedTubeResult.model_validate_json(
      (FIXTURE_ROOT / 'invalid_visual_nonmonotonic.json').read_text(encoding='utf-8')
    )
