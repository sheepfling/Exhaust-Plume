from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from scripts.verify_fpa_validation import build_fpa_validation_readiness_report


def _zip(path: Path, members: tuple[str, ...]) -> str:
  with ZipFile(path, 'w') as archive:
    for member in members:
      archive.writestr(member, 'fixture')
  digest = sha256(path.read_bytes()).hexdigest()
  return digest
####


def _manifest(path: Path, corpus: Path, alignment: Path) -> None:
  path.write_text(json.dumps({
    'archives': [
      {
        'archive_id': 'validation-corpus-v8',
        'filename': corpus.name,
        'sha256': sha256(corpus.read_bytes()).hexdigest(),
      },
      {
        'archive_id': 'mvp-validation-alignment-v1',
        'filename': alignment.name,
        'sha256': sha256(alignment.read_bytes()).hexdigest(),
      },
    ],
  }), encoding='utf-8')
####


def test_fpa_readiness_keeps_missing_measurements_blocked(tmp_path: Path) -> None:
  corpus = tmp_path / 'corpus.zip'
  alignment = tmp_path / 'alignment.zip'
  _zip(corpus, ('data/rp_bsuv2_001_uv_spectral_radiance.csv',))
  _zip(alignment, ('alignment/operator_registry.csv',))
  manifest = tmp_path / 'manifest.json'
  _manifest(manifest, corpus, alignment)

  report = build_fpa_validation_readiness_report(corpus, tmp_path / 'missing-alignment.zip', manifest_path=manifest)

  assert report['status'] == 'corpus-intake-pending'
  assert report['intake']['corpus']['status'] == 'verified'
  assert report['intake']['alignment']['status'] == 'missing'
  assert report['measurement_contract']['dataset_status'] == 'not-present-in-corpus'
  assert report['accepted_external_claim'] is False


def test_fpa_readiness_only_reaches_contract_review_when_all_inputs_are_declared(tmp_path: Path) -> None:
  corpus = tmp_path / 'corpus.zip'
  alignment = tmp_path / 'alignment.zip'
  _zip(corpus, ('data/fpa_detector_counts.csv', 'docs/README.md'))
  _zip(alignment, ('alignment/operator_registry.csv',))
  manifest = tmp_path / 'manifest.json'
  _manifest(manifest, corpus, alignment)

  report = build_fpa_validation_readiness_report(corpus, alignment, manifest_path=manifest)

  assert report['status'] == 'ready-for-contract-review'
  assert report['measurement_contract']['measurement_space'] == 'detector-pixel-counts'
  assert report['measurement_contract']['measurement_operator_id'] == 'operator.sensor.fpa-detector-counts'
  assert report['measurement_contract']['candidate_observation_members'] == ['data/fpa_detector_counts.csv']
  assert report['accepted_external_claim'] is False
