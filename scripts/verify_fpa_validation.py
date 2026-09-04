"""Report whether the recovered validation intake can support an FPA comparison.

The Version 8 corpus is source-centric and covers the three public products.
This checker deliberately treats an FPA image as a separate measurement-space
dataset.  Finding a spectral or thermal plot is not enough to close the FPA
gate, and the deterministic downstream adapter is never promoted to measured
detector evidence by this report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
  sys.path.insert(0, str(REPO_ROOT))
####

from scripts.verify_validation_corpus import (  # noqa: E402
  ArchiveCheck,
  load_manifest,
  verify_manifest,
)


FPA_VALIDATION_READINESS_SCHEMA = 'plume.validation.fpa-readiness@1'
FPA_LANE_ID = 'focal-plane-array-v1'
FPA_MEASUREMENT_SPACE = 'detector-pixel-counts'
FPA_MEASUREMENT_OPERATOR_ID = 'operator.sensor.fpa-detector-counts'
FPA_PROVIDER_OPERATOR_IDS = (
  'op.sensor.fpa-pixel-detector',
  'op.sensor.fpa-digitization',
)
FPA_REQUIRED_METADATA = (
  'camera_id',
  'mapping_model_id',
  'detector_response_id',
  'exposure_s',
  'wavelength_axis_m',
  'adc_policy_id',
  'frame_id',
  'pixel_validity_mask',
)


def _archive_summary(check: ArchiveCheck) -> dict[str, Any]:
  """Return a path-free archive check suitable for committed reports."""

  return {
    'archive_id': check.archive_id,
    'filename': check.filename,
    'expected_sha256': check.expected_sha256,
    'actual_sha256': check.actual_sha256,
    'status': check.status,
    'member_count': check.member_count,
    'unsafe_members': list(check.unsafe_members),
    'duplicate_members': list(check.duplicate_members),
    'errors': list(check.errors),
  }
####


def _candidate_fpa_members(path: Path) -> tuple[str, ...]:
  if not path.is_file():
    return ()
  ####
  with ZipFile(path) as archive:
    names = tuple(info.filename for info in archive.infolist())
  ####
  tokens = ('fpa', 'pixel', 'detector', 'camera')
  return tuple(sorted(
    name for name in names
    if any(token in name.lower() for token in tokens)
    and not name.endswith('/')
  ))
####


def _measurement_contract(candidate_members: tuple[str, ...]) -> dict[str, Any]:
  dataset_present = bool(candidate_members)
  return {
    'measurement_space': FPA_MEASUREMENT_SPACE,
    'measurement_operator_id': FPA_MEASUREMENT_OPERATOR_ID,
    'measurement_operator_namespace': 'future-external-measurement-contract',
    'provider_operator_ids': list(FPA_PROVIDER_OPERATOR_IDS),
    'required_metadata': list(FPA_REQUIRED_METADATA),
    'candidate_observation_members': list(candidate_members),
    'dataset_status': 'candidate-members-present' if dataset_present else 'not-present-in-corpus',
    'comparison_status': 'ready-for-contract-review' if dataset_present else 'blocked-pending-fpa-measurement',
  }
####


def build_fpa_validation_readiness_report(
  corpus_path: Path,
  alignment_path: Path,
  *,
  manifest_path: Path | None = None,
) -> dict[str, Any]:
  """Build a non-claiming FPA readiness report from the intake archives."""

  manifest = load_manifest(manifest_path) if manifest_path is not None else load_manifest()
  checks = verify_manifest(
    manifest,
    corpus_path=corpus_path,
    alignment_path=alignment_path,
  )
  check_by_id = {check.archive_id: check for check in checks}
  corpus_check = check_by_id['validation-corpus-v8']
  alignment_check = check_by_id['mvp-validation-alignment-v1']
  candidate_members = _candidate_fpa_members(corpus_path) if corpus_check.status == 'verified' else ()
  contract = _measurement_contract(candidate_members)
  intake_verified = all(check.status == 'verified' for check in checks)
  comparison_ready = (
    intake_verified
    and bool(candidate_members)
  )
  blockers = []
  if corpus_check.status != 'verified':
    blockers.append('content-addressed Version 8 corpus is not verified')
  ####
  if alignment_check.status != 'verified':
    blockers.append('separately named MVP alignment archive is not verified')
  ####
  if not candidate_members:
    blockers.append('no FPA camera/detector/pixel observation dataset is present in the recovered corpus')
  ####
  blockers.append('no accepted external FPA measurement claim is emitted by this report')
  return {
    'schema': FPA_VALIDATION_READINESS_SCHEMA,
    'report_id': 'exhaust-plume-fpa-validation-readiness-v1',
    'lane_id': FPA_LANE_ID,
    'status': 'ready-for-contract-review' if comparison_ready else (
      'corpus-intake-pending' if not intake_verified else 'blocked-pending-fpa-measurement'
    ),
    'intake': {
      'corpus': _archive_summary(corpus_check),
      'alignment': _archive_summary(alignment_check),
      'all_required_archives_verified': intake_verified,
    },
    'measurement_contract': contract,
    'implemented_downstream_boundary': {
      'pixel_detector_operator_id': FPA_PROVIDER_OPERATOR_IDS[0],
      'digitization_operator_id': FPA_PROVIDER_OPERATOR_IDS[1],
      'status': 'boundary-validated-downstream',
      'claim_ceiling': (
        'Deterministic expected-electron and expected-ADC-count views only; '
        'no externally validated FPA image, measured detector-count, '
        'noise-realization, or detection claim.'
      ),
    },
    'accepted_external_claim': False,
    'blockers': blockers,
  }
####


def _parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', required=True, type=Path)
  parser.add_argument('--alignment', required=True, type=Path)
  parser.add_argument('--manifest', type=Path)
  parser.add_argument('--output', type=Path)
  return parser
####


def main(argv: list[str] | None = None) -> int:
  arguments = _parser().parse_args(argv)
  report = build_fpa_validation_readiness_report(
    arguments.corpus,
    arguments.alignment,
    manifest_path=arguments.manifest,
  )
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if arguments.output is not None:
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(serialized, encoding='utf-8')
  ####
  print(serialized, end='')
  return 0 if report['status'] == 'ready-for-contract-review' else 1
####


if __name__ == '__main__':
  raise SystemExit(main())
####
