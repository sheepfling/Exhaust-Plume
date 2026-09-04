"""Quantify the planar-MOC component against the recovered CJ-UEJ trace.

The comparison is intentionally a supporting component diagnostic.  CJ-UEJ is
a cold convergent/choked air jet, while the current MOC foundation requires a
supersonic exit state and stops at an open reflected characteristic lattice.
The adapter, measurement operator, partial coverage, and uncertainty-weighted
residual are therefore recorded explicitly and never promoted to a product or
physical first-cell claim.
"""

from __future__ import annotations

import argparse
from bisect import bisect_left
from dataclasses import dataclass
import json
from math import cos, isfinite, sqrt
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence
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
from exhaust_plume.models.moc import (  # noqa: E402
  MocReflectedBoundaryResult,
  MocReflectedCharacteristicZoneResult,
  MocExpansionFanResult,
  assemble_reflected_characteristic_zone,
  solve_reflected_free_boundary,
  solve_underexpanded_expansion_fan,
)
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
MACH_METHOD = 'ldv_total_temperature_assumption'


@dataclass(frozen=True)
class MocCJRunConfiguration:
  """Explicit adapter assumptions for the underdetermined cold-jet case."""

  gamma: float = 1.4
  ambient_pressure_Pa: float = 101325.0
  ambient_temperature_K: float = 300.0
  total_temperature_K: float = 300.0
  near_sonic_exit_mach: float = 1.000001
  characteristic_count: int = 64
  refinement_counts: tuple[int, ...] = (16, 32, 64)

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
    if self.gamma <= 1.0:
      raise ValueError('gamma must be greater than one')
    ####
    if self.near_sonic_exit_mach <= 1.0:
      raise ValueError('near_sonic_exit_mach must be greater than one')
    ####
    if (
      isinstance(self.characteristic_count, bool)
      or not isinstance(self.characteristic_count, int)
      or self.characteristic_count < 2
    ):
      raise ValueError('characteristic_count must be an integer of at least two')
    ####
    if not self.refinement_counts or any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 2
        for value in self.refinement_counts
    ):
      raise ValueError('refinement_counts must contain integers of at least two')
    ####
  ####
####


def _score_samples(
    samples: Sequence[Mapping[str, float]],
    *,
    observed_count: int,
    skipped: Mapping[str, int],
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
  """Return explicit profile metrics without turning them into a claim."""

  observed = [float(sample['observed']) for sample in samples]
  predicted = [float(sample['predicted']) for sample in samples]
  residuals = [model - reference for model, reference in zip(predicted, observed, strict=True)]
  uncertainties = [float(sample['uncertainty']) for sample in samples]
  squared = sum(residual * residual for residual in residuals)
  rmse = sqrt(squared / len(residuals)) if residuals else None
  value_range = max(observed) - min(observed) if observed else 0.0
  standardized = [
    residual / uncertainty
    for residual, uncertainty in zip(residuals, uncertainties, strict=True)
    if uncertainty > 0.0
  ]
  return {
    **metadata,
    'observed_count': observed_count,
    'predicted_count': len(samples),
    'coverage_fraction': len(samples) / observed_count if observed_count else 0.0,
    'skipped_rows': dict(sorted(skipped.items())),
    'predicted_x_over_D_range': (
      [
        min(float(sample['x_over_D']) for sample in samples),
        max(float(sample['x_over_D']) for sample in samples),
      ]
      if samples else None
    ),
    'metrics': {
      'rmse': rmse,
      'nrmse_by_observed_range': (
        rmse / value_range if rmse is not None and value_range > 0.0 else None
      ),
      'mean_absolute_error': (
        sum(abs(residual) for residual in residuals) / len(residuals)
        if residuals else None
      ),
      'maximum_absolute_error': max((abs(residual) for residual in residuals), default=None),
      'digitization_uncertainty_weighted_rmse': (
        sqrt(sum(value * value for value in standardized) / len(standardized))
        if standardized else None
      ),
    },
    'comparison_status': 'quantified-diagnostic' if samples else 'not-evaluated',
    'claim_status': 'not_accepted',
  }
####


def _sample_centerline_mach(
    rows: Sequence[Mapping[str, str]],
    *,
    model_x_over_D: Sequence[float],
    model_mach: Sequence[float],
) -> tuple[list[dict[str, float]], dict[str, int]]:
  """Sample the open-MOC centerline without extrapolating beyond its support."""

  if len(model_x_over_D) != len(model_mach) or len(model_x_over_D) < 2:
    raise ValueError('the MOC centerline requires matching arrays with at least two points')
  ####
  if any(right <= left for left, right in zip(model_x_over_D, model_x_over_D[1:])):
    raise ValueError('the MOC centerline x/D support must be strictly increasing')
  ####
  samples: list[dict[str, float]] = []
  skipped: dict[str, int] = {}
  for row in rows:
    x_over_D = float(row['x_over_D'])
    if x_over_D < model_x_over_D[0] or x_over_D > model_x_over_D[-1]:
      skipped['outside_open_moc_support'] = skipped.get('outside_open_moc_support', 0) + 1
      continue
    ####
    upper = bisect_left(model_x_over_D, x_over_D)
    if upper == 0:
      predicted = float(model_mach[0])
    elif upper == len(model_x_over_D):
      predicted = float(model_mach[-1])
    elif model_x_over_D[upper] == x_over_D:
      predicted = float(model_mach[upper])
    else:
      lower = upper - 1
      fraction = (
        (x_over_D - model_x_over_D[lower])
        / (model_x_over_D[upper] - model_x_over_D[lower])
      )
      predicted = float(model_mach[lower]) + fraction * (
        float(model_mach[upper]) - float(model_mach[lower])
      )
    ####
    samples.append({
      'x_over_D': x_over_D,
      'observed': float(row['mach_number']),
      'predicted': predicted,
      'uncertainty': max(0.0, float(row['mach_digitization_uncertainty_abs'])),
    })
  ####
  return samples, skipped
####


def _sample_moc_profile(
  rows: Sequence[Mapping[str, str]],
  *,
  zone: MocReflectedCharacteristicZoneResult,
  diameter_m: float,
  quantity: str,
  ambient_pressure_Pa: float,
  gas: CaloricallyPerfectGas,
  total_temperature_K: float,
) -> tuple[list[dict[str, float]], dict[str, int]]:
  """Sample a disclosed profile inside the bounded reflected-MOC field.

  The sampler is deliberately domain-bounded.  Static pressure uses the
  zone's carried total-pressure lineage, while axial velocity uses the
  explicitly disclosed constant-gamma total-temperature assumption.  The
  latter is a model-derived axial-speed prediction, not a reinterpretation of
  the source's Pitot-pressure observable.
  """

  if quantity not in {'static_pressure_ratio', 'axial_velocity'}:
    raise ValueError(f'unsupported MOC profile quantity {quantity!r}')
  ####
  if not isfinite(float(diameter_m)) or diameter_m <= 0.0:
    raise ValueError('diameter_m must be finite and positive')
  ####
  if not isfinite(float(ambient_pressure_Pa)) or ambient_pressure_Pa <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  ####
  if not isfinite(float(total_temperature_K)) or total_temperature_K <= 0.0:
    raise ValueError('total_temperature_K must be finite and positive')
  ####
  samples: list[dict[str, float]] = []
  skipped: dict[str, int] = {}
  for row in rows:
    x_over_D = float(row['x_over_D'])
    radial_position_y_over_D = float(row['radial_position_y_over_D'])
    point_m = (
      x_over_D * diameter_m,
      radial_position_y_over_D * diameter_m,
    )
    state = zone.state_at(point_m)
    if state is None:
      skipped['outside_open_moc_support'] = skipped.get('outside_open_moc_support', 0) + 1
      continue
    ####
    if quantity == 'static_pressure_ratio':
      pressure = zone.static_pressure_at(point_m)
      if pressure is None or not isfinite(float(pressure)) or pressure <= 0.0:
        skipped['missing_total_pressure_lineage'] = skipped.get('missing_total_pressure_lineage', 0) + 1
        continue
      ####
      predicted = pressure / ambient_pressure_Pa
    else:
      static_temperature = gas.static_temperature_from_total(
        state.mach,
        total_temperature_K,
      )
      predicted = gas.velocity_mps(state.mach, static_temperature) * cos(state.theta_rad)
    ####
    if not isfinite(float(predicted)):
      skipped['nonfinite_prediction'] = skipped.get('nonfinite_prediction', 0) + 1
      continue
    ####
    samples.append({
      'x_over_D': x_over_D,
      'radial_position_y_over_D': radial_position_y_over_D,
      'observed': float(row['value']),
      'predicted': float(predicted),
      'uncertainty': max(0.0, float(row['value_digitization_uncertainty'])),
    })
  ####
  return samples, skipped
####


def _group_profile_rows(
  rows: Sequence[Mapping[str, str]],
) -> dict[tuple[str, str], list[Mapping[str, str]]]:
  """Group profile observations by their declared line and observable."""

  grouped: dict[tuple[str, str], list[Mapping[str, str]]] = {}
  for row in rows:
    key = (str(row.get('profile_id', '')), str(row.get('observable', '')))
    grouped.setdefault(key, []).append(row)
  ####
  return grouped
####


def _case_from_metadata(
    metadata: Mapping[str, Any],
    configuration: MocCJRunConfiguration,
    *,
    characteristic_count: int | None = None,
) -> tuple[
  MocExpansionFanResult,
  MocReflectedBoundaryResult,
  MocReflectedCharacteristicZoneResult,
  dict[str, Any],
]:
  case = metadata['case']
  diameter_m = float(case['exit_diameter_m'])
  count = configuration.characteristic_count if characteristic_count is None else characteristic_count
  gas = CaloricallyPerfectGas.dry_air(gamma=configuration.gamma)
  ambient = derive_ambient_state(
    AmbientInput(
      pressure_Pa=configuration.ambient_pressure_Pa,
      temperature_K=configuration.ambient_temperature_K,
    ),
    gas,
  )
  # The source is convergent/choked at M=1. The explicit near-sonic adapter is
  # required only because CharacteristicState intentionally excludes M <= 1.
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=configuration.near_sonic_exit_mach,
      total_pressure_Pa=ambient.pressure_Pa * float(case['nozzle_pressure_ratio']),
      total_temperature_K=configuration.total_temperature_K,
      exit_radius_m=diameter_m / 2.0,
    ),
    gas,
  )
  fan = solve_underexpanded_expansion_fan(
    exit_state,
    ambient,
    characteristic_count=count,
  )
  boundary = solve_reflected_free_boundary(fan, exit_state, ambient)
  zone = assemble_reflected_characteristic_zone(
    fan,
    boundary,
    total_pressure_Pa=exit_state.total_pressure_Pa,
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
    'characteristic_count': count,
  }
  return fan, boundary, zone, model_case
####


def _solver_summary(
    fan: MocExpansionFanResult,
    boundary: MocReflectedBoundaryResult,
    zone: MocReflectedCharacteristicZoneResult,
    *,
    diameter_m: float,
) -> dict[str, Any]:
  model_points = [
    (state.x_m / diameter_m, state.mach)
    for state in boundary.centerline_states
  ]
  open_extent = max(
    (point[0] / diameter_m for point in boundary.boundary_points_m),
    default=None,
  )
  return {
    'component_id': 'exhaust_plume.models.moc.solve_reflected_free_boundary',
    'fan_status': fan.status.value,
    'reflected_boundary_status': boundary.status.value,
    'zone_status': zone.status.value,
    'characteristic_count': zone.characteristic_count,
    'node_count': zone.node_count,
    'cell_count': zone.cell_count,
    'centerline_support_x_over_D': (
      [model_points[0][0], model_points[-1][0]] if model_points else None
    ),
    'centerline_support_mach': (
      [model_points[0][1], model_points[-1][1]] if model_points else None
    ),
    'open_boundary_extent_x_over_D': open_extent,
    'maximum_boundary_radius_over_D': (
      max(point[1] / diameter_m for point in boundary.boundary_points_m)
      if boundary.boundary_points_m else None
    ),
    'total_pressure_Pa': zone.total_pressure_Pa,
    'maximum_pressure_residual': max(
      (abs(point.pressure_residual or 0.0) for point in boundary.point_results),
      default=None,
    ),
    'maximum_tangent_residual': max(
      (abs(point.tangent_residual or 0.0) for point in boundary.point_results),
      default=None,
    ),
    'physical_closure_status': zone.physical_closure_status,
    'shock_closure_status': zone.shock_closure_status,
    'model_centerline_points': [
      {'x_over_D': x_over_D, 'mach_number': mach}
      for x_over_D, mach in model_points
    ],
  }
####


def _refinement_report(
    metadata: Mapping[str, Any],
    configuration: MocCJRunConfiguration,
) -> dict[str, Any]:
  records: list[dict[str, Any]] = []
  for count in configuration.refinement_counts:
    fan, boundary, zone, case = _case_from_metadata(
      metadata,
      configuration,
      characteristic_count=count,
    )
    summary = _solver_summary(
      fan,
      boundary,
      zone,
      diameter_m=float(case['exit_diameter_m']),
    )
    records.append({
      'characteristic_count': count,
      'status': zone.status.value,
      'centerline_endpoint_x_over_D': (
        summary['centerline_support_x_over_D'][1]
        if summary['centerline_support_x_over_D'] is not None else None
      ),
      'open_boundary_extent_x_over_D': summary['open_boundary_extent_x_over_D'],
      'maximum_boundary_radius_over_D': summary['maximum_boundary_radius_over_D'],
      'node_count': summary['node_count'],
      'cell_count': summary['cell_count'],
      'physical_closure_status': summary['physical_closure_status'],
      'shock_closure_status': summary['shock_closure_status'],
    })
  ####
  return {
    'status': 'diagnostic-open-lattice-only',
    'characteristic_counts': list(configuration.refinement_counts),
    'cases': records,
    'acceptance_note': (
      'Refinement metrics describe the open fan/reflected boundary construction; '
      'they are not convergence evidence for a physical first-cell length.'
    ),
  }
####


def _typed_claim(archive_sha256: str, configuration: MocCJRunConfiguration) -> dict[str, Any]:
  registry = ValidationRegistry.from_alignment_directory(
    REPO_ROOT / 'docs' / 'coding_agent_handoff' / 'resync_v0.1.0a1' / 'alignment'
  )
  operator_ids = {operator.operator_id for operator in registry.operators}
  if INTERNAL_OPERATOR_ID not in operator_ids:
    raise ValueError(f'{INTERNAL_OPERATOR_ID!r} is missing from the committed operator registry')
  ####
  claim = ValidationClaim(
    claim_id='VAL-003-CJ-UEJ-MOC-CENTERLINE-MACH-DIAGNOSTIC',
    benchmark_id=CJ_BENCHMARK_ID,
    product_id=FIELD_PRODUCT_ID,
    measurement_operator_id=INTERNAL_OPERATOR_ID,
    metric_id='metric.profile.nrmse',
    applicability_domain={
      'working_fluid': 'cold dry air',
      'model_lane': 'open planar-MOC component diagnostic',
      'coordinate': 'centerline x/D probe line',
    },
    evidence_level=EvidenceLevel.QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR,
    claim_role=ClaimRole.VALIDATION,
    uncertainty={
      'source_digitization': 'per-row Mach digitization uncertainty',
      'model_input_assumptions': {
        'gamma': configuration.gamma,
        'total_temperature_K': configuration.total_temperature_K,
        'near_sonic_exit_mach': configuration.near_sonic_exit_mach,
      },
    },
    provenance={
      'corpus_archive_sha256': archive_sha256,
      'source_metadata_member': 'data/cj_uej_001_metadata.json',
      'source_observation_member': 'data/cj_uej_001_mach_estimates.csv',
      'solver_component': 'src/exhaust_plume/models/moc/',
      'operator_registry': 'docs/coding_agent_handoff/resync_v0.1.0a1/alignment/measurement_operator_registry.csv',
    },
    limitations=(
      'The source is a convergent/choked cold jet while the MOC state contract requires M > 1.',
      'The near-sonic exit Mach and total temperature are explicit adapter assumptions, not source measurements.',
      'The comparison covers only the open reflected-MOC support and does not include a physical shock closure.',
      'The published Mach trace is author-derived from LDV/pressure evidence rather than a direct Mach probe.',
      'This is supporting component evidence and does not validate VIS, a finite shock train, or a public provider.',
    ),
    status=ClaimStatus.PROPOSED,
  )
  return claim.model_dump(mode='json')
####


def build_moc_cj_uej_component_report(
    corpus_path: Path,
    *,
    configuration: MocCJRunConfiguration = MocCJRunConfiguration(),
) -> dict[str, Any]:
  """Build a reproducible, non-accepting MOC component evidence record."""

  preflight = preflight_corpus(corpus_path)
  archive = {
    key: value for key, value in preflight.get('archive', {}).items()
    if key != 'path'
  }
  report: dict[str, Any] = {
    'report_id': 'exhaust-plume-cj-uej-moc-component-validation-v1',
    'benchmark_id': CJ_BENCHMARK_ID,
    'model_fidelity': 'planar-moc-open-fan-reflected-boundary',
    'archive': archive,
    'corpus_status': preflight.get('status'),
    'operator': {
      'external_operator_id': EXTERNAL_OPERATOR_ID,
      'internal_operator_id': INTERNAL_OPERATOR_ID,
      'crosswalk_status': 'semantic-match-reviewed-for-cj-uej-component-only',
      'crosswalk_scope': 'centerline x/D sampling, source uncertainty, and published Mach semantics only',
      'supplemental_crosswalk_scope': (
        'centerline and off-axis x/D profile coordinates for static-pressure '
        'ratio and axial-velocity diagnostics'
      ),
      'namespace_status': preflight.get('operator_reconciliation', {}).get('crosswalk_status'),
      'semantic_crosswalk_status': preflight.get('operator_reconciliation', {}).get('semantic_crosswalk_status'),
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
    mach_rows = _read_csv(archive_file, 'data/cj_uej_001_mach_estimates.csv')
    profile_rows = _read_csv(archive_file, 'data/cj_uej_001_profiles.csv')
  ####
  fan, boundary, zone, model_case = _case_from_metadata(metadata, configuration)
  solver = _solver_summary(
    fan,
    boundary,
    zone,
    diameter_m=float(model_case['exit_diameter_m']),
  )
  if not fan.converged or not boundary.converged or not zone.converged:
    report.update({
      'validation_status': 'moc-foundation-failed',
      'errors': [
        f'fan status: {fan.status.value}',
        f'reflected boundary status: {boundary.status.value}',
        f'characteristic zone status: {zone.status.value}',
      ],
      'case': model_case,
      'solver': solver,
    })
    return report
  ####
  observed_rows = [
    row for row in mach_rows
    if row.get('profile_id') == 'centerline' and row.get('method') == MACH_METHOD
  ]
  model_x_over_D = [point['x_over_D'] for point in solver['model_centerline_points']]
  model_mach = [point['mach_number'] for point in solver['model_centerline_points']]
  samples, skipped = _sample_centerline_mach(
    observed_rows,
    model_x_over_D=model_x_over_D,
    model_mach=model_mach,
  )
  comparison = _score_samples(
    samples,
    observed_count=len(observed_rows),
    skipped=skipped,
    metadata={
      'profile_id': 'centerline',
      'method': MACH_METHOD,
      'quantity': 'mach_number',
      'observed_unit': 'dimensionless',
      'operator_id': EXTERNAL_OPERATOR_ID,
      'internal_operator_id': INTERNAL_OPERATOR_ID,
      'metric_ids': ['metric.profile.nrmse'],
      'source_shift_variant': False,
    },
  )
  gas = CaloricallyPerfectGas.dry_air(gamma=configuration.gamma)
  supplemental_profile_comparisons: list[dict[str, Any]] = []
  for (profile_id, observable), rows in sorted(
    _group_profile_rows(profile_rows).items()
  ):
    if observable not in {'static_pressure_ratio', 'axial_velocity'}:
      continue
    ####
    profile_samples, profile_skipped = _sample_moc_profile(
      rows,
      zone=zone,
      diameter_m=float(model_case['exit_diameter_m']),
      quantity=observable,
      ambient_pressure_Pa=configuration.ambient_pressure_Pa,
      gas=gas,
      total_temperature_K=configuration.total_temperature_K,
    )
    supplemental_profile_comparisons.append(
      _score_samples(
        profile_samples,
        observed_count=len(rows),
        skipped=profile_skipped,
        metadata={
          'profile_id': profile_id,
          'observable': observable,
          'quantity': observable,
          'observed_unit': rows[0].get('unit'),
          'operator_id': EXTERNAL_OPERATOR_ID,
          'internal_operator_id': INTERNAL_OPERATOR_ID,
          'metric_ids': ['metric.profile.nrmse'],
          'model_method': (
            'isentropic-static-pressure-from-carried-total-pressure'
            if observable == 'static_pressure_ratio'
            else 'isentropic-axial-speed-from-total-temperature-assumption'
          ),
          'source_shift_variant': False,
          'claim_status': 'not_accepted_supplemental_diagnostic',
        },
      )
    )
  ####
  report.update({
    'validation_status': 'partial_component_evidence',
    'claim_status': 'not_accepted',
    'claim': _typed_claim(str(archive['actual_sha256']), configuration),
    'case': model_case,
    'source_evidence_limits': list(metadata.get('evidence_limits', ())),
    'source_validation_role': metadata.get('validation_role'),
    'solver': solver,
    'refinement': _refinement_report(metadata, configuration),
    'comparison': comparison,
    'supplemental_profile_comparisons': {
      'status': 'quantified-supplemental-diagnostic',
      'claim_status': 'not_accepted',
      'operator_id': EXTERNAL_OPERATOR_ID,
      'internal_operator_id': INTERNAL_OPERATOR_ID,
      'provenance': {
        'corpus_archive_sha256': archive['actual_sha256'],
        'source_observation_member': 'data/cj_uej_001_profiles.csv',
        'solver_component': 'src/exhaust_plume/models/moc/',
      },
      'model_assumptions': {
        'gamma': configuration.gamma,
        'total_temperature_K': configuration.total_temperature_K,
        'total_pressure_source': 'near-sonic adapter exit total pressure',
      },
      'scope': (
        'static-pressure-ratio and axial-velocity profiles sampled only '
        'inside the bounded open reflected-MOC field'
      ),
      'cases': supplemental_profile_comparisons,
    },
    'acceptance_blockers': [
      'The source is convergent/choked while the MOC exit-state contract requires an explicit near-sonic M > 1 adapter.',
      'The source does not publish total temperature; the adapter temperature and resulting velocity field are assumptions.',
      'The open reflected characteristic lattice has no physical compression/shock closure or post-shock continuation.',
      'The centerline Mach comparison remains the only proposed MOC claim; supplemental static-pressure and axial-velocity profile comparisons are diagnostic only and do not establish shock-cell phase.',
      'The recovered corpus contains one benchmark case, so no disjoint calibration/validation split is available.',
      'The component diagnostic does not authorize a public MOC provider or a primary VIS claim.',
    ],
  })
  return report
####


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', required=True, type=Path)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  report = build_moc_cj_uej_component_report(args.corpus)
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
