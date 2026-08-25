"""Record non-accepting evidence for the reduced-order shock-train lane.

The recovered CJ-UEJ archive is used for provenance and feature context.  It
does not contain a disjoint calibration/validation split for the empirical
train closure, so this command never promotes the reduced-order provider to an
externally validated product claim.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))

from exhaust_plume.models.shock_train import (  # noqa: E402
  ShockTrainCalibrationValidationSplit,
  ShockTrainCalibration,
  ShockTrainTerminationPolicy,
  propagate_shock_train_covariance,
  solve_shock_train,
  sweep_shock_train_parameter,
)
from exhaust_plume.validation import (  # noqa: E402
  SHOCK_TRAIN_PRESSURE_EXTREMA_SPACING_OPERATOR_ID,
  PressureExtremum,
  compare_shock_train_pressure_extrema_spacing,
)

try:
  from scripts.validate_cj_uej_component import (  # noqa: E402
    CJRunConfiguration,
    _case_from_metadata,
    _local_extrema,
    _read_csv,
    _read_json,
    preflight_corpus,
  )
except ModuleNotFoundError:  # pragma: no cover - direct script execution
  from validate_cj_uej_component import (  # noqa: E402
    CJRunConfiguration,
    _case_from_metadata,
    _local_extrema,
    _read_csv,
    _read_json,
    preflight_corpus,
  )


BENCHMARK_ID = 'CJ-UEJ-001'


def _calibration() -> ShockTrainCalibration:
  return ShockTrainCalibration(
    calibration_id='shock-train-engineering-seed-v1',
    source_description=(
      'engineering closure seed for solver-contract and sensitivity diagnostics; '
      'not fitted or accepted against the recovered corpus'
    ),
    applicable_mach_range=(1.0, 1.2),
    applicable_pressure_ratio_range=(1.0, 3.0),
    applicable_temperature_ratio_range=(0.5, 2.0),
    mixing_layer_growth_rate=0.01,
    pressure_amplitude_decay_coefficient=0.3,
    cell_spacing_coefficient=1.306,
    finite_shear_layer_spacing_correction=0.5,
    total_pressure_loss_coefficient=0.02,
    mean_pressure_relaxation_coefficient=0.2,
  )
####


def _policy(diameter_m: float) -> ShockTrainTerminationPolicy:
  return ShockTrainTerminationPolicy(
    max_cells=128,
    max_axial_distance_m=10.0 * diameter_m,
  )
####


def _train_metrics(
    result: Any,
    diameter_m: float,
    ambient_pressure_Pa: float,
) -> list[dict[str, Any]]:
  return [
    {
      'cell_index': cell.metrics.cell_index,
      'start_x_over_D': cell.metrics.start_x_m / diameter_m,
      'end_x_over_D': cell.metrics.end_x_m / diameter_m,
      'length_over_D': cell.metrics.length_m / diameter_m,
      'effective_core_diameter_over_D': cell.metrics.effective_core_diameter_m / diameter_m,
      'core_mach': cell.metrics.core_mach,
      'mean_pressure_ratio': cell.metrics.mean_pressure_Pa / ambient_pressure_Pa,
      'pressure_oscillation_ratio': cell.metrics.pressure_oscillation_ratio,
      'mean_pressure_residual': cell.metrics.mean_pressure_residual,
      'inlet_total_pressure_ratio': cell.metrics.inlet_total_pressure_Pa / ambient_pressure_Pa,
      'outlet_total_pressure_ratio': cell.metrics.outlet_total_pressure_Pa / ambient_pressure_Pa,
      'geometry_fidelity': cell.metrics.geometry_fidelity.value,
    }
    for cell in result.cells
  ]
####


def build_shock_train_component_report(corpus_path: Path) -> dict[str, Any]:
  preflight = preflight_corpus(corpus_path)
  archive = {
    key: value for key, value in preflight.get('archive', {}).items()
    if key != 'path'
  }
  report: dict[str, Any] = {
    'report_id': 'exhaust-plume-shock-train-component-validation-v1',
    'benchmark_id': BENCHMARK_ID,
    'archive': archive,
    'corpus_status': preflight.get('status'),
    'validation_status': 'blocked-invalid-corpus',
    'claim_status': 'not_accepted',
    'release_ready': False,
    'calibration_validation_split': ShockTrainCalibrationValidationSplit().as_report(
      reason='the recovered archive has not yet been verified',
    ),
  }
  if preflight.get('status') != 'preflight-valid-pending-release-gates':
    report['errors'] = list(preflight.get('errors', ()))
    return report

  with ZipFile(corpus_path) as archive_file:
    metadata = _read_json(archive_file, 'data/cj_uej_001_metadata.json')
    profile_rows = _read_csv(archive_file, 'data/cj_uej_001_profiles.csv')
  case = metadata['case']
  split = ShockTrainCalibrationValidationSplit(
    unassigned_case_ids=(BENCHMARK_ID,),
  )
  report['calibration_validation_split'] = split.as_report(
    reason=(
      'the recovered archive provides one gasdynamic precursor case, not a '
      'disjoint closure calibration/validation split'
    ),
  )
  diameter_m = float(case['exit_diameter_m'])
  first_cell, model_case = _case_from_metadata(
    metadata,
    CJRunConfiguration(max_cells=1),
  )
  calibration = _calibration()
  policy = _policy(diameter_m)
  result = solve_shock_train(first_cell, calibration, policy)
  uncertainty_propagation = propagate_shock_train_covariance(
    first_cell,
    calibration,
    policy,
  )
  pressure_rows = [
    {
      'x_over_D': float(row['x_over_D']),
      'observed': float(row['value']),
      'x_digitization_uncertainty_over_D': float(
        row['x_digitization_uncertainty_over_D']
      ),
    }
    for row in profile_rows
    if row.get('profile_id') == 'centerline' and row.get('observable') == 'static_pressure_ratio'
  ]
  observed_extrema = _local_extrema(pressure_rows)
  x_uncertainty_by_position = {
    float(row['x_over_D']): float(row['x_digitization_uncertainty_over_D'])
    for row in pressure_rows
  }
  observed_pressure_extrema = tuple(
    PressureExtremum(
      kind=str(extremum['kind']),
      x_over_D=float(extremum['x_over_D']),
      x_uncertainty_over_D=x_uncertainty_by_position.get(
        float(extremum['x_over_D'])
      ),
    )
    for extremum in observed_extrema
  )
  phase_spacing_comparisons = {
    phase_kind: compare_shock_train_pressure_extrema_spacing(
      tuple(cell.metrics.length_m for cell in result.cells),
      diameter_m,
      observed_pressure_extrema,
      phase_kind=phase_kind,
    ).as_report()
    for phase_kind in ('minimum', 'maximum')
  }
  observed_spacing = [
    float(current['x_over_D']) - float(previous['x_over_D'])
    for previous, current in zip(observed_extrema, observed_extrema[1:])
  ]
  sensitivity = sweep_shock_train_parameter(
    first_cell,
    calibration,
    policy,
    parameter_name='mixing_layer_growth_rate',
    values=(0.0, calibration.mixing_layer_growth_rate, 2.0 * calibration.mixing_layer_growth_rate),
  )
  report.update({
    'validation_status': 'partial_component_evidence',
    'claim_status': 'not_accepted',
    'case': model_case,
    'solver': {
      'component_id': 'exhaust_plume.models.shock_train.solve_shock_train',
      'status': result.status.value,
      'termination_reason': result.termination_reason.value,
      'termination_is_physical': result.termination.is_physical,
      'was_domain_truncated': result.was_domain_truncated,
      'cell_count': result.cell_count,
      'shock_train_end_x_over_D': (
        result.shock_train_end_x_m / diameter_m
        if result.shock_train_end_x_m is not None else None
      ),
      'supersonic_core_end_x_over_D': (
        result.supersonic_core_end_x_m / diameter_m
        if result.supersonic_core_end_x_m is not None else None
      ),
      'calibration_id': result.calibration_id,
      'uncertainty': dict(result.uncertainty),
      'uncertainty_propagation': uncertainty_propagation,
      'diagnostics': dict(result.diagnostics),
      'cells': _train_metrics(
        result,
        diameter_m,
        float(model_case['ambient_pressure_Pa']),
      ),
    },
    'observed_pressure_feature_context': {
      'operator_id': 'operator.sample.canonical_jet_probe_lines',
      'profile_id': 'centerline',
      'observed_extrema': observed_extrema,
      'observed_extrema_spacing_over_D': observed_spacing,
      'comparison_status': (
        'diagnostic-only; same-phase pressure-extrema spacing does not '
        'identify reduced-order train cells'
      ),
      'measurement_operator': {
        'operator_id': SHOCK_TRAIN_PRESSURE_EXTREMA_SPACING_OPERATOR_ID,
        'status': 'diagnostic-only',
        'claim_status': 'not_accepted',
        'phase_comparisons': phase_spacing_comparisons,
      },
      'claim_status': 'not_accepted',
    },
    'sensitivity': [
      {
        'parameter_name': point.parameter_name,
        'parameter_value': point.parameter_value,
        'status': point.status.value,
        'termination_reason': point.termination_reason,
        'cell_count': point.cell_count,
        'shock_train_end_x_over_D': (
          point.shock_train_end_x_m / diameter_m
          if point.shock_train_end_x_m is not None else None
        ),
        'pressure_amplitude_final': point.pressure_amplitude_final,
      }
      for point in sensitivity
    ],
    'acceptance_blockers': [
      'No disjoint calibration and validation cases are present for the closure coefficients.',
      'The source is convergent/choked while the current first-cell contract uses an explicit near-sonic M>1 adapter.',
      'The pressure-extrema spacing operator is diagnostic-only; it does not identify reduced-order cell centers, and no independent calibration/validation split is available.',
      'The engineering seed supplies no calibrated parameter covariance; output uncertainty propagation is available only when a covariance-bearing calibration artifact is supplied.',
      'The provider advertises visual geometry only and cannot promote this evidence to signature, ray, or FPA claims.',
    ],
  })
  return report
####


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', required=True, type=Path)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  report = build_shock_train_component_report(args.corpus)
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if args.output is not None:
    args.output.write_text(serialized, encoding='utf-8')
  print(serialized, end='')
  return 0 if report['validation_status'] != 'blocked-invalid-corpus' else 1


if __name__ == '__main__':
  raise SystemExit(main())
