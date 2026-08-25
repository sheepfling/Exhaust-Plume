"""Run the standalone planar-MOC primitive evidence gate."""

from __future__ import annotations

import argparse
import json
from math import isfinite, log
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))

from exhaust_plume.models.moc import (  # noqa: E402
  CharacteristicFamily,
  CharacteristicState,
  MocPostShockBoundaryState,
  MocTopologyStatus,
  MocPrimitiveStatus,
  assemble_reflected_characteristic_zone,
  centerline_characteristic_point,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
  prandtl_meyer_angle_rad,
  solve_attached_compression_to_pressure,
  solve_attached_compression_to_turn,
  solve_attached_shock_to_centerline,
  continue_post_shock_characteristics_to_centerline,
  solve_ambient_pressure_free_boundary,
  solve_ambient_pressure_free_boundary_point,
  solve_reflected_free_boundary,
  solve_overexpanded_lip_shock,
  solve_underexpanded_expansion_fan,
  validate_fan_reflected_interface,
  validate_moc_mesh,
)
from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput  # noqa: E402
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit  # noqa: E402
from exhaust_plume.util.aero.shock_validity import ShockSolveStatus  # noqa: E402


def _observed_refinement_order(
  coarse: float,
  medium: float,
  fine: float,
) -> float | None:
  """Estimate the observed order for two successive resolution halvings.

  The fan count doubles in the resolution probe, so the nominal mesh-size
  ratio is two.  This helper is intentionally a diagnostic: it returns no
  order when either successive change is zero or non-finite, rather than
  manufacturing a convergence claim from a flat or failed sequence.
  """

  values = (float(coarse), float(medium), float(fine))
  if not all(isfinite(value) for value in values):
    return None
  coarse_delta = abs(values[1] - values[0])
  fine_delta = abs(values[2] - values[1])
  if coarse_delta <= 0.0 or fine_delta <= 0.0:
    return None
  return log(coarse_delta / fine_delta, 2.0)


def _refinement_diagnostic(
  resolution_probe: list[dict[str, Any]],
) -> dict[str, Any]:
  """Summarize monotonicity and observed order for the open-lattice probe.

  These metrics describe the convergent numerical construction only.  The
  returned status deliberately says ``diagnostic`` and is not reused as a
  physical first-cell or Mach-disk acceptance gate.
  """

  if len(resolution_probe) < 3:
    return {
      'status': 'diagnostic-insufficient-resolution',
      'minimum_resolution_count': 3,
      'metrics': {},
    }
  specs = {
    'coverage_area_m2': 'increasing',
    'maximum_radius_m': 'decreasing',
    'open_extent_x_m': 'decreasing',
    'candidate_shock_endpoint_x_m': 'decreasing',
  }
  metrics: dict[str, Any] = {}
  all_monotone = True
  all_orders_finite = True
  for field, direction in specs.items():
    values = [float(case[field]) for case in resolution_probe]
    if direction == 'increasing':
      monotone = all(right > left for left, right in zip(values, values[1:]))
    else:
      monotone = all(right < left for left, right in zip(values, values[1:]))
    order = _observed_refinement_order(values[0], values[1], values[2])
    all_monotone = all_monotone and monotone
    all_orders_finite = all_orders_finite and order is not None and isfinite(order)
    metrics[field] = {
      'direction': direction,
      'values': values,
      'coarse_to_medium_absolute_delta': abs(values[1] - values[0]),
      'medium_to_fine_absolute_delta': abs(values[2] - values[1]),
      'observed_order': order,
      'monotone': monotone,
    }
  return {
    'status': (
      'diagnostic-monotone-finite-open-lattice'
      if all_monotone and all_orders_finite
      else 'diagnostic-nonmonotone-or-insufficient-order'
    ),
    'interpretation': 'open-lattice-only; physical first-cell closure remains pending',
    'metrics': metrics,
  }


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
  reflected_boundary = solve_reflected_free_boundary(
    fan,
    fan_exit,
    fan_ambient,
  )
  reflected_zone = assemble_reflected_characteristic_zone(
    fan,
    reflected_boundary,
  )
  fan_reflected_interface = validate_fan_reflected_interface(
    fan,
    reflected_boundary,
  )
  lip_ray_grid_residual = max(
    (
      (
        (lip_point[0] - centerline_point[0]) ** 2
        + (lip_point[1] - centerline_point[1]) ** 2
      ) ** 0.5
      for lip_point, centerline_point in zip(
        fan.lip_ray_centerline_points_m,
        fan.centerline_points_m,
        strict=True,
      )
    ),
    default=0.0,
  )
  shock_closure = (
    solve_attached_shock_to_centerline(
      reflected_boundary.boundary_states[-1],
      upstream_pressure_Pa=fan_ambient.pressure_Pa,
    )
    if reflected_boundary.boundary_states
    else None
  )
  post_shock_continuation = None
  if (
    shock_closure is not None
    and shock_closure.converged
    and shock_closure.shock_start_m is not None
    and shock_closure.shock_end_m is not None
    and shock_closure.downstream_state is not None
    and shock_closure.compression is not None
    and shock_closure.compression.downstream_total_pressure_Pa is not None
    and shock_closure.compression.upstream_total_pressure_Pa is not None
    and shock_closure.downstream_mach is not None
  ):
    downstream_at_shock_start = CharacteristicState(
      x_m=shock_closure.shock_start_m[0],
      y_m=shock_closure.shock_start_m[1],
      theta_rad=shock_closure.target_centerline_flow_angle_rad,
      mach=shock_closure.downstream_mach,
      gamma=reflected_boundary.boundary_states[-1].gamma,
    )
    post_shock_continuation = continue_post_shock_characteristics_to_centerline((
      MocPostShockBoundaryState(
        point_m=shock_closure.shock_start_m,
        state=downstream_at_shock_start,
        upstream_total_pressure_Pa=shock_closure.compression.upstream_total_pressure_Pa,
        downstream_total_pressure_Pa=shock_closure.compression.downstream_total_pressure_Pa,
      ),
      MocPostShockBoundaryState(
        point_m=shock_closure.shock_end_m,
        state=shock_closure.downstream_state,
        upstream_total_pressure_Pa=shock_closure.compression.upstream_total_pressure_Pa,
        downstream_total_pressure_Pa=shock_closure.compression.downstream_total_pressure_Pa,
      ),
    ))
  overexpanded_exit = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=300000.0,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  overexpanded_lip_shock = solve_overexpanded_lip_shock(overexpanded_exit, fan_ambient)
  fan_topology = validate_moc_mesh(fan.cells)
  compression = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=180000.0,
  )
  compression_limit_case = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=500000.0,
  )
  turn_compression = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.1,
  )
  turn_compression_limit_case = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=1.0,
  )
  free_boundary = solve_ambient_pressure_free_boundary(
    fan_exit,
    fan_ambient,
    extent_m=0.2,
  )
  boundary_point = solve_ambient_pressure_free_boundary_point(
    CharacteristicState(
      x_m=0.0,
      y_m=0.0,
      theta_rad=0.0,
      mach=2.0,
      gamma=1.4,
    ),
    CharacteristicState(
      x_m=0.0,
      y_m=0.05,
      theta_rad=0.0,
      mach=2.0,
      gamma=1.4,
    ),
    CharacteristicFamily.PLUS,
    total_pressure_Pa=2.0e6,
    ambient_pressure_Pa=101325.0,
  )
  resolution_probe = []
  resolution_failures = []
  for resolution in (4, 8, 16):
    refined_fan = solve_underexpanded_expansion_fan(
      fan_exit,
      fan_ambient,
      characteristic_count=resolution,
    )
    refined_reflected_boundary = solve_reflected_free_boundary(
      refined_fan,
      fan_exit,
      fan_ambient,
    )
    refined_zone = assemble_reflected_characteristic_zone(
      refined_fan,
      refined_reflected_boundary,
    )
    refined_shock = (
      solve_attached_shock_to_centerline(
        refined_reflected_boundary.boundary_states[-1],
        upstream_pressure_Pa=fan_ambient.pressure_Pa,
      )
      if refined_reflected_boundary.boundary_states
      else None
    )
    refined_interface = validate_fan_reflected_interface(
      refined_fan,
      refined_reflected_boundary,
    )
    if not refined_zone.converged:
      resolution_failures.append({
        'case': f'reflected_characteristic_zone_resolution_{resolution}',
        'status': refined_zone.status.value,
        'message': refined_zone.message,
      })
    resolution_probe.append({
      'characteristic_count': resolution,
      'status': refined_fan.status.value,
      'cell_count': len(refined_fan.cells),
      'first_axis_x_m': refined_fan.centerline_points_m[0][0] if refined_fan.centerline_points_m else None,
      'last_axis_x_m': refined_fan.centerline_points_m[-1][0] if refined_fan.centerline_points_m else None,
      'terminal_pressure_residual': refined_fan.terminal_pressure_residual,
      'reflected_boundary_status': refined_reflected_boundary.status.value,
      'reflected_boundary_point_count': len(refined_reflected_boundary.boundary_points_m),
      'reflected_boundary_last_point_m': (
        refined_reflected_boundary.boundary_points_m[-1]
        if refined_reflected_boundary.boundary_points_m
        else None
      ),
      'reflected_zone_status': refined_zone.status.value,
      'reflected_zone_node_count': refined_zone.node_count,
      'reflected_zone_cell_count': refined_zone.cell_count,
      'reflected_zone_forms_closed_zone': refined_zone.topology.forms_closed_zone,
      'coverage_area_m2': refined_zone.coverage_area_m2,
      'reflected_zone_coverage_area_residual_m2': refined_zone.coverage_area_residual_m2,
      'maximum_radius_m': max(
        (point[1] for point in refined_reflected_boundary.boundary_points_m),
        default=None,
      ),
      'open_extent_x_m': max(
        (
          max((node.point_m[0] for node in refined_zone.nodes), default=0.0),
          max((point[0] for point in refined_reflected_boundary.boundary_points_m), default=0.0),
        ),
        default=0.0,
      ),
      'candidate_shock_status': refined_shock.status.value if refined_shock is not None else None,
      'candidate_shock_endpoint_x_m': (
        refined_shock.shock_end_m[0]
        if refined_shock is not None and refined_shock.shock_end_m is not None
        else None
      ),
      'fan_reflected_interface_status': refined_interface.status.value,
      'fan_reflected_interface_maximum_coordinate_residual_m': (
        refined_interface.maximum_coordinate_residual_m
      ),
    })
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
      'normal_shock_limit_failure': {
        'status': compression_limit_case.status.value,
        'shock_status': compression_limit_case.shock_status.value,
      },
    },
    'attached_turn_compression_foundation': {
      'status': turn_compression.status.value,
      'shock_status': turn_compression.shock_status.value,
      'target_turn_rad': turn_compression.target_turn_rad,
      'turn_residual': turn_compression.turn_residual,
      'pressure_ratio': turn_compression.pressure_ratio,
      'downstream_pressure_Pa': turn_compression.downstream_pressure_Pa,
      'downstream_mach': turn_compression.downstream_mach,
      'upstream_total_pressure_Pa': turn_compression.upstream_total_pressure_Pa,
      'downstream_total_pressure_Pa': turn_compression.downstream_total_pressure_Pa,
      'total_pressure_ratio': turn_compression.total_pressure_ratio,
      'detached_turn_failure': {
        'status': turn_compression_limit_case.status.value,
        'shock_status': turn_compression_limit_case.shock_status.value,
      },
    },
    'mild_overexpanded_lip_shock_foundation': {
      'status': overexpanded_lip_shock.status.value,
      'shock_status': (
        overexpanded_lip_shock.shock.shock_status.value
        if overexpanded_lip_shock.shock is not None
        else None
      ),
      'shock_start_m': overexpanded_lip_shock.shock_start_m,
      'centerline_point_m': overexpanded_lip_shock.centerline_point_m,
      'downstream_mach': (
        overexpanded_lip_shock.shock.downstream_mach
        if overexpanded_lip_shock.shock is not None
        else None
      ),
      'closure_status': 'open',
    },
    'ambient_pressure_free_boundary_foundation': {
      'status': free_boundary.status.value,
      'terminal_mach': free_boundary.terminal_mach,
      'terminal_flow_angle_rad': free_boundary.terminal_flow_angle_rad,
      'pressure_residual': free_boundary.pressure_residual,
      'tangent_residual': free_boundary.tangent_residual,
      'extent_m': 0.2,
      'closure_status': 'open',
      'march_point': {
        'status': boundary_point.status.value,
        'point_m': boundary_point.point_m,
        'pressure_residual': boundary_point.pressure_residual,
        'tangent_residual': boundary_point.tangent_residual,
        'geometry_residual': boundary_point.geometry_residual,
        'iterations': boundary_point.iterations,
      },
    },
    'reflected_free_boundary_foundation': {
      'status': reflected_boundary.status.value,
      'centerline_point_count': len(reflected_boundary.centerline_states),
      'boundary_point_count': len(reflected_boundary.boundary_points_m),
      'maximum_absolute_pressure_residual': max(
        (abs(point.pressure_residual) for point in reflected_boundary.point_results if point.pressure_residual is not None),
        default=None,
      ),
      'maximum_absolute_tangent_residual': max(
        (abs(point.tangent_residual) for point in reflected_boundary.point_results if point.tangent_residual is not None),
        default=None,
      ),
      'maximum_absolute_geometry_residual': max(
        (abs(point.geometry_residual) for point in reflected_boundary.point_results if point.geometry_residual is not None),
        default=None,
      ),
      'first_boundary_point_m': reflected_boundary.boundary_points_m[0] if reflected_boundary.boundary_points_m else None,
      'last_boundary_point_m': reflected_boundary.boundary_points_m[-1] if reflected_boundary.boundary_points_m else None,
      'closure_status': 'open',
      'shock_closure': 'candidate-open-cell',
      'shock_closure_candidate': (
        {
          'status': shock_closure.status.value,
          'shock_status': shock_closure.shock_status.value if shock_closure.shock_status is not None else None,
          'shock_start_m': shock_closure.shock_start_m,
          'shock_end_m': shock_closure.shock_end_m,
          'shock_angle_rad': shock_closure.shock_angle_rad,
          'geometry_residual_m': shock_closure.geometry_residual_m,
          'downstream_mach': shock_closure.downstream_mach,
          'downstream_pressure_Pa': shock_closure.downstream_pressure_Pa,
          'downstream_state': (
            {
              'x_m': shock_closure.downstream_state.x_m,
              'y_m': shock_closure.downstream_state.y_m,
              'theta_rad': shock_closure.downstream_state.theta_rad,
              'mach': shock_closure.downstream_state.mach,
              'gamma': shock_closure.downstream_state.gamma,
            }
            if shock_closure.downstream_state is not None
            else None
          ),
          'downstream_total_pressure_Pa': shock_closure.downstream_total_pressure_Pa,
          'total_pressure_ratio': shock_closure.total_pressure_ratio,
          'topology_status': 'not_assembled',
          'post_shock_continuation': (
            {
              'status': post_shock_continuation.status.value,
              'boundary_sample_count': 2,
              'characteristic_family': 'C-',
              'centerline_point_count': len(post_shock_continuation.centerline_states),
              'centerline_points_m': [
                segment.centerline_point_m
                for segment in post_shock_continuation.segments
              ],
              'maximum_geometry_residual_m': post_shock_continuation.maximum_geometry_residual_m,
              'maximum_absolute_invariant_residual': post_shock_continuation.maximum_absolute_invariant_residual,
              'continuation_status': 'prescribed-boundary-trace-only',
              'message': post_shock_continuation.message,
            }
            if post_shock_continuation is not None
            else None
          ),
        }
        if shock_closure is not None
        else None
      ),
    },
    'reflected_characteristic_zone_assembly': {
      'status': reflected_zone.status.value,
      'characteristic_count': reflected_zone.characteristic_count,
      'node_count': reflected_zone.node_count,
      'cell_count': reflected_zone.cell_count,
      'topology_status': reflected_zone.topology.status.value,
      'boundary_edge_count': reflected_zone.topology.boundary_edge_count,
      'boundary_component_count': reflected_zone.topology.boundary_component_count,
      'forms_closed_zone': reflected_zone.topology.forms_closed_zone,
      'nonmanifold_edge_count': reflected_zone.topology.nonmanifold_edge_count,
      'coverage_area_m2': reflected_zone.coverage_area_m2,
      'coverage_area_residual_m2': reflected_zone.coverage_area_residual_m2,
      'physical_closure_status': reflected_zone.physical_closure_status,
      'shock_closure_status': reflected_zone.shock_closure_status,
      'message': reflected_zone.message,
    },
    'fan_reflected_interface': {
      'status': fan_reflected_interface.status.value,
      'aligned': fan_reflected_interface.aligned,
      'maximum_coordinate_residual_m': fan_reflected_interface.maximum_coordinate_residual_m,
      'lip_ray_vs_compatibility_grid_maximum_residual_m': lip_ray_grid_residual,
      'position_tolerance_m': fan_reflected_interface.position_tolerance_m,
      'message': (
        fan_reflected_interface.message
        if fan_reflected_interface.message
        else 'fan and reflected march share the averaged compatibility grid; direct lip-ray coordinates remain diagnostic'
      ),
      'claim_status': 'diagnostic-interface-aligned-physical-closure-pending',
    },
    'fan_resolution_probe': {
      'status': 'diagnostic-only-open-mesh',
      'cases': resolution_probe,
      'refinement_diagnostic': _refinement_diagnostic(resolution_probe),
    },
  }
  failures = [
    *round_trip_failures,
    *resolution_failures,
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
    *([
      {
        'case': 'compression_normal_shock_limit_failure',
        'status': compression_limit_case.status.value,
        'message': compression_limit_case.message,
      }
    ] if (
      compression_limit_case.status is not MocPrimitiveStatus.OUTSIDE_DOMAIN
      or compression_limit_case.shock_status is not ShockSolveStatus.PRESSURE_ABOVE_NORMAL_SHOCK_LIMIT
    ) else []),
    *([
      {
        'case': 'attached_turn_compression_foundation',
        'status': turn_compression.status.value,
        'message': turn_compression.message,
      }
    ] if not turn_compression.converged else []),
    *([
      {
        'case': 'compression_detached_turn_failure',
        'status': turn_compression_limit_case.status.value,
        'message': turn_compression_limit_case.message,
      }
    ] if (
      turn_compression_limit_case.status is not MocPrimitiveStatus.OUTSIDE_DOMAIN
      or turn_compression_limit_case.shock_status is not ShockSolveStatus.DETACHED_SHOCK_REQUIRED
    ) else []),
    *([
      {
        'case': 'mild_overexpanded_lip_shock_foundation',
        'status': overexpanded_lip_shock.status.value,
        'message': overexpanded_lip_shock.message,
      }
    ] if not overexpanded_lip_shock.converged else []),
    *([
      {
        'case': 'ambient_pressure_free_boundary_foundation',
        'status': free_boundary.status.value,
        'message': free_boundary.message,
      }
    ] if not free_boundary.converged else []),
    *([
      {
        'case': 'ambient_pressure_free_boundary_point',
        'status': boundary_point.status.value,
        'message': boundary_point.message,
      }
    ] if not boundary_point.converged else []),
    *([
      {
        'case': 'reflected_free_boundary_foundation',
        'status': reflected_boundary.status.value,
        'message': reflected_boundary.message,
      }
    ] if not reflected_boundary.converged else []),
    *([
      {
        'case': 'reflected_characteristic_zone_assembly',
        'status': reflected_zone.status.value,
        'message': reflected_zone.message,
      }
    ] if not reflected_zone.converged else []),
    *([
      {
        'case': 'shock_closure_candidate',
        'status': shock_closure.status.value,
        'message': shock_closure.message,
      }
    ] if shock_closure is not None and not shock_closure.converged else []),
    *([
      {
        'case': 'post_shock_continuation',
        'status': post_shock_continuation.status.value,
        'message': post_shock_continuation.message,
      }
    ] if post_shock_continuation is not None and not post_shock_continuation.converged else []),
  ]
  ####
  return {
    'report_id': 'exhaust-plume-moc-foundation-validation-v1',
    'model_fidelity': 'planar-moc-primitives',
    'status': 'fan-compression-boundary-foundation-gate-passed-closure-pending' if not failures else 'moc-foundation-gate-failed',
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
      'sampled shock-boundary state field, post-shock C+ interior continuation, and complete downstream bookkeeping',
      'grid/refinement convergence for the assembled reflected zone and mild attached-overexpanded cases',
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
  return 0 if report['status'] == 'fan-compression-boundary-foundation-gate-passed-closure-pending' else 1


if __name__ == '__main__':
  raise SystemExit(main())
