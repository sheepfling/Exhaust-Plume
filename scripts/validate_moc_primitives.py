"""Run the standalone planar-MOC primitive evidence gate."""

from __future__ import annotations

import argparse
import json
from math import cos, isfinite, log, sin
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))

from exhaust_plume.models.moc import (  # noqa: E402
  CharacteristicFamily,
  CharacteristicState,
  MocInvariantClosureFamily,
  MocFreeBoundaryShockResult,
  MocPostShockClosureStatus,
  MocPostShockBoundaryState,
  MocPostShockChainCellSolve,
  MocPostShockCharacteristicFieldResult,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocShockBoundaryFitResult,
  MocShockBoundaryFitStatus,
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
  solve_marched_attached_shock_chain_cell,
  solve_marched_attached_shock_from_source_strip,
  solve_marched_attached_shock_with_constant_invariant_closure,
  solve_reflected_boundary_trace_extension,
  solve_uniform_attached_shock_field,
  assemble_post_shock_characteristic_zone,
  assemble_post_shock_characteristic_field,
  assemble_post_shock_first_layer,
  continue_post_shock_characteristics_to_centerline,
  continue_post_shock_characteristic_chain,
  fit_attached_shock_boundary,
  solve_ambient_pressure_free_boundary,
  solve_ambient_pressure_free_boundary_point,
  solve_reflected_free_boundary,
  solve_overexpanded_lip_shock,
  solve_underexpanded_expansion_fan,
  assemble_source_characteristic_strip,
  extend_source_characteristic_strip_constant_k_plus,
  sample_reflected_zone_along_shock_path,
  validate_fan_reflected_interface,
  validate_closed_post_shock_field,
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


def _sampled_attached_shock_gate() -> tuple[Any, Any, Any]:
  """Exercise the sampled shock-fit and open-field rejection gates."""

  compression = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.2,
  )
  if compression.beta_rad is None:
    raise RuntimeError('synthetic attached-shock validation could not obtain beta')
  shock_angle = -0.2 - compression.beta_rad
  start = (0.5, 0.5)
  step = 0.5 / (3.0 * abs(sin(shock_angle)))
  points = tuple(
    (
      start[0] + index * step * cos(shock_angle),
      start[1] + index * step * sin(shock_angle),
    )
    for index in range(4)
  )
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    )
    for point in points
  )
  shock_fit = fit_attached_shock_boundary(
    upstream_states,
    (100000.0,) * 4,
    points,
    (0.0,) * 4,
  )
  continuation = continue_post_shock_characteristics_to_centerline(
    shock_fit.boundary_states,
  )
  first_layer = assemble_post_shock_first_layer(continuation)
  open_zone = assemble_post_shock_characteristic_zone(
    continuation,
    first_layer,
    shock_fit.boundary_states,
  )
  closed_gate = validate_closed_post_shock_field(
    continuation,
    shock_fit,
    open_zone.nodes,
    open_zone.cells,
  )
  return shock_fit, continuation, closed_gate


def _shock_seeded_field_fixture() -> MocPostShockCharacteristicFieldResult:
  """Assemble a varied prescribed field to exercise the full-field contract.

  This fixture is deliberately not a free-boundary solution.  It supplies a
  turning post-shock boundary so the characteristic fan has finite cell area;
  the report records it as a solver-contract fixture rather than validation
  or provider evidence.
  """

  points = (
    (0.76, 0.165),
    (0.78, 0.110),
    (0.80, 0.055),
    (0.82, 0.0),
  )
  samples = tuple(
    MocPostShockBoundaryState(
      point_m=point,
      state=CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.1 * (3 - index),
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=2.0e6,
      downstream_total_pressure_Pa=1.8e6,
    )
    for index, point in enumerate(points)
  )
  fit = MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=samples,
    shock_angle_residuals_rad=(0.0,) * len(samples),
    maximum_shock_angle_residual_rad=0.0,
  )
  return assemble_post_shock_characteristic_field(fit)


def _shock_seeded_field_refinement_probe() -> list[dict[str, Any]]:
  """Probe compatible shock-sample refinement on the prescribed field lane."""

  probe: list[dict[str, Any]] = []
  for sample_count in (3, 4, 5):
    points = tuple(
      (0.76 + 0.02 * index, 0.165 * (1.0 - index / (sample_count - 1)))
      for index in range(sample_count)
    )
    samples = tuple(
      MocPostShockBoundaryState(
        point_m=point,
        state=CharacteristicState(
          x_m=point[0],
          y_m=point[1],
          theta_rad=-0.3 * (1.0 - index / (sample_count - 1)),
          mach=2.0,
          gamma=1.4,
        ),
        upstream_total_pressure_Pa=2.0e6,
        downstream_total_pressure_Pa=1.8e6,
      )
      for index, point in enumerate(points)
    )
    field = assemble_post_shock_characteristic_field(
      MocShockBoundaryFitResult(
        status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
        boundary_states=samples,
        shock_angle_residuals_rad=(0.0,) * sample_count,
        maximum_shock_angle_residual_rad=0.0,
      )
    )
    probe.append({
      'shock_sample_count': sample_count,
      'status': field.status.value,
      'characteristic_layer_count': field.characteristic_layer_count,
      'node_count': field.node_count,
      'cell_count': field.cell_count,
      'topology_status': field.topology.status.value,
      'topology_forms_closed_zone': field.topology.forms_closed_zone,
      'nonmanifold_edge_count': field.topology.nonmanifold_edge_count,
      'maximum_geometry_residual_m': field.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': field.maximum_absolute_invariant_residual,
      'minimum_forward_margin_m': field.minimum_forward_margin_m,
      'pressure_loss_verified': field.pressure_loss_verified,
    })
  return probe


def _solver_generated_shock_fixture() -> MocFreeBoundaryShockResult:
  """Generate a shock boundary and field without supplying shock points."""

  return solve_uniform_attached_shock_field(
    CharacteristicState(
      x_m=0.5,
      y_m=0.5,
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=17,
  )


def _solver_generated_shock_refinement_probe() -> list[dict[str, Any]]:
  """Record solver-generated shock endpoint and field refinement evidence."""

  probe: list[dict[str, Any]] = []
  for sample_count in (9, 17, 33):
    result = solve_uniform_attached_shock_field(
      CharacteristicState(
        x_m=0.5,
        y_m=0.5,
        theta_rad=-0.2,
        mach=2.0,
        gamma=1.4,
      ),
      100000.0,
      (0.5, 0.5),
      outer_downstream_flow_angle_rad=0.05,
      sample_count=sample_count,
    )
    field = result.field
    probe.append({
      'sample_count': sample_count,
      'status': result.status.value,
      'endpoint_m': result.endpoint_m,
      'maximum_shock_angle_residual_rad': result.maximum_shock_angle_residual_rad,
      'field_status': None if field is None else field.status.value,
      'node_count': None if field is None else field.node_count,
      'cell_count': None if field is None else field.cell_count,
      'topology_forms_closed_zone': None if field is None else field.topology.forms_closed_zone,
      'nonmanifold_edge_count': None if field is None else field.topology.nonmanifold_edge_count,
      'minimum_forward_margin_m': None if field is None else field.minimum_forward_margin_m,
      'pressure_loss_verified': None if field is None else field.pressure_loss_verified,
    })
  return probe


def _shock_cell_chain_planner_mock(
  seed_field: MocPostShockCharacteristicFieldResult,
) -> tuple[Any, list[dict[str, Any]]]:
  """Exercise a continued-cell planner with prescribed next-shock geometry.

  This is an orchestration fixture, not a free-boundary solver.  Each mock
  step records the previous terminal trace through ``incoming_handoff`` and
  supplies a separate prescribed shock boundary for the next local field.
  Keeping this fixture in the validation script makes the chain contract
  executable without allowing it to become a production provider.
  """

  observations: list[dict[str, Any]] = []

  def solve_next(current, cell_index, handoff):
    observations.append({
      'cell_index': cell_index,
      'incoming_handoff_sample_count': len(handoff),
      'incoming_total_pressure_range_Pa': (
        min(sample.total_pressure_Pa for sample in handoff),
        max(sample.total_pressure_Pa for sample in handoff),
      ),
      'current_end_x_m': current.end_x_m,
    })
    if cell_index >= 4:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message='planner mock exhausted its prescribed three-cell fixture',
      )
    shock_start_x_m = current.end_x_m + 0.20
    points = tuple(
      (shock_start_x_m + 0.02 * index, ordinate)
      for index, ordinate in enumerate((0.20, 0.14, 0.08, 0.04, 0.0))
    )
    downstream_angles = (-0.30, -0.20, -0.10, -0.05, 0.0)
    samples = tuple(
      MocPostShockBoundaryState(
        point_m=point,
        state=CharacteristicState(
          x_m=point[0],
          y_m=point[1],
          theta_rad=angle,
          mach=2.0,
          gamma=1.4,
        ),
        upstream_total_pressure_Pa=1.8e6,
        downstream_total_pressure_Pa=1.6e6,
      )
      for point, angle in zip(points, downstream_angles, strict=True)
    )
    upstream_states = tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.35 + 0.08 * index,
        mach=2.0,
        gamma=1.4,
      )
      for index, point in enumerate(points)
    )
    upstream_total_pressure_Pa = max(
      sample.total_pressure_Pa for sample in handoff
    )
    downstream_total_pressure_Pa = 0.8888888888888889 * upstream_total_pressure_Pa
    samples = tuple(
      MocPostShockBoundaryState(
        point_m=sample.point_m,
        state=sample.state,
        upstream_total_pressure_Pa=upstream_total_pressure_Pa,
        downstream_total_pressure_Pa=downstream_total_pressure_Pa,
      )
      for sample in samples
    )
    fit = MocShockBoundaryFitResult(
      status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
      boundary_states=samples,
      shock_angle_residuals_rad=(0.0,) * len(samples),
      maximum_shock_angle_residual_rad=0.0,
      upstream_states=upstream_states,
      upstream_total_pressure_Pa=(upstream_total_pressure_Pa,) * len(samples),
    )
    return MocPostShockChainCellSolve(
      field=assemble_post_shock_characteristic_field(
        fit,
        incoming_handoff=handoff,
      ),
      end_x_m=current.end_x_m + 0.50,
    )

  return (
    continue_post_shock_characteristic_chain(
      seed_field,
      solve_next,
      start_x_m=0.7,
      end_x_m=1.0,
    ),
    observations,
  )


def _solver_generated_chain_reference(
  seed_field: MocPostShockCharacteristicFieldResult,
) -> tuple[Any, list[dict[str, Any]]]:
  """Exercise generated shock cells with an explicit carried-state callback.

  The upstream state and pressure callbacks deliberately derive their
  thermodynamic level from the incoming trace so the chain can verify
  monotonic total-pressure carry. They are still a reference field, not the
  reflected-zone solution required for production promotion.
  """

  observations: list[dict[str, Any]] = []

  def solve_next(current, cell_index, handoff):
    observations.append({
      'cell_index': cell_index,
      'incoming_handoff_sample_count': len(handoff),
      'incoming_total_pressure_range_Pa': (
        min(sample.total_pressure_Pa for sample in handoff),
        max(sample.total_pressure_Pa for sample in handoff),
      ),
      'current_end_x_m': current.end_x_m,
    })
    if cell_index >= 4:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'solver-generated reference stopped after its three-cell fixture; '
          'no physical endpoint was inferred'
        ),
      )
    incoming_max = max(sample.total_pressure_Pa for sample in handoff)
    upstream_mach = 2.0
    upstream_gamma = 1.4
    pressure_ratio = (1.0 + 0.2 * upstream_mach * upstream_mach) ** (
      upstream_gamma / (upstream_gamma - 1.0)
    )
    upstream_pressure = incoming_max / pressure_ratio

    return solve_marched_attached_shock_chain_cell(
      current,
      cell_index,
      handoff,
      start_point_m=(current.end_x_m + 0.2, 0.5),
      end_x_m=current.end_x_m + 0.8,
      upstream_state_at=lambda point: CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.2,
        mach=upstream_mach,
        gamma=upstream_gamma,
      ),
      upstream_pressure_at=lambda _point: upstream_pressure,
      downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
      sample_count=9,
    )

  return (
    continue_post_shock_characteristic_chain(
      seed_field,
      solve_next,
      start_x_m=0.5,
      end_x_m=1.0,
    ),
    observations,
  )


def _reflected_zone_shock_coupling_probe(
  reflected_zone: Any,
  reflected_boundary: Any,
  reflected_source_strip: Any,
) -> dict[str, Any]:
  """Probe the domain-bounded reflected-field callbacks at a shock start."""

  if not reflected_zone.converged or not reflected_boundary.boundary_points_m:
    return {
      'status': 'invalid_input',
      'sample_count': 0,
      'message': 'reflected zone or boundary did not converge',
      'claim_status': 'reflected-field-shock-coupling-pending',
    }
  start = reflected_boundary.boundary_points_m[-1]
  if start[1] <= 0.0:
    return {
      'status': 'invalid_input',
      'sample_count': 0,
      'message': 'reflected boundary shock probe requires a positive start ordinate',
      'claim_status': 'reflected-field-shock-coupling-pending',
    }
  upstream_pressure = reflected_source_strip.static_pressure_at(start)
  if upstream_pressure is None:
    return {
      'status': 'pressure_failure',
      'sample_count': 0,
      'message': 'reflected zone could not provide terminal upstream pressure',
      'claim_status': 'reflected-field-shock-coupling-pending',
    }
  trace_extension = solve_reflected_boundary_trace_extension(
    reflected_boundary,
    upstream_pressure,
    sample_count=9,
  )
  coupling = sample_reflected_zone_along_shock_path(
    reflected_zone,
    trace_extension.shock_points_m,
  )
  result = solve_marched_attached_shock_from_source_strip(
    reflected_source_strip,
    start,
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / start[1]),
    ),
    sample_count=9,
  )
  return {
    'status': result.status.value,
    'sample_count': result.sample_count,
    'shock_start_m': start,
    'last_valid_point_m': result.shock_points_m[-1] if result.shock_points_m else None,
    'message': result.message,
    'coupling': coupling.as_report(),
    'claim_status': (
      'reflected-field-domain-bounded-probe; shock-path-extension-pending'
    ),
  }


def _reflected_simple_wave_extension_probe(
  reflected_boundary: Any,
  reflected_simple_wave_extension: Any,
) -> dict[str, Any]:
  """Probe shock marching after an explicit open-strip continuation."""

  strip = reflected_simple_wave_extension.strip
  if not reflected_simple_wave_extension.converged or strip is None:
    return {
      'status': reflected_simple_wave_extension.status.value,
      'sample_count': 0,
      'message': reflected_simple_wave_extension.message,
      'extension': reflected_simple_wave_extension.as_report(),
      'claim_status': 'constant-k-plus-simple-wave-extension-pending',
    }
  if not reflected_boundary.boundary_points_m:
    return {
      'status': 'invalid_input',
      'sample_count': 0,
      'message': 'reflected boundary did not provide a shock start',
      'extension': reflected_simple_wave_extension.as_report(),
      'claim_status': 'constant-k-plus-simple-wave-extension-pending',
    }
  start = reflected_boundary.boundary_points_m[-1]
  result = solve_marched_attached_shock_from_source_strip(
    strip,
    start,
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / start[1]),
    ),
    sample_count=17,
  )
  return {
    'status': result.status.value,
    'sample_count': result.sample_count,
    'shock_start_m': start,
    'last_valid_point_m': result.shock_points_m[-1] if result.shock_points_m else None,
    'message': result.message,
    'extension': reflected_simple_wave_extension.as_report(),
    'claim_status': 'constant-k-plus-simple-wave-extension; shock-closure-pending',
  }


def _terminal_source_window_invariant_closure_probe(
  reflected_boundary: Any,
  fan_exit: Any,
  fan_ambient: Any,
) -> dict[str, Any]:
  """Attempt a domain-bounded invariant-conditioned first-cell closure.

  The long extension is intentionally kept as a diagnostic evidence case.  In
  the canonical configuration the full triangular continuation reaches a
  characteristic caustic while the terminal window remains valid; the
  invariant bracket is retained so the report records whether the physical
  closure is actually found rather than promoting the window by geometry
  alone.
  """

  if not reflected_boundary.converged or not reflected_boundary.boundary_points_m:
    return {
      'status': 'invalid_input',
      'claim_status': 'domain-bounded-invariant-shooting-attempt; closure-pending',
      'message': 'reflected boundary did not provide a converged shock start',
    }
  extension = extend_source_characteristic_strip_constant_k_plus(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
    additional_sample_count=190,
    axis_step_m=0.0035,
    source_window_start_index=8,
  )
  strip = extension.strip
  start = reflected_boundary.boundary_points_m[-1]
  if not extension.converged or strip is None:
    return {
      'status': extension.status.value,
      'claim_status': 'domain-bounded-invariant-shooting-attempt; closure-pending',
      'source_extension': extension.as_report(),
      'message': extension.message,
    }
  closure = solve_marched_attached_shock_with_constant_invariant_closure(
    strip,
    start,
    MocInvariantClosureFamily.K_PLUS,
    invariant_target_lower=-0.78,
    invariant_target_upper=-0.70,
    sample_count=17,
    shock_angle_tolerance_rad=0.2,
  )
  return {
    **closure.as_report(),
    'source_extension': extension.as_report(),
    'shock_start_m': start,
    'claim_status': (
      'domain-bounded-invariant-shooting-attempt; '
      'constant-downstream-invariant-is-not-yet-a-physical-closure'
    ),
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
  reflected_trace_extension = solve_reflected_boundary_trace_extension(
    reflected_boundary,
    fan_ambient.pressure_Pa,
  )
  reflected_zone = assemble_reflected_characteristic_zone(
    fan,
    reflected_boundary,
    total_pressure_Pa=fan_exit.total_pressure_Pa,
  )
  reflected_source_strip = assemble_source_characteristic_strip(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    fan_exit.total_pressure_Pa,
  )
  reflected_simple_wave_extension = extend_source_characteristic_strip_constant_k_plus(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
    additional_sample_count=12,
    axis_step_m=0.03,
  )
  reflected_zone_shock_coupling = _reflected_zone_shock_coupling_probe(
    reflected_zone,
    reflected_boundary,
    reflected_source_strip,
  )
  reflected_simple_wave_shock_probe = _reflected_simple_wave_extension_probe(
    reflected_boundary,
    reflected_simple_wave_extension,
  )
  terminal_source_window_invariant_closure = _terminal_source_window_invariant_closure_probe(
    reflected_boundary,
    fan_exit,
    fan_ambient,
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
  sampled_shock_fit, sampled_continuation, sampled_closed_gate = _sampled_attached_shock_gate()
  shock_seeded_field = _shock_seeded_field_fixture()
  shock_seeded_refinement_probe = _shock_seeded_field_refinement_probe()
  solver_generated_shock = _solver_generated_shock_fixture()
  solver_generated_shock_refinement_probe = _solver_generated_shock_refinement_probe()
  solver_generated_chain_reference = None
  solver_generated_chain_observations: list[dict[str, Any]] = []
  if solver_generated_shock.field is not None and solver_generated_shock.field.converged:
    solver_generated_chain_reference, solver_generated_chain_observations = _solver_generated_chain_reference(
      solver_generated_shock.field,
    )
  shock_cell_chain_mock, shock_cell_chain_mock_observations = _shock_cell_chain_planner_mock(
    shock_seeded_field,
  )
  shock_seeded_refinement_failures = [
    case for case in shock_seeded_refinement_probe
    if (
      case['status'] != 'converged_closed'
      or not case['topology_forms_closed_zone']
      or case['nonmanifold_edge_count']
      or not case['pressure_loss_verified']
    )
  ]
  solver_generated_chain_report = (
    None
    if solver_generated_chain_reference is None
    else solver_generated_chain_reference.as_report()
  )
  shock_cell_chain_mock_report = shock_cell_chain_mock.as_report()
  solver_generated_chain_pressure_lineage_ok = (
    solver_generated_chain_report is not None
    and solver_generated_chain_report['continuation_boundary_maxima_nonincreasing'] is True
  )
  solver_generated_shock_refinement_failures = [
    case for case in solver_generated_shock_refinement_probe
    if (
      case['status'] != 'converged_free_boundary_field'
      or case['field_status'] != 'converged_closed'
      or not case['topology_forms_closed_zone']
      or case['nonmanifold_edge_count']
      or not case['pressure_loss_verified']
    )
  ]
  solver_generated_chain_failure = (
    solver_generated_chain_reference is None
    or not solver_generated_chain_reference.resolved
    or solver_generated_chain_reference.cell_count != 3
    or solver_generated_chain_reference.physical_termination
    or any(
      not cell.carries_state
      for cell in solver_generated_chain_reference.cells
    )
    or not solver_generated_chain_pressure_lineage_ok
  )
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
      'total_pressure_Pa': reflected_zone.total_pressure_Pa,
      'physical_closure_status': reflected_zone.physical_closure_status,
      'shock_closure_status': reflected_zone.shock_closure_status,
      'message': reflected_zone.message,
    },
    'reflected_source_characteristic_strip': {
      **reflected_source_strip.as_report(),
      'claim_status': 'reusable-open-upstream-strip; shock-closure-pending',
    },
    'reflected_source_strip_constant_k_plus_extension': {
      **reflected_simple_wave_extension.as_report(),
      'shock_probe': reflected_simple_wave_shock_probe,
      'claim_status': 'open-simple-wave-extension; shock-closure-pending',
    },
    'terminal_source_window_invariant_closure': terminal_source_window_invariant_closure,
    'reflected_zone_shock_coupling': reflected_zone_shock_coupling,
    'reflected_boundary_trace_extension': {
      'status': reflected_trace_extension.status.value,
      'accepted': reflected_trace_extension.converged,
      'sample_count': reflected_trace_extension.sample_count,
      'endpoint_m': reflected_trace_extension.endpoint_m,
      'field_status': (
        reflected_trace_extension.field_status.value
        if reflected_trace_extension.field_status is not None
        else None
      ),
      'shock_closure_status': (
        reflected_trace_extension.field.shock_closure_status
        if reflected_trace_extension.field is not None
        else None
      ),
      'topology_forms_closed_zone': (
        reflected_trace_extension.field.topology.forms_closed_zone
        if reflected_trace_extension.field is not None
        else None
      ),
      'pressure_loss_verified': (
        reflected_trace_extension.field.pressure_loss_verified
        if reflected_trace_extension.field is not None
        else False
      ),
      'message': reflected_trace_extension.message,
      'claim_status': 'reflected-boundary-trace-extension-only; upstream-strip-coupling-pending',
    },
    'sampled_attached_shock_fit': {
      'status': sampled_shock_fit.status.value,
      'sample_count': len(sampled_shock_fit.boundary_states),
      'maximum_shock_angle_residual_rad': sampled_shock_fit.maximum_shock_angle_residual_rad,
      'total_pressure_ratio_range': (
        min(
          sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
          for sample in sampled_shock_fit.boundary_states
        )
        if sampled_shock_fit.boundary_states
        else None,
        max(
          sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
          for sample in sampled_shock_fit.boundary_states
        )
        if sampled_shock_fit.boundary_states
        else None,
      ),
      'continuation_status': sampled_continuation.status.value,
      'continuation_centerline_count': len(sampled_continuation.centerline_states),
      'claim_status': 'sampled-boundary-contract-only',
    },
    'closed_post_shock_field_gate': {
      'status': sampled_closed_gate.status.value,
      'accepted': sampled_closed_gate.converged,
      'topology_status': sampled_closed_gate.topology.status.value,
      'message': sampled_closed_gate.message,
      'claim_status': 'open-zone-rejection-exercised; canonical-full-field-pending',
    },
    'solver_generated_attached_shock_field': {
      'status': solver_generated_shock.status.value,
      'accepted': solver_generated_shock.converged,
      'sample_count': solver_generated_shock.sample_count,
      'endpoint_m': solver_generated_shock.endpoint_m,
      'maximum_shock_angle_residual_rad': solver_generated_shock.maximum_shock_angle_residual_rad,
      'field_status': solver_generated_shock.field_status.value if solver_generated_shock.field_status is not None else None,
      'node_count': solver_generated_shock.field.node_count if solver_generated_shock.field is not None else None,
      'cell_count': solver_generated_shock.field.cell_count if solver_generated_shock.field is not None else None,
      'topology_forms_closed_zone': (
        solver_generated_shock.field.topology.forms_closed_zone
        if solver_generated_shock.field is not None
        else None
      ),
      'minimum_forward_margin_m': (
        solver_generated_shock.field.minimum_forward_margin_m
        if solver_generated_shock.field is not None
        else None
      ),
      'pressure_loss_verified': (
        solver_generated_shock.field.pressure_loss_verified
        if solver_generated_shock.field is not None
        else False
      ),
      'shock_closure_status': (
        solver_generated_shock.field.shock_closure_status
        if solver_generated_shock.field is not None
        else None
      ),
      'message': solver_generated_shock.message,
      'claim_status': 'solver-generated-boundary-conditioned-field; upstream-field-coupling-pending',
    },
    'solver_generated_shock_refinement': {
      'status': (
        'diagnostic-all-solver-generated-resolutions-converged'
        if not solver_generated_shock_refinement_failures
        else 'diagnostic-solver-generated-resolution-failure'
      ),
      'cases': solver_generated_shock_refinement_probe,
      'claim_status': 'solver-generated-boundary-refinement-only; upstream-field-coupling-pending',
    },
    'solver_generated_chain_reference': {
      'status': (
        None
        if solver_generated_chain_reference is None
        else solver_generated_chain_reference.status.value
      ),
      'accepted': not solver_generated_chain_failure,
      'cell_count': (
        None
        if solver_generated_chain_reference is None
        else solver_generated_chain_reference.cell_count
      ),
      'resolved': (
        False
        if solver_generated_chain_reference is None
        else solver_generated_chain_reference.resolved
      ),
      'physical_termination': (
        None
        if solver_generated_chain_reference is None
        else solver_generated_chain_reference.physical_termination
      ),
      'termination_reason': (
        None
        if solver_generated_chain_reference is None
        else solver_generated_chain_reference.termination_reason.value
      ),
      'state_carry_count': (
        None
        if solver_generated_chain_reference is None
        else solver_generated_chain_reference.as_report()['state_carry_count']
      ),
      'continuation_total_pressure_ranges_Pa': (
        None
        if solver_generated_chain_report is None
        else solver_generated_chain_report['continuation_total_pressure_ranges_Pa']
      ),
      'continuation_boundary_maxima_nonincreasing': (
        None
        if solver_generated_chain_report is None
        else solver_generated_chain_report['continuation_boundary_maxima_nonincreasing']
      ),
      'observations': solver_generated_chain_observations,
      'claim_status': 'solver-generated-chain-reference; upstream-field-coupling-pending',
    },
    'shock_seeded_post_shock_field': {
      'status': shock_seeded_field.status.value,
      'accepted': shock_seeded_field.converged,
      'characteristic_layer_count': shock_seeded_field.characteristic_layer_count,
      'node_count': shock_seeded_field.node_count,
      'cell_count': shock_seeded_field.cell_count,
      'topology_status': shock_seeded_field.topology.status.value,
      'topology_forms_closed_zone': shock_seeded_field.topology.forms_closed_zone,
      'nonmanifold_edge_count': shock_seeded_field.topology.nonmanifold_edge_count,
      'maximum_geometry_residual_m': shock_seeded_field.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': shock_seeded_field.maximum_absolute_invariant_residual,
      'minimum_forward_margin_m': shock_seeded_field.minimum_forward_margin_m,
      'minimum_post_shock_total_pressure_ratio': shock_seeded_field.minimum_post_shock_total_pressure_ratio,
      'maximum_post_shock_total_pressure_ratio': shock_seeded_field.maximum_post_shock_total_pressure_ratio,
      'continuation_boundary_sample_count': len(shock_seeded_field.continuation_boundary_states),
      'incoming_handoff_sample_count': len(shock_seeded_field.incoming_handoff_states),
      'continuation_boundary_kind': 'terminal-characteristic-trace',
      'physical_closure_status': shock_seeded_field.physical_closure_status,
      'shock_closure_status': shock_seeded_field.shock_closure_status,
      'message': shock_seeded_field.message,
      'claim_status': 'synthetic-prescribed-field-contract-only; canonical-free-boundary-pending',
    },
    'shock_seeded_field_refinement': {
      'status': (
        'diagnostic-all-prescribed-resolutions-converged'
        if not shock_seeded_refinement_failures
        else 'diagnostic-prescribed-resolution-failure'
      ),
      'cases': shock_seeded_refinement_probe,
      'claim_status': 'prescribed-boundary-refinement-only; physical-shock-convergence-pending',
    },
    'shock_cell_chain_planner_mock': {
      'status': shock_cell_chain_mock.status.value,
      'termination_reason': shock_cell_chain_mock.termination_reason.value,
      'physical_termination': shock_cell_chain_mock.physical_termination,
      'cell_count': shock_cell_chain_mock.cell_count,
      'resolved': shock_cell_chain_mock.resolved,
      'state_carry_count': shock_cell_chain_mock.as_report()['state_carry_count'],
      'continuation_boundary_kinds': shock_cell_chain_mock.as_report()['continuation_boundary_kinds'],
      'continuation_total_pressure_ranges_Pa': shock_cell_chain_mock_report[
        'continuation_total_pressure_ranges_Pa'
      ],
      'continuation_boundary_maxima_nonincreasing': shock_cell_chain_mock_report[
        'continuation_boundary_maxima_nonincreasing'
      ],
      'observations': shock_cell_chain_mock_observations,
      'claim_status': (
        'deterministic-prescribed-next-shock-planner-mock; '
        'not-free-boundary-chain-evidence'
      ),
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
        'case': 'reflected_boundary_trace_extension',
        'status': reflected_trace_extension.status.value,
        'message': reflected_trace_extension.message,
      }
    ] if not reflected_trace_extension.converged else []),
    *([
      {
        'case': 'reflected_characteristic_zone_assembly',
        'status': reflected_zone.status.value,
        'message': reflected_zone.message,
      }
    ] if not reflected_zone.converged else []),
    *([
      {
        'case': 'reflected_source_characteristic_strip',
        'status': reflected_source_strip.status.value,
        'message': reflected_source_strip.message,
      }
    ] if not reflected_source_strip.converged else []),
    *([
      {
        'case': 'reflected_source_strip_constant_k_plus_extension',
        'status': reflected_simple_wave_extension.status.value,
        'message': reflected_simple_wave_extension.message,
      }
    ] if not reflected_simple_wave_extension.converged else []),
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
    *([
      {
        'case': 'sampled_attached_shock_fit',
        'status': sampled_shock_fit.status.value,
        'message': sampled_shock_fit.message,
      }
    ] if not sampled_shock_fit.converged else []),
    *([
      {
        'case': 'sampled_attached_shock_continuation',
        'status': sampled_continuation.status.value,
        'message': sampled_continuation.message,
      }
    ] if not sampled_continuation.converged else []),
    *([
      {
        'case': 'closed_post_shock_field_gate',
        'status': sampled_closed_gate.status.value,
        'message': sampled_closed_gate.message,
      }
    ] if sampled_closed_gate.status is not MocPostShockClosureStatus.GEOMETRY_FAILURE else []),
    *([
      {
        'case': 'shock_seeded_post_shock_field',
        'status': shock_seeded_field.status.value,
        'message': shock_seeded_field.message,
      }
    ] if not shock_seeded_field.converged else []),
    *([
      {
        'case': 'shock_seeded_field_refinement',
        'status': 'resolution_failure',
        'message': str(shock_seeded_refinement_failures),
      }
    ] if shock_seeded_refinement_failures else []),
    *([
      {
        'case': 'solver_generated_attached_shock_field',
        'status': solver_generated_shock.status.value,
        'message': solver_generated_shock.message,
      }
    ] if not solver_generated_shock.converged else []),
    *([
      {
        'case': 'solver_generated_shock_refinement',
        'status': 'resolution_failure',
        'message': str(solver_generated_shock_refinement_failures),
      }
    ] if solver_generated_shock_refinement_failures else []),
    *([
      {
        'case': 'solver_generated_chain_reference',
        'status': (
          'missing'
          if solver_generated_chain_reference is None
          else solver_generated_chain_reference.status.value
        ),
        'message': (
          'solver-generated chain reference did not produce three resolved '
          'state-carrying cells'
          if solver_generated_chain_reference is not None
          else 'solver-generated chain reference could not be constructed'
        ),
      }
    ] if solver_generated_chain_failure else []),
    *([
      {
        'case': 'shock_cell_chain_planner_mock',
        'status': shock_cell_chain_mock.status.value,
        'message': shock_cell_chain_mock.message,
      }
    ] if (
      not shock_cell_chain_mock.resolved
      or shock_cell_chain_mock_report['continuation_boundary_maxima_nonincreasing'] is not True
    ) else []),
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
      'extend the reflected MOC upstream state/pressure field beyond the terminal source window without crossing a characteristic caustic',
      'replace the provisional constant-invariant boundary with a physically validated downstream closure and a straddling canonical bracket',
      'production next-cell shock fitting that consumes the typed state/total-pressure handoff without a geometric template',
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
