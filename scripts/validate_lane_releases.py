"""Build the fidelity-scoped lane release manifest.

The manifest intentionally separates a lane's local release boundary from an
externally validated product claim.  A local contract/analytic release is
useful for consumers of that exact lane, but it must not inherit validation or
capabilities from another solver lane.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

MATRIX_PATH = REPO_ROOT / 'docs' / 'solver_fidelity_matrix_v1.json'
PRODUCT_REPORT_PATH = REPO_ROOT / 'docs' / 'validation' / 'product_lane_validation_v1.json'
RELEASE_FREEZE_PATH = REPO_ROOT / 'docs' / 'validation' / 'release_freeze_v1.json'
PROVIDER_PREFLIGHT_PATH = REPO_ROOT / 'docs' / 'validation' / 'provider_comparison_preflight_v1.json'
MISSION_TIME_LANE_ID = 'mission-time-product-composition-v1'
MISSION_TIME_SCHEDULE_S = (0.0, 5.0, 10.0)


def _git_head_commit() -> str | None:
  """Return the committed candidate HEAD when this runs inside a checkout."""

  try:
    completed = subprocess.run(
      (
        'git',
        '-C',
        str(REPO_ROOT),
        'rev-parse',
        '--verify',
        'HEAD',
      ),
      capture_output=True,
      check=True,
      text=True,
    )
  except (OSError, subprocess.CalledProcessError):
    return None
  ####
  commit = completed.stdout.strip()
  return commit or None
####


def _git_worktree_clean() -> bool | None:
  """Return whether the checkout has no staged, unstaged, or untracked files."""

  try:
    completed = subprocess.run(
      (
        'git',
        '-C',
        str(REPO_ROOT),
        'status',
        '--porcelain',
        '--untracked-files=all',
      ),
      capture_output=True,
      check=True,
      text=True,
    )
  except (OSError, subprocess.CalledProcessError):
    return None
  ####
  return completed.stdout == ''
####


def _read_json(path: Path) -> dict[str, Any]:
  payload = json.loads(path.read_text(encoding='utf-8'))
  if not isinstance(payload, dict):
    raise ValueError(f'{path} must contain a JSON object')
  ####
  return payload
####


def _product_report_lanes(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
  lanes = report.get('lanes')
  if not isinstance(lanes, dict):
    raise ValueError('product lane report must contain a lanes object')
  ####
  return {
    str(lane_id): value
    for lane_id, value in lanes.items()
    if isinstance(value, dict)
  }
####


def _local_release_status(
  *,
  matrix_status: str,
  product_report: dict[str, Any] | None,
) -> tuple[str, bool]:
  if matrix_status == 'planned':
    return 'planned', False
  ####
  if matrix_status in {'experimental', 'foundation-validated-provider-pending'}:
    return 'not-released-validation-pending', False
  ####
  if product_report is None:
    return 'not-released-missing-lane-evidence', False
  ####
  status = product_report.get('status')
  if status == 'boundary-validated-downstream':
    return 'scoped-downstream-boundary', True
  ####
  if status == 'passed':
    return 'scoped-local-release', True
  ####
  return 'not-released-local-evidence-failed', False
####


def _external_status(product_report: dict[str, Any] | None) -> str:
  if product_report is None:
    return 'not-applicable'
  ####
  comparison = product_report.get('external_comparison')
  if not isinstance(comparison, dict):
    return 'not-recorded'
  ####
  return str(comparison.get('status', 'not-recorded'))
####


def _mission_time_composition_status(
  product_report: dict[str, Any],
) -> tuple[dict[str, Any] | None, bool]:
  """Validate the committed three-product mission-time composition record."""

  record = product_report.get('lanes', {}).get('mission_time')
  if not isinstance(record, dict):
    return None, False
  ####
  if record.get('lane_id') != MISSION_TIME_LANE_ID:
    return record, False
  ####
  if tuple(record.get('mission_times_s', ())) != MISSION_TIME_SCHEDULE_S:
    return record, False
  ####
  if record.get('status') != 'passed':
    return record, False
  ####
  visualization = record.get('visualization')
  signature = record.get('signature')
  focal_plane_array = record.get('focal_plane_array')
  if not all(isinstance(value, dict) for value in (
      visualization,
      signature,
      focal_plane_array,
  )):
    return record, False
  ####
  return record, all(
    value.get('status') == 'passed'
    for value in (visualization, signature, focal_plane_array)
  )
####


def _lane_record(
  lane: dict[str, Any],
  *,
  product_report: dict[str, Any] | None,
  product_evidence_source: str | None = None,
) -> dict[str, Any]:
  lane_id = str(lane['lane_id'])
  local_status, local_release_ready = _local_release_status(
    matrix_status=str(lane.get('status', 'missing')),
    product_report=product_report,
  )
  advertised = [str(value) for value in lane.get('advertised_capabilities', [])]
  forbidden = [str(value) for value in lane.get('forbidden_capabilities', [])]
  product_status = None if product_report is None else product_report.get('status')
  return {
    'lane_id': lane_id,
    'matrix_status': lane.get('status'),
    'provider_ids': list(lane.get('provider_ids', [])),
    'advertised_capabilities': advertised,
    'forbidden_capabilities': forbidden,
    'promotion_guard': {
      'advertised_disjoint_from_forbidden': not bool(set(advertised) & set(forbidden)),
      'low_fidelity_promotion_detected': False,
    },
    'product_report_status': product_status,
    'product_evidence_source': product_evidence_source,
    'external_validation_status': _external_status(product_report),
    'local_release_status': local_status,
    'local_release_ready': local_release_ready,
    'claim_ceiling': (
      lane.get('claim_ceiling')
      if lane.get('claim_ceiling') is not None
      else (product_report.get('claim_ceiling') if product_report is not None else None)
    ),
    'complexity_policy': lane.get('complexity_policy'),
  }
####


def _product_report_for_lane(
  product_lanes: dict[str, dict[str, Any]],
  product_key: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
  """Resolve direct evidence or an explicitly scoped visual-bundle record."""

  if product_key is None:
    return None, None
  ####
  direct = product_lanes.get(product_key)
  if direct is not None:
    return direct, f'committed-product-report.lanes.{product_key}'
  ####
  if product_key != 'washed_integral':
    return None, None
  ####
  visual = product_lanes.get('visual')
  if visual is None:
    return None, None
  ####
  standardized = visual.get('standardized_model_lanes')
  if not isinstance(standardized, dict):
    return None, None
  ####
  standardized_lanes = standardized.get('lanes', [])
  if (
    standardized.get('status') != 'passed'
    or 'washed-integral-v1' not in standardized_lanes
  ):
    return None, None
  ####
  return {
    'status': 'passed',
    'external_comparison': standardized.get('external_comparison'),
    'claim_ceiling': (
      'Common renderer-neutral visualization evidence for the washed-integral '
      'lane; the source lane retains its declared engineering-approximate '
      'claim ceiling.'
    ),
  }, 'committed-product-report.lanes.visual.standardized_model_lanes'
####


def build_lane_release_manifest() -> dict[str, Any]:
  """Build a deterministic release record from committed lane evidence."""

  matrix = _read_json(MATRIX_PATH)
  product_report = _read_json(PRODUCT_REPORT_PATH)
  release_freeze = _read_json(RELEASE_FREEZE_PATH)
  provider_preflight = _read_json(PROVIDER_PREFLIGHT_PATH)
  product_lanes = _product_report_lanes(product_report)
  mission_time, mission_time_passed = _mission_time_composition_status(product_report)
  matrix_lanes = matrix.get('lanes')
  if not isinstance(matrix_lanes, list):
    raise ValueError('solver fidelity matrix must contain a lanes list')
  ####
  report_key_by_lane = {
    'shock-cell-basic-v1': 'visual',
    'washed-integral-v1': 'washed_integral',
    'signature-table-mvp-v1': 'signature',
    'optical-transfer-v1': 'optical',
    'curved-optical-transfer-v1': 'curved_optical',
    'ray-to-signature-consistency-v1': 'cross_product',
    'focal-plane-array-v1': 'focal_plane_array',
  }
  lane_records = []
  for lane in matrix_lanes:
    if not isinstance(lane, dict) or 'lane_id' not in lane:
      raise ValueError('every solver matrix lane must be an object with lane_id')
    ####
    product_key = report_key_by_lane.get(str(lane['lane_id']))
    product_report_for_lane, evidence_source = _product_report_for_lane(
      product_lanes,
      product_key,
    )
    lane_records.append(_lane_record(
      lane,
      product_report=product_report_for_lane,
      product_evidence_source=evidence_source,
    ))
  ####
  violations = [
    record['lane_id']
    for record in lane_records
    if not record['promotion_guard']['advertised_disjoint_from_forbidden']
    or record['promotion_guard']['low_fidelity_promotion_detected']
  ]
  active_local_failures = [
    record['lane_id']
    for record in lane_records
    if record['matrix_status'] == 'active' and not record['local_release_ready']
  ]
  fpa = next(record for record in lane_records if record['lane_id'] == 'focal-plane-array-v1')
  fpa_provider_guard = fpa['provider_ids'] == [] and fpa['local_release_status'] == 'scoped-downstream-boundary'
  blockers = list(release_freeze.get('release_blockers', []))
  candidate_head_commit = _git_head_commit()
  candidate_worktree_clean = _git_worktree_clean()
  recorded_freeze_head_commit = release_freeze.get('head_commit')
  validated_code_commit = release_freeze.get(
    'validated_code_commit',
    release_freeze.get('head_commit'),
  )
  freeze_matches_candidate_head = bool(
    candidate_head_commit is not None
    and isinstance(recorded_freeze_head_commit, str)
    and candidate_head_commit == recorded_freeze_head_commit
  )
  candidate_matches_validated_code_commit = bool(
    candidate_head_commit is not None
    and isinstance(validated_code_commit, str)
    and candidate_head_commit == validated_code_commit
  )
  if candidate_head_commit is None:
    blockers.append('candidate HEAD could not be resolved from the release checkout')
  elif not freeze_matches_candidate_head:
    blockers.append(
      'release freeze does not identify the current candidate HEAD; refresh '
      'release evidence after the final code and documentation commit'
    )
  ####
  if candidate_worktree_clean is not True:
    blockers.append(
      'candidate worktree is not clean; release evidence must be generated '
      'from a committed candidate'
    )
  ####
  if provider_preflight.get('release_ready') is not True:
    blockers.append('provider comparison preflight is not externally accepted')
  ####
  if not mission_time_passed:
    blockers.append(
      'mission-time product composition is missing or failed in the committed '
      'local product-lane evidence'
    )
  ####
  release_provenance_ready = bool(
    freeze_matches_candidate_head and candidate_worktree_clean is True
  )
  return {
    'report_id': 'exhaust-plume-lane-release-manifest-v1',
    'schema_version': 'plume.lane-release-manifest@1',
    # A release freeze may receive documentation-only provenance refreshes
    # after the code and wheel evidence are produced. Keep the manifest tied
    # to the validated code tranche while retaining the actual branch HEAD in
    # the freeze record.
    'source_commit': validated_code_commit,
    'release_provenance': {
      'candidate_head_commit': candidate_head_commit,
      'recorded_freeze_head_commit': recorded_freeze_head_commit,
      'validated_code_commit': validated_code_commit,
      'candidate_head_matches_recorded_freeze': freeze_matches_candidate_head,
      'candidate_head_matches_validated_code_commit': (
        candidate_matches_validated_code_commit
      ),
      'candidate_worktree_clean': candidate_worktree_clean,
    },
    'wheel_sha256': release_freeze.get('repository_quality', {}).get('wheel_sha256'),
    'release_policy': {
      'local_release_definition': 'versioned lane evidence plus an explicit claim ceiling; it is not an external validation claim',
      'external_validation_required_for_product_claim': True,
      'low_fidelity_promotion_forbidden': True,
      'fpa_is_downstream_adapter_only_until_provider_validation': True,
    },
    'checks': {
      'all_active_lanes_have_local_release_evidence': not active_local_failures,
      'low_fidelity_promotion_detected': bool(violations),
      'fpa_provider_guard_passed': fpa_provider_guard,
      'mission_time_composition_passed': mission_time_passed,
      'provider_preflight_release_ready': provider_preflight.get('release_ready') is True,
      'release_freeze_matches_candidate_head': freeze_matches_candidate_head,
      'candidate_worktree_clean': candidate_worktree_clean is True,
    },
    'lanes': lane_records,
    'mission_time_composition': mission_time,
    'umbrella_release': {
      'release_ready': (
        not blockers
        and not violations
        and not active_local_failures
        and fpa_provider_guard
        and mission_time_passed
        and release_provenance_ready
      ),
      'blockers': blockers,
    },
  }
####


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  report = build_lane_release_manifest()
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if args.output is not None:
    args.output.write_text(serialized, encoding='utf-8')
  ####
  print(serialized, end='')
  return 0 if report['checks']['low_fidelity_promotion_detected'] is False else 1
####


if __name__ == '__main__':
  raise SystemExit(main(sys.argv[1:]))
####
