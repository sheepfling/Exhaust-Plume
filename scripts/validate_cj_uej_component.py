"""Quantify the bounded shock-cell component against the CJ-UEJ corpus.

This command is deliberately a component diagnostic, not a visual-product
acceptance test.  The recovered case is a cold convergent/choked jet and does
not publish all boundary conditions required by the current supersonic exit
contract.  The run therefore records explicit near-sonic and temperature
assumptions, keeps source-derived Mach data separate from pressure/velocity
profiles, and leaves the claim unaccepted.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import json
from math import isfinite, sqrt
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping, Sequence
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))
####

from exhaust_plume import (  # noqa: E402
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.models.shock_cells import (  # noqa: E402
  ShockCellSolveConfig,
  ShockCellSolveResult,
  solve_shock_cells,
)
from exhaust_plume.util.aero.flow_state import FlowState  # noqa: E402
from exhaust_plume.validation import (  # noqa: E402
  ClaimRole,
  ClaimStatus,
  EvidenceLevel,
  ValidationClaim,
  ValidationRegistry,
)

try:
  from scripts.validate_external_corpus_alignment import (  # noqa: E402
    _read_csv,
    _read_json,
    preflight_corpus,
  )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
  from validate_external_corpus_alignment import _read_csv, _read_json, preflight_corpus  # noqa: E402
####


CJ_BENCHMARK_ID = 'CJ-UEJ-001'
EXTERNAL_OPERATOR_ID = 'operator.sample.canonical_jet_probe_lines'
INTERNAL_OPERATOR_ID = 'op.field.profile-probe'
FIELD_PRODUCT_ID = 'plume.field.local-state@1'


@dataclass(frozen=True)
class CJRunConfiguration:
  """Explicit adapter assumptions for the underdetermined source case."""

  gamma: float = 1.4
  ambient_pressure_Pa: float = 101325.0
  ambient_temperature_K: float = 300.0
  total_temperature_K: float = 300.0
  near_sonic_exit_mach: float = 1.000001
  max_cells: int = 1

  def __post_init__(self) -> None:
    for name in (
        'gamma',
        'ambient_pressure_Pa',
        'ambient_temperature_K',
        'total_temperature_K',
        'near_sonic_exit_mach',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
    ####
    if self.near_sonic_exit_mach <= 1.0:
      raise ValueError('near_sonic_exit_mach must be greater than one for the current exit contract')
    ####
    if isinstance(self.max_cells, bool) or self.max_cells < 1:
      raise ValueError('max_cells must be a positive integer')
    ####
  ####
####


@dataclass(frozen=True)
class _ZoneMatch:
  zone: Any | None
  reason: str | None
  match_count: int
####


def _point_on_segment(
    x: float,
    y: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> bool:
  dx = x2 - x1
  dy = y2 - y1
  cross = (x - x1) * dy - (y - y1) * dx
  scale = max(1.0, abs(dx), abs(dy), abs(x - x1), abs(y - y1))
  if abs(cross) > 1.0e-12 * scale:
    return False
  ####
  return (
    min(x1, x2) - 1.0e-12 <= x <= max(x1, x2) + 1.0e-12
    and min(y1, y2) - 1.0e-12 <= y <= max(y1, y2) + 1.0e-12
  )
####


def _strictly_contains(point: tuple[float, float], vertices: Any) -> bool:
  """Return true only for an unambiguous polygon interior point."""

  x, y = point
  inside = False
  count = len(vertices)
  for index in range(count):
    x1, y1 = (float(value) for value in vertices[index])
    x2, y2 = (float(value) for value in vertices[(index + 1) % count])
    if _point_on_segment(x, y, x1, y1, x2, y2):
      return False
    ####
    if (y1 > y) != (y2 > y):
      crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
      if x < crossing_x:
        inside = not inside
      ####
    ####
  ####
  return inside
####


def _contains_or_boundary(point: tuple[float, float], vertices: Any) -> bool:
  """Return true for polygon interior or boundary points."""

  x, y = point
  inside = False
  count = len(vertices)
  for index in range(count):
    x1, y1 = (float(value) for value in vertices[index])
    x2, y2 = (float(value) for value in vertices[(index + 1) % count])
    if _point_on_segment(x, y, x1, y1, x2, y2):
      return True
    ####
    if (y1 > y) != (y2 > y):
      crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
      if x < crossing_x:
        inside = not inside
      ####
    ####
  ####
  return inside
####


def _match_zone(result: ShockCellSolveResult, x_m: float, radius_m: float) -> _ZoneMatch:
  interior_matches = tuple(
    zone for zone in result.zones
    if _strictly_contains((x_m, radius_m), zone.vertices_xr_m)
  )
  if len(interior_matches) == 1:
    return _ZoneMatch(zone=interior_matches[0], reason=None, match_count=1)
  ####
  boundary_matches = tuple(
    zone for zone in result.zones
    if _contains_or_boundary((x_m, radius_m), zone.vertices_xr_m)
  )
  if len(boundary_matches) == 1:
    return _ZoneMatch(zone=boundary_matches[0], reason='boundary_selected', match_count=1)
  ####
  if not boundary_matches:
    return _ZoneMatch(zone=None, reason='outside_or_boundary_support', match_count=0)
  ####
  # The legacy construction commonly places the axis on more than one
  # closed-zone boundary.  A deterministic first-in-solver-order selection
  # keeps the diagnostic reproducible while recording that it is not a native
  # point-field partition.
  if abs(radius_m) <= 1.0e-12:
    return _ZoneMatch(
      zone=boundary_matches[0],
      reason='centerline_boundary_first_solver_zone',
      match_count=len(boundary_matches),
    )
  ####
  return _ZoneMatch(zone=None, reason='overlapping_support', match_count=len(boundary_matches))
####


def _float(row: Mapping[str, str], key: str) -> float:
  value = row.get(key)
  if value is None or value == '':
    raise ValueError(f'row is missing numeric field {key!r}')
  ####
  return float(value)
####


def _prediction(
    flow: FlowState,
    quantity: str,
    ambient_pressure_Pa: float,
) -> float:
  if quantity == 'static_pressure_ratio':
    return flow.static_pressure / ambient_pressure_Pa
  ####
  if quantity == 'axial_velocity':
    # The current ClosedZone state stores scalar speed, not a velocity vector.
    # The report labels this explicitly as an axial-speed proxy.
    return flow.speed_mps
  ####
  if quantity == 'mach_number':
    return flow.mach
  ####
  raise ValueError(f'unsupported validation quantity {quantity!r}')
####


def _sample_rows(
    rows: Iterable[Mapping[str, str]],
    *,
    result: ShockCellSolveResult,
    diameter_m: float,
    quantity: str,
    ambient_pressure_Pa: float,
    observed_key: str,
    uncertainty_key: str,
) -> tuple[list[dict[str, float]], dict[str, int]]:
  samples: list[dict[str, float]] = []
  skipped: dict[str, int] = defaultdict(int)
  for row in rows:
    x_over_D = _float(row, 'x_over_D')
    radius_over_D = _float(row, 'radial_position_y_over_D')
    match = _match_zone(result, x_over_D * diameter_m, radius_over_D * diameter_m)
    if match.zone is None:
      skipped[match.reason or 'unavailable'] += 1
      continue
    ####
    samples.append({
      'x_over_D': x_over_D,
      'observed': _float(row, observed_key),
      'predicted': _prediction(match.zone.flow, quantity, ambient_pressure_Pa),
      'uncertainty': max(0.0, _float(row, uncertainty_key)),
    })
  ####
  return samples, dict(sorted(skipped.items()))
####


def _score_samples(
    samples: Sequence[Mapping[str, float]],
    *,
    observed_count: int,
    skipped: Mapping[str, int],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
  observed = [float(sample['observed']) for sample in samples]
  predicted = [float(sample['predicted']) for sample in samples]
  residuals = [model - reference for model, reference in zip(predicted, observed, strict=True)]
  uncertainties = [float(sample['uncertainty']) for sample in samples]
  squared = sum(residual * residual for residual in residuals)
  rmse = sqrt(squared / len(residuals)) if residuals else None
  value_range = max(observed) - min(observed) if observed else 0.0
  nrmse = rmse / value_range if rmse is not None and value_range > 0.0 else None
  usable_uncertainties = [
    (residual, uncertainty)
    for residual, uncertainty in zip(residuals, uncertainties, strict=True)
    if uncertainty > 0.0
  ]
  standardized_rmse = (
    sqrt(sum((residual / uncertainty) ** 2 for residual, uncertainty in usable_uncertainties) / len(usable_uncertainties))
    if usable_uncertainties
    else None
  )
  coverage = len(samples) / observed_count if observed_count else 0.0
  return {
    **metadata,
    'observed_count': observed_count,
    'predicted_count': len(samples),
    'coverage_fraction': coverage,
    'skipped_rows': dict(skipped),
    'predicted_x_over_D_range': (
      [min(float(sample['x_over_D']) for sample in samples), max(float(sample['x_over_D']) for sample in samples)]
      if samples else None
    ),
    'metrics': {
      'rmse': rmse,
      'nrmse_by_observed_range': nrmse,
      'mean_absolute_error': (
        sum(abs(residual) for residual in residuals) / len(residuals)
        if residuals else None
      ),
      'maximum_absolute_error': max((abs(residual) for residual in residuals), default=None),
      'digitization_uncertainty_weighted_rmse': standardized_rmse,
    },
    'comparison_status': 'quantified-diagnostic' if samples else 'not-evaluated',
    'claim_status': 'not_accepted',
  }
####


def _local_extrema(samples: Sequence[Mapping[str, float]]) -> list[dict[str, float | str]]:
  ordered = sorted(samples, key=lambda sample: float(sample['x_over_D']))
  extrema: list[dict[str, float | str]] = []
  for index in range(1, len(ordered) - 1):
    previous = float(ordered[index - 1]['observed'])
    current = float(ordered[index]['observed'])
    following = float(ordered[index + 1]['observed'])
    if current > previous and current > following:
      kind = 'maximum'
    elif current < previous and current < following:
      kind = 'minimum'
    else:
      continue
    ####
    extrema.append({
      'kind': kind,
      'x_over_D': float(ordered[index]['x_over_D']),
      'value': current,
    })
  ####
  return extrema
####


def _feature_summary(
    observed_rows: Sequence[Mapping[str, str]],
    *,
    result: ShockCellSolveResult,
    diameter_m: float,
    ambient_pressure_Pa: float,
) -> dict[str, Any]:
  pressure_rows = [
    row for row in observed_rows
    if row.get('profile_id') == 'centerline' and row.get('observable') == 'static_pressure_ratio'
  ]
  observed_samples = [
    {
      'x_over_D': _float(row, 'x_over_D'),
      'observed': _float(row, 'value'),
    }
    for row in pressure_rows
  ]
  predicted_samples, skipped = _sample_rows(
    pressure_rows,
    result=result,
    diameter_m=diameter_m,
    quantity='static_pressure_ratio',
    ambient_pressure_Pa=ambient_pressure_Pa,
    observed_key='value',
    uncertainty_key='value_digitization_uncertainty',
  )
  # Re-label the predicted samples so the same feature detector can be used
  # without treating model values as source observations.
  predicted_feature_samples = [
    {
      'x_over_D': float(sample['x_over_D']),
      'observed': float(sample['predicted']),
    }
    for sample in predicted_samples
  ]
  observed_extrema = _local_extrema(observed_samples)
  predicted_extrema = _local_extrema(predicted_feature_samples)
  observed_spacing = [
    float(current['x_over_D']) - float(previous['x_over_D'])
    for previous, current in zip(observed_extrema, observed_extrema[1:])
  ]
  predicted_spacing = [
    float(current['x_over_D']) - float(previous['x_over_D'])
    for previous, current in zip(predicted_extrema, predicted_extrema[1:])
  ]
  enough_for_spacing = len(observed_extrema) >= 2 and len(predicted_extrema) >= 2
  return {
    'operator_id': EXTERNAL_OPERATOR_ID,
    'internal_operator_id': INTERNAL_OPERATOR_ID,
    'profile_id': 'centerline',
    'observable': 'static_pressure_ratio',
    'observed_extrema': observed_extrema,
    'predicted_extrema': predicted_extrema,
    'observed_extrema_spacing_over_D': observed_spacing,
    'predicted_extrema_spacing_over_D': predicted_spacing,
    'skipped_predicted_rows': skipped,
    'phase_and_spacing_status': 'quantified-diagnostic' if enough_for_spacing else 'insufficient-resolved-features',
    'claim_status': 'not_accepted',
    'limitations': [
      'The current solver exposes one bounded construction cell, not a finite physical shock train.',
      'A piecewise zone boundary is not promoted to a physical shock-cell center.',
    ],
  }
####


def _case_from_metadata(
    metadata: Mapping[str, Any],
    configuration: CJRunConfiguration,
) -> tuple[ShockCellSolveResult, dict[str, Any]]:
  case = metadata['case']
  diameter_m = float(case['exit_diameter_m'])
  gas = CaloricallyPerfectGas.dry_air(gamma=configuration.gamma)
  ambient = derive_ambient_state(
    AmbientInput(
      pressure_Pa=configuration.ambient_pressure_Pa,
      temperature_K=configuration.ambient_temperature_K,
    ),
    gas,
  )
  # CJ-UEJ supplies nozzle pressure ratio p0/pa and an ideally-expanded jet
  # Mach number.  The current provider's exit contract requires M>1, while
  # the convergent source is choked at M=1.  The near-sonic surrogate is an
  # explicit adapter assumption, never a source measurement.
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=configuration.near_sonic_exit_mach,
      total_pressure_Pa=ambient.pressure_Pa * float(case['nozzle_pressure_ratio']),
      total_temperature_K=configuration.total_temperature_K,
      exit_radius_m=diameter_m / 2.0,
    ),
    gas,
  )
  result = solve_shock_cells(
    ShockCellSolveConfig(
      exit=exit_state,
      ambient=ambient,
      max_cells=configuration.max_cells,
    )
  )
  model_case = {
    'exit_diameter_m': diameter_m,
    'exit_radius_m': diameter_m / 2.0,
    'source_ideally_expanded_jet_mach': float(case['ideally_expanded_jet_mach']),
    'source_nozzle_pressure_ratio_p0_over_pa': float(case['nozzle_pressure_ratio']),
    'adapter_exit_mach': configuration.near_sonic_exit_mach,
    'adapter_total_temperature_K': configuration.total_temperature_K,
    'adapter_gamma': configuration.gamma,
    'ambient_pressure_Pa': ambient.pressure_Pa,
    'ambient_temperature_K': ambient.temperature_K,
    'derived_exit_pressure_ratio_pe_over_pa': exit_state.static_pressure_Pa / ambient.pressure_Pa,
    'derived_exit_velocity_mps': exit_state.velocity_mps,
  }
  return result, model_case
####


def _typed_claim(archive_sha256: str, configuration: CJRunConfiguration) -> dict[str, Any]:
  registry = ValidationRegistry.from_alignment_directory(
    REPO_ROOT / 'docs' / 'coding_agent_handoff' / 'resync_v0.1.0a1' / 'alignment'
  )
  operator_ids = {operator.operator_id for operator in registry.operators}
  if INTERNAL_OPERATOR_ID not in operator_ids:
    raise ValueError(f'{INTERNAL_OPERATOR_ID!r} is missing from the committed operator registry')
  ####
  claim = ValidationClaim(
    claim_id='VAL-002-CJ-UEJ-LOCAL-FIELD-DIAGNOSTIC',
    benchmark_id=CJ_BENCHMARK_ID,
    product_id=FIELD_PRODUCT_ID,
    measurement_operator_id=INTERNAL_OPERATOR_ID,
    metric_id='metric.profile.nrmse',
    applicability_domain={
      'working_fluid': 'cold dry air',
      'model_lane': 'bounded first-cell component diagnostic',
      'coordinate': 'x/D and y/D probe lines',
    },
    evidence_level=EvidenceLevel.QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR,
    claim_role=ClaimRole.VALIDATION,
    uncertainty={
      'source_digitization': 'per-row corpus uncertainty fields',
      'model_input_assumptions': {
        'gamma': configuration.gamma,
        'total_temperature_K': configuration.total_temperature_K,
        'near_sonic_exit_mach': configuration.near_sonic_exit_mach,
      },
    },
    provenance={
      'corpus_archive_sha256': archive_sha256,
      'source_metadata_member': 'data/cj_uej_001_metadata.json',
      'solver_component': 'src/exhaust_plume/models/shock_cells/solve.py',
      'operator_registry': 'docs/coding_agent_handoff/resync_v0.1.0a1/alignment/measurement_operator_registry.csv',
    },
    limitations=(
      'The source does not publish a total-temperature boundary condition.',
      'The source is a convergent/choked cold jet while the current exit contract requires M>1.',
      'The current solver returns one bounded construction cell and uses a construction limit as termination.',
      'Axial velocity is compared through a scalar-speed proxy because the zone state has no velocity vector.',
      'This is supporting-component evidence and does not validate the visual product or a physical shock train.',
    ),
    status=ClaimStatus.PROPOSED,
  )
  return claim.model_dump(mode='json')
####


def _group_rows(rows: Sequence[Mapping[str, str]], keys: Sequence[str]) -> dict[tuple[str, ...], list[Mapping[str, str]]]:
  grouped: dict[tuple[str, ...], list[Mapping[str, str]]] = defaultdict(list)
  for row in rows:
    grouped[tuple(str(row.get(key, '')) for key in keys)].append(row)
  ####
  return dict(grouped)
####


def build_cj_uej_component_report(
    corpus_path: Path,
    *,
    configuration: CJRunConfiguration = CJRunConfiguration(),
) -> dict[str, Any]:
  """Build a reproducible, non-accepting component evidence record."""

  preflight = preflight_corpus(corpus_path)
  archive = {
    key: value for key, value in preflight.get('archive', {}).items()
    if key != 'path'
  }
  report: dict[str, Any] = {
    'report_id': 'exhaust-plume-cj-uej-component-validation-v1',
    'benchmark_id': CJ_BENCHMARK_ID,
    'archive': archive,
    'corpus_status': preflight.get('status'),
    'operator': {
      'external_operator_id': EXTERNAL_OPERATOR_ID,
      'internal_operator_id': INTERNAL_OPERATOR_ID,
      'crosswalk_status': 'semantic-match-reviewed-for-cj-uej-component-only',
      'crosswalk_scope': 'profile probe coordinates, source uncertainty, and disclosed averaging semantics only',
      'namespace_status': preflight.get('operator_reconciliation', {}).get('crosswalk_status'),
      'semantic_crosswalk_status': preflight.get('operator_reconciliation', {}).get('semantic_crosswalk_status'),
      'unreviewed_external_operator_count': len(
        preflight.get('operator_reconciliation', {}).get('unreviewed_external_only', [])
      ),
    },
    'validation_status': 'blocked-invalid-corpus',
    'claim_status': 'not_accepted',
    'release_ready': False,
  }
  if preflight.get('status') != 'preflight-valid-pending-release-gates':
    report['errors'] = list(preflight.get('errors', ()))
    return report
  ####

  with ZipFile(corpus_path) as archive_file:
    metadata = _read_json(archive_file, 'data/cj_uej_001_metadata.json')
    profile_rows = _read_csv(archive_file, 'data/cj_uej_001_profiles.csv')
    mach_rows = _read_csv(archive_file, 'data/cj_uej_001_mach_estimates.csv')
  ####
  result, model_case = _case_from_metadata(metadata, configuration)
  diameter_m = float(model_case['exit_diameter_m'])
  pressure_groups = _group_rows(profile_rows, ('profile_id', 'observable'))
  profile_results: list[dict[str, Any]] = []
  quantity_by_observable: dict[str, tuple[str, str, str]] = {
    'static_pressure_ratio': ('static_pressure_ratio', 'value', 'value_digitization_uncertainty'),
    'axial_velocity': ('axial_velocity', 'value', 'value_digitization_uncertainty'),
  }
  for (profile_id, observable), rows in sorted(pressure_groups.items()):
    if observable not in quantity_by_observable:
      continue
    ####
    quantity, observed_key, uncertainty_key = quantity_by_observable[observable]
    samples, skipped = _sample_rows(
      rows,
      result=result,
      diameter_m=diameter_m,
      quantity=quantity,
      ambient_pressure_Pa=configuration.ambient_pressure_Pa,
      observed_key=observed_key,
      uncertainty_key=uncertainty_key,
    )
    profile_results.append(_score_samples(
      samples,
      observed_count=len(rows),
      skipped=skipped,
      metadata={
        'profile_id': profile_id,
        'observable': observable,
        'quantity': 'axial_speed_proxy' if observable == 'axial_velocity' else quantity,
        'observed_unit': str(rows[0].get('unit', 'dimensionless')),
        'operator_id': EXTERNAL_OPERATOR_ID,
        'internal_operator_id': INTERNAL_OPERATOR_ID,
        'metric_ids': ['metric.profile.nrmse'],
      },
    ))
  ####
  mach_results: list[dict[str, Any]] = []
  for (profile_id, method), rows in sorted(_group_rows(mach_rows, ('profile_id', 'method')).items()):
    samples, skipped = _sample_rows(
      rows,
      result=result,
      diameter_m=diameter_m,
      quantity='mach_number',
      ambient_pressure_Pa=configuration.ambient_pressure_Pa,
      observed_key='mach_number',
      uncertainty_key='mach_digitization_uncertainty_abs',
    )
    mach_results.append(_score_samples(
      samples,
      observed_count=len(rows),
      skipped=skipped,
      metadata={
        'profile_id': profile_id,
        'method': method,
        'quantity': 'mach_number',
        'observed_unit': 'dimensionless',
        'operator_id': EXTERNAL_OPERATOR_ID,
        'internal_operator_id': INTERNAL_OPERATOR_ID,
        'metric_ids': ['metric.profile.nrmse'],
        'source_shift_variant': method == 'pressure_static_profile_shifted_downstream',
      },
    ))
  ####
  x_values = [
    float(zone.vertices_xr_m[:, 0].min()) / diameter_m
    for zone in result.zones
  ] + [
    float(zone.vertices_xr_m[:, 0].max()) / diameter_m
    for zone in result.zones
  ]
  report.update({
    'validation_status': 'partial_component_evidence',
    'claim_status': 'not_accepted',
    'claim': _typed_claim(str(archive['actual_sha256']), configuration),
    'case': model_case,
    'source_evidence_limits': list(metadata.get('evidence_limits', ())),
    'source_validation_role': metadata.get('validation_role'),
    'solver': {
      'component_id': 'exhaust_plume.models.shock_cells.solve_shock_cells',
      'requested_max_cells': configuration.max_cells,
      'status': result.status.value,
      'termination_reason': result.termination_reason.value,
      'cell_count': len(result.cells),
      'zone_count': len(result.zones),
      'construction_domain_x_over_D': [min(x_values), max(x_values)] if x_values else None,
      'solver_pressure_residual': result.pressure_residual,
    },
    'profile_results': profile_results,
    'mach_results': mach_results,
    'feature_summary': _feature_summary(
      profile_rows,
      result=result,
      diameter_m=diameter_m,
      ambient_pressure_Pa=configuration.ambient_pressure_Pa,
    ),
    'acceptance_blockers': [
      'The current public visual providers do not expose local-field channels or this component diagnostic as product output.',
      'The source does not disclose total temperature; velocity evidence is assumption-sensitive.',
      'The source is convergent/choked while the current exit-state contract requires a near-sonic M>1 adapter.',
      'Only one bounded construction cell is available; physical shock-cell phase and spacing are not resolved.',
      'Construction-limit termination is not physical plume termination.',
      'The component mapping is intentionally scoped to CJ-UEJ supporting evidence and does not authorize a primary VIS claim.',
    ],
  })
  return report
####


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', required=True, type=Path)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  report = build_cj_uej_component_report(args.corpus)
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if args.output is not None:
    args.output.write_text(serialized, encoding='utf-8')
  ####
  print(serialized, end='')
  return 0 if report['validation_status'] != 'blocked-invalid-corpus' else 1
####


if __name__ == '__main__':
  raise SystemExit(main())
####
