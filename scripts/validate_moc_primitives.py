"""Run the standalone planar-MOC primitive evidence gate."""

from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))

from exhaust_plume.models.moc import (  # noqa: E402
  CharacteristicFamily,
  CharacteristicState,
  MocTopologyStatus,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
  prandtl_meyer_angle_rad,
  solve_attached_compression_to_pressure,
  solve_underexpanded_expansion_fan,
  validate_moc_mesh,
)
from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput  # noqa: E402
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit  # noqa: E402


def build_moc_primitive_report() -> dict[str, Any]:
  cases = [
    (gamma, mach)
    for gamma in (1.2, 1.4, 1.67)
    for mach in (1.000001, 1.2, 2.0, 5.0, 25.0)
  ]
  round_trip_residuals: list[float] = []
  round_trip_failures: list[dict[str, Any]] = []
  for gamma, mach in cases:
    angle = prandtl_meyer_angle_rad(mach, gamma)
    result = inverse_prandtl_meyer_angle_rad(angle, gamma)
    residual = abs(result.residual) if result.residual is not None else float('inf')
    round_trip_residuals.append(residual)
    if result.status is not MocPrimitiveStatus.CONVERGED or result.value is None:
      round_trip_failures.append({
        'gamma': gamma,
        'mach': mach,
        'status': result.status.value,
        'message': result.message,
      })
  ####
  plus_source = CharacteristicState(
    x_m=0.0,
    y_m=-0.15,
    theta_rad=-0.02,
    mach=2.0,
    gamma=1.4,
  )
  minus_source = CharacteristicState(
    x_m=0.0,
    y_m=0.15,
    theta_rad=0.02,
    mach=2.0,
    gamma=1.4,
  )
  interior = interior_characteristic_point(plus_source, minus_source)
  centerline = centerline_characteristic_point(
    minus_source,
    CharacteristicFamily.MINUS,
  )
  gas = CaloricallyPerfectGas.dry_air()
  fan_exit = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=2.0e6,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  fan_ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )
  fan = solve_underexpanded_expansion_fan(
    fan_exit,
    fan_ambient,
    characteristic_count=8,
  )
  fan_topology = validate_moc_mesh(fan.cells)
  compression = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=180000.0,
  )
  geometry_results = {
    'interior': {
      'status': interior.status.value,
      'invariant_residual_plus': interior.invariant_residual_plus,
      'invariant_residual_minus': interior.invariant_residual_minus,
      'geometry_residual': interior.geometry_residual,
      'point_m': interior.point_m,
    },
    'centerline': {
      'status': centerline.status.value,
      'invariant_residual_minus': centerline.invariant_residual_minus,
      'geometry_residual': centerline.geometry_residual,
      'point_m': centerline.point_m,
    },
    'underexpanded_fan_foundation': {
      'status': fan.status.value,
      'cell_count': len(fan.cells),
      'centerline_point_count': len(fan.centerline_points_m),
      'terminal_pressure_residual': fan.terminal_pressure_residual,
      'terminal_turn_rad': fan.terminal_turn_rad,
      'closure_status': 'open',
      'topology_status': fan_topology.status.value,
      'boundary_edge_count': fan_topology.boundary_edge_count,
      'boundary_component_count': fan_topology.boundary_component_count,
      'forms_closed_zone': fan_topology.forms_closed_zone,
    },
    'attached_compression_foundation': {
      'status': compression.status.value,
      'shock_status': compression.shock_status.value,
      'pressure_residual': compression.pressure_residual,
      'theta_rad': compression.theta_rad,
      'beta_rad': compression.beta_rad,
      'downstream_mach': compression.downstream_mach,
    },
  }
  failures = [
    *round_trip_failures,
    *([
      {
        'case': 'interior',
        'status': interior.status.value,
        'message': interior.message,
      }
    ] if not interior.converged else []),
    *([
      {
        'case': 'centerline',
        'status': centerline.status.value,
        'message': centerline.message,
      }
    ] if not centerline.converged else []),
    *([
      {
        'case': 'underexpanded_fan_foundation',
        'status': fan.status.value,
        'message': fan.message,
      }
    ] if not fan.converged else []),
    *([
      {
        'case': 'fan_topology',
        'status': fan_topology.status.value,
        'message': fan_topology.message,
      }
    ] if (
      fan_topology.status is not MocTopologyStatus.OPEN
      or not fan_topology.forms_closed_zone
      or fan_topology.nonmanifold_edge_count
    ) else []),
    *([
      {
        'case': 'attached_compression_foundation',
        'status': compression.status.value,
        'message': compression.message,
      }
    ] if not compression.converged else []),
  ]
  ####
  return {
    'report_id': 'exhaust-plume-moc-foundation-validation-v1',
    'model_fidelity': 'planar-moc-primitives',
    'status': 'fan-compression-foundation-gate-passed-closure-pending' if not failures else 'moc-foundation-gate-failed',
    'claim_status': 'not_accepted',
    'provider_integration': 'not_started',
    'low_fidelity_promotion_detected': False,
    'round_trip': {
      'case_count': len(cases),
      'gamma_values': [1.2, 1.4, 1.67],
      'mach_values': [1.000001, 1.2, 2.0, 5.0, 25.0],
      'maximum_absolute_nu_residual': max(round_trip_residuals, default=None),
      'all_residuals_finite': all(isfinite(value) for value in round_trip_residuals),
      'failures': round_trip_failures,
    },
    'geometry_cases': geometry_results,
    'failures': failures,
    'next_gates': [
      'physical free-boundary/compression geometry closure; pressure-state and open-mesh primitives remain insufficient',
      'first-cell assembly with reflected-centerline and shock-endpoint semantics',
      'grid/refinement convergence on underexpanded and mild attached-overexpanded cases',
      'independent measurement-operator comparison before provider integration',
    ],
  }


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  report = build_moc_primitive_report()
  serialized = json.dumps(report, indent=2) + '\n'
  if args.output is not None:
    args.output.write_text(serialized, encoding='utf-8')
  print(serialized, end='')
  return 0 if report['status'] == 'fan-compression-foundation-gate-passed-closure-pending' else 1


if __name__ == '__main__':
  raise SystemExit(main())
