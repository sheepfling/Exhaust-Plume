from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _json(path: Path) -> dict:
  return json.loads(path.read_text(encoding='utf-8'))
####


def test_frozen_manifest_matches_canonical_registry_and_assets() -> None:
  freeze = _json(ROOT / 'schemas' / 'public_contract_freeze_v1.json')
  source = _json(ROOT / 'schemas' / 'public_contract_manifest_v1.json')
  assert freeze['freeze_status'] == 'accepted'
  assert freeze['schema_dialect'] == source['schema_dialect']
  assert [item['wire_id'] for item in freeze['capabilities']] == [
    item['wire_id'] for item in source['capabilities']
  ]
  for asset in freeze['assets']:
    digest = hashlib.sha256((ROOT / asset['path']).read_bytes()).hexdigest()
    assert digest == asset['sha256'], asset['path']
  ####
####


def test_freeze_report_records_independent_product_boundaries() -> None:
  report = _json(ROOT / 'docs' / 'api_v1_freeze_report.json')
  assert report['status'] == 'accepted'
  assert report['product_boundaries']['visual'].startswith('sectioned geometry')
  assert 'no atmosphere' in report['product_boundaries']['signature']
  assert report['compatibility']['removal_horizon'] == (
    'no earlier than 0.2.0 after a new major-version migration review'
  )
####
