"""Run the standalone planar-MOC primitive evidence gate."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from math import atan2, cos, isfinite, log, pi, sin, sqrt
from pathlib import Path
import sys
from typing import Any
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))

from exhaust_plume.models.moc import (  # noqa: E402
  CharacteristicFamily,
  CharacteristicState,
  MocAmbientClosureStatus,
  MocAmbientShockStripStatus,
  MocAmbientAxisClosureStatus,
  MocAmbientAxisClosureShootStatus,
  MocAmbientPhysicalFieldStatus,
  MocAmbientClosedChainSourceMode,
  MocBoundedUpstreamFieldSource,
  MocMixedRegimeBoundaryStatus,
  MocMixedRegimeControlSection,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeFieldSample,
  MocMixedRegimePlanarSolveStatus,
  MocMixedRegimePlanarPotentialReference,
  MocMixedRegimePlanarFrozenProfileReference,
  MocSolverGeneratedMixedRegimeClosureReference,
  MocInvariantClosureFamily,
  MocFreeBoundaryShockResult,
  MocPostShockClosureStatus,
  MocPostShockBoundaryState,
  MocPostShockChainCellSolve,
  MocPostShockCharacteristicFieldResult,
  MocPrescribedMixedRegimeClosureMock,
  MocPrescribedPostShockChainMock,
  MocPrescribedAmbientClosedPostShockChainMock,
  MocAmbientClosedPostShockChainCandidate,
  MocSolverGeneratedPostShockChainReference,
  MocSolverGeneratedAmbientClosedPostShockChainReference,
  MocTerminalReflectionPatchAmbientClosureChainReference,
  MocFieldCoupledPostShockChainReference,
  MocReflectedCharacteristicZoneResult,
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainContinuationPolicy,
  MocChainGeometryFidelity,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocChainStatus,
  MocChainPlannerKind,
  MocCausticFamilyBandEnvelopeStatus,
  MocCausticShockBridgeStatus,
  MocCausticShockRemeshStatus,
  MocCausticShockRemeshPreparationStatus,
  MocCausticUpstreamRemeshRequest,
  MocCausticUpstreamRemeshStatus,
  MocCausticSimpleWaveTerminalStatus,
  MocCausticSimpleWaveTraceStatus,
  MocCausticBridgeSide,
  MocCausticBridgeStatus,
  MocCausticUpstreamContinuationStatus,
  build_caustic_upstream_bridge,
  sample_caustic_upstream_bridge,
  plan_caustic_family_band_chain,
  plan_caustic_family_band_invariant_chain,
  plan_caustic_upstream_continuation,
  plan_caustic_upstream_bridge_chain,
  plan_caustic_upstream_bridge_invariant_chain,
  plan_ambient_pressure_field_chain,
  plan_ambient_closed_post_shock_chain,
  plan_prescribed_ambient_closed_post_shock_chain_mock,
  plan_ambient_closed_post_shock_chain_terminal_patch,
  plan_ambient_closed_post_shock_chain_terminal_patch_mock,
  plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure,
  plan_post_shock_characteristic_chain,
  plan_field_coupled_post_shock_chain_reference,
  plan_solver_generated_ambient_closed_post_shock_chain_reference,
  plan_post_shock_field_invariant_chain,
  plan_post_shock_zone_chain,
  plan_source_strip_shock_chain,
  plan_source_strip_shock_chain_sequence,
  plan_terminal_reflection_patch_chain,
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
  solve_terminal_compression_candidate,
  assemble_terminal_trace_centerline_patch,
  assemble_first_cell_composite,
  assemble_first_cell_terminal_shock_field,
  solve_marched_attached_shock_from_terminal_reflection_patch,
  solve_marched_attached_shock_from_caustic_family_band,
  solve_marched_attached_shock_from_caustic_family_band_with_invariant_boundary,
  solve_marched_attached_shock_from_caustic_upstream_bridge,
  solve_marched_attached_shock_from_caustic_upstream_bridge_with_invariant_boundary,
  solve_normal_shock_terminal,
  solve_marched_attached_shock_chain_cell_or_termination,
  solve_marched_attached_shock_chain_cell_from_reflected_zone_or_termination,
  solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_from_reflected_zone,
  solve_marched_attached_shock_from_source_strip,
  solve_marched_attached_shock_with_ambient_pressure_closure,
  solve_marched_attached_shock_with_ambient_pressure_closure_from_reflected_zone,
  solve_marched_attached_shock_with_ambient_attachment_closure,
  solve_marched_ambient_attachment_shock_cell_transition,
  solve_marched_attached_shock_with_constant_invariant_closure,
  solve_mixed_regime_compressible_potential_field,
  solve_mixed_regime_subsonic_field,
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
  assemble_ambient_shock_characteristic_strip,
  build_caustic_shock_seed,
  resolve_caustic_shock_seed,
  solve_caustic_shock_bridge,
  prepare_caustic_shock_remesh,
  solve_caustic_shock_remesh,
  solve_caustic_shock_remesh_from_upstream_bridge,
  solve_caustic_upstream_remesh,
  solve_caustic_simple_wave_terminal_remesh,
  plan_caustic_shock_remesh_chain,
  plan_caustic_shock_remesh_chain_from_upstream_bridge,
  plan_caustic_upstream_remesh_shock_chain,
  plan_caustic_upstream_remesh_shock_chain_sequence,
  plan_caustic_simple_wave_terminal_chain,
  plan_caustic_remesh_downstream_field_chain,
  plan_caustic_remesh_downstream_field_invariant_chain,
  plan_prescribed_first_cell_terminal_closure_mock,
  plan_solver_generated_first_cell_terminal_closure_reference,
  restart_characteristic_family_from_caustic,
  trace_caustic_family_band_forward_envelope,
  extend_source_characteristic_strip_centerline_reflection,
  extend_source_characteristic_strip_constant_k_plus,
  march_post_shock_ambient_boundary,
  probe_post_shock_ambient_axis_closure,
  solve_marched_attached_shock_with_ambient_axis_closure,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_marched_attached_shock_with_ambient_physical_field,
  solve_ambient_closed_post_shock_chain_cell_from_physical_field_or_termination,
  sample_reflected_zone_along_shock_path,
  validate_fan_reflected_interface,
  validate_closed_post_shock_field,
  validate_mixed_regime_control_section,
  run_mixed_regime_planar_field_solver,
  validate_characteristic_trace,
  validate_mixed_regime_boundary,
  validate_mixed_regime_downstream_condition,
  validate_post_shock_ambient_boundary,
  validate_moc_mesh,
)
from exhaust_plume.validation.moc_measurements import (  # noqa: E402
  MocCausticRemeshMeasurementStatus,
  MocCausticRemeshObservation,
  MocMixedRegimeFreeBoundaryMeasurementStatus,
  MocMixedRegimeFreeBoundaryRefinementCase,
  MocMixedRegimeFreeBoundaryRefinementMeasurementStatus,
  MocTerminalClosureObservation,
  MocShockCellObservation,
  MocShockCellChainRefinementCase,
  measure_moc_caustic_remesh,
  measure_moc_chain_planner,
  measure_mixed_regime_control_section,
  measure_mixed_regime_free_boundary_reference,
  measure_mixed_regime_free_boundary_refinement,
  measure_mixed_regime_compressible_potential_field,
  measure_moc_terminal_closure,
  measure_moc_shock_cell,
  measure_moc_shock_cell_chain,
  measure_moc_shock_cell_chain_refinement,
)
from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput  # noqa: E402
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit  # noqa: E402
from exhaust_plume.util.aero.shock_validity import ShockBranch, ShockSolveStatus  # noqa: E402


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


def _shock_seeded_field_fit() -> MocShockBoundaryFitResult:
  """Return the varied prescribed shock fit used by the field fixture."""

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
  return MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=samples,
    shock_angle_residuals_rad=(0.0,) * len(samples),
    maximum_shock_angle_residual_rad=0.0,
  )


def _shock_seeded_field_fixture() -> MocPostShockCharacteristicFieldResult:
  """Assemble a varied prescribed field to exercise the full-field contract.

  This fixture is deliberately not a free-boundary solution.  It supplies a
  turning post-shock boundary so the characteristic fan has finite cell area;
  the report records it as a solver-contract fixture rather than validation
  or provider evidence.
  """

  return assemble_post_shock_characteristic_field(_shock_seeded_field_fit())


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


def _ambient_shock_strip_probe(
  solver_generated_shock: MocFreeBoundaryShockResult,
) -> dict[str, Any]:
  """Exercise the correctly oriented physical shock/ambient strip seam."""

  shock_fit = solver_generated_shock.shock_fit
  if shock_fit is None or not shock_fit.converged or not shock_fit.boundary_states:
    return {
      'status': 'shock_boundary_failure',
      'accepted': False,
      'message': 'solver-generated shock fixture did not provide a converged shock fit',
      'claim_status': 'shock-plus-ambient-strip-pending',
    }
  first = shock_fit.boundary_states[0]
  state = first.state
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))
  march = march_post_shock_ambient_boundary(
    shock_fit,
    ambient_pressure,
  )
  if not march.converged:
    return {
      'status': march.status.value,
      'accepted': False,
      'ambient_pressure_Pa': ambient_pressure,
      'march': march.as_report(),
      'message': march.message,
      'claim_status': 'shock-plus-ambient-strip-pending',
    }
  ambient_axis_closure = probe_post_shock_ambient_axis_closure(
    march,
    ambient_pressure,
  )
  upstream_reference = solver_generated_shock.upstream_states[0]
  upstream_reference_pressure = solver_generated_shock.upstream_pressure_Pa[0]
  shock_start_y_m = shock_fit.boundary_states[0].point_m[1]
  ambient_axis_closure_shoot = (
    solve_marched_attached_shock_with_ambient_axis_closure(
      lambda point: replace(
        upstream_reference,
        x_m=point[0],
        y_m=point[1],
      ),
      lambda _point: upstream_reference_pressure,
      lambda parameter: (parameter, shock_start_y_m),
      0.7,
      0.8,
      ambient_pressure,
      0.02,
      0.12,
      sample_count=9,
    )
  )
  ambient_axis_closure_shoot_probe_accepted = (
    ambient_axis_closure_shoot.status
    is MocAmbientAxisClosureShootStatus.BRACKET_FAILURE
    and len(ambient_axis_closure_shoot.trials) == 2
    and all(
      trial.residual is not None
      and trial.axis_closure is not None
      and trial.axis_closure.axis_candidate_verified
      and not trial.axis_closure.ambient_pressure_verified
      and not trial.axis_closure.axis_boundary_verified
      for trial in ambient_axis_closure_shoot.trials
    )
    and not ambient_axis_closure_shoot.physical_closure_verified
    and ambient_axis_closure_shoot.chain_promotion_blocked
  )
  ambient_axis_closure_shoot_reference = (
    solve_marched_attached_shock_with_ambient_axis_closure(
      lambda point: replace(
        upstream_reference,
        x_m=point[0],
        y_m=point[1],
        mach=2.0 + (point[0] - 0.5),
      ),
      lambda _point: upstream_reference_pressure,
      lambda parameter: (parameter, shock_start_y_m),
      0.7,
      0.8,
      ambient_pressure,
      0.02,
      0.12,
      sample_count=9,
      maximum_attachment_shooting_iterations=30,
    )
  )
  ambient_axis_closure_shoot_reference_accepted = (
    ambient_axis_closure_shoot_reference.status
    is MocAmbientAxisClosureShootStatus.CONVERGED_AXIS_PRESSURE
    and ambient_axis_closure_shoot_reference.converged
    and ambient_axis_closure_shoot_reference.axis_pressure_closure_verified
    and ambient_axis_closure_shoot_reference.closure_residual is not None
    and abs(ambient_axis_closure_shoot_reference.closure_residual) <= 1.0e-8
    and not ambient_axis_closure_shoot_reference.physical_closure_verified
    and not ambient_axis_closure_shoot_reference.axis_boundary_verified
    and ambient_axis_closure_shoot_reference.chain_promotion_blocked
  )
  ambient_physical_field = (
    solve_marched_attached_shock_with_ambient_physical_field(
      lambda point: replace(
        upstream_reference,
        x_m=point[0],
        y_m=point[1],
      ),
      lambda _point: upstream_reference_pressure,
      lambda parameter: (parameter, shock_start_y_m),
      0.7,
      0.8,
      ambient_pressure,
      0.02,
      0.12,
      sample_count=9,
    )
  )
  ambient_physical_field_probe_accepted = (
    ambient_physical_field.status
    is MocAmbientPhysicalFieldStatus.AXIS_SHOOT_FAILURE
    and ambient_physical_field.axis_closure_shoot is not None
    and ambient_physical_field.axis_closure_shoot.status
    is MocAmbientAxisClosureShootStatus.BRACKET_FAILURE
    and ambient_physical_field.field is None
    and not ambient_physical_field.physical_closure_verified
    and ambient_physical_field.chain_promotion_blocked
  )
  ambient_physical_field_reference = (
    solve_marched_attached_shock_with_ambient_physical_field(
      lambda point: replace(
        upstream_reference,
        x_m=point[0],
        y_m=point[1],
        mach=2.0 + (point[0] - 0.5),
      ),
      lambda _point: upstream_reference_pressure,
      lambda parameter: (parameter, shock_start_y_m),
      0.7,
      0.8,
      ambient_pressure,
      0.02,
      0.12,
      sample_count=9,
      maximum_attachment_shooting_iterations=30,
    )
  )
  ambient_physical_field_reference_accepted = (
    ambient_physical_field_reference.status
    is MocAmbientPhysicalFieldStatus.AXIS_BOUNDARY_FAILURE
    and ambient_physical_field_reference.axis_closure_shoot is not None
    and ambient_physical_field_reference.axis_closure_shoot.axis_pressure_closure_verified
    and not ambient_physical_field_reference.axis_closure_shoot.axis_boundary_verified
    and ambient_physical_field_reference.field is None
    and not ambient_physical_field_reference.physical_closure_verified
    and ambient_physical_field_reference.chain_promotion_blocked
  )
  ambient_centerline_physical_field = (
    solve_marched_attached_shock_with_ambient_centerline_physical_field(
      lambda point: replace(
        upstream_reference,
        x_m=point[0],
        y_m=point[1],
      ),
      lambda _point: upstream_reference_pressure,
      (0.5, shock_start_y_m),
      ambient_pressure,
      0.02,
      0.12,
      sample_count=9,
    )
  )
  ambient_centerline_physical_field_accepted = (
    ambient_centerline_physical_field.status
    is MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
    and ambient_centerline_physical_field.converged
    and ambient_centerline_physical_field.physical_closure_verified
    and ambient_centerline_physical_field.state_sampling_available
    and ambient_centerline_physical_field.upstream_coupling_verified
    and not ambient_centerline_physical_field.chain_promotion_blocked
    and not ambient_centerline_physical_field.production_claim_allowed
    and ambient_centerline_physical_field.axis_closure_shoot is None
    and ambient_centerline_physical_field.ambient_attachment is not None
    and ambient_centerline_physical_field.ambient_attachment.converged
    and ambient_centerline_physical_field.field is not None
    and ambient_centerline_physical_field.field.node_count == 45
    and ambient_centerline_physical_field.field.cell_count == 53
  )
  ambient_centerline_physical_field_refinement = []
  ambient_centerline_physical_field_refinement_results = {}
  for refinement_sample_count in (5, 9, 17):
    if refinement_sample_count == 9:
      refinement_result = ambient_centerline_physical_field
    else:
      refinement_result = (
        solve_marched_attached_shock_with_ambient_centerline_physical_field(
          lambda point: replace(
            upstream_reference,
            x_m=point[0],
            y_m=point[1],
          ),
          lambda _point: upstream_reference_pressure,
          (0.5, shock_start_y_m),
          ambient_pressure,
          0.02,
          0.12,
          sample_count=refinement_sample_count,
        )
      )
    ambient_centerline_physical_field_refinement_results[refinement_sample_count] = (
      refinement_result
    )
    refinement_field = refinement_result.field
    ambient_centerline_physical_field_refinement.append({
      'sample_count': refinement_sample_count,
      'status': refinement_result.status.value,
      'converged': refinement_result.converged,
      'physical_closure_verified': refinement_result.physical_closure_verified,
      'state_sampling_available': refinement_result.state_sampling_available,
      'upstream_coupling_verified': refinement_result.upstream_coupling_verified,
      'node_count': None if refinement_field is None else refinement_field.node_count,
      'cell_count': None if refinement_field is None else refinement_field.cell_count,
      'maximum_geometry_residual_m': (
        None
        if refinement_field is None
        else refinement_field.maximum_geometry_residual_m
      ),
      'maximum_absolute_invariant_residual': (
        None
        if refinement_field is None
        else refinement_field.maximum_absolute_invariant_residual
      ),
      'message': refinement_result.message,
    })
  ambient_centerline_physical_field_refinement_accepted = (
    len(ambient_centerline_physical_field_refinement) == 3
    and all(
      case['status'] == MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED.value
      and case['converged'] is True
      and case['physical_closure_verified'] is True
      and case['state_sampling_available'] is True
      and case['upstream_coupling_verified'] is True
      and isinstance(case['node_count'], int)
      and isinstance(case['cell_count'], int)
      and case['node_count'] > 0
      and case['cell_count'] > 0
      and case['maximum_geometry_residual_m'] is not None
      and case['maximum_absolute_invariant_residual'] is not None
      for case in ambient_centerline_physical_field_refinement
    )
  )
  ambient_centerline_physical_chain_probe = None
  ambient_centerline_physical_chain_probe_accepted = False
  ambient_centerline_physical_chain_mock = None
  ambient_centerline_physical_chain_mock_accepted = False
  ambient_centerline_physical_generated_chain = None
  ambient_centerline_physical_generated_chain_accepted = False
  ambient_centerline_physical_reflected_source_chain = None
  ambient_centerline_physical_reflected_source_chain_accepted = False
  ambient_centerline_physical_terminal_source_chain = None
  ambient_centerline_physical_terminal_source_chain_accepted = False
  ambient_centerline_physical_terminal_patch_planner = None
  ambient_centerline_physical_terminal_patch_planner_accepted = False
  ambient_centerline_physical_terminal_patch_mixed_regime_planner = None
  ambient_centerline_physical_terminal_patch_mixed_regime_planner_accepted = False
  ambient_centerline_physical_terminal_patch_ambient_closure_chain = None
  ambient_centerline_physical_terminal_patch_ambient_closure_chain_accepted = False
  ambient_centerline_physical_terminal_patch_refinement = []
  ambient_centerline_physical_terminal_patch_refinement_accepted = False
  if (
    ambient_centerline_physical_field_accepted
    and ambient_centerline_physical_field.field is not None
    and ambient_centerline_physical_field.ambient_attachment is not None
    and ambient_centerline_physical_field.ambient_attachment.ambient_march is not None
  ):
    physical_field = ambient_centerline_physical_field.field
    mesh_points = tuple(
      point
      for cell in physical_field.cells
      for point in cell.vertices_xr_m
    )
    seed_end_x_m = max(point[0] for point in mesh_points)
    candidate_points = ((2.1, 0.3), (2.3, 0.15), (2.5, 0.0))
    candidate_ambient_samples = tuple(
      replace(
        sample,
        point_m=point,
        state=replace(sample.state, x_m=point[0], y_m=point[1]),
      )
      for point, sample in zip(
        candidate_points,
        ambient_centerline_physical_field.ambient_attachment.ambient_march.boundary_samples,
        strict=False,
      )
    )

    def solve_ambient_physical_chain_next(
      current_cell,
      next_cell_index,
      incoming_handoff,
    ):
      return solve_ambient_closed_post_shock_chain_cell_from_physical_field_or_termination(
        current_cell,
        next_cell_index,
        incoming_handoff,
        physical_field,
        shock_points_m=candidate_points,
        downstream_flow_angles_rad=(0.03, 0.015, 0.0),
        ambient_boundary=candidate_ambient_samples,
        ambient_pressure_Pa=ambient_pressure,
        end_x_m=2.6,
      )

    physical_chain_planner = plan_ambient_closed_post_shock_chain(
      physical_field,
      solve_ambient_physical_chain_next,
      start_x_m=shock_fit.boundary_states[0].point_m[0],
      end_x_m=seed_end_x_m,
      policy=MocChainContinuationPolicy(max_cells=2),
    )
    ambient_centerline_physical_chain_probe = physical_chain_planner.as_report()
    ambient_centerline_physical_chain_probe_accepted = (
      physical_chain_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
      and physical_chain_planner.production_claim_allowed is False
      and physical_chain_planner.chain.resolved
      and physical_chain_planner.chain.cell_count == 1
      and physical_chain_planner.chain.termination_reason
      is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      and physical_chain_planner.chain.physical_termination is False
      and len(physical_chain_planner.steps) == 1
      and physical_chain_planner.steps[0].result_kind == 'termination-returned'
      and physical_chain_planner.steps[0].result_termination_reason
      == MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value
    )
    prescribed_physical_chain_candidate = MocAmbientClosedPostShockChainCandidate(
      shock_points_m=candidate_points,
      downstream_flow_angles_rad=(0.03, 0.015, 0.0),
      ambient_boundary=candidate_ambient_samples,
      ambient_pressure_Pa=ambient_pressure,
      end_x_m=2.6,
    )
    prescribed_physical_chain_mock = MocPrescribedAmbientClosedPostShockChainMock(
      candidates=(prescribed_physical_chain_candidate,),
    )
    prescribed_physical_chain_planner = (
      plan_prescribed_ambient_closed_post_shock_chain_mock(
        physical_field,
        start_x_m=shock_fit.boundary_states[0].point_m[0],
        end_x_m=seed_end_x_m,
        mock=prescribed_physical_chain_mock,
        policy=MocChainContinuationPolicy(
          max_cells=2,
          require_state_carry=True,
        ),
      )
    )
    ambient_centerline_physical_chain_mock = (
      prescribed_physical_chain_planner.as_report()
    )
    ambient_centerline_physical_chain_mock_accepted = (
      prescribed_physical_chain_planner.planner_kind
      is MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
      and prescribed_physical_chain_planner.production_claim_allowed is False
      and prescribed_physical_chain_planner.chain.resolved
      and prescribed_physical_chain_planner.chain.cell_count == 1
      and prescribed_physical_chain_planner.chain.termination_reason
      is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      and prescribed_physical_chain_planner.chain.physical_termination is False
      and len(prescribed_physical_chain_planner.steps) == 1
      and prescribed_physical_chain_planner.steps[0].result_kind
      == 'termination-returned'
      and prescribed_physical_chain_planner.steps[0].result_termination_reason
      == MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      and prescribed_physical_chain_planner.diagnostics[
        'prescribed_ambient_closed_chain_mock'
      ]['candidate_count'] == 1
      and prescribed_physical_chain_planner.diagnostics[
        'prescribed_ambient_closed_chain_mock'
      ]['physical_chain_promotion_allowed'] is False
    )
    generated_chain_source = MocBoundedUpstreamFieldSource(
      state_at=lambda point: replace(
        upstream_reference,
        x_m=point[0],
        y_m=point[1],
      ),
      static_pressure_at=lambda _point: upstream_reference_pressure,
      model='uniform-upstream-reference-source',
      domain_x_extent_m=(0.0, 10.0),
      domain_y_extent_m=(0.0, shock_start_y_m),
    )
    generated_chain_reference = (
      MocSolverGeneratedAmbientClosedPostShockChainReference(
        total_cell_count=3,
        cell_axial_length_m=0.4,
        shock_start_offset_m=0.02,
        shock_start_y_m=shock_start_y_m,
        ambient_pressure_Pa=ambient_pressure,
        outer_downstream_flow_angle_lower_rad=0.02,
        outer_downstream_flow_angle_upper_rad=0.12,
        sample_count=9,
        upstream_source_provider=lambda *_args: generated_chain_source,
      )
    )
    generated_chain_planner = (
      plan_solver_generated_ambient_closed_post_shock_chain_reference(
        physical_field,
        start_x_m=shock_fit.boundary_states[0].point_m[0],
        end_x_m=seed_end_x_m,
        reference=generated_chain_reference,
        policy=MocChainContinuationPolicy(
          max_cells=4,
          require_state_carry=True,
        ),
      )
    )
    ambient_centerline_physical_generated_chain = generated_chain_planner.as_report()
    ambient_centerline_physical_generated_chain_accepted = (
      generated_chain_planner.planner_kind
      is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
      and generated_chain_planner.production_claim_allowed is False
      and generated_chain_planner.chain.resolved
      and generated_chain_planner.chain.cell_count == 3
      and generated_chain_planner.chain.termination_reason
      is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
      and generated_chain_planner.chain.physical_termination is False
      and generated_chain_planner.handoff_links_verified is True
      and [step.result_kind for step in generated_chain_planner.steps] == [
        'physical-field-solve-returned',
        'physical-field-solve-returned',
        'termination-returned',
      ]
      and generated_chain_planner.diagnostics[
        'solver_generated_ambient_closed_chain_reference'
      ]['physical_chain_promotion_allowed'] is False
      and generated_chain_planner.diagnostics[
        'solver_generated_ambient_closed_chain_reference'
      ]['upstream_source_model'] == 'callback-supplied-bounded-source'
    )
    reflected_source_reference = (
      MocSolverGeneratedAmbientClosedPostShockChainReference(
        total_cell_count=2,
        shock_start_y_m=shock_start_y_m,
        ambient_pressure_Pa=ambient_pressure,
        outer_downstream_flow_angle_lower_rad=0.02,
        outer_downstream_flow_angle_upper_rad=0.12,
        sample_count=9,
        upstream_source_mode=(
          MocAmbientClosedChainSourceMode.TERMINAL_REFLECTION_PATCH
        ),
      )
    )
    reflected_source_planner = (
      plan_solver_generated_ambient_closed_post_shock_chain_reference(
        physical_field,
        start_x_m=shock_fit.boundary_states[0].point_m[0],
        end_x_m=physical_field.ambient_boundary_points_m[-1][0],
        reference=reflected_source_reference,
        policy=MocChainContinuationPolicy(
          max_cells=2,
          require_state_carry=True,
        ),
      )
    )
    reflected_source_planner_report = reflected_source_planner.as_report()
    reflected_source_report = reflected_source_planner.chain.diagnostics.get(
      'upstream_source'
    )
    ambient_centerline_physical_reflected_source_chain_accepted = (
      reflected_source_planner.planner_kind
      is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
      and reflected_source_planner.production_claim_allowed is False
      and reflected_source_planner.chain.resolved
      and reflected_source_planner.chain.cell_count == 1
      and reflected_source_planner.chain.physical_termination is False
      and reflected_source_planner.chain.termination_reason
      is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      and len(reflected_source_planner.steps) == 1
      and reflected_source_planner.steps[0].result_kind == 'termination-returned'
      and reflected_source_planner.steps[0].result_termination_reason
      == MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE.value
      and isinstance(reflected_source_report, dict)
      and reflected_source_report['model'] == 'bounded-terminal-reflection-patch'
    )
    ambient_centerline_physical_reflected_source_chain = {
      'accepted': ambient_centerline_physical_reflected_source_chain_accepted,
      'source': reflected_source_report,
      'planner': reflected_source_planner_report,
      'claim_status': (
        'solver-owned-terminal-reflection-patch-source-reaches-ambient-'
        'attachment-closure-boundary; no extrapolation or next-cell promotion'
      ),
    }
    terminal_source = MocBoundedUpstreamFieldSource(
      state_at=lambda point: CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      ),
      static_pressure_at=lambda _point: 100000.0,
      model='uniform-normal-shock-terminal-reference-source',
      domain_x_extent_m=(0.0, 10.0),
      domain_y_extent_m=(0.0, shock_start_y_m),
    )
    terminal_source_compression = solve_attached_compression_to_turn(
      upstream_mach=2.0,
      gamma=1.4,
      upstream_pressure_Pa=100000.0,
      target_turn_rad=0.05,
    )
    if terminal_source_compression.downstream_pressure_Pa is not None:
      terminal_source_reference = MocSolverGeneratedAmbientClosedPostShockChainReference(
        total_cell_count=2,
        shock_start_y_m=shock_start_y_m,
        ambient_pressure_Pa=terminal_source_compression.downstream_pressure_Pa,
        outer_downstream_flow_angle_lower_rad=0.02,
        outer_downstream_flow_angle_upper_rad=0.12,
        sample_count=9,
        upstream_source_provider=lambda *_args, source=terminal_source: source,
      )
      terminal_source_planner = (
        plan_solver_generated_ambient_closed_post_shock_chain_reference(
          physical_field,
          start_x_m=shock_fit.boundary_states[0].point_m[0],
          end_x_m=physical_field.ambient_boundary_points_m[-1][0],
          reference=terminal_source_reference,
          policy=MocChainContinuationPolicy(
            max_cells=2,
            require_state_carry=True,
          ),
        )
      )
      ambient_centerline_physical_terminal_source_chain_accepted = (
        terminal_source_planner.planner_kind
        is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
        and terminal_source_planner.production_claim_allowed is False
        and terminal_source_planner.chain.resolved
        and terminal_source_planner.chain.cell_count == 1
        and terminal_source_planner.chain.physical_termination is True
        and terminal_source_planner.chain.termination_reason
        is MocChainTerminationReason.PHYSICAL_TERMINATION
        and len(terminal_source_planner.steps) == 1
        and terminal_source_planner.steps[0].result_kind == 'termination-returned'
        and terminal_source_planner.steps[0].result_termination_reason
        == MocChainTerminationReason.PHYSICAL_TERMINATION.value
        and terminal_source_planner.chain.diagnostics.get(
          'termination_model'
        ) == 'normal-shock-terminal'
        and terminal_source_planner.chain.diagnostics.get('shock_status')
        == 'subsonic_terminal_required'
      )
      ambient_centerline_physical_terminal_source_chain = {
        'accepted': ambient_centerline_physical_terminal_source_chain_accepted,
        'planner': terminal_source_planner.as_report(),
        'source': terminal_source.as_report(),
        'ambient_pressure_Pa': terminal_source_compression.downstream_pressure_Pa,
        'claim_status': (
          'independent-generated-chain-normal-shock-terminal-mapping; '
          'mixed-regime-downstream-field-remains-outside-supersonic-chain'
        ),
      }
    else:
      ambient_centerline_physical_terminal_source_chain = {
        'accepted': False,
        'source': terminal_source.as_report(),
        'claim_status': 'normal-shock-terminal-fixture-compression-failed',
      }
    terminal_patch_planner = plan_ambient_closed_post_shock_chain_terminal_patch(
      physical_field,
      start_x_m=shock_fit.boundary_states[0].point_m[0],
      end_x_m=physical_field.ambient_boundary_points_m[-1][0],
      terminal_end_x_m=physical_field.centerline_boundary_points_m[-1][0] + 0.25,
      downstream_flow_angle_rad=0.0,
      sample_count=9,
      trace_position_tolerance_m=1.0e-3,
      seam_position_tolerance_m=3.0e-3,
      position_tolerance_m=1.0e-3,
      policy=MocChainContinuationPolicy(
        max_cells=2,
        require_state_carry=True,
      ),
    )
    ambient_centerline_physical_terminal_patch_planner = terminal_patch_planner.as_report()
    ambient_centerline_physical_terminal_patch_planner_accepted = (
      terminal_patch_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
      and terminal_patch_planner.production_claim_allowed is False
      and terminal_patch_planner.chain.resolved
      and terminal_patch_planner.chain.cell_count == 1
      and terminal_patch_planner.chain.physical_termination
      and terminal_patch_planner.chain.termination_reason
      is MocChainTerminationReason.PHYSICAL_TERMINATION
      and len(terminal_patch_planner.steps) == 1
      and terminal_patch_planner.steps[0].result_kind == 'termination-returned'
      and terminal_patch_planner.steps[0].result_termination_reason
      == MocChainTerminationReason.PHYSICAL_TERMINATION.value
      and terminal_patch_planner.chain.diagnostics.get('centerline_seam_verified') is True
    )
    terminal_patch_mixed_regime_planner = (
      plan_ambient_closed_post_shock_chain_terminal_patch_mock(
        physical_field,
        start_x_m=shock_fit.boundary_states[0].point_m[0],
        end_x_m=physical_field.ambient_boundary_points_m[-1][0],
        terminal_end_x_m=physical_field.centerline_boundary_points_m[-1][0] + 0.25,
        sample_count=9,
        trace_position_tolerance_m=1.0e-3,
        seam_position_tolerance_m=3.0e-3,
        position_tolerance_m=1.0e-3,
        policy=MocChainContinuationPolicy(
          max_cells=2,
          require_state_carry=True,
        ),
      )
    )
    ambient_centerline_physical_terminal_patch_mixed_regime_planner = (
      terminal_patch_mixed_regime_planner.as_report()
    )
    ambient_centerline_physical_terminal_patch_mixed_regime_planner_accepted = (
      terminal_patch_mixed_regime_planner.planner_kind
      is MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
      and terminal_patch_mixed_regime_planner.production_claim_allowed is False
      and terminal_patch_mixed_regime_planner.resolved
      and terminal_patch_mixed_regime_planner.physical_termination
      and terminal_patch_mixed_regime_planner.physical_closure_verified is False
      and terminal_patch_mixed_regime_planner.chain_promotion_blocked
      and terminal_patch_mixed_regime_planner.transition is not None
      and terminal_patch_mixed_regime_planner.transition.mixed_regime_seam_available
      and terminal_patch_mixed_regime_planner.mixed_regime_closure is not None
      and terminal_patch_mixed_regime_planner.mixed_regime_closure.converged
      and terminal_patch_mixed_regime_planner.mixed_regime_model_closure_verified
      and terminal_patch_mixed_regime_planner.diagnostics[
        'mixed_regime_closure_attached'
      ] is False
    )
    terminal_patch_ambient_closure_reference = (
      MocTerminalReflectionPatchAmbientClosureChainReference(
        total_cell_count=2,
      )
    )
    terminal_patch_ambient_closure_end_x_m = max(
      seed_end_x_m,
      physical_field.ambient_boundary_points_m[-1][0] + 2.0,
    )
    terminal_patch_ambient_closure_planner = (
      plan_ambient_closed_post_shock_chain_terminal_reflection_patch_ambient_closure(
        physical_field,
        start_x_m=shock_fit.boundary_states[0].point_m[0],
        end_x_m=terminal_patch_ambient_closure_end_x_m,
        reference=terminal_patch_ambient_closure_reference,
        policy=MocChainContinuationPolicy(
          max_cells=4,
          require_state_carry=True,
        ),
      )
    )
    ambient_centerline_physical_terminal_patch_ambient_closure_chain = (
      terminal_patch_ambient_closure_planner.as_report()
    )
    ambient_centerline_physical_terminal_patch_ambient_closure_chain_accepted = (
      terminal_patch_ambient_closure_planner.planner_kind
      is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
      and terminal_patch_ambient_closure_planner.production_claim_allowed is False
      and terminal_patch_ambient_closure_planner.chain.resolved
      and terminal_patch_ambient_closure_planner.chain.cell_count == 2
      and terminal_patch_ambient_closure_planner.chain.physical_termination is False
      and terminal_patch_ambient_closure_planner.chain.termination_reason
      is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
      and terminal_patch_ambient_closure_planner.handoff_links_verified is True
      and [
        step.result_kind
        for step in terminal_patch_ambient_closure_planner.steps
      ] == [
        'physical-field-solve-returned',
        'termination-returned',
      ]
      and terminal_patch_ambient_closure_planner.diagnostics[
        'terminal_reflection_patch_ambient_closure_chain_reference'
      ]['physical_chain_promotion_allowed'] is True
      and terminal_patch_ambient_closure_planner.diagnostics[
        'requested_end_x_m'
      ] == terminal_patch_ambient_closure_end_x_m
      and terminal_patch_ambient_closure_planner.diagnostics[
        'endpoint_policy'
      ].startswith('use-next-field-ambient-boundary-endpoint')
    )
    for refinement_sample_count in (5, 9, 17):
      refinement_result = ambient_centerline_physical_field_refinement_results.get(
        refinement_sample_count
      )
      refinement_field = (
        None if refinement_result is None else refinement_result.field
      )
      if refinement_field is None:
        ambient_centerline_physical_terminal_patch_refinement.append({
          'sample_count': refinement_sample_count,
          'accepted': False,
          'status': 'missing-physical-field',
        })
        continue
      refinement_planner = plan_ambient_closed_post_shock_chain_terminal_patch(
        refinement_field,
        start_x_m=shock_fit.boundary_states[0].point_m[0],
        end_x_m=refinement_field.ambient_boundary_points_m[-1][0],
        terminal_end_x_m=refinement_field.centerline_boundary_points_m[-1][0] + 0.25,
        downstream_flow_angle_rad=0.0,
        sample_count=refinement_sample_count,
        trace_position_tolerance_m=1.0e-3,
        seam_position_tolerance_m=3.0e-3,
        position_tolerance_m=1.0e-3,
        policy=MocChainContinuationPolicy(
          max_cells=2,
          require_state_carry=True,
        ),
      )
      refinement_decision = refinement_planner.chain
      ambient_centerline_physical_terminal_patch_refinement.append({
        'sample_count': refinement_sample_count,
        'accepted': (
          refinement_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
          and refinement_planner.production_claim_allowed is False
          and refinement_decision.resolved
          and refinement_decision.cell_count == 1
          and refinement_decision.physical_termination
          and refinement_decision.termination_reason
          is MocChainTerminationReason.PHYSICAL_TERMINATION
          and len(refinement_planner.steps) == 1
          and refinement_decision.diagnostics.get('centerline_seam_verified') is True
        ),
        'status': refinement_decision.status.value,
        'termination_reason': refinement_decision.termination_reason.value,
        'physical_termination': refinement_decision.physical_termination,
        'cell_count': refinement_decision.cell_count,
        'centerline_seam_verified': refinement_decision.diagnostics.get(
          'centerline_seam_verified'
        ),
        'terminal_shock_point_m': refinement_decision.diagnostics.get(
          'terminal_shock_point_m'
        ),
        'message': refinement_decision.message,
      })
    ambient_centerline_physical_terminal_patch_refinement_accepted = (
      len(ambient_centerline_physical_terminal_patch_refinement) == 3
      and all(
        case['accepted'] is True
        and case['termination_reason'] == MocChainTerminationReason.PHYSICAL_TERMINATION.value
        and case['physical_termination'] is True
        and case['cell_count'] == 1
        and case['centerline_seam_verified'] is True
        for case in ambient_centerline_physical_terminal_patch_refinement
      )
    )
  ambient_axis_closure_probe_accepted = (
    ambient_axis_closure.status is MocAmbientAxisClosureStatus.PRESSURE_FAILURE
    and ambient_axis_closure.axis_candidate_verified
    and not ambient_axis_closure.ambient_pressure_verified
    and not ambient_axis_closure.axis_boundary_verified
    and not ambient_axis_closure.physical_closure_verified
    and ambient_axis_closure.chain_promotion_blocked
  )
  strip = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )
  terminal_patch = assemble_terminal_trace_centerline_patch(
    strip,
    trace_position_tolerance_m=2.0e-4,
  )
  terminal_patch_shock_probe = None
  terminal_patch_chain_probe = None
  terminal_patch_chain_planner = None
  terminal_patch_chain_planner_measurement = None
  first_cell_composite = None
  first_cell_composite_measurement = None
  first_cell_terminal_closure = None
  first_cell_terminal_closure_planner = None
  first_cell_terminal_closure_free_boundary_planner = None
  first_cell_terminal_closure_free_boundary_result = None
  first_cell_terminal_closure_free_boundary_measurement = None
  first_cell_terminal_closure_free_boundary_refinement_measurement = None
  if terminal_patch.converged:
    terminal_patch_shock_probe = solve_marched_attached_shock_from_terminal_reflection_patch(
      terminal_patch,
      terminal_patch.outgoing_trace_points_m[0],
      downstream_flow_angle_rad=0.0,
      sample_count=len(terminal_patch.outgoing_trace_points_m),
      position_tolerance_m=2.0e-4,
    )
    if solver_generated_shock.field is not None:
      current_cell = solver_generated_shock.field.as_coupled_chain_cell(
        start_x_m=0.5,
        end_x_m=1.0,
      )
      current_cell = replace(
        current_cell,
        continuation_boundary=terminal_patch.outgoing_trace_samples,
        continuation_boundary_kind=MocChainBoundaryKind.TERMINAL_CHARACTERISTIC_TRACE,
      )
      terminal_patch_chain_result = solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination(
        current_cell,
        2,
        current_cell.continuation_boundary,
        terminal_patch,
        start_point_m=terminal_patch.outgoing_trace_points_m[0],
        end_x_m=2.0,
        downstream_flow_angle_rad=0.0,
        sample_count=len(terminal_patch.outgoing_trace_points_m),
        position_tolerance_m=2.0e-4,
      )
      terminal_patch_chain_report = (
        terminal_patch_chain_result.as_report()
        if isinstance(terminal_patch_chain_result, MocChainTerminationDecision)
        else {
          'status': 'cell_solve',
          'converged': terminal_patch_chain_result.field.converged,
          'physical_closure_verified': (
            terminal_patch_chain_result.field.physical_closure_verified
          ),
          'chain_promotion_blocked': True,
          'end_x_m': terminal_patch_chain_result.end_x_m,
          'field': {
            'status': terminal_patch_chain_result.field.status.value,
            'converged': terminal_patch_chain_result.field.converged,
            'physical_closure_verified': (
              terminal_patch_chain_result.field.physical_closure_verified
            ),
            'upstream_shock_coupling_verified': (
              terminal_patch_chain_result.field.upstream_shock_coupling_verified
            ),
            'characteristic_layer_count': (
              terminal_patch_chain_result.field.characteristic_layer_count
            ),
            'node_count': terminal_patch_chain_result.field.node_count,
            'cell_count': terminal_patch_chain_result.field.cell_count,
            'physical_closure_status': (
              terminal_patch_chain_result.field.physical_closure_status
            ),
            'shock_closure_status': (
              terminal_patch_chain_result.field.shock_closure_status
            ),
            'incoming_handoff_sample_count': len(
              terminal_patch_chain_result.field.incoming_handoff_states
            ),
            'message': terminal_patch_chain_result.field.message,
          },
        }
      )
      terminal_patch_chain_probe = {
        **terminal_patch_chain_report,
        'expected_physical_termination': (
          isinstance(terminal_patch_chain_result, MocChainTerminationDecision)
          and terminal_patch_chain_result.physical_termination
          and terminal_patch_chain_result.reason is MocChainTerminationReason.PHYSICAL_TERMINATION
        ),
        'claim_status': (
          'terminal-reflection-patch-exact-handoff-to-typed-normal-shock-stop; '
          'nonterminal-cell-return-remains-research-only'
        ),
      }
      terminal_patch_chain_planner = plan_terminal_reflection_patch_chain(
        current_cell,
        terminal_patch,
        start_point_m=terminal_patch.outgoing_trace_points_m[0],
        end_x_m=2.0,
        downstream_flow_angle_rad=0.0,
        sample_count=len(current_cell.continuation_boundary),
        position_tolerance_m=2.0e-4,
      )
      terminal_patch_chain_planner_measurement = measure_moc_chain_planner(
        terminal_patch_chain_planner
      )
      terminal_patch_chain_probe['planner'] = terminal_patch_chain_planner.as_report()
      terminal_patch_chain_probe['planner_measurement'] = (
        terminal_patch_chain_planner_measurement.as_report()
      )
      terminal_patch_chain_probe['planner_expected_physical_termination'] = (
        terminal_patch_chain_planner.chain.physical_termination
        and terminal_patch_chain_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
        and not terminal_patch_chain_planner.production_claim_allowed
        and len(terminal_patch_chain_planner.steps) == 1
        and terminal_patch_chain_planner_measurement.converged
        and terminal_patch_chain_planner_measurement.termination_verified
        and terminal_patch_chain_planner_measurement.fidelity_isolation_verified
        and terminal_patch_chain_planner_measurement.physical_termination is True
        and terminal_patch_chain_planner_measurement.production_claim_allowed is False
      )
      first_cell_composite = assemble_first_cell_composite(
        shock_fit,
        strip,
        terminal_patch,
        position_tolerance_m=2.0e-4,
      )
      if first_cell_composite.converged:
        first_cell_composite_measurement = measure_moc_shock_cell(
          MocShockCellObservation(
            cell_index=1,
            shock_boundary_points_m=first_cell_composite.shock_boundary_points_m,
            centerline_boundary_points_m=first_cell_composite.centerline_boundary_points_m,
            cells=first_cell_composite.cells,
            upstream_total_pressure_Pa=tuple(
              sample.upstream_total_pressure_Pa
              for sample in shock_fit.boundary_states
            ),
            downstream_total_pressure_Pa=tuple(
              sample.downstream_total_pressure_Pa
              for sample in shock_fit.boundary_states
            ),
            )
          )
        if terminal_patch_shock_probe is not None:
          first_cell_terminal_closure = assemble_first_cell_terminal_shock_field(
            first_cell_composite,
            terminal_patch_shock_probe,
            position_tolerance_m=1.0e-10,
            mesh_vertex_tolerance_m=1.0e-9,
          )
          first_cell_terminal_closure_planner = (
            plan_prescribed_first_cell_terminal_closure_mock(
              first_cell_terminal_closure,
            )
          )
          if (
            first_cell_terminal_closure.terminal_field is not None
            and first_cell_terminal_closure.terminal_field.terminal_normal_shock is not None
            and first_cell_terminal_closure.terminal_field.terminal_normal_shock.downstream_pressure_Pa is not None
          ):
            free_boundary_solver = MocSolverGeneratedMixedRegimeClosureReference(
              ambient_pressure_Pa=(
                0.95
                * first_cell_terminal_closure.terminal_field.terminal_normal_shock.downstream_pressure_Pa
              ),
            )
            first_cell_terminal_closure_free_boundary_result = (
              free_boundary_solver.solve(
                first_cell_terminal_closure.mixed_regime_perimeter_request()
              )
            )
            first_cell_terminal_closure_free_boundary_measurement = (
              measure_mixed_regime_free_boundary_reference(
                first_cell_terminal_closure_free_boundary_result,
              )
            )
            first_cell_terminal_closure_free_boundary_refinement_measurement = (
              _solver_generated_free_boundary_refinement_probe(
                first_cell_terminal_closure.mixed_regime_perimeter_request(),
                free_boundary_solver,
              )
            )
            first_cell_terminal_closure_free_boundary_planner = (
              plan_solver_generated_first_cell_terminal_closure_reference(
                first_cell_terminal_closure,
                solver=free_boundary_solver,
              )
            )
  accepted = (
    strip.status is MocAmbientShockStripStatus.CONVERGED_OPEN
    and strip.topology.forms_closed_zone
    and strip.topology.nonmanifold_edge_count == 0
    and not strip.physical_closure_verified
    and strip.chain_promotion_blocked
  )
  return {
    'status': strip.status.value,
    'accepted': accepted,
    'ambient_pressure_Pa': ambient_pressure,
    'march': march.as_report(),
    'ambient_axis_closure': ambient_axis_closure.as_report(),
    'ambient_axis_closure_probe_accepted': ambient_axis_closure_probe_accepted,
    'ambient_axis_closure_shoot': ambient_axis_closure_shoot.as_report(),
    'ambient_axis_closure_shoot_probe_accepted': (
      ambient_axis_closure_shoot_probe_accepted
    ),
    'ambient_axis_closure_shoot_reference': (
      ambient_axis_closure_shoot_reference.as_report()
    ),
    'ambient_axis_closure_shoot_reference_accepted': (
      ambient_axis_closure_shoot_reference_accepted
    ),
    'ambient_physical_field': ambient_physical_field.as_report(),
    'ambient_physical_field_probe_accepted': (
      ambient_physical_field_probe_accepted
    ),
    'ambient_physical_field_reference': ambient_physical_field_reference.as_report(),
    'ambient_physical_field_reference_accepted': (
      ambient_physical_field_reference_accepted
    ),
    'ambient_centerline_physical_field': (
      ambient_centerline_physical_field.as_report()
    ),
    'ambient_centerline_physical_field_accepted': (
      ambient_centerline_physical_field_accepted
    ),
    'ambient_centerline_physical_field_refinement': (
      ambient_centerline_physical_field_refinement
    ),
    'ambient_centerline_physical_field_refinement_accepted': (
      ambient_centerline_physical_field_refinement_accepted
    ),
    'ambient_centerline_physical_chain_probe': (
      ambient_centerline_physical_chain_probe
    ),
    'ambient_centerline_physical_chain_probe_accepted': (
      ambient_centerline_physical_chain_probe_accepted
    ),
    'ambient_centerline_physical_chain_mock': (
      ambient_centerline_physical_chain_mock
    ),
    'ambient_centerline_physical_chain_mock_accepted': (
      ambient_centerline_physical_chain_mock_accepted
    ),
    'ambient_centerline_physical_generated_chain': (
      ambient_centerline_physical_generated_chain
    ),
    'ambient_centerline_physical_generated_chain_accepted': (
      ambient_centerline_physical_generated_chain_accepted
    ),
    'ambient_centerline_physical_reflected_source_chain': (
      ambient_centerline_physical_reflected_source_chain
    ),
    'ambient_centerline_physical_reflected_source_chain_accepted': (
      ambient_centerline_physical_reflected_source_chain_accepted
    ),
    'ambient_centerline_physical_terminal_source_chain': (
      ambient_centerline_physical_terminal_source_chain
    ),
    'ambient_centerline_physical_terminal_source_chain_accepted': (
      ambient_centerline_physical_terminal_source_chain_accepted
    ),
    'ambient_centerline_physical_terminal_patch_planner': (
      ambient_centerline_physical_terminal_patch_planner
    ),
    'ambient_centerline_physical_terminal_patch_planner_accepted': (
      ambient_centerline_physical_terminal_patch_planner_accepted
    ),
    'ambient_centerline_physical_terminal_patch_mixed_regime_planner': (
      ambient_centerline_physical_terminal_patch_mixed_regime_planner
    ),
    'ambient_centerline_physical_terminal_patch_mixed_regime_planner_accepted': (
      ambient_centerline_physical_terminal_patch_mixed_regime_planner_accepted
    ),
    'ambient_centerline_physical_terminal_patch_ambient_closure_chain': (
      ambient_centerline_physical_terminal_patch_ambient_closure_chain
    ),
    'ambient_centerline_physical_terminal_patch_ambient_closure_chain_accepted': (
      ambient_centerline_physical_terminal_patch_ambient_closure_chain_accepted
    ),
    'ambient_centerline_physical_terminal_patch_refinement': (
      ambient_centerline_physical_terminal_patch_refinement
    ),
    'ambient_centerline_physical_terminal_patch_refinement_accepted': (
      ambient_centerline_physical_terminal_patch_refinement_accepted
    ),
    'strip': strip.as_report(),
    'terminal_compression_candidate': solve_terminal_compression_candidate(
      strip,
      ambient_pressure_Pa=ambient_pressure,
      # The strict primitive validator remains in ``strip``. This declared
      # mesh-scale tolerance is only for the local candidate diagnostic.
      trace_position_tolerance_m=2.0e-4,
    ).as_report(),
    'terminal_reflection_patch': terminal_patch.as_report(),
    'terminal_reflection_patch_shock_probe': (
      None
      if terminal_patch_shock_probe is None
      else terminal_patch_shock_probe.as_report()
    ),
    'terminal_reflection_patch_chain_probe': terminal_patch_chain_probe,
    'first_cell_composite': (
      None
      if first_cell_composite is None
      else {
        **first_cell_composite.as_report(),
        'measurement_operator': (
          None
          if first_cell_composite_measurement is None
          else first_cell_composite_measurement.as_report()
        ),
      }
    ),
    'first_cell_terminal_closure': (
      None
      if first_cell_terminal_closure is None
      else first_cell_terminal_closure.as_report()
    ),
    'first_cell_terminal_closure_planner': (
      None
      if first_cell_terminal_closure_planner is None
      else first_cell_terminal_closure_planner.as_report()
    ),
    'first_cell_terminal_closure_free_boundary_planner': (
      None
      if first_cell_terminal_closure_free_boundary_planner is None
      else first_cell_terminal_closure_free_boundary_planner.as_report()
    ),
    'first_cell_terminal_closure_free_boundary_measurement': (
      None
      if first_cell_terminal_closure_free_boundary_measurement is None
      else first_cell_terminal_closure_free_boundary_measurement.as_report()
    ),
    'first_cell_terminal_closure_free_boundary_refinement_measurement': (
      None
      if first_cell_terminal_closure_free_boundary_refinement_measurement is None
      else first_cell_terminal_closure_free_boundary_refinement_measurement.as_report()
    ),
    'terminal_trace_acceptance_tolerance_m': 2.0e-4,
    'message': strip.message,
    'claim_status': (
      'solver-generated-shock-plus-ambient-C-plus-C-minus-strip; '
      'terminal-reflection-patch-open; terminal-shock-probe-mixed-regime-gated; '
      'local-compression-candidate-only; '
      'physical-downstream-boundary-closure-pending'
    ),
  }


def _ambient_pressure_closure_probe() -> dict[str, Any]:
  """Exercise scalar ambient shooting and retain the full perimeter gate."""

  state = CharacteristicState(
    x_m=0.5,
    y_m=0.5,
    theta_rad=-0.2,
    mach=2.0,
    gamma=1.4,
  )
  result = solve_marched_attached_shock_with_ambient_pressure_closure(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=state.theta_rad,
      mach=state.mach,
      gamma=state.gamma,
    ),
    lambda _point: 55000.0,
    (0.5, 0.5),
    100000.0,
    -0.05,
    0.02,
    sample_count=17,
    closure_tolerance=1.0e-4,
    maximum_shooting_iterations=8,
  )
  return {
    **result.as_report(),
    'expected_status': MocAmbientClosureStatus.AMBIENT_BOUNDARY_FAILURE.value,
    'expected_bounded_failure': (
      result.status is MocAmbientClosureStatus.AMBIENT_BOUNDARY_FAILURE
      and not result.physical_closure_verified
    ),
    'claim_status': (
      'scalar-ambient-shoot-reached-pressure-coordinate-but-full-perimeter-'
      'tangency-gate-remains-open'
    ),
  }


def _ambient_attachment_closure_probe(
  solver_generated_shock: MocFreeBoundaryShockResult,
) -> dict[str, Any]:
  """Solve ambient shock attachment before retaining the terminal trace open."""

  shock_fit = solver_generated_shock.shock_fit
  if (
    shock_fit is None
    or not shock_fit.converged
    or not shock_fit.boundary_states
    or not solver_generated_shock.upstream_states
    or not solver_generated_shock.upstream_pressure_Pa
    or not solver_generated_shock.shock_points_m
  ):
    return {
      'status': 'shock_boundary_failure',
      'converged': False,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'expected_open_strip': False,
      'message': 'solver-generated shock fixture did not provide attachment inputs',
      'claim_status': 'ambient-matched-attachment-and-open-strip-pending',
    }

  first = shock_fit.boundary_states[0]
  downstream_state = first.state
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (downstream_state.gamma - 1.0)
    * downstream_state.mach * downstream_state.mach
  ) ** (downstream_state.gamma / (downstream_state.gamma - 1.0))
  upstream_state = solver_generated_shock.upstream_states[0]
  upstream_pressure = solver_generated_shock.upstream_pressure_Pa[0]
  result = solve_marched_attached_shock_with_ambient_attachment_closure(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=upstream_state.theta_rad,
      mach=upstream_state.mach,
      gamma=upstream_state.gamma,
    ),
    lambda _point: upstream_pressure,
    solver_generated_shock.shock_points_m[0],
    ambient_pressure,
    0.0,
    0.1,
    sample_count=solver_generated_shock.sample_count,
  )
  return {
    **result.as_report(),
    'expected_open_strip': (
      result.converged
      and result.strip is not None
      and result.strip.converged
      and not result.physical_closure_verified
      and result.chain_promotion_blocked
    ),
    'claim_status': (
      'ambient-matched-shock-attachment-plus-physical-open-strip; '
      'linear-centerline-reference-only; terminal-centerline-closure-pending'
    ),
  }


def _ambient_attachment_transition_probe(
  solver_generated_shock: MocFreeBoundaryShockResult,
) -> dict[str, Any]:
  """Compose attachment, reflection, and the typed next-shock terminal."""

  shock_fit = solver_generated_shock.shock_fit
  if (
    shock_fit is None
    or not shock_fit.converged
    or not shock_fit.boundary_states
    or not solver_generated_shock.upstream_states
    or not solver_generated_shock.upstream_pressure_Pa
    or not solver_generated_shock.shock_points_m
  ):
    return {
      'status': 'shock_boundary_failure',
      'converged': False,
      'physical_termination': False,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'expected_physical_termination': False,
      'message': 'solver-generated shock fixture did not provide transition inputs',
      'claim_status': 'staged-shock-cell-transition-pending',
    }

  first = shock_fit.boundary_states[0]
  downstream_state = first.state
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (downstream_state.gamma - 1.0)
    * downstream_state.mach * downstream_state.mach
  ) ** (downstream_state.gamma / (downstream_state.gamma - 1.0))
  upstream_state = solver_generated_shock.upstream_states[0]
  upstream_pressure = solver_generated_shock.upstream_pressure_Pa[0]
  result = solve_marched_ambient_attachment_shock_cell_transition(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=upstream_state.theta_rad,
      mach=upstream_state.mach,
      gamma=upstream_state.gamma,
    ),
    lambda _point: upstream_pressure,
    solver_generated_shock.shock_points_m[0],
    ambient_pressure,
    0.0,
    0.1,
    sample_count=solver_generated_shock.sample_count,
  )
  return {
    **result.as_report(),
    'expected_physical_termination': (
      result.physical_termination
      and result.converged
      and not result.physical_closure_verified
      and result.chain_promotion_blocked
      and result.downstream_shock is not None
      and result.downstream_shock.physical_terminal_verified
      and result.terminal_field is not None
      and result.terminal_field.supersonic_region_closed
      and result.terminal_field.characteristic_field_evidence_verified
      and not result.terminal_field.mixed_regime_field_complete
      and result.terminal_field.terminal_shock_boundary_coverage_verified
      and result.terminal_field.terminal_supersonic_downstream_patch_converged
    ),
    'claim_status': (
      'staged-ambient-attachment-to-centerline-reflection-to-next-shock; '
      'verified-normal-shock-chain-stop; unresolved-cell-promotion-pending'
    ),
  }


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


def _terminal_reflection_patch_refinement_probe() -> list[dict[str, Any]]:
  """Record terminal-patch and mixed-regime shock-probe refinement evidence."""

  probe: list[dict[str, Any]] = []
  for sample_count in (9, 17, 33):
    shock = solve_uniform_attached_shock_field(
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
    fit = shock.shock_fit
    if fit is None or not fit.converged or not fit.boundary_states:
      probe.append({
        'sample_count': sample_count,
        'trace_position_tolerance_m': None,
        'status': 'shock_boundary_failure',
        'shock_status': shock.status.value,
      })
      continue
    first = fit.boundary_states[0]
    state = first.state
    ambient_pressure = first.downstream_total_pressure_Pa / (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
    march = march_post_shock_ambient_boundary(fit, ambient_pressure)
    if not march.converged:
      probe.append({
        'sample_count': sample_count,
        'trace_position_tolerance_m': None,
        'status': 'ambient_boundary_failure',
        'shock_status': shock.status.value,
        'march_status': march.status.value,
      })
      continue
    trace_position_tolerance_m = 1.0e-3 if sample_count == 9 else 2.0e-4
    strip = assemble_ambient_shock_characteristic_strip(
      fit,
      march.boundary_samples,
      ambient_pressure,
    )
    patch = assemble_terminal_trace_centerline_patch(
      strip,
      trace_position_tolerance_m=trace_position_tolerance_m,
    )
    shock_probe = None
    first_cell_composite = None
    first_cell_measurement = None
    first_cell_terminal_closure = None
    if patch.converged:
      shock_probe = solve_marched_attached_shock_from_terminal_reflection_patch(
        patch,
        patch.outgoing_trace_points_m[0],
        downstream_flow_angle_rad=0.0,
        sample_count=len(patch.outgoing_trace_points_m),
        position_tolerance_m=trace_position_tolerance_m,
      )
      first_cell_composite = assemble_first_cell_composite(
        fit,
        strip,
        patch,
        position_tolerance_m=trace_position_tolerance_m,
      )
      if first_cell_composite.converged:
        first_cell_measurement = measure_moc_shock_cell(
          MocShockCellObservation(
            cell_index=1,
            shock_boundary_points_m=first_cell_composite.shock_boundary_points_m,
            centerline_boundary_points_m=first_cell_composite.centerline_boundary_points_m,
            cells=first_cell_composite.cells,
            upstream_total_pressure_Pa=tuple(
              sample.upstream_total_pressure_Pa for sample in fit.boundary_states
            ),
            downstream_total_pressure_Pa=tuple(
              sample.downstream_total_pressure_Pa for sample in fit.boundary_states
            ),
          )
        )
        if shock_probe is not None:
          first_cell_terminal_closure = assemble_first_cell_terminal_shock_field(
            first_cell_composite,
            shock_probe,
            position_tolerance_m=1.0e-10,
            mesh_vertex_tolerance_m=1.0e-9,
          )
    input_trace = patch.input_trace_validation
    output_trace = patch.outgoing_trace_validation
    probe.append({
      'sample_count': sample_count,
      'trace_position_tolerance_m': trace_position_tolerance_m,
      'status': patch.status.value,
      'patch_converged': patch.converged,
      'node_count': patch.node_count,
      'cell_count': patch.cell_count,
      'combined_topology_forms_closed_zone': patch.combined_topology.forms_closed_zone,
      'combined_topology_nonmanifold_edge_count': patch.combined_topology.nonmanifold_edge_count,
      'axis_end_m': patch.axis_points_m[-1] if patch.axis_points_m else None,
      'input_trace_converged': None if input_trace is None else input_trace.converged,
      'input_trace_geometry_residual_m': (
        None if input_trace is None else input_trace.maximum_geometry_residual_m
      ),
      'outgoing_trace_converged': None if output_trace is None else output_trace.converged,
      'outgoing_trace_geometry_residual_m': (
        None if output_trace is None else output_trace.maximum_geometry_residual_m
      ),
      'shock_probe_status': None if shock_probe is None else shock_probe.shock.status.value,
      'shock_probe_sample_count': (
        None if shock_probe is None else shock_probe.shock.sample_count
      ),
      'shock_probe_coupling_status': (
        None if shock_probe is None else shock_probe.coupling.status.value
      ),
      'shock_probe_coupling_sampled_count': (
        None if shock_probe is None else shock_probe.coupling.sampled_count
      ),
      'normal_shock_terminal': (
        None
        if shock_probe is None or shock_probe.shock.normal_shock_terminal is None
        else shock_probe.shock.normal_shock_terminal.as_report()
      ),
      'physical_closure_verified': (
        None if shock_probe is None else shock_probe.physical_closure_verified
      ),
      'physical_terminal_verified': (
        None if shock_probe is None else shock_probe.physical_terminal_verified
      ),
      'first_cell_composite_status': (
        None if first_cell_composite is None else first_cell_composite.status.value
      ),
      'first_cell_composite_topology_closed': (
        None if first_cell_composite is None else first_cell_composite.topology_closed
      ),
      'first_cell_composite_boundary_conditions_verified': (
        None
        if first_cell_composite is None
        else first_cell_composite.physical_boundary_conditions_verified
      ),
      'first_cell_composite_physical_closure_verified': (
        None
        if first_cell_composite is None
        else first_cell_composite.physical_closure_verified
      ),
      'first_cell_composite_measurement': (
        None if first_cell_measurement is None else first_cell_measurement.as_report()
      ),
      'first_cell_terminal_closure_status': (
        None
        if first_cell_terminal_closure is None
        else first_cell_terminal_closure.status.value
      ),
      'first_cell_terminal_closure_converged': (
        None
        if first_cell_terminal_closure is None
        else first_cell_terminal_closure.converged
      ),
      'first_cell_terminal_closure_supersonic_region_closed': (
        None
        if first_cell_terminal_closure is None
        else first_cell_terminal_closure.supersonic_region_closed
      ),
      'first_cell_terminal_closure_mixed_regime_field_complete': (
        None
        if first_cell_terminal_closure is None
        else first_cell_terminal_closure.mixed_regime_field_complete
      ),
      'first_cell_terminal_closure_physical_closure_verified': (
        None
        if first_cell_terminal_closure is None
        else first_cell_terminal_closure.physical_closure_verified
      ),
      'first_cell_terminal_closure_chain_promotion_blocked': (
        None
        if first_cell_terminal_closure is None
        else first_cell_terminal_closure.chain_promotion_blocked
      ),
      'first_cell_terminal_closure_physical_termination_verified': (
        None
        if first_cell_terminal_closure is None
        else first_cell_terminal_closure.physical_termination_verified
      ),
      'first_cell_terminal_closure_terminal_shock_boundary_coverage_verified': (
        None
        if first_cell_terminal_closure is None
        or first_cell_terminal_closure.terminal_field is None
        else first_cell_terminal_closure.terminal_field.terminal_shock_boundary_coverage_verified
      ),
    })
  return probe


def _terminal_composite_refinement_probe(
  solver_generated_shock: MocFreeBoundaryShockResult,
) -> list[dict[str, Any]]:
  """Record refinement of the assembled supersonic terminal composite."""

  shock_fit = solver_generated_shock.shock_fit
  if shock_fit is None or not shock_fit.converged or not shock_fit.boundary_states:
    return [{
      'sample_count': None,
      'trace_position_tolerance_m': None,
      'status': 'shock_boundary_failure',
      'terminal_field_status': None,
      'message': 'solver-generated shock fixture did not provide a terminal input',
    }]
  first = shock_fit.boundary_states[0]
  state = first.state
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))
  probe: list[dict[str, Any]] = []
  for sample_count in (9, 17, 33):
    trace_position_tolerance_m = 1.0e-3 if sample_count == 9 else 2.0e-4
    result = solve_marched_ambient_attachment_shock_cell_transition(
      lambda point: CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.2,
        mach=2.0,
        gamma=1.4,
      ),
      lambda _point: 100000.0,
      (0.5, 0.5),
      ambient_pressure,
      0.0,
      0.1,
      sample_count=sample_count,
      trace_position_tolerance_m=trace_position_tolerance_m,
    )
    field = result.terminal_field
    shock = result.downstream_shock
    terminal = None if shock is None else shock.shock.normal_shock_terminal
    probe.append({
      'sample_count': sample_count,
      'trace_position_tolerance_m': trace_position_tolerance_m,
      'status': result.status.value,
      'converged': result.converged,
      'physical_termination': result.physical_termination,
      'physical_closure_verified': result.physical_closure_verified,
      'chain_promotion_blocked': result.chain_promotion_blocked,
      'downstream_condition_status': result.downstream_condition_status,
      'terminal_field_status': None if field is None else field.status.value,
      'terminal_field_converged': None if field is None else field.converged,
      'supersonic_region_closed': None if field is None else field.supersonic_region_closed,
      'terminal_field_characteristic_field_evidence_verified': (
        None if field is None else field.characteristic_field_evidence_verified
      ),
      'terminal_field_node_count': None if field is None else field.node_count,
      'terminal_field_cell_count': None if field is None else len(field.cells),
      'topology_forms_closed_zone': None if field is None else field.topology.forms_closed_zone,
      'topology_nonmanifold_edge_count': None if field is None else field.topology.nonmanifold_edge_count,
      'terminal_shock_boundary_sample_count': (
        None if field is None else len(field.terminal_shock_boundary_points_m)
      ),
      'terminal_shock_upstream_sample_count': (
        None if field is None else len(field.terminal_shock_upstream_states)
      ),
      'terminal_shock_supersonic_downstream_sample_count': (
        None
        if field is None
        else len(field.terminal_shock_supersonic_downstream_states)
      ),
      'terminal_shock_supersonic_downstream_maximum_angle_residual_rad': (
        None
        if field is None
        else field.terminal_shock_supersonic_downstream_maximum_angle_residual_rad
      ),
      'terminal_supersonic_downstream_patch_converged': (
        None
        if field is None
        else field.terminal_supersonic_downstream_patch_converged
      ),
      'terminal_shock_supersonic_downstream_continuation_status': (
        None
        if field is None
        or field.terminal_shock_supersonic_downstream_continuation is None
        else field.terminal_shock_supersonic_downstream_continuation.status.value
      ),
      'terminal_shock_supersonic_downstream_first_layer_status': (
        None
        if field is None
        or field.terminal_shock_supersonic_downstream_first_layer is None
        else field.terminal_shock_supersonic_downstream_first_layer.status.value
      ),
      'terminal_shock_supersonic_downstream_zone_status': (
        None
        if field is None
        or field.terminal_shock_supersonic_downstream_zone is None
        else field.terminal_shock_supersonic_downstream_zone.status.value
      ),
      'terminal_shock_supersonic_downstream_zone_cell_count': (
        None
        if field is None
        or field.terminal_shock_supersonic_downstream_zone is None
        else field.terminal_shock_supersonic_downstream_zone.cell_count
      ),
      'terminal_shock_boundary_edge_count': (
        None if field is None else field.terminal_shock_boundary_edge_count
      ),
      'terminal_shock_boundary_coverage_verified': (
        None if field is None else field.terminal_shock_boundary_coverage_verified
      ),
      'terminal_shock_boundary_maximum_geometry_residual_m': (
        None
        if field is None
        else field.terminal_shock_boundary_maximum_geometry_residual_m
      ),
      'shock_status': None if shock is None else shock.shock.status.value,
      'shock_sample_count': None if shock is None else shock.shock.sample_count,
      'physical_terminal_verified': (
        None if shock is None else shock.physical_terminal_verified
      ),
      'terminal_downstream_mach': None if terminal is None else terminal.downstream_mach,
      'terminal_point_m': None if terminal is None else terminal.shock_point_m,
      'message': result.message,
    })
  return probe


def _terminal_composite_refinement_case_failed(case: dict[str, Any]) -> bool:
  """Return whether one terminal-composite refinement case missed a gate."""

  residual = case.get('terminal_shock_boundary_maximum_geometry_residual_m')
  sample_count = case.get('sample_count')
  downstream_residual = case.get(
    'terminal_shock_supersonic_downstream_maximum_angle_residual_rad'
  )
  if not isinstance(sample_count, int):
    return True
  return (
    case.get('status') != 'physically_terminated_at_normal_shock'
    or case.get('converged') is not True
    or case.get('physical_termination') is not True
    or case.get('physical_closure_verified') is not False
    or case.get('chain_promotion_blocked') is not True
    or case.get('terminal_field_status') != 'converged_closed_supersonic_terminal_region'
    or case.get('terminal_field_converged') is not True
    or case.get('supersonic_region_closed') is not True
    or case.get('topology_forms_closed_zone') is not True
    or case.get('topology_nonmanifold_edge_count')
    or case.get('terminal_shock_boundary_sample_count') != sample_count
    or case.get('terminal_shock_upstream_sample_count') != sample_count
    or case.get('terminal_shock_supersonic_downstream_sample_count') != sample_count - 1
    or case.get('terminal_supersonic_downstream_patch_converged') is not True
    or case.get('terminal_shock_supersonic_downstream_continuation_status') != 'converged_open_boundary'
    or case.get('terminal_shock_supersonic_downstream_first_layer_status') != 'converged_first_downstream_layer'
    or case.get('terminal_shock_supersonic_downstream_zone_status') != 'converged_open'
    or not isinstance(case.get('terminal_shock_supersonic_downstream_zone_cell_count'), int)
    or not isinstance(downstream_residual, (int, float))
    or downstream_residual > 1.0e-2
    or not case.get('terminal_shock_boundary_edge_count')
    or case.get('terminal_shock_boundary_coverage_verified') is not True
    or not isinstance(residual, (int, float))
    or residual > 1.0e-8
    or case.get('shock_status') != 'subsonic_terminal_required'
    or case.get('shock_sample_count') != sample_count - 1
    or case.get('physical_terminal_verified') is not True
  )


def _mixed_regime_boundary_probe(
  solver_generated_shock: MocFreeBoundaryShockResult,
) -> dict[str, Any]:
  """Exercise the scalar mixed-regime handoff without promoting a field."""

  shock_fit = solver_generated_shock.shock_fit
  if shock_fit is None or not shock_fit.converged or not shock_fit.boundary_states:
    return {
      'status': 'missing_terminal_input',
      'accepted': False,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'claim_status': 'mixed-regime-boundary-contract-pending',
      'message': 'solver-generated shock fixture did not provide mixed-regime inputs',
    }
  first = shock_fit.boundary_states[0]
  state = first.state
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))
  transition = solve_marched_ambient_attachment_shock_cell_transition(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 100000.0,
    (0.5, 0.5),
    ambient_pressure,
    0.0,
    0.1,
    sample_count=17,
    trace_position_tolerance_m=2.0e-4,
  )
  field = transition.terminal_field
  downstream_shock = transition.downstream_shock
  terminal = (
    None
    if downstream_shock is None
    else downstream_shock.shock.normal_shock_terminal
  )
  if (
    field is None
    or downstream_shock is None
    or terminal is None
    or not field.terminal_supersonic_downstream_patch_converged
  ):
    return {
      'status': 'missing_terminal_input',
      'accepted': False,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'claim_status': 'mixed-regime-boundary-contract-pending',
      'message': 'terminal composite did not expose a verified open supersonic patch and scalar terminal',
    }
  patch = field.terminal_shock_supersonic_downstream_states
  missing_field = validate_mixed_regime_boundary(
    terminal,
    patch,
    supersonic_patch_converged=field.terminal_supersonic_downstream_patch_converged,
    subsonic_samples=(),
  )
  if (
    terminal.shock_point_m is None
    or terminal.downstream_mach is None
    or terminal.downstream_flow_angle_rad is None
    or terminal.downstream_pressure_Pa is None
    or terminal.downstream_total_pressure_Pa is None
    or terminal.upstream_state is None
  ):
    return {
      'status': 'invalid_terminal_scalars',
      'accepted': False,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'missing_scalar_field': missing_field.as_report(),
      'claim_status': 'mixed-regime-boundary-contract-pending',
      'message': 'normal-shock terminal did not expose complete scalar values',
    }
  terminal_x, terminal_y = terminal.shock_point_m
  perimeter_mock = MocPrescribedMixedRegimeClosureMock(radial_divisions=2)
  perimeter_request = field.mixed_regime_perimeter_request()
  control_section_requirement = validate_mixed_regime_control_section(
    perimeter_request,
    None,
  )
  control_section_measurement = measure_mixed_regime_control_section(
    perimeter_request,
    None,
  )
  perimeter_specification = perimeter_mock.specification(perimeter_request)
  contract_points = perimeter_specification.perimeter_points_m
  contract_samples = tuple(
    perimeter_mock.sample_at(perimeter_request, index, point)
    for index, point in enumerate(contract_points)
  )
  contract_fixture = validate_mixed_regime_boundary(
    terminal,
    patch,
    supersonic_patch_converged=field.terminal_supersonic_downstream_patch_converged,
    subsonic_samples=contract_samples,
  )
  explicit_perimeter_closure = perimeter_mock.solve(perimeter_request)
  explicit_perimeter_field = explicit_perimeter_closure.field
  assert explicit_perimeter_field is not None
  planar_section_mach = terminal.downstream_mach + 0.01
  planar_section_static_pressure = terminal.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (terminal.upstream_state.gamma - 1.0)
    * planar_section_mach * planar_section_mach
  ) ** (terminal.upstream_state.gamma / (terminal.upstream_state.gamma - 1.0))
  planar_section_points = (
    (terminal_x + 0.02, terminal_y - 0.01),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
  )
  planar_control_section = MocMixedRegimeControlSection(
    points_m=planar_section_points,
    samples=tuple(
      MocMixedRegimeFieldSample(
        point_m=point,
        mach=planar_section_mach,
        flow_angle_rad=terminal.downstream_flow_angle_rad,
        static_pressure_Pa=planar_section_static_pressure,
        total_pressure_Pa=terminal.downstream_total_pressure_Pa,
        gamma=terminal.upstream_state.gamma,
      )
      for point in planar_section_points
    ),
    normal_angle_rad=0.0,
  )
  planar_downstream_handoff = run_mixed_regime_planar_field_solver(
    perimeter_request,
    planar_control_section,
    perimeter_specification,
    lambda _request, section, _specification: replace(
      explicit_perimeter_field,
      control_section=section,
    ),
    solver_model='scalar-reference-callback-fixture',
  )
  planar_handoff_measurement = measure_moc_terminal_closure(
    MocTerminalClosureObservation(
      terminal_field=field,
      mixed_regime_closure=planar_downstream_handoff.closure,
    )
  )
  planar_reference_specification = replace(
    perimeter_specification,
    condition_edge_indices=(0,),
    condition_sample_indices=(0, 1),
  )
  planar_reference_sonic_factor = 0.5 * (terminal.upstream_state.gamma - 1.0)
  planar_reference_terminal_speed = terminal.downstream_mach / sqrt(
    1.0
    + planar_reference_sonic_factor * terminal.downstream_mach * terminal.downstream_mach
  )

  def planar_reference_sample(
    point: tuple[float, float],
  ) -> MocMixedRegimeFieldSample:
    tangential_speed = 0.12 * (point[1] - terminal_y)
    speed_squared = (
      planar_reference_terminal_speed * planar_reference_terminal_speed
      + tangential_speed * tangential_speed
    )
    mach = sqrt(
      speed_squared
      / (1.0 - planar_reference_sonic_factor * speed_squared)
    )
    static_pressure = terminal.downstream_total_pressure_Pa / (
      1.0 + planar_reference_sonic_factor * mach * mach
    ) ** (terminal.upstream_state.gamma / (terminal.upstream_state.gamma - 1.0))
    return MocMixedRegimeFieldSample(
      point_m=point,
      mach=mach,
      flow_angle_rad=atan2(
        tangential_speed,
        planar_reference_terminal_speed,
      ),
      static_pressure_Pa=static_pressure,
      total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      gamma=terminal.upstream_state.gamma,
    )

  planar_reference_control_section = MocMixedRegimeControlSection(
    points_m=planar_section_points,
    samples=tuple(planar_reference_sample(point) for point in planar_section_points),
    normal_angle_rad=0.0,
  )
  planar_potential_reference = MocMixedRegimePlanarPotentialReference(
    radial_divisions=2,
  )
  planar_potential_handoff = planar_potential_reference.solve(
    perimeter_request,
    planar_reference_control_section,
    planar_reference_specification,
  )
  planar_potential_measurement = (
    None
    if planar_potential_handoff.field is None
    else measure_mixed_regime_compressible_potential_field(
      planar_potential_handoff.field,
    )
  )
  planar_frozen_profile_tangential_speeds = (0.002, 0.0, 0.002)

  def planar_frozen_profile_sample(
    point: tuple[float, float],
    tangential_speed: float,
  ) -> MocMixedRegimeFieldSample:
    speed_squared = (
      planar_reference_terminal_speed * planar_reference_terminal_speed
      + tangential_speed * tangential_speed
    )
    mach = sqrt(
      speed_squared
      / (1.0 - planar_reference_sonic_factor * speed_squared)
    )
    static_pressure = terminal.downstream_total_pressure_Pa / (
      1.0 + planar_reference_sonic_factor * mach * mach
    ) ** (terminal.upstream_state.gamma / (terminal.upstream_state.gamma - 1.0))
    return MocMixedRegimeFieldSample(
      point_m=point,
      mach=mach,
      flow_angle_rad=atan2(tangential_speed, planar_reference_terminal_speed),
      static_pressure_Pa=static_pressure,
      total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      gamma=terminal.upstream_state.gamma,
    )

  planar_frozen_profile_control_section = MocMixedRegimeControlSection(
    points_m=planar_section_points,
    samples=tuple(
      planar_frozen_profile_sample(point, tangential_speed)
      for point, tangential_speed in zip(
        planar_section_points,
        planar_frozen_profile_tangential_speeds,
        strict=True,
      )
    ),
    normal_angle_rad=0.0,
  )
  planar_frozen_profile_reference = MocMixedRegimePlanarFrozenProfileReference(
    radial_divisions=2,
  )
  planar_frozen_profile_handoff = planar_frozen_profile_reference.solve(
    perimeter_request,
    planar_frozen_profile_control_section,
    planar_reference_specification,
  )
  planar_frozen_profile_measurement = (
    None
    if planar_frozen_profile_handoff.field is None
    else measure_mixed_regime_compressible_potential_field(
      planar_frozen_profile_handoff.field,
    )
  )
  contract_condition = validate_mixed_regime_downstream_condition(
    contract_fixture,
    MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
  )
  wall_points = (
    (terminal_x, terminal_y),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
    (terminal_x, terminal_y + 0.01),
    (terminal_x, terminal_y),
  )
  wall_samples = tuple(
    MocMixedRegimeFieldSample(
      point_m=point,
      mach=terminal.downstream_mach,
      flow_angle_rad=flow_angle,
      static_pressure_Pa=terminal.downstream_pressure_Pa,
      total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      gamma=terminal.upstream_state.gamma,
    )
    for point, flow_angle in zip(
      wall_points,
      (0.0, 0.0, pi, pi, 0.0),
      strict=True,
    )
  )
  wall_fixture = validate_mixed_regime_boundary(
    terminal,
    patch,
    supersonic_patch_converged=field.terminal_supersonic_downstream_patch_converged,
    subsonic_samples=wall_samples,
  )
  wall_condition = validate_mixed_regime_downstream_condition(
    wall_fixture,
    MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
  )
  outflow_condition = validate_mixed_regime_downstream_condition(
    contract_fixture,
    MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=terminal.downstream_pressure_Pa,
  )
  contract_field = solve_mixed_regime_subsonic_field(contract_fixture)
  contract_field_refinement = tuple(
    solve_mixed_regime_subsonic_field(
      contract_fixture,
      radial_divisions=radial_divisions,
    )
    for radial_divisions in (2, 3, 4)
  )
  conditioned_field = solve_mixed_regime_subsonic_field(
    contract_fixture,
    downstream_condition=outflow_condition,
  )
  conditioned_field_refinement = tuple(
    solve_mixed_regime_subsonic_field(
      contract_fixture,
      radial_divisions=radial_divisions,
      downstream_condition=outflow_condition,
    )
    for radial_divisions in (2, 3, 4)
  )
  compressible_potential_field = solve_mixed_regime_compressible_potential_field(
    contract_fixture,
    downstream_condition=outflow_condition,
  )
  compressible_potential_field_refinement = tuple(
    solve_mixed_regime_compressible_potential_field(
      contract_fixture,
      radial_divisions=radial_divisions,
      downstream_condition=outflow_condition,
    )
    for radial_divisions in (2, 3, 4)
  )
  compressible_potential_measurement = (
    measure_mixed_regime_compressible_potential_field(
      compressible_potential_field,
    )
  )
  compressible_potential_measurement_refinement = tuple(
    measure_mixed_regime_compressible_potential_field(result)
    for result in compressible_potential_field_refinement
  )
  terminal_attachment_refinement: tuple[dict[str, Any], ...] = ()
  if field is not None and all(
    result.physical_closure_verified for result in conditioned_field_refinement
  ):
    attachment_cases: list[dict[str, Any]] = []
    for result in conditioned_field_refinement:
      attached = field.with_mixed_regime_field(result)
      attachment_cases.append({
        'radial_divisions': result.radial_divisions,
        'model': result.model,
        'mixed_regime_field_complete': attached.mixed_regime_field_complete,
        'physical_closure_verified': attached.physical_closure_verified,
        'physical_termination_verified': attached.physical_termination_verified,
        'chain_promotion_blocked': attached.chain_promotion_blocked,
        'termination_decision': attached.as_physical_termination_decision().as_report(),
      })
    terminal_attachment_refinement = tuple(attachment_cases)
  terminal_attachment_fixture = None
  terminal_attachment_termination_decision = None
  terminal_attachment_closure = None
  terminal_closure_measurement = measure_moc_terminal_closure(
    MocTerminalClosureObservation(terminal_field=field)
  )
  terminal_attachment_measurement = None
  if field is not None and explicit_perimeter_closure.converged:
    terminal_attachment_closure = explicit_perimeter_closure
    if terminal_attachment_closure.field is None:
      raise ValueError(
        'accepted mixed-regime contract fixture did not return an attachable field'
      )
    terminal_attachment = field.with_mixed_regime_field(terminal_attachment_closure.field)
    terminal_attachment_fixture = terminal_attachment.as_report()
    terminal_attachment_termination_decision = (
      terminal_attachment.as_physical_termination_decision().as_report()
    )
    terminal_attachment_measurement = measure_moc_terminal_closure(
      MocTerminalClosureObservation(
        terminal_field=field,
        mixed_regime_closure=terminal_attachment_closure,
      )
    )
  return {
    'status': contract_fixture.status.value,
    'accepted': (
      missing_field.status is MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE
      and contract_fixture.converged
      and contract_field.model_closure_verified
      and contract_field.physical_closure_verified is False
      and explicit_perimeter_closure.converged
      and explicit_perimeter_closure.physical_closure_verified
      and explicit_perimeter_closure.chain_promotion_blocked
      and explicit_perimeter_closure.perimeter_spec == perimeter_specification
      and explicit_perimeter_closure.downstream_condition is not None
      and explicit_perimeter_closure.downstream_condition.converged
      and outflow_condition.converged
      and conditioned_field.physical_closure_verified
      and all(
        result.physical_closure_verified
        for result in conditioned_field_refinement
      )
      and compressible_potential_field.physical_closure_verified
      and compressible_potential_field.model == (
        'compressible-isentropic-potential-reference'
      )
      and all(
        result.physical_closure_verified
        and result.model == 'compressible-isentropic-potential-reference'
        and result.maximum_mass_conservation_residual is not None
        and result.maximum_mass_conservation_residual <= 1.0e-8
        and result.maximum_boundary_velocity_residual is not None
        and result.maximum_boundary_velocity_residual <= 1.0e-8
        and result.potential_circulation_residual is not None
        and result.potential_circulation_residual <= 1.0e-8
        for result in compressible_potential_field_refinement
      )
      and compressible_potential_measurement.converged
      and compressible_potential_measurement.reference_model_verified
      and compressible_potential_measurement.physical_closure_verified is False
      and compressible_potential_measurement.chain_promotion_blocked
      and all(
        result.converged
        and result.reference_model_verified
        and result.physical_closure_verified is False
        and result.chain_promotion_blocked
        for result in compressible_potential_measurement_refinement
      )
      and len(terminal_attachment_refinement) == len(conditioned_field_refinement)
      and all(
        case['physical_termination_verified'] is True
        and case['chain_promotion_blocked'] is True
        for case in terminal_attachment_refinement
      )
      and terminal_attachment_closure is not None
      and terminal_attachment_closure.converged
      and terminal_closure_measurement.status.value == 'mixed_regime_failure'
      and terminal_closure_measurement.physical_closure_verified is False
      and terminal_closure_measurement.chain_promotion_blocked
      and terminal_attachment_measurement is not None
      and terminal_attachment_measurement.converged
      and terminal_attachment_measurement.physical_closure_verified
      and terminal_attachment_measurement.physical_termination_verified
      and terminal_attachment_measurement.chain_promotion_blocked
      and contract_fixture.physical_closure_verified is False
      and contract_fixture.chain_promotion_blocked
      and control_section_requirement.status.value == 'invalid_input'
      and not control_section_requirement.physical_closure_verified
      and control_section_requirement.chain_promotion_blocked
      and control_section_measurement.status.value == 'invalid_input'
      and not control_section_measurement.physical_closure_verified
      and control_section_measurement.chain_promotion_blocked
      and planar_downstream_handoff.status is MocMixedRegimePlanarSolveStatus.CONVERGED_HANDOFF
      and planar_downstream_handoff.handoff_verified
      and planar_downstream_handoff.section_is_varying
      and planar_downstream_handoff.field_physical_closure_verified
      and planar_downstream_handoff.physical_closure_verified is False
      and planar_downstream_handoff.canonical_free_boundary_verified is False
      and planar_downstream_handoff.chain_promotion_blocked
      and planar_downstream_handoff.production_claim_allowed is False
      and planar_handoff_measurement.converged
      and planar_handoff_measurement.physical_closure_verified
      and planar_handoff_measurement.chain_promotion_blocked
      and planar_potential_handoff.status is MocMixedRegimePlanarSolveStatus.CONVERGED_HANDOFF
      and planar_potential_handoff.handoff_verified
      and planar_potential_handoff.section_is_varying
      and planar_potential_handoff.control_section_projection_verified
      and planar_potential_handoff.maximum_control_section_projection_residual is not None
      and planar_potential_handoff.maximum_control_section_projection_residual <= 1.0e-8
      and planar_potential_handoff.field_physical_closure_verified
      and planar_potential_handoff.physical_closure_verified is False
      and planar_potential_handoff.canonical_free_boundary_verified is False
      and planar_potential_handoff.chain_promotion_blocked
      and planar_potential_handoff.production_claim_allowed is False
      and planar_potential_handoff.field is not None
      and planar_potential_handoff.field.model == (
        'compressible-isentropic-potential-reference'
      )
      and planar_potential_measurement is not None
      and planar_potential_measurement.converged
      and planar_potential_measurement.reference_model_verified
      and planar_potential_measurement.physical_closure_verified is False
      and planar_potential_measurement.chain_promotion_blocked
      and planar_frozen_profile_handoff.status is MocMixedRegimePlanarSolveStatus.CONVERGED_HANDOFF
      and planar_frozen_profile_handoff.handoff_verified
      and planar_frozen_profile_handoff.section_is_varying
      and planar_frozen_profile_handoff.control_section_projection_verified
      and planar_frozen_profile_handoff.maximum_control_section_projection_residual is not None
      and planar_frozen_profile_handoff.maximum_control_section_projection_residual <= 1.0e-8
      and planar_frozen_profile_handoff.projection_model == (
        'piecewise-linear-frozen-transverse-profile'
      )
      and planar_frozen_profile_handoff.field_physical_closure_verified
      and planar_frozen_profile_handoff.physical_closure_verified is False
      and planar_frozen_profile_handoff.canonical_free_boundary_verified is False
      and planar_frozen_profile_handoff.chain_promotion_blocked
      and planar_frozen_profile_handoff.production_claim_allowed is False
      and planar_frozen_profile_handoff.field is not None
      and planar_frozen_profile_handoff.field.model == (
        'compressible-isentropic-potential-reference'
      )
      and planar_frozen_profile_measurement is not None
      and planar_frozen_profile_measurement.converged
      and planar_frozen_profile_measurement.reference_model_verified
      and planar_frozen_profile_measurement.physical_closure_verified is False
      and planar_frozen_profile_measurement.chain_promotion_blocked
      and contract_condition.status.value == 'downstream-tangency-failure'
      and wall_condition.converged
      and wall_condition.chain_promotion_blocked
    ),
    'physical_closure_verified': contract_fixture.physical_closure_verified,
    'chain_promotion_blocked': contract_fixture.chain_promotion_blocked,
    'missing_scalar_field': missing_field.as_report(),
    'control_section_requirement': control_section_requirement.as_report(),
    'control_section_measurement': control_section_measurement.as_report(),
    'planar_downstream_handoff': planar_downstream_handoff.as_report(),
    'planar_downstream_handoff_measurement': planar_handoff_measurement.as_report(),
    'planar_potential_reference_configuration': planar_potential_reference.as_report(),
    'planar_potential_reference': planar_potential_handoff.as_report(),
    'planar_potential_reference_measurement': (
      None
      if planar_potential_measurement is None
      else planar_potential_measurement.as_report()
    ),
    'planar_frozen_profile_reference_configuration': (
      planar_frozen_profile_reference.as_report()
    ),
    'planar_frozen_profile_reference': (
      planar_frozen_profile_handoff.as_report()
    ),
    'planar_frozen_profile_reference_measurement': (
      None
      if planar_frozen_profile_measurement is None
      else planar_frozen_profile_measurement.as_report()
    ),
    'mixed_regime_closure_mock': perimeter_mock.as_report(),
    'scalar_perimeter_contract_fixture': contract_fixture.as_report(),
    'explicit_downstream_perimeter_solver': explicit_perimeter_closure.as_report(),
    'downstream_condition_contract': contract_condition.as_report(),
    'downstream_condition_positive_wall_fixture': wall_condition.as_report(),
    'downstream_condition_positive_outflow_fixture': outflow_condition.as_report(),
    'elliptic_subsonic_field_contract_fixture': contract_field.as_report(),
    'elliptic_subsonic_field_refinement': [
      result.as_report() for result in contract_field_refinement
    ],
    'elliptic_subsonic_field_conditioned_fixture': conditioned_field.as_report(),
    'elliptic_subsonic_field_conditioned_refinement': [
      result.as_report() for result in conditioned_field_refinement
    ],
    'compressible_potential_field_reference': compressible_potential_field.as_report(),
    'compressible_potential_field_refinement': [
      result.as_report() for result in compressible_potential_field_refinement
    ],
    'compressible_potential_measurement': compressible_potential_measurement.as_report(),
    'compressible_potential_measurement_refinement': [
      result.as_report() for result in compressible_potential_measurement_refinement
    ],
    'terminal_attachment_refinement': list(terminal_attachment_refinement),
    'terminal_attachment_closure_result': (
      None
      if terminal_attachment_closure is None
      else terminal_attachment_closure.as_report()
    ),
    'terminal_closure_measurement': terminal_closure_measurement.as_report(),
    'terminal_attachment_measurement': (
      None
      if terminal_attachment_measurement is None
      else terminal_attachment_measurement.as_report()
    ),
    'terminal_attachment_contract_fixture': terminal_attachment_fixture,
    'terminal_attachment_termination_decision': terminal_attachment_termination_decision,
    'claim_status': (
      'typed-scalar-subsonic-boundary-handoff-only; '
      'condition-qualified-elliptic-reference-is-synthetic; '
      'canonical-subsonic-field-and-chain-promotion-pending'
    ),
    'message': contract_fixture.message,
  }


def _shock_cell_chain_planner_mock(
  seed_field: MocPostShockCharacteristicFieldResult,
) -> tuple[Any, list[dict[str, Any]], list[MocShockCellObservation], Any]:
  """Exercise a continued-cell planner with prescribed next-shock geometry.

  This is an orchestration fixture, not a free-boundary solver.  Each mock
  step records the previous terminal trace through ``incoming_handoff`` and
  supplies a separate prescribed shock boundary for the next local field.
  The reusable geometry fixture lives in the isolated planner module; this
  wrapper only adds report-oriented observations and never promotes it to a
  production provider.
  """

  observations: list[dict[str, Any]] = []
  measurement_observations = [
    _post_shock_field_measurement_observation(seed_field, cell_index=1)
  ]
  # Exercise a longer chain in the standalone artifact so the exact
  # handoff/fresh-domain checks cover more than the unit-test default.
  mock = MocPrescribedPostShockChainMock(
    total_cell_count=5,
    cell_axial_lengths_m=(0.46, 0.50, 0.54, 0.58),
    shock_start_offsets_m=(0.16, 0.18, 0.20, 0.22),
    shock_geometry_scales_per_cell=(1.00, 1.05, 1.10, 1.15),
  )

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
    solved = mock.solve_next(current, cell_index, handoff)
    if isinstance(solved, MocPostShockChainCellSolve):
      field = solved.field
      measurement_observations.append(
        _post_shock_field_measurement_observation(field, cell_index=cell_index)
      )
    return solved

  planner = plan_post_shock_characteristic_chain(
    seed_field,
    solve_next,
    start_x_m=0.7,
    end_x_m=1.0,
    planner_kind=MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK,
  )
  planner = replace(
    planner,
    diagnostics={
      'prescribed_chain_mock': mock.as_report(),
    },
  )
  return (
    planner.chain,
    observations,
    measurement_observations,
    planner,
  )


def _post_shock_field_measurement_observation(
  field: MocPostShockCharacteristicFieldResult,
  *,
  cell_index: int,
) -> MocShockCellObservation:
  """Convert a solved field into raw data for the independent chain operator."""

  shock_count = len(field.shock_boundary_points_m)
  upstream_pressures = field.upstream_boundary_total_pressure_Pa
  downstream_pressures = field.shock_boundary_total_pressure_Pa
  pressure_kwargs: dict[str, Any] = {}
  if (
    len(upstream_pressures) == shock_count
    and len(downstream_pressures) == shock_count
  ):
    pressure_kwargs = {
      'upstream_total_pressure_Pa': upstream_pressures,
      'downstream_total_pressure_Pa': downstream_pressures,
    }
  incoming_handoff = tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      field.incoming_handoff_states,
      field.incoming_handoff_total_pressure_Pa,
      strict=True,
    )
  )
  outgoing_handoff = tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      field.continuation_boundary_states,
      field.continuation_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  return MocShockCellObservation(
    cell_index=cell_index,
    shock_boundary_points_m=field.shock_boundary_points_m,
    centerline_boundary_points_m=field.centerline_boundary_points_m,
    cells=field.cells,
    incoming_handoff=incoming_handoff,
    outgoing_handoff=outgoing_handoff,
    incoming_boundary_kind=(
      MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
      if incoming_handoff
      else None
    ),
    outgoing_boundary_kind=(
      MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
      if outgoing_handoff
      else None
    ),
    **pressure_kwargs,
  )


def _planner_boundary_validation(cell: Any) -> dict[str, Any]:
  """Report the boundary contract without calling every boundary a C trace."""

  kind = cell.continuation_boundary_kind
  if kind is MocChainBoundaryKind.TERMINAL_CHARACTERISTIC_TRACE:
    return {
      'boundary_kind': kind.value,
      'trace': validate_characteristic_trace(
        cell.continuation_boundary,
        CharacteristicFamily.MINUS,
      ).as_report(),
    }
  if kind is not MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER:
    return {
      'boundary_kind': kind.value,
      'trace': {
        'status': 'not_applicable',
        'converged': False,
        'family': None,
        'sample_count': len(cell.continuation_boundary),
        'message': 'planner fixture has no characteristic-trace validator for this boundary kind',
      },
    }
  points = tuple(sample.point_m for sample in cell.continuation_boundary)
  segment_lengths = tuple(
    ((second[0] - first[0]) ** 2 + (second[1] - first[1]) ** 2) ** 0.5
    for first, second in zip(points[:-1], points[1:], strict=True)
  )
  forward_x = all(
    second[0] > first[0]
    for first, second in zip(points[:-1], points[1:], strict=True)
  )
  nonnegative_y = all(point[1] >= -1.0e-10 for point in points)
  distinct = all(length > 1.0e-10 for length in segment_lengths)
  return {
    'boundary_kind': kind.value,
    'trace': {
      'status': 'not_applicable',
      'converged': False,
      'family': None,
      'sample_count': len(points),
      'message': (
        'composite post-shock field perimeter; characteristic invariant '
        'validation is intentionally not applied'
      ),
    },
    'geometry': {
      'status': 'converged' if forward_x and nonnegative_y and distinct else 'failure',
      'sample_count': len(points),
      'forward_x': forward_x,
      'nonnegative_y': nonnegative_y,
      'distinct_segments': distinct,
      'minimum_segment_length_m': min(segment_lengths, default=None),
      'path_length_m': sum(segment_lengths),
      'start_m': points[0] if points else None,
      'end_m': points[-1] if points else None,
    },
  }


def _solver_generated_chain_reference(
  seed_field: MocPostShockCharacteristicFieldResult,
) -> tuple[Any, list[dict[str, Any]], list[MocShockCellObservation], Any]:
  """Exercise the reusable generated reference with report observations.

  The fixture owns the solver-backed local solve and its research-only claim
  ceiling.  This wrapper adds validation observations without changing the
  production boundary or moving the reference into a provider.
  """

  observations: list[dict[str, Any]] = []
  measurement_observations = [
    _post_shock_field_measurement_observation(seed_field, cell_index=1)
  ]
  # Match the standalone prescribed mock's longer chain depth.  This tests
  # repeated solver-backed shock/field re-solves, while the explicit upstream
  # and downstream reference laws remain below the canonical claim boundary.
  reference = MocSolverGeneratedPostShockChainReference(total_cell_count=5)

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
    solved = reference.solve_next(current, cell_index, handoff)
    if isinstance(solved, MocPostShockChainCellSolve):
      measurement_observations.append(
        _post_shock_field_measurement_observation(
          solved.field,
          cell_index=cell_index,
        )
      )
    return solved

  planner = plan_post_shock_characteristic_chain(
    seed_field,
    solve_next,
    start_x_m=0.5,
    end_x_m=1.0,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  )
  planner = replace(
    planner,
    diagnostics={
      'solver_generated_chain_reference': reference.as_report(),
    },
  )
  return planner.chain, observations, measurement_observations, planner


def _solver_generated_chain_refinement_probe() -> Any:
  """Measure the generated continued-chain reference at three resolutions."""

  cases: list[MocShockCellChainRefinementCase] = []
  for sample_count in (9, 17, 33):
    generated = solve_uniform_attached_shock_field(
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
    field = generated.field
    if field is None or not field.converged:
      continue
    reference = MocSolverGeneratedPostShockChainReference(
      total_cell_count=5,
      sample_count=sample_count,
    )
    returned_fields: list[MocPostShockCharacteristicFieldResult] = []

    def solve_next(current, cell_index, handoff):
      solved = reference.solve_next(current, cell_index, handoff)
      if isinstance(solved, MocPostShockChainCellSolve):
        returned_fields.append(solved.field)
      return solved

    planner = plan_post_shock_characteristic_chain(
      field,
      solve_next,
      start_x_m=0.5,
      end_x_m=1.0,
      require_upstream_shock_coupling=True,
      planner_kind=MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
    )
    observations = tuple(
      [
        _post_shock_field_measurement_observation(field, cell_index=1),
      ]
      + [
        _post_shock_field_measurement_observation(
          returned_field,
          cell_index=index + 2,
        )
        for index, returned_field in enumerate(returned_fields)
      ]
    )
    cases.append(
      MocShockCellChainRefinementCase(
        resolution=sample_count,
        observations=observations,
        termination_reason=planner.chain.termination_reason.value,
        physical_termination=planner.chain.physical_termination,
      )
    )
  return measure_moc_shock_cell_chain_refinement(cases)


def _solver_generated_free_boundary_refinement_probe(
  request: Any,
  solver: Any,
) -> Any:
  """Measure the quasi-one-dimensional free-boundary reference at 3 resolutions."""

  cases = tuple(
    MocMixedRegimeFreeBoundaryRefinementCase(
      resolution=sample_count,
      result=replace(
        solver,
        free_boundary_sample_count=sample_count,
      ).solve(request),
    )
    for sample_count in (5, 7, 9)
  )
  return measure_mixed_regime_free_boundary_refinement(cases)


def _solver_generated_field_coupled_chain_planner(
  seed_field: MocPostShockCharacteristicFieldResult,
) -> Any:
  """Exercise the public planner whose next shock samples the solved field.

  The start point and downstream turn law are deliberately explicit reference
  conditions. The upstream state and pressure are no longer callbacks that
  manufacture a uniform field: they are bounded samples from the completed
  solver-generated post-shock lattice. A typed terminal is still expected
  before this research planner can produce a second cell.
  """

  if not seed_field.converged or not seed_field.upstream_shock_coupling_verified:
    return None
  return plan_field_coupled_post_shock_chain_reference(
    seed_field,
    start_x_m=0.5,
    end_x_m=0.9,
    reference=MocFieldCoupledPostShockChainReference(),
  )


def _solver_generated_invariant_field_coupled_chain_planner(
  seed_field: MocPostShockCharacteristicFieldResult,
) -> Any:
  """Exercise continued cells with a field-aware invariant boundary law."""

  if not seed_field.converged or not seed_field.upstream_shock_coupling_verified:
    return None

  start_y_m = 0.05

  def invariant_target(
    field: MocPostShockCharacteristicFieldResult,
    _index: int,
    point: tuple[float, float],
  ) -> float:
    state = field.state_at(point)
    pressure = field.static_pressure_at(point)
    if state is None or pressure is None:
      raise ValueError(
        'invariant planner could not sample the bounded prior field at '
        f'{point!r}'
      )
    downstream_angle = 2.4 * point[1]
    compression = solve_attached_compression_to_turn(
      upstream_mach=state.mach,
      gamma=state.gamma,
      upstream_pressure_Pa=pressure,
      target_turn_rad=downstream_angle - state.theta_rad,
    )
    if not compression.converged or compression.downstream_mach is None:
      raise ValueError(
        'invariant planner could not derive an attached-compression target: '
        f'{compression.message}'
      )
    return downstream_angle - prandtl_meyer_angle_rad(
      compression.downstream_mach,
      state.gamma,
    )

  return plan_post_shock_field_invariant_chain(
    seed_field,
    start_x_m=0.5,
    end_x_m=0.9,
    start_point_at=lambda _field, current, _cell_index: (
      current.end_x_m + 0.02,
      start_y_m,
    ),
    downstream_invariant_family=CharacteristicFamily.PLUS,
    downstream_invariant_at=invariant_target,
    sample_count=9,
    position_tolerance_m=1.0e-8,
    shock_angle_tolerance_rad=0.1,
  )


def _ambient_pressure_field_coupled_chain_planner(
  seed_field: MocPostShockCharacteristicFieldResult,
) -> dict[str, Any]:
  """Audit the repeated ambient-pressure planner at its bounded-domain seam."""

  if not seed_field.converged or not seed_field.upstream_shock_coupling_verified:
    return {
      'status': 'invalid_seed',
      'accepted': False,
      'planner': None,
      'claim_status': 'ambient-pressure-field-chain-pending',
    }
  planner = plan_ambient_pressure_field_chain(
    seed_field,
    start_x_m=0.5,
    end_x_m=0.9,
    start_point_at=lambda _field, _current, _cell_index: (1.2, 0.1),
    ambient_pressure_Pa=100000.0,
    outer_downstream_flow_angle_lower_rad=0.0,
    outer_downstream_flow_angle_upper_rad=0.1,
    sample_count=9,
    position_tolerance_m=1.0e-8,
  )
  report = planner.as_report()
  chain = report['chain']
  steps = report['steps']
  diagnostics = chain['diagnostics']
  planner_measurement = measure_moc_chain_planner(planner)
  accepted = (
    report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
    and report['planning_only'] is True
    and report['production_claim_allowed'] is False
    and report['step_count'] == 1
    and chain['status'] == MocChainStatus.SOLVER_TERMINATED.value
    and chain['termination_reason'] == MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value
    and chain['physical_termination'] is False
    and chain['cell_count'] == 1
    and len(steps) == 1
    and steps[0]['boundary_kind'] == MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER.value
    and steps[0]['result_kind'] == 'termination-returned'
    and steps[0]['result_termination_reason'] == MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value
    and diagnostics['termination_model'] == 'ambient-pressure-field-coupled-chain'
    and diagnostics['upstream_field_model'] == 'caller-bounded-state-pressure-field'
    and diagnostics['ambient_closure_status'] == 'ambient_closure_field_failure'
    and diagnostics['sampled_count'] == 0
    and diagnostics['first_missing_sample_index'] == 0
    and planner_measurement.converged
    and planner_measurement.termination_verified
    and planner_measurement.fidelity_isolation_verified
    and planner_measurement.physical_termination is False
    and planner_measurement.production_claim_allowed is False
  )
  return {
    'status': 'diagnostic-ambient-pressure-field-chain-boundary',
    'accepted': accepted,
    'planner': report,
    'planner_measurement': planner_measurement.as_report(),
    'claim_status': (
      'ambient-pressure-field-coupled-chain-handoff; '
      'canonical-upstream-domain-extension-pending'
    ),
  }


def _source_strip_chain_planner_probe(
  source_continuation: Any,
  seed_field: MocPostShockCharacteristicFieldResult | None,
  start_point_m: tuple[float, float],
) -> dict[str, Any]:
  """Audit the source-strip-to-chain seam at the canonical caustic boundary."""

  if (
    seed_field is None
    or not seed_field.converged
    or not seed_field.upstream_shock_coupling_verified
  ):
    return {
      'status': 'invalid_seed',
      'accepted': False,
      'planner': None,
      'claim_status': 'source-strip-shock-chain-pending',
      'message': 'source-strip planner did not receive a coupled closed seed field',
    }
  planner = plan_source_strip_shock_chain(
    seed_field,
    source_continuation,
    start_point_m=start_point_m,
    start_x_m=0.5,
    end_x_m=0.9,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  report = planner.as_report()
  chain = report['chain']
  steps = report['steps']
  planner_measurement = measure_moc_chain_planner(planner)
  accepted = (
    report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
    and report['planning_only'] is True
    and report['production_claim_allowed'] is False
    and report['step_count'] == 1
    and chain['status'] == MocChainStatus.SOLVER_TERMINATED.value
    and chain['termination_reason'] == MocChainTerminationReason.CHARACTERISTIC_CAUSTIC.value
    and chain['physical_termination'] is False
    and chain['cell_count'] == 1
    and len(steps) == 1
    and steps[0]['boundary_kind'] == MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER.value
    and steps[0]['result_kind'] == 'termination-returned'
    and steps[0]['result_termination_reason'] == MocChainTerminationReason.CHARACTERISTIC_CAUSTIC.value
    and report['diagnostics']['source_strip_chain_model'] == 'bounded-source-strip-one-step'
    and report['diagnostics']['one_step_domain'] is True
    and report['diagnostics']['source_strip_reuse_policy'] == (
      'never-reuse-after-one-next-cell-attempt'
    )
    and planner_measurement.converged
    and planner_measurement.termination_verified
    and planner_measurement.fidelity_isolation_verified
    and planner_measurement.physical_termination is False
    and planner_measurement.production_claim_allowed is False
  )
  return {
    'status': chain['status'],
    'accepted': accepted,
    'planner': report,
    'planner_measurement': planner_measurement.as_report(),
    'claim_status': planner.claim_status,
    'message': chain['message'],
  }


def _source_strip_chain_sequence_planner_probe(
  source_continuation: Any,
  seed_field: MocPostShockCharacteristicFieldResult | None,
  start_point_m: tuple[float, float],
) -> dict[str, Any]:
  """Audit the fresh-source-domain sequence seam at the canonical caustic."""

  if (
    seed_field is None
    or not seed_field.converged
    or not seed_field.upstream_shock_coupling_verified
  ):
    return {
      'status': 'invalid_seed',
      'accepted': False,
      'planner': None,
      'claim_status': 'source-strip-shock-chain-sequence-pending',
      'message': 'source-strip sequence did not receive a coupled closed seed field',
    }
  planner = plan_source_strip_shock_chain_sequence(
    seed_field,
    source_continuation,
    source_continuation_at=lambda _current, _next_index, _handoff: None,
    start_point_at=lambda _current, _next_index, _source: start_point_m,
    start_x_m=0.5,
    end_x_m=0.9,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  report = planner.as_report()
  chain = report['chain']
  steps = report['steps']
  planner_measurement = measure_moc_chain_planner(planner)
  expected_reason = (
    MocChainTerminationReason.CHARACTERISTIC_CAUSTIC.value
    if (
      source_continuation.remesh is not None
      and source_continuation.remesh.chain_termination_available
    )
    else MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value
  )
  accepted = (
    report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
    and report['planning_only'] is True
    and report['production_claim_allowed'] is False
    and report['step_count'] == 1
    and chain['status'] == MocChainStatus.SOLVER_TERMINATED.value
    and chain['termination_reason'] == expected_reason
    and chain['physical_termination'] is False
    and chain['cell_count'] == 1
    and len(steps) == 1
    and steps[0]['boundary_kind'] == MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER.value
    and steps[0]['result_kind'] == 'termination-returned'
    and steps[0]['result_termination_reason'] == expected_reason
    and report['diagnostics']['source_strip_chain_model'] == (
      'bounded-source-strip-fresh-domain-sequence'
    )
    and report['diagnostics']['one_step_domain'] is False
    and report['diagnostics']['source_domain_count'] == 1
    and report['diagnostics']['source_domain_attempt_count'] == 1
    and report['diagnostics']['source_strip_reuse_policy'] == (
      'fresh-bounded-source-strip-required-per-cell'
    )
    and planner_measurement.converged
    and planner_measurement.termination_verified
    and planner_measurement.fidelity_isolation_verified
    and planner_measurement.physical_termination is False
    and planner_measurement.production_claim_allowed is False
  )
  return {
    'status': chain['status'],
    'accepted': accepted,
    'planner': report,
    'planner_measurement': planner_measurement.as_report(),
    'claim_status': planner.claim_status,
    'message': chain['message'],
  }


def _solver_generated_chain_terminal_probe(
  seed_field: MocPostShockCharacteristicFieldResult,
) -> dict[str, Any]:
  """Exercise a continued-cell solver that stops at a typed normal shock."""

  if not seed_field.converged:
    return {
      'status': 'invalid_seed',
      'physical_termination': False,
      'message': f'generated chain terminal probe received an open seed: {seed_field.message}',
      'claim_status': 'typed-terminal-chain-stop-pending',
    }

  def solve_next(current, cell_index, handoff):
    return solve_marched_attached_shock_chain_cell_or_termination(
      current,
      cell_index,
      handoff,
      start_point_m=(current.end_x_m + 0.2, 0.5),
      end_x_m=current.end_x_m + 0.8,
      upstream_state_at=lambda point: CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.2 * point[1] / 0.5,
        mach=2.0,
        gamma=1.4,
      ),
      upstream_pressure_at=lambda _point: 100000.0,
      downstream_flow_angle_rad=0.0,
      sample_count=9,
    )

  planner = plan_post_shock_characteristic_chain(
    seed_field,
    solve_next,
    start_x_m=0.5,
    end_x_m=1.0,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  )
  chain = planner.chain
  planner_measurement = measure_moc_chain_planner(planner)
  return {
    **chain.as_report(),
    'planner': {
      'planner_kind': planner.planner_kind.value,
      'planning_only': planner.as_report()['planning_only'],
      'production_claim_allowed': planner.production_claim_allowed,
      'planner_step_count': len(planner.steps),
      'planner_steps': [step.as_report() for step in planner.steps],
      'claim_status': planner.claim_status,
    },
    'expected_physical_termination': (
      chain.physical_termination
      and chain.status is MocChainStatus.PHYSICALLY_TERMINATED
      and chain.cell_count == 1
      and chain.resolved
      and chain.termination_reason is MocChainTerminationReason.PHYSICAL_TERMINATION
      and chain.diagnostics.get('termination_model') == 'normal-shock-terminal'
      and planner_measurement.converged
      and planner_measurement.termination_verified
      and planner_measurement.fidelity_isolation_verified
      and planner_measurement.physical_termination is True
      and planner_measurement.production_claim_allowed is False
    ),
    'planner_measurement': planner_measurement.as_report(),
    'claim_status': (
      'solver-generated-continued-cell-to-typed-normal-shock-stop; '
      'mixed-regime-cell-promotion-pending'
    ),
  }


def _reflected_zone_chain_boundary_probe(
  reflected_zone: MocReflectedCharacteristicZoneResult,
  seed_field: MocPostShockCharacteristicFieldResult | None,
) -> dict[str, Any]:
  """Expose a bounded reflected-zone chain stop without raising or extrapolating."""

  if not reflected_zone.converged or seed_field is None or not seed_field.converged:
    return {
      'status': 'invalid_input',
      'accepted': False,
      'physical_termination': False,
      'message': 'reflected-zone chain-boundary probe requires converged inputs',
      'claim_status': 'typed-upstream-field-boundary-stop-pending',
    }
  if not reflected_zone.boundary_states:
    return {
      'status': 'invalid_input',
      'accepted': False,
      'physical_termination': False,
      'message': 'reflected-zone chain-boundary probe requires a boundary anchor',
      'claim_status': 'typed-upstream-field-boundary-stop-pending',
    }
  start_point = reflected_zone.boundary_states[-1]
  try:
    _seed = seed_field.as_coupled_chain_cell(start_x_m=0.0, end_x_m=0.5)
  except (TypeError, ValueError) as error:
    return {
      'status': 'invalid_seed',
      'accepted': False,
      'physical_termination': False,
      'message': f'reflected-zone chain-boundary seed rejected: {error}',
      'claim_status': 'typed-upstream-field-boundary-stop-pending',
    }
  chain = continue_post_shock_characteristic_chain(
    seed_field,
    lambda cell, cell_index, handoff: (
      solve_marched_attached_shock_chain_cell_from_reflected_zone_or_termination(
        cell,
        cell_index,
        handoff,
        reflected_zone,
        start_point_m=(start_point.x_m, start_point.y_m),
        end_x_m=1.5,
        downstream_flow_angle_rad=0.05,
        sample_count=9,
      )
    ),
    start_x_m=0.0,
    end_x_m=0.5,
    require_upstream_shock_coupling=True,
  )
  report = chain.as_report()
  return {
    **report,
    'accepted': (
      report['status'] == 'solver-terminated'
      and report['physical_termination'] is False
      and report['termination_reason'] == 'upstream-field-boundary'
      and report['diagnostics']['coupling_status'] == 'outside_reflected_zone_domain'
    ),
    'claim_status': 'typed-nonphysical-upstream-field-boundary-stop',
  }


def _post_shock_zone_chain_planner_probe(
  post_shock_zone: Any,
  seed_field: MocPostShockCharacteristicFieldResult,
) -> dict[str, Any]:
  """Exercise one bounded open-zone planner step with a typed terminal."""

  if (
    not getattr(post_shock_zone, 'converged', False)
    or not getattr(post_shock_zone, 'state_sampling_available', False)
    or not seed_field.converged
  ):
    return {
      'status': 'invalid_input',
      'accepted': False,
      'physical_termination': False,
      'message': (
        'bounded open-zone planner probe requires a converged, state-sampling '
        'post-shock zone and a converged seed field'
      ),
      'claim_status': 'bounded-open-post-shock-zone-chain-pending',
    }
  try:
    seed = seed_field.as_chain_cell(start_x_m=0.5, end_x_m=0.85)
  except (TypeError, ValueError) as error:
    return {
      'status': 'invalid_seed',
      'accepted': False,
      'physical_termination': False,
      'message': f'bounded open-zone planner seed rejected: {error}',
      'claim_status': 'bounded-open-post-shock-zone-chain-pending',
    }

  def downstream_angle(
    _sample_index: int,
    point: tuple[float, float],
  ) -> float:
    return 0.02 * max(-1.0, min(1.0, point[1] / 0.001))

  planner = plan_post_shock_zone_chain(
    seed,
    post_shock_zone,
    start_point_m=(0.9, 0.01),
    end_x_m=1.35,
    downstream_flow_angle_at=downstream_angle,
    sample_count=5,
    position_tolerance_m=1.0e-8,
  )
  report = planner.as_report()
  chain = report['chain']
  steps = report['steps']
  diagnostics = chain['diagnostics']
  planner_measurement = measure_moc_chain_planner(planner)
  accepted = (
    report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
    and report['planning_only'] is True
    and report['production_claim_allowed'] is False
    and report['step_count'] == 1
    and chain['status'] == MocChainStatus.PHYSICALLY_TERMINATED.value
    and chain['termination_reason'] == MocChainTerminationReason.PHYSICAL_TERMINATION.value
    and chain['physical_termination'] is True
    and chain['cell_count'] == 1
    and len(steps) == 1
    and steps[0]['boundary_kind'] == MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER.value
    and steps[0]['result_kind'] == 'termination-returned'
    and steps[0]['result_status'] == MocChainTerminationReason.PHYSICAL_TERMINATION.value
    and steps[0]['result_termination_reason'] == MocChainTerminationReason.PHYSICAL_TERMINATION.value
    and steps[0]['result_physical_termination'] is True
    and diagnostics['termination_model'] == 'normal-shock-terminal'
    and diagnostics['upstream_field_model'] == 'bounded-open-post-shock-zone'
    and diagnostics['upstream_sample_count'] == 4
    and planner_measurement.converged
    and planner_measurement.termination_verified
    and planner_measurement.fidelity_isolation_verified
    and planner_measurement.physical_termination is True
    and planner_measurement.production_claim_allowed is False
  )
  return {
    'status': 'diagnostic-bounded-open-post-shock-zone-chain',
    'accepted': accepted,
    'physical_termination': chain['physical_termination'],
    'open_zone': post_shock_zone.as_report(),
    'planner': report,
    'planner_measurement': planner_measurement.as_report(),
    'claim_status': (
      'bounded-open-post-shock-zone-next-shock; '
      'mixed-regime-downstream-closure-pending'
    ),
  }


def _caustic_family_restart_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
) -> dict[str, Any]:
  """Run both one-sided open-family restart orientations at the caustic."""

  if seed is None:
    return {
      'status': 'missing_seed',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-new-family-restart-pending',
    }
  cases: list[dict[str, Any]] = []
  for anchor_edge_index in (0, 1):
    result = restart_characteristic_family_from_caustic(
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=6,
    )
    report = result.as_report()
    report['accepted'] = (
      result.converged
      and result.physical_closure_verified is False
      and result.chain_promotion_blocked
      and result.caustic_handoff_verified
      and result.boundary_sample_count == 6
      and result.minimum_forward_progress_m is not None
      and result.minimum_forward_progress_m > 0.0
      and result.maximum_absolute_pressure_residual is not None
      and result.maximum_absolute_pressure_residual <= 1.0e-10
      and result.maximum_absolute_tangent_residual is not None
      and result.maximum_absolute_tangent_residual <= 1.0e-10
      and result.source_strip is not None
      and not result.source_strip.converged
      and result.family_band is not None
      and result.family_band.converged
      and result.family_band.cell_count == 11
      and result.family_band.topology.connected
      and result.family_band.topology.forms_closed_zone
      and result.family_band.caustic_handoff_verified
      and result.family_band.anchor_point_m == result.anchor_point_m
      and result.family_band.anchor_state == result.anchor_state
      and result.family_band.anchor_to_input_min_forward_progress_m is not None
      and result.family_band.anchor_to_input_min_forward_progress_m > 0.0
      and result.family_band.physical_closure_verified is False
      and result.family_band.chain_promotion_blocked
      and result.as_chain_termination_decision().physical_termination is False
      and result.as_chain_termination_decision().reason is MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
      and result.as_chain_termination_decision().diagnostics['old_family_bridge_verified'] is False
    )
    cases.append(report)
  return {
    'status': 'diagnostic-open-new-family-boundary-restarts',
    'accepted': all(case['accepted'] is True for case in cases),
    'cases': cases,
    'claim_status': (
      'one-sided-new-family-boundary-restart-only; interior-remesh-and-'
      'shock-closure-pending'
    ),
  }


def _caustic_shock_bridge_probe(seed: Any) -> dict[str, Any]:
  """Audit the explicit-invariant local shock bridge at the caustic."""

  if (
    seed is None
    or len(getattr(seed, 'edge_states', ())) != 2
    or seed.edge_states[1].state is None
  ):
    return {
      'status': 'missing_seed_or_edge_state',
      'accepted': False,
      'bridge': None,
      'claim_status': 'caustic-local-shock-bridge-pending',
    }
  target_invariant = seed.edge_states[1].state.k_plus
  bridge = solve_caustic_shock_bridge(
    seed,
    CharacteristicFamily.PLUS,
    target_invariant,
    upstream_edge_index=0,
  )
  remesh = prepare_caustic_shock_remesh(
    seed,
    CharacteristicFamily.PLUS,
    target_invariant,
    upstream_edge_index=0,
  )
  report = bridge.as_report()
  remesh_report = remesh.as_report()
  report['accepted'] = (
    bridge.status is MocCausticShockBridgeStatus.CONVERGED_LOCAL_COMPATIBILITY
    and bridge.converged
    and bridge.entropy_admissible
    and bridge.invariant_residual is not None
    and abs(bridge.invariant_residual) <= 1.0e-10
    and bridge.downstream_state is not None
    and abs(bridge.downstream_state.k_plus - target_invariant) <= 1.0e-10
    and bridge.shock_curve_verified is False
    and bridge.physical_closure_verified is False
    and bridge.chain_promotion_blocked
    and remesh.status is MocCausticShockRemeshPreparationStatus.READY_FOR_COUPLED_REMESH
    and remesh.converged
    and remesh.local_shock_state_ready
    and remesh.request is not None
    and remesh.request.event_point_m == seed.event.caustic_point_m
    and remesh.request.local_bridge is remesh.local_bridge
    and remesh.shock_curve_verified is False
    and remesh.downstream_field_verified is False
    and remesh.physical_closure_verified is False
    and remesh.chain_promotion_blocked
  )
  report['remesh_preparation'] = remesh_report
  report['remesh_preparation_accepted'] = (
    remesh.status is MocCausticShockRemeshPreparationStatus.READY_FOR_COUPLED_REMESH
    and remesh.converged
    and remesh.local_shock_state_ready
    and remesh.request is not None
  )
  return {
    'status': 'diagnostic-invariant-conditioned-caustic-shock-bridge',
    'accepted': report['accepted'],
    'bridge': report,
    'remesh_preparation': remesh_report,
    'remesh_preparation_accepted': report['remesh_preparation_accepted'],
    'claim_status': (
      'local-invariant-conditioned-shock-state-only; shock-curve-and-'
      'downstream-field-pending'
    ),
  }


def _build_diagnostic_caustic_upstream_request(
  seed: Any,
  total_pressure_Pa: float,
  *,
  invariant_step: float = 0.004,
  theta_step: float = -0.006,
) -> MocCausticUpstreamRemeshRequest:
  """Build the deterministic two-trace fixture used by caustic probes."""

  selected = seed.edge_states[0].state
  if selected is None or seed.event is None or seed.event.caustic_point_m is None:
    raise ValueError('caustic request fixture requires a selected seed event')
  event = seed.event.caustic_point_m
  centerline_states: list[CharacteristicState] = []
  outer_states: list[CharacteristicState] = []
  for index in range(6):
    k_plus = selected.k_plus + invariant_step * index
    theta = selected.theta_rad + theta_step * index
    centerline_inverse = inverse_prandtl_meyer_angle_rad(
      -k_plus,
      selected.gamma,
    )
    outer_inverse = inverse_prandtl_meyer_angle_rad(
      theta - k_plus,
      selected.gamma,
    )
    if centerline_inverse.value is None or outer_inverse.value is None:
      raise ValueError(
        'deterministic caustic Cauchy trace inversion did not converge'
      )
    centerline_probe = CharacteristicState(
      x_m=0.0,
      y_m=0.0,
      theta_rad=0.0,
      mach=centerline_inverse.value,
      gamma=selected.gamma,
    )
    outer_probe = CharacteristicState(
      x_m=0.0,
      y_m=0.0,
      theta_rad=theta,
      mach=outer_inverse.value,
      gamma=selected.gamma,
    )
    characteristic_angle = 0.5 * (
      centerline_probe.theta_rad
      + centerline_probe.mu_rad
      + outer_probe.theta_rad
      + outer_probe.mu_rad
    )
    sine = sin(characteristic_angle)
    if abs(sine) <= 1.0e-12:
      raise ValueError(
        'deterministic caustic Cauchy trace has a degenerate characteristic'
      )
    y = event[1] * (1.0 - 0.12 * index)
    if index == 0:
      centerline_x = event[0] - event[1] * cos(characteristic_angle) / sine
    else:
      centerline_x = 0.5191348811250018 + 0.027 * index
    centerline_states.append(
      CharacteristicState(
        x_m=centerline_x,
        y_m=0.0,
        theta_rad=0.0,
        mach=centerline_inverse.value,
        gamma=selected.gamma,
      )
    )
    if index == 0:
      outer_states.append(selected)
    else:
      distance = y / sine
      outer_states.append(
        CharacteristicState(
          x_m=centerline_x + distance * cos(characteristic_angle),
          y_m=y,
          theta_rad=theta,
          mach=outer_inverse.value,
          gamma=selected.gamma,
        )
      )
  return MocCausticUpstreamRemeshRequest(
    seed=seed,
    upstream_edge_index=0,
    centerline_source_states=tuple(centerline_states),
    outer_source_states=tuple(outer_states),
    total_pressure_Pa=total_pressure_Pa,
  )


def _caustic_upstream_cauchy_remesh_probe(
  seed: Any,
  total_pressure_Pa: float,
  field: MocPostShockCharacteristicFieldResult | None,
) -> dict[str, Any]:
  """Audit the explicit two-trace caustic upstream remesh lane.

  The trace construction is a deterministic compatibility fixture for this
  report.  It exercises the solver-owned Cauchy assembler and its one-step
  planner contract; it is not the canonical free-boundary remesher.
  """

  def failure(status: str, message: str) -> dict[str, Any]:
    return {
      'status': status,
      'accepted': False,
      'remesh': None,
      'direct_shock': None,
      'planner': None,
      'planner_measurement': None,
      'message': message,
      'claim_status': 'caustic-upstream-cauchy-remesh-pending',
    }

  if (
    seed is None
    or field is None
    or len(getattr(seed, 'edge_states', ())) != 2
    or seed.edge_states[0].state is None
    or seed.event is None
    or seed.event.caustic_point_m is None
  ):
    return failure(
      'missing_seed_or_post_shock_field',
      'explicit caustic Cauchy remesh requires a seed event and post-shock field',
    )

  try:
    request = _build_diagnostic_caustic_upstream_request(
      seed,
      total_pressure_Pa,
    )
    remesh = solve_caustic_upstream_remesh(request)
    direct_shock = None
    if remesh.state_sampling_available and remesh.strip is not None:
      direct_shock = solve_marched_attached_shock_from_source_strip(
        remesh.strip,
        request.event_point_m,
        downstream_flow_angle_rad=0.2,
        sample_count=9,
        shock_angle_tolerance_rad=0.2,
      )
    planner = None
    if direct_shock is not None:
      planner = plan_caustic_upstream_remesh_shock_chain(
        field,
        remesh,
        start_point_m=request.event_point_m,
        start_x_m=0.2,
        end_x_m=0.6,
        downstream_flow_angle_rad=0.2,
        sample_count=9,
        shock_angle_tolerance_rad=0.2,
        policy=MocChainContinuationPolicy(
          max_cells=2,
          require_state_carry=True,
        ),
      )
    planner_measurement = (
      None if planner is None else measure_moc_chain_planner(planner)
    )
    accepted = bool(
      remesh.status is MocCausticUpstreamRemeshStatus.CONVERGED_BOUNDED_FIELD
      and remesh.converged
      and remesh.state_sampling_available
      and remesh.event_seam_verified
      and remesh.centerline_trace_verified
      and remesh.outer_trace_verified
      and remesh.source_field_verified
      and remesh.physical_closure_verified is False
      and remesh.chain_promotion_blocked
      and direct_shock is not None
      and direct_shock.status.value == 'upstream_field_failure'
      and direct_shock.sample_count == 4
      and direct_shock.failed_sample_index == 4
      and planner is not None
      and planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
      and planner.production_claim_allowed is False
      and planner.chain.status is MocChainStatus.SOLVER_TERMINATED
      and planner.chain.cell_count == 1
      and planner.chain.physical_termination is False
      and planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      and len(planner.steps) == 1
      and planner.steps[0].result_kind == 'termination-returned'
      and planner.steps[0].result_termination_reason is (
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      )
      and planner.diagnostics.get('one_step_domain') is True
      and planner.diagnostics.get('source_strip_reuse_policy') == (
        'never-reuse-after-one-next-cell-attempt'
      )
      and planner_measurement is not None
      and planner_measurement.converged
      and planner_measurement.termination_verified
      and planner_measurement.fidelity_isolation_verified
      and planner_measurement.physical_termination is False
      and planner_measurement.production_claim_allowed is False
    )
    return {
      'status': 'diagnostic-caustic-upstream-cauchy-remesh',
      'accepted': accepted,
      'remesh': remesh.as_report(),
      'direct_shock': (
        None if direct_shock is None else direct_shock.as_report()
      ),
      'planner': None if planner is None else planner.as_report(),
      'planner_measurement': (
        None
        if planner_measurement is None
        else planner_measurement.as_report()
      ),
      'trace_model': (
        'deterministic-compatible-centerline-c-plus-and-outer-pre-shock-'
        'c-minus-diagnostic-traces'
      ),
      'claim_status': (
        'solver-owned-two-trace-cauchy-remesh-and-one-step-chain-attempt; '
        'canonical-outer-trace-and-physical-closure-pending'
      ),
    }
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return failure('caustic-upstream-cauchy-remesh-failure', str(error))


def _caustic_upstream_remesh_chain_sequence_probe(
  seed: Any,
  total_pressure_Pa: float,
  field: MocPostShockCharacteristicFieldResult | None,
) -> dict[str, Any]:
  """Audit repeated caustic remesh orchestration and its fidelity ceiling.

  The remesh domains are solver-assembled two-trace fixtures.  A prescribed
  local cell solver is patched only inside this report probe so the sequence
  planner can reach the later provider seam deterministically.  The report
  therefore validates handoff provenance and fresh-domain enforcement, not a
  production shock-cell or free-boundary solution.
  """

  def failure(status: str, message: str) -> dict[str, Any]:
    return {
      'status': status,
      'accepted': False,
      'initial_remesh': None,
      'replacement_remesh': None,
      'planner': None,
      'planner_measurement': None,
      'provider_attempts': [],
      'provider_calls': [],
      'prescribed_cell_solver': None,
      'message': message,
      'claim_status': 'caustic-upstream-remesh-chain-sequence-pending',
    }

  if (
    seed is None
    or field is None
    or not field.converged
    or not field.upstream_shock_coupling_verified
  ):
    return failure(
      'missing_seed_or_post_shock_field',
      'caustic remesh sequence requires a seed event and coupled post-shock field',
    )

  try:
    initial_request = _build_diagnostic_caustic_upstream_request(
      seed,
      total_pressure_Pa,
    )
    replacement_request = _build_diagnostic_caustic_upstream_request(
      seed,
      total_pressure_Pa,
      invariant_step=0.005,
      theta_step=-0.005,
    )
    initial = solve_caustic_upstream_remesh(initial_request)
    replacement = solve_caustic_upstream_remesh(replacement_request)
    if (
      not initial.converged
      or initial.strip is None
      or not replacement.converged
      or replacement.strip is None
      or initial.strip is replacement.strip
    ):
      return failure(
        'remesh_fixture_failure',
        'caustic remesh sequence fixtures did not produce distinct bounded source strips',
      )

    cell_solver_fixture = MocPrescribedPostShockChainMock(
      total_cell_count=3,
      cell_axial_length_m=0.10,
      shock_start_offset_m=0.005,
      shock_sample_spacing_m=0.02,
    )
    provider_calls: list[dict[str, Any]] = []

    def solve_cell(
      current,
      next_cell_index,
      incoming_handoff,
      source_strip,
      **kwargs,
    ):
      del source_strip, kwargs
      return cell_solver_fixture.solve_next(
        current,
        next_cell_index,
        incoming_handoff,
      )

    def remesh_at(current, next_cell_index, incoming_handoff):
      provider_calls.append({
        'current_cell_index': current.cell_index,
        'next_cell_index': next_cell_index,
        'incoming_handoff_sample_count': len(incoming_handoff),
      })
      if replacement.request is None:
        return None
      return replace(
        replacement,
        request=replace(
          replacement.request,
          incoming_handoff=tuple(incoming_handoff),
        ),
      )

    with patch(
      'exhaust_plume.models.moc.planner.solve_marched_attached_shock_chain_cell_from_source_strip_or_termination',
      solve_cell,
    ):
      planner = plan_caustic_upstream_remesh_shock_chain_sequence(
        field,
        initial,
        remesh_at,
        start_point_at=lambda current, _index, _remesh: (
          current.end_x_m + 0.01,
          0.25,
        ),
        start_x_m=0.3,
        end_x_m=0.4,
        downstream_flow_angle_rad=0.05,
        sample_count=9,
        policy=MocChainContinuationPolicy(
          max_cells=4,
          require_state_carry=True,
        ),
      )
    planner = replace(
      planner,
      diagnostics={
        **planner.diagnostics,
        'prescribed_cell_solver_mock': cell_solver_fixture.as_report(),
      },
    )
    planner_measurement = measure_moc_chain_planner(planner)
    planner_report = planner.as_report()
    attempts = planner.diagnostics['upstream_remesh_domain_attempts']
    chain = planner.chain
    accepted = bool(
      planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
      and planner.production_claim_allowed is False
      and planner_report['planning_only'] is True
      and chain.status is MocChainStatus.SOLVER_TERMINATED
      and chain.cell_count == 3
      and chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      and chain.physical_termination is False
      and planner.handoff_links_verified is True
      and len(planner.steps) == 3
      and len(provider_calls) == 2
      and len(attempts) == 3
      and attempts[1]['incoming_handoff_verified'] is True
      and attempts[2]['incoming_handoff_verified'] is True
      and attempts[2]['fresh_remesh'] is False
      and attempts[2]['fresh_strip'] is False
      and planner.diagnostics['one_step_domain'] is False
      and planner.diagnostics['upstream_remesh_domain_count'] == 2
      and planner.diagnostics['upstream_remesh_domain_attempt_count'] == 3
      and planner_measurement.converged
      and planner_measurement.termination_verified
      and planner_measurement.fidelity_isolation_verified
      and planner_measurement.physical_termination is False
      and planner_measurement.production_claim_allowed is False
    )
    return {
      'status': 'diagnostic-caustic-upstream-remesh-chain-sequence',
      'accepted': accepted,
      'initial_remesh': initial.as_report(),
      'replacement_remesh': replacement.as_report(),
      'planner': planner_report,
      'planner_measurement': planner_measurement.as_report(),
      'provider_attempts': attempts,
      'provider_calls': provider_calls,
      'prescribed_cell_solver': cell_solver_fixture.as_report(),
      'claim_status': (
        'solver-assembled-remesh-and-prescribed-cell-sequence-audit; '
        'canonical-outer-trace-mixed-regime-closure-and-production-provider-pending'
      ),
    }
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return failure('caustic-upstream-remesh-chain-sequence-failure', str(error))


def _caustic_shock_remesh_execution_probe(
  seed: Any,
  old_family: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
) -> dict[str, Any]:
  """Exercise the bounded caustic remesh executor and one-step planner.

  The canonical reflected seed has a positive event-side turn, so it is not a
  suitable local compression fixture for a forward shock ending on the axis.
  The probe changes only the selected one-sided state angle, keeps the event
  and local invariant seam solver-owned, and labels the resulting field as a
  research contract fixture.  It deliberately stops at open physical
  closure; no remesh result is appended to the chain.
  """

  if (
    seed is None
    or len(getattr(seed, 'edge_states', ())) != 2
    or seed.edge_states[0].state is None
    or seed.edge_states[1].state is None
  ):
    return {
      'status': 'missing_seed_or_edge_state',
      'accepted': False,
      'direct': None,
      'planner': None,
      'direct_measurement': None,
      'bridge_coupled_remesh': None,
      'bridge_coupled_measurement': None,
      'bridge_coupled_planner': None,
      'upstream_cauchy_remesh': None,
      'claim_status': 'caustic-remesh-execution-pending',
    }

  negative_state = replace(seed.edge_states[0].state, theta_rad=-0.2)
  fixture_seed = replace(
    seed,
    edge_states=(
      replace(seed.edge_states[0], state=negative_state),
      *seed.edge_states[1:],
    ),
  )
  target_invariant = fixture_seed.edge_states[1].state.k_plus
  prepared = prepare_caustic_shock_remesh(
    fixture_seed,
    CharacteristicFamily.PLUS,
    target_invariant,
    upstream_edge_index=0,
  )
  if prepared.request is None:
    return {
      'status': 'preparation_failure',
      'accepted': False,
      'direct': None,
      'planner': None,
      'direct_measurement': None,
      'bridge_coupled_remesh': None,
      'bridge_coupled_measurement': None,
      'bridge_coupled_planner': None,
      'upstream_cauchy_remesh': None,
      'preparation': prepared.as_report(),
      'claim_status': 'caustic-remesh-execution-pending',
    }
  request = prepared.request
  bridge_state = request.local_bridge.downstream_state
  if bridge_state is None or abs(request.event_point_m[1]) <= 1.0e-12:
    return {
      'status': 'invalid_fixture_bridge',
      'accepted': False,
      'direct': None,
      'planner': None,
      'direct_measurement': None,
      'bridge_coupled_remesh': None,
      'bridge_coupled_measurement': None,
      'bridge_coupled_planner': None,
      'upstream_cauchy_remesh': None,
      'preparation': prepared.as_report(),
      'claim_status': 'caustic-remesh-execution-pending',
    }

  reference = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  if reference.field is None:
    return {
      'status': 'reference_field_failure',
      'accepted': False,
      'direct': None,
      'planner': None,
      'direct_measurement': None,
      'bridge_coupled_remesh': None,
      'bridge_coupled_measurement': None,
      'bridge_coupled_planner': None,
      'upstream_cauchy_remesh': None,
      'preparation': prepared.as_report(),
      'claim_status': 'caustic-remesh-execution-pending',
    }
  current = reference.field.as_coupled_chain_cell(start_x_m=0.2, end_x_m=0.5)
  caustic_upstream_cauchy_remesh = _caustic_upstream_cauchy_remesh_probe(
    seed,
    total_pressure_Pa,
    reference.field,
  )

  def upstream_state_at(point_m: tuple[float, float]) -> CharacteristicState:
    if point_m == request.event_point_m:
      return request.upstream_state
    return CharacteristicState(
      x_m=point_m[0],
      y_m=point_m[1],
      theta_rad=request.upstream_state.theta_rad,
      mach=request.upstream_state.mach,
      gamma=request.upstream_state.gamma,
    )

  def invariant_law(_index: int, point_m: tuple[float, float]) -> float:
    desired_angle = bridge_state.theta_rad * max(
      0.0,
      min(1.0, point_m[1] / request.event_point_m[1]),
    )
    compression = solve_attached_compression_to_turn(
      upstream_mach=request.upstream_state.mach,
      gamma=request.upstream_state.gamma,
      upstream_pressure_Pa=request.upstream_static_pressure_Pa,
      target_turn_rad=desired_angle - request.upstream_state.theta_rad,
    )
    if compression.downstream_mach is None:
      raise ValueError('remesh validation invariant law produced no downstream Mach')
    return desired_angle - prandtl_meyer_angle_rad(
      compression.downstream_mach,
      request.upstream_state.gamma,
    )

  direct = solve_caustic_shock_remesh(
    request,
    upstream_state_at,
    lambda _point: request.upstream_static_pressure_Pa,
    current.continuation_boundary,
    downstream_invariant_at=invariant_law,
    target_centerline_y_m=0.0,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )
  simple_wave_terminal = solve_caustic_simple_wave_terminal_remesh(
    request,
    current.continuation_boundary,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )
  simple_wave_terminal_planner = plan_caustic_simple_wave_terminal_chain(
    current,
    request,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
    policy=MocChainContinuationPolicy(
      # The seed counts as cell one; two permits exactly one attempted
      # research handoff before the terminal decision is recorded.
      max_cells=2,
      require_state_carry=True,
    ),
  )
  bridge_restart = restart_characteristic_family_from_caustic(
    fixture_seed,
    total_pressure_Pa,
    ambient_pressure_Pa,
    anchor_edge_index=0,
    sample_count=6,
  )
  bridge_coupled_remesh = None
  bridge_coupled_measurement = None
  bridge_coupled_planner = None
  if bridge_restart.family_band is not None and bridge_restart.family_band.converged:
    upstream_bridge = build_caustic_upstream_bridge(
      old_family,
      bridge_restart.family_band,
      side_at=lambda _point: MocCausticBridgeSide.RESTARTED_FAMILY,
    )
    bridge_coupled_remesh = solve_caustic_shock_remesh_from_upstream_bridge(
      request,
      upstream_bridge,
      current.continuation_boundary,
      downstream_invariant_at=lambda _index, _point: request.downstream_invariant_target,
      target_centerline_y_m=0.0,
      sample_count=9,
      shock_angle_tolerance_rad=0.2,
    )
    bridge_coupled_measurement = measure_moc_caustic_remesh(
      MocCausticRemeshObservation(
        remesh_result=bridge_coupled_remesh,
        upstream_bridge=upstream_bridge,
        incoming_handoff=current.continuation_boundary,
      ),
    )
    bridge_coupled_planner = plan_caustic_shock_remesh_chain_from_upstream_bridge(
      current,
      request,
      upstream_bridge,
      downstream_invariant_at=lambda _index, _point: request.downstream_invariant_target,
      target_centerline_y_m=0.0,
      sample_count=9,
      shock_angle_tolerance_rad=0.2,
    )
  planner = plan_caustic_shock_remesh_chain(
    current,
    request,
    upstream_state_at,
    lambda _point: request.upstream_static_pressure_Pa,
    downstream_invariant_at=invariant_law,
    target_centerline_y_m=0.0,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )
  downstream_field_planner = plan_caustic_remesh_downstream_field_chain(
    direct,
    start_x_m=request.event_point_m[0],
    end_x_m=request.event_point_m[0] + 0.1,
    start_point_at=lambda _field, _cell, _index: (0.7, 0.05),
    downstream_flow_angle_rad=0.2,
    policy=MocChainContinuationPolicy(
      max_cells=1,
      require_state_carry=True,
    ),
    allow_research_continuation=True,
  )
  invariant_downstream_field_planner = plan_caustic_remesh_downstream_field_invariant_chain(
    direct,
    start_x_m=request.event_point_m[0],
    end_x_m=request.event_point_m[0] + 0.1,
    start_point_at=lambda _field, _cell, _index: (0.7, 0.05),
    downstream_invariant_family=CharacteristicFamily.PLUS,
    downstream_invariant_at=(
      lambda _field, _index, _point: request.downstream_invariant_target
    ),
    policy=MocChainContinuationPolicy(
      max_cells=1,
      require_state_carry=True,
    ),
    allow_research_continuation=True,
  )
  direct_report = direct.as_report()
  direct_measurement = measure_moc_caustic_remesh(
    MocCausticRemeshObservation(
      remesh_result=direct,
      incoming_handoff=current.continuation_boundary,
    ),
  )
  planner_report = planner.as_report()
  downstream_field_planner_report = downstream_field_planner.as_report()
  invariant_downstream_field_planner_report = invariant_downstream_field_planner.as_report()
  planner_measurement = measure_moc_chain_planner(planner)
  bridge_coupled_planner_measurement = (
    None
    if bridge_coupled_planner is None
    else measure_moc_chain_planner(bridge_coupled_planner)
  )
  simple_wave_terminal_planner_measurement = measure_moc_chain_planner(
    simple_wave_terminal_planner
  )
  accepted = (
    prepared.converged
    and direct.status is MocCausticShockRemeshStatus.CONVERGED_COUPLED_REMESH
    and direct.converged
    and direct.remesh_seam_verified
    and direct.event_seam_verified
    and direct.local_bridge_state_verified
    and direct.upstream_coupling_verified
    and direct.shock_curve_verified
    and direct.downstream_field_verified
    and direct.physical_closure_verified is False
    and direct.chain_promotion_blocked
    and direct_measurement.status is MocCausticRemeshMeasurementStatus.CONVERGED
    and direct_measurement.bounded_remesh_verified
    and direct_measurement.physical_closure_verified is False
    and direct_measurement.chain_promotion_blocked
    and planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
    and planner.production_claim_allowed is False
    and planner.chain.cell_count == 1
    and planner.chain.physical_termination is False
    and planner.chain.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    and len(planner.steps) == 1
    and planner.steps[0].result_kind == 'termination-returned'
    and planner.steps[0].incoming_handoff_sample_count == len(
      current.continuation_boundary
    )
    and planner_measurement.converged
    and planner_measurement.termination_verified
    and planner_measurement.fidelity_isolation_verified
    and planner_measurement.physical_termination is False
    and planner_measurement.production_claim_allowed is False
    and caustic_upstream_cauchy_remesh['accepted'] is True
    and downstream_field_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
    and downstream_field_planner.production_claim_allowed is False
    and downstream_field_planner.chain.status is MocChainStatus.TRUNCATED
    and downstream_field_planner.chain.cell_count == 1
    and downstream_field_planner.chain.resolved
    and downstream_field_planner.diagnostics.get('seed_field_model') == (
      'bounded-caustic-remesh-post-shock-field'
    )
    and downstream_field_planner.diagnostics.get('remesh_physical_closure_verified') is False
    and downstream_field_planner.diagnostics.get('remesh_chain_promotion_blocked') is True
    and simple_wave_terminal.status is MocCausticSimpleWaveTerminalStatus.CONVERGED_OPEN_TERMINAL_FIELD
    and simple_wave_terminal.converged
    and simple_wave_terminal.trace is not None
    and simple_wave_terminal.trace.status is MocCausticSimpleWaveTraceStatus.CONVERGED_TRACE
    and simple_wave_terminal.event_seam_verified
    and simple_wave_terminal.local_bridge_state_verified
    and simple_wave_terminal.upstream_coupling_verified
    and simple_wave_terminal.shock_prefix_verified
    and simple_wave_terminal.downstream_zone_verified
    and simple_wave_terminal.terminal_verified
    and simple_wave_terminal.physical_terminal_verified
    and simple_wave_terminal.physical_closure_verified is False
    and simple_wave_terminal.chain_promotion_blocked
    and simple_wave_terminal_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
    and simple_wave_terminal_planner.production_claim_allowed is False
    and simple_wave_terminal_planner.chain.status is MocChainStatus.SOLVER_TERMINATED
    and simple_wave_terminal_planner.chain.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    and simple_wave_terminal_planner.chain.physical_termination is False
    and simple_wave_terminal_planner.chain.cell_count == 1
    and len(simple_wave_terminal_planner.steps) == 1
    and simple_wave_terminal_planner.steps[0].result_kind == 'termination-returned'
    and simple_wave_terminal_planner.steps[0].incoming_handoff_sample_count == len(current.continuation_boundary)
    and simple_wave_terminal_planner.chain.diagnostics.get('terminal_verified') is True
    and simple_wave_terminal_planner.chain.diagnostics.get('chain_promotion_blocked') is True
    and simple_wave_terminal_planner_measurement.converged
    and simple_wave_terminal_planner_measurement.termination_verified
    and simple_wave_terminal_planner_measurement.fidelity_isolation_verified
    and simple_wave_terminal_planner_measurement.physical_termination is False
    and simple_wave_terminal_planner_measurement.production_claim_allowed is False
    and bridge_coupled_remesh is not None
    and bridge_coupled_remesh.status is MocCausticShockRemeshStatus.UPSTREAM_FIELD_FAILURE
    and bridge_coupled_remesh.upstream_bridge_verified is False
    and bridge_coupled_remesh.upstream_bridge_audit is not None
    and bridge_coupled_remesh.upstream_bridge_audit.status is MocCausticBridgeStatus.DOMAIN_GAP
    and bridge_coupled_remesh.upstream_bridge_audit.first_missing_sample_index == 1
    and bridge_coupled_remesh.shock is not None
    and bridge_coupled_remesh.shock.failed_sample_index == 1
    and bridge_coupled_remesh.upstream_bridge_audit.first_missing_point_m == (
      bridge_coupled_remesh.shock.failed_point_m
    )
    and bridge_coupled_measurement is not None
    and bridge_coupled_measurement.status is MocCausticRemeshMeasurementStatus.UPSTREAM_FAILURE
    and bridge_coupled_measurement.upstream_bridge_verified is False
    and bridge_coupled_measurement.first_missing_sample_index == 1
    and bridge_coupled_measurement.first_missing_point_m == (
      bridge_coupled_remesh.shock.failed_point_m
    )
    and bridge_coupled_planner is not None
    and bridge_coupled_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
    and bridge_coupled_planner.production_claim_allowed is False
    and bridge_coupled_planner.chain.cell_count == 1
    and bridge_coupled_planner.chain.physical_termination is False
    and bridge_coupled_planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    and bridge_coupled_planner.diagnostics.get('strict_bridge_required') is True
    and bridge_coupled_planner.chain.diagnostics['remesh_report']['upstream_bridge_audit']['status'] == (
      MocCausticBridgeStatus.DOMAIN_GAP.value
    )
    and bridge_coupled_planner_measurement is not None
    and bridge_coupled_planner_measurement.converged
    and bridge_coupled_planner_measurement.termination_verified
    and bridge_coupled_planner_measurement.fidelity_isolation_verified
    and bridge_coupled_planner_measurement.physical_termination is False
    and bridge_coupled_planner_measurement.production_claim_allowed is False
    and invariant_downstream_field_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
    and invariant_downstream_field_planner.production_claim_allowed is False
    and invariant_downstream_field_planner.chain.status is MocChainStatus.TRUNCATED
    and invariant_downstream_field_planner.chain.cell_count == 1
    and invariant_downstream_field_planner.chain.resolved
    and invariant_downstream_field_planner.diagnostics.get('downstream_invariant_family') == 'C+'
    and invariant_downstream_field_planner.diagnostics.get('remesh_chain_promotion_blocked') is True
  )
  return {
    'status': 'diagnostic-coupled-caustic-remesh-execution',
    'accepted': accepted,
    'preparation': prepared.as_report(),
    'direct': direct_report,
    'direct_measurement': direct_measurement.as_report(),
    'planner': planner_report,
    'planner_measurement': planner_measurement.as_report(),
    'upstream_cauchy_remesh': caustic_upstream_cauchy_remesh,
    'bridge_coupled_remesh': (
      None if bridge_coupled_remesh is None else bridge_coupled_remesh.as_report()
    ),
    'bridge_coupled_measurement': (
      None
      if bridge_coupled_measurement is None
      else bridge_coupled_measurement.as_report()
    ),
    'bridge_coupled_planner': (
      None if bridge_coupled_planner is None else bridge_coupled_planner.as_report()
    ),
    'bridge_coupled_planner_measurement': (
      None
      if bridge_coupled_planner_measurement is None
      else bridge_coupled_planner_measurement.as_report()
    ),
    'downstream_field_planner': downstream_field_planner_report,
    'invariant_downstream_field_planner': invariant_downstream_field_planner_report,
    'simple_wave_terminal': simple_wave_terminal.as_report(),
    'simple_wave_terminal_planner': simple_wave_terminal_planner.as_report(),
    'simple_wave_terminal_planner_measurement': (
      simple_wave_terminal_planner_measurement.as_report()
    ),
    'incoming_handoff_sample_count': len(current.continuation_boundary),
    'claim_status': (
      'solver-backed-local-caustic-remesh-and-one-step-planner; '
      'open-physical-closure-and-external-validation-pending'
    ),
  }


def _caustic_family_band_shock_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
) -> dict[str, Any]:
  """Couple the open family band to a bounded shock-march diagnostic."""

  if seed is None:
    return {
      'status': 'missing_seed',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-family-band-shock-coupling-pending',
    }
  cases: list[dict[str, Any]] = []
  for anchor_edge_index in (0, 1):
    restart = restart_characteristic_family_from_caustic(
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=6,
    )
    band = restart.family_band
    if band is None or not band.converged or len(band.boundary_states) < 3:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': False,
        'status': 'missing_open_family_band',
        'shock': None,
      })
      continue
    start = band.boundary_states[-2]
    start_point = (start.x_m, start.y_m)

    def downstream_angle_at(
      _index: int,
      point_m: tuple[float, float],
    ) -> float:
      fraction = max(0.0, min(1.0, point_m[1] / start.y_m))
      return 0.05 * fraction

    try:
      shock = solve_marched_attached_shock_field(
        band.state_at,
        band.static_pressure_at,
        start_point,
        target_centerline_y_m=0.0,
        downstream_flow_angle_at=downstream_angle_at,
        sample_count=5,
        branch=ShockBranch.WEAK,
        shock_angle_tolerance_rad=0.2,
      )
      shock_report = shock.as_report()
      accepted = (
        shock.status.value == 'subsonic_terminal_required'
        and shock.sample_count == 4
        and shock.subsonic_terminal_required
        and shock.terminal_model_verified
        and shock.physical_closure_verified is False
      )
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'start_point_m': start_point,
        'start_boundary_index': len(band.boundary_states) - 2,
        'accepted': accepted,
        'shock': shock_report,
      })
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'start_point_m': start_point,
        'start_boundary_index': len(band.boundary_states) - 2,
        'accepted': False,
        'shock': None,
        'message': f'band shock probe raised: {error}',
      })
  return {
    'status': 'diagnostic-open-band-shock-coupling',
    'accepted': all(case['accepted'] is True for case in cases),
    'cases': cases,
    'claim_status': (
      'band-state-sampler-fed-shock-march-reaches-typed-subsonic-terminal; '
      'shock-field-and-chain-closure-pending'
    ),
  }


def _caustic_family_band_origin_envelope_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
) -> dict[str, Any]:
  """Measure whether the restarted band can carry an attached path to y=0."""

  if seed is None:
    return {
      'status': 'missing_seed',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-origin-envelope-pending',
    }
  cases: list[dict[str, Any]] = []
  for anchor_edge_index in (0, 1):
    restart = restart_characteristic_family_from_caustic(
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=6,
    )
    band = restart.family_band
    if band is None or not band.converged:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': False,
        'status': 'missing_open_family_band',
        'envelope': None,
      })
      continue
    try:
      envelope = trace_caustic_family_band_forward_envelope(
        band,
        sample_count=17,
      )
      report = envelope.as_report()
      termination = envelope.as_chain_termination_decision()
      accepted = (
        envelope.status is MocCausticFamilyBandEnvelopeStatus.CENTERLINE_UNREACHABLE
        and not envelope.converged
        and envelope.physical_closure_verified is False
        and envelope.chain_promotion_blocked
        and envelope.first_missing_sample_index == envelope.sample_count
        and envelope.first_missing_point_m is not None
        and envelope.last_valid_point_m is not None
        and envelope.minimum_lower_boundary_margin_m is not None
        and envelope.minimum_lower_boundary_margin_m < 0.0
        and termination.reason is MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
        and termination.physical_termination is False
      )
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': accepted,
        'envelope': report,
      })
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': False,
        'envelope': None,
        'message': f'caustic-origin envelope probe raised: {error}',
      })
  return {
    'status': 'diagnostic-caustic-origin-forward-envelope',
    'accepted': all(case['accepted'] is True for case in cases),
    'cases': cases,
    'claim_status': (
      'weak-attached-forward-envelope-measures-bounded-origin-seam; '
      'physical-caustic-remesh-and-shock-closure-pending'
    ),
  }


def _caustic_family_band_terminal_field_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
) -> dict[str, Any]:
  """Grow a solver-backed open post-shock zone from both family orientations."""

  if seed is None:
    return {
      'status': 'missing_seed',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-family-band-terminal-field-pending',
    }
  cases: list[dict[str, Any]] = []
  for anchor_edge_index in (0, 1):
    restart = restart_characteristic_family_from_caustic(
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=6,
    )
    band = restart.family_band
    if band is None or not band.converged:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': False,
        'status': 'missing_open_family_band',
        'result': None,
      })
      continue
    start_point = (
      0.5 * (band.input_edge_points_m[0][0] + band.input_edge_points_m[1][0]),
      0.5 * (band.input_edge_points_m[0][1] + band.input_edge_points_m[1][1]),
    )
    try:
      result = solve_marched_attached_shock_from_caustic_family_band(
        band,
        start_point,
        sample_count=9,
      )
      report = result.as_report()
      mixed_boundary = result.validate_mixed_regime_boundary(())
      accepted = (
        result.status.value == 'converged_open_caustic_band_terminal_field'
        and result.converged
        and result.physical_terminal_verified
        and result.physical_closure_verified is False
        and result.chain_promotion_blocked
        and result.shock is not None
        and result.shock.sample_count == 8
        and result.shock_fit is not None
        and result.shock_fit.converged
        and result.shock_fit.maximum_shock_angle_residual_rad is not None
        and result.shock_fit.maximum_shock_angle_residual_rad <= 0.1
        and result.continuation is not None
        and result.continuation.converged
        and result.first_layer is not None
        and result.first_layer.converged
        and result.zone is not None
        and result.zone.converged
        and result.zone.cell_count == 27
        and result.zone.topology.connected
        and result.zone.topology.forms_closed_zone
        and result.zone.topology.nonmanifold_edge_count == 0
        and result.zone.physical_closure_status == 'open'
        and result.zone.state_sampling_available
        and mixed_boundary.status.value == 'subsonic_field_failure'
        and mixed_boundary.supersonic_patch_verified
        and mixed_boundary.physical_closure_verified is False
        and mixed_boundary.chain_promotion_blocked
      )
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'start_point_m': start_point,
        'accepted': accepted,
        'result': report,
        'mixed_regime_boundary_gate': mixed_boundary.as_report(),
      })
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'start_point_m': start_point,
        'accepted': False,
        'result': None,
        'message': f'caustic-band terminal field probe raised: {error}',
      })
  return {
    'status': 'diagnostic-open-band-terminal-field',
    'accepted': all(case['accepted'] is True for case in cases),
    'cases': cases,
    'claim_status': (
      'solver-generated-open-post-shock-zone-and-typed-normal-shock-terminal; '
      'mixed-regime-closure-and-chain-promotion-pending'
    ),
  }


def _caustic_family_band_chain_planner_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  current_field: MocPostShockCharacteristicFieldResult | None,
) -> dict[str, Any]:
  """Audit the caustic-band handoff through the one-step chain planner."""

  if seed is None:
    return {
      'status': 'missing_seed',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-family-band-chain-planner-pending',
    }
  if (
    current_field is None
    or not current_field.converged
    or not current_field.upstream_shock_coupling_verified
  ):
    return {
      'status': 'invalid_current_field',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-family-band-chain-planner-pending',
      'message': (
        'caustic-family band chain planner requires a converged current field '
        'with upstream shock coupling'
      ),
    }
  try:
    current = current_field.as_coupled_chain_cell(
      start_x_m=0.2,
      end_x_m=0.8,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return {
      'status': 'invalid_current_cell',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-family-band-chain-planner-pending',
      'message': f'current solver field could not seed the chain: {error}',
    }

  cases: list[dict[str, Any]] = []
  for anchor_edge_index in (0, 1):
    restart = restart_characteristic_family_from_caustic(
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=6,
    )
    band = restart.family_band
    if band is None or not band.converged or len(band.boundary_states) < 3:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': False,
        'status': 'missing_open_family_band',
        'planner': None,
      })
      continue
    start_point = (
      0.5 * (band.input_edge_points_m[0][0] + band.input_edge_points_m[1][0]),
      0.5 * (band.input_edge_points_m[0][1] + band.input_edge_points_m[1][1]),
    )
    try:
      planner = plan_caustic_family_band_chain(
        current,
        band,
        start_point_m=start_point,
        end_x_m=1.4,
        sample_count=9,
      )
      report = planner.as_report()
      chain = report['chain']
      steps = report['steps']
      diagnostics = chain['diagnostics']
      planner_measurement = measure_moc_chain_planner(planner)
      accepted = (
        report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
        and report['planning_only'] is True
        and report['production_claim_allowed'] is False
        and report['step_count'] == 1
        and chain['status'] == MocChainStatus.SOLVER_TERMINATED.value
        and chain['termination_reason'] == MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE.value
        and chain['physical_termination'] is False
        and chain['cell_count'] == 1
        and chain['resolved'] is True
        and len(steps) == 1
        and steps[0]['incoming_handoff_sample_count'] == len(
          current.continuation_boundary
        )
        and diagnostics['upstream_field_model'] == 'bounded-caustic-family-band'
        and diagnostics['upstream_shock_coupling_verified'] is True
        and diagnostics['physical_terminal_verified'] is True
        and diagnostics['post_shock_zone_converged'] is True
        and planner_measurement.converged
        and planner_measurement.termination_verified
        and planner_measurement.fidelity_isolation_verified
        and planner_measurement.physical_termination is False
        and planner_measurement.production_claim_allowed is False
      )
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'start_point_m': start_point,
        'accepted': accepted,
        'planner': report,
        'planner_measurement': planner_measurement.as_report(),
      })
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'start_point_m': start_point,
        'accepted': False,
        'planner': None,
        'message': f'caustic-band chain planner raised: {error}',
      })
  return {
    'status': 'diagnostic-caustic-band-next-shock-planner',
    'accepted': all(case['accepted'] is True for case in cases),
    'cases': cases,
    'claim_status': (
      'solver-generated-caustic-band-next-shock-handoff; '
      'open-mixed-regime-closure-and-chain-promotion-pending'
    ),
  }


def _caustic_family_band_invariant_chain_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  current_field: MocPostShockCharacteristicFieldResult | None,
) -> dict[str, Any]:
  """Audit the invariant-conditioned caustic shock path and chain stop."""

  if seed is None or len(getattr(seed, 'edge_states', ())) != 2:
    return {
      'status': 'missing_seed',
      'accepted': False,
      'direct': None,
      'planner': None,
      'claim_status': 'invariant-caustic-band-chain-pending',
    }
  if (
    current_field is None
    or not current_field.converged
    or not current_field.upstream_shock_coupling_verified
  ):
    return {
      'status': 'invalid_current_field',
      'accepted': False,
      'direct': None,
      'planner': None,
      'claim_status': 'invariant-caustic-band-chain-pending',
    }
  assert seed.edge_states[1].state is not None
  target_invariant = seed.edge_states[1].state.k_plus
  restart = restart_characteristic_family_from_caustic(
    seed,
    total_pressure_Pa,
    ambient_pressure_Pa,
    anchor_edge_index=0,
    sample_count=6,
  )
  band = restart.family_band
  if band is None or not band.converged or band.anchor_point_m is None:
    return {
      'status': 'missing_open_family_band',
      'accepted': False,
      'direct': None,
      'planner': None,
      'claim_status': 'invariant-caustic-band-chain-pending',
    }
  direct_result = solve_marched_attached_shock_from_caustic_family_band_with_invariant_boundary(
    band,
    band.anchor_point_m,
    CharacteristicFamily.PLUS,
    lambda _index, _point: target_invariant,
    sample_count=9,
  )
  direct = direct_result.as_report()
  try:
    current = current_field.as_coupled_chain_cell(
      start_x_m=0.2,
      end_x_m=0.5,
    )
    planner = plan_caustic_family_band_invariant_chain(
      current,
      band,
      start_point_m=band.anchor_point_m,
      end_x_m=1.4,
      downstream_invariant_family=CharacteristicFamily.PLUS,
      downstream_invariant_at=lambda _index, _point: target_invariant,
      sample_count=9,
    )
    planner_report = planner.as_report()
    planner_measurement = measure_moc_chain_planner(planner)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return {
      'status': 'planner_failure',
      'accepted': False,
      'direct': direct,
      'planner': None,
      'message': str(error),
      'claim_status': 'invariant-caustic-band-chain-pending',
    }
  chain = planner_report['chain']
  steps = planner_report['steps']
  diagnostics = chain['diagnostics']
  accepted = (
    direct_result.status.value == 'invariant_caustic_band_upstream_domain_failure'
    and direct_result.first_missing_sample_index == 4
    and direct_result.shock is not None
    and direct_result.shock.sample_count == 4
    and direct_result.shock_curve_verified is False
    and direct_result.physical_closure_verified is False
    and direct_result.chain_promotion_blocked is True
    and planner_report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
    and planner_report['planning_only'] is True
    and planner_report['production_claim_allowed'] is False
    and planner_report['step_count'] == 1
    and chain['status'] == MocChainStatus.SOLVER_TERMINATED.value
    and chain['termination_reason'] == MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value
    and chain['physical_termination'] is False
    and chain['cell_count'] == 1
    and len(steps) == 1
    and steps[0]['incoming_handoff_sample_count'] == len(current.continuation_boundary)
    and diagnostics['upstream_field_model'] == 'bounded-caustic-family-band'
    and diagnostics['first_missing_sample_index'] == 4
    and planner_measurement.converged
    and planner_measurement.termination_verified
    and planner_measurement.fidelity_isolation_verified
    and planner_measurement.physical_termination is False
    and planner_measurement.production_claim_allowed is False
  )
  return {
    'status': 'diagnostic-invariant-caustic-band-chain',
    'accepted': accepted,
    'target_invariant': target_invariant,
    'direct': direct,
    'planner': planner_report,
    'planner_measurement': planner_measurement.as_report(),
    'claim_status': (
      'invariant-conditioned-shock-march-and-typed-upstream-boundary-stop; '
      'physical-caustic-remesh-pending'
    ),
  }


def _caustic_upstream_bridge_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  old_family: Any,
  current_field: MocPostShockCharacteristicFieldResult | None,
  physical_seed: Any = None,
) -> dict[str, Any]:
  """Audit the explicit old-family/restarted-family upstream seam."""

  if seed is None or old_family is None:
    return {
      'status': 'missing_seed_or_old_family',
      'accepted': False,
      'bridge': None,
      'claim_status': 'caustic-upstream-bridge-pending',
    }
  try:
    restart = restart_characteristic_family_from_caustic(
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=0,
      sample_count=6,
    )
    band = restart.family_band
    if band is None or not band.converged or band.anchor_point_m is None:
      return {
        'status': 'missing_open_family_band',
        'accepted': False,
        'bridge': None,
        'claim_status': 'caustic-upstream-bridge-pending',
      }
    bridge = build_caustic_upstream_bridge(old_family, band)
    bridge_source = MocBoundedUpstreamFieldSource.from_caustic_upstream_bridge(
      bridge,
      sample_position_tolerance_m=1.0e-3,
      preferred_start_point_m=band.anchor_point_m,
    )
    source_old_point = old_family.cells[0].vertices_xr_m[0]
    source_restarted_point = band.cells[0].vertices_xr_m[0]
    source_gap_point = (0.680, 0.050)
    bounded_source_audit = {
      'source': bridge_source.as_report(),
      'old_point_m': source_old_point,
      'restarted_point_m': source_restarted_point,
      'old_point_state_matches_bridge': bridge_source.state_at(source_old_point)
      == bridge.state_at(source_old_point, position_tolerance_m=1.0e-3),
      'restarted_point_state_matches_bridge': bridge_source.state_at(
        source_restarted_point
      ) == bridge.state_at(
        source_restarted_point,
        position_tolerance_m=1.0e-3,
      ),
      'old_point_pressure_matches_bridge': bridge_source.static_pressure_at(
        source_old_point
      ) == bridge.static_pressure_at(
        source_old_point,
        position_tolerance_m=1.0e-3,
      ),
      'restarted_point_pressure_matches_bridge': bridge_source.static_pressure_at(
        source_restarted_point
      ) == bridge.static_pressure_at(
        source_restarted_point,
        position_tolerance_m=1.0e-3,
      ),
      'gap_state_is_none': bridge_source.state_at(source_gap_point) is None,
      'gap_pressure_is_none': bridge_source.static_pressure_at(source_gap_point)
      is None,
    }
    covered_path = tuple(
      (state.x_m, state.y_m)
      for state in band.boundary_states[:4]
    )
    covered = sample_caustic_upstream_bridge(bridge, covered_path)
    gap = sample_caustic_upstream_bridge(
      bridge,
      (
        band.anchor_point_m,
        (0.675, 0.052),
        (0.680, 0.050),
      ),
    )
    old_only = build_caustic_upstream_bridge(
      old_family,
      band,
      side_at=lambda _point: MocCausticBridgeSide.OLD_FAMILY,
    )
    no_fallback = sample_caustic_upstream_bridge(
      old_only,
      (band.anchor_point_m,),
    )
    if seed.edge_states[1].state is None:
      return {
        'status': 'missing_invariant_target',
        'accepted': False,
        'bridge': bridge.as_report(),
        'claim_status': 'caustic-upstream-bridge-pending',
      }
    target_invariant = seed.edge_states[1].state.k_plus
    invariant_shock = solve_marched_attached_shock_from_caustic_upstream_bridge_with_invariant_boundary(
      bridge,
      band.anchor_point_m,
      CharacteristicFamily.PLUS,
      lambda _index, _point: target_invariant,
      sample_count=9,
    )
    start = (
      0.5 * (band.input_edge_points_m[0][0] + band.input_edge_points_m[1][0]),
      0.5 * (band.input_edge_points_m[0][1] + band.input_edge_points_m[1][1]),
    )
    shock = solve_marched_attached_shock_from_caustic_upstream_bridge(
      bridge,
      start,
      downstream_flow_angle_at=lambda _index, point: 0.05 * max(
        0.0,
        min(1.0, point[1] / start[1]),
      ),
      sample_count=9,
      shock_angle_tolerance_rad=0.2,
    )
    candidate_start_state = old_family.minus_source_states[-1]
    candidate_start = (candidate_start_state.x_m, candidate_start_state.y_m)
    candidate_shock = solve_marched_attached_shock_from_caustic_upstream_bridge(
      bridge,
      candidate_start,
      downstream_flow_angle_at=lambda _index, point: 0.05 * max(
        0.0,
        min(1.0, point[1] / candidate_start[1]),
      ),
      sample_count=17,
      shock_angle_tolerance_rad=0.2,
    )
    planner = None
    candidate_planner = None
    if current_field is not None and current_field.converged:
      current = current_field.as_coupled_chain_cell(
        start_x_m=0.2,
        end_x_m=0.8,
      )
      planner = plan_caustic_upstream_bridge_chain(
        current,
        bridge,
        start_point_m=start,
        end_x_m=1.4,
        downstream_flow_angle_at=lambda _index, point: 0.05 * max(
          0.0,
          min(1.0, point[1] / start[1]),
        ),
        sample_count=9,
        shock_angle_tolerance_rad=0.2,
      )
      candidate_planner = plan_caustic_upstream_bridge_chain(
        current,
        bridge,
        start_point_m=candidate_start,
        end_x_m=1.4,
        downstream_flow_angle_at=lambda _index, point: 0.05 * max(
          0.0,
          min(1.0, point[1] / candidate_start[1]),
        ),
        sample_count=17,
        shock_angle_tolerance_rad=0.2,
      )
    planner_report = None if planner is None else planner.as_report()
    candidate_planner_report = (
      None if candidate_planner is None else candidate_planner.as_report()
    )
    invariant_planner = None
    if current_field is not None and current_field.converged:
      current = current_field.as_coupled_chain_cell(
        start_x_m=0.2,
        end_x_m=0.5,
      )
      invariant_planner = plan_caustic_upstream_bridge_invariant_chain(
        current,
        bridge,
        start_point_m=band.anchor_point_m,
        end_x_m=1.4,
        downstream_invariant_family=CharacteristicFamily.PLUS,
        downstream_invariant_at=lambda _index, _point: target_invariant,
        sample_count=9,
      )
    invariant_planner_report = (
      None if invariant_planner is None else invariant_planner.as_report()
    )
    planner_measurement = (
      None if planner is None else measure_moc_chain_planner(planner)
    )
    candidate_planner_measurement = (
      None
      if candidate_planner is None
      else measure_moc_chain_planner(candidate_planner)
    )
    invariant_planner_measurement = (
      None
      if invariant_planner is None
      else measure_moc_chain_planner(invariant_planner)
    )
    physical_bridge_planner = None
    if (
      physical_seed is not None
      and getattr(physical_seed, 'converged', False)
      and getattr(physical_seed, 'physical_closure_verified', False)
      and seed.event is not None
      and seed.event.caustic_point_m is not None
    ):
      event_x_m = seed.event.caustic_point_m[0]
      physical_start_x_m = physical_seed.shock_boundary_points_m[0][0]
      physical_bridge_reference = (
        MocSolverGeneratedAmbientClosedPostShockChainReference(
          total_cell_count=2,
          shock_start_y_m=0.5,
          ambient_pressure_Pa=ambient_pressure_Pa,
          outer_downstream_flow_angle_lower_rad=0.02,
          outer_downstream_flow_angle_upper_rad=0.12,
          sample_count=9,
          upstream_source_provider=lambda *_args, source=bridge_source: source,
        )
      )
      physical_bridge_planner = (
        plan_solver_generated_ambient_closed_post_shock_chain_reference(
          physical_seed,
          start_x_m=physical_start_x_m,
          end_x_m=event_x_m - 0.01,
          reference=physical_bridge_reference,
          policy=MocChainContinuationPolicy(
            max_cells=2,
            require_state_carry=True,
          ),
        )
      )
    physical_bridge_planner_report = (
      None
      if physical_bridge_planner is None
      else physical_bridge_planner.as_report()
    )
    physical_bridge_planner_measurement = (
      None
      if physical_bridge_planner is None
      else measure_moc_chain_planner(physical_bridge_planner)
    )
    accepted = (
      bridge.fields_converged
      and bounded_source_audit['source']['model']
      == 'bounded-caustic-upstream-bridge'
      and bounded_source_audit['source']['upstream_coupling_verified'] is False
      and bounded_source_audit['source']['extrapolation_allowed'] is False
      and bounded_source_audit['source']['preferred_start_point_m']
      == band.anchor_point_m
      and bounded_source_audit['old_point_state_matches_bridge']
      and bounded_source_audit['restarted_point_state_matches_bridge']
      and bounded_source_audit['old_point_pressure_matches_bridge']
      and bounded_source_audit['restarted_point_pressure_matches_bridge']
      and bounded_source_audit['gap_state_is_none']
      and bounded_source_audit['gap_pressure_is_none']
      and covered.status is MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH
      and covered.sampled_count == 4
      and all(
        sample.side is MocCausticBridgeSide.RESTARTED_FAMILY
        and not sample.old_family_available
        and sample.restarted_family_available
        for sample in covered.samples
      )
      and gap.status is MocCausticBridgeStatus.DOMAIN_GAP
      and gap.first_missing_sample_index == 2
      and no_fallback.status is MocCausticBridgeStatus.SELECTED_SIDE_DOMAIN_GAP
      and shock.coupling.status is MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH
      and shock.upstream_coupling_verified
      and shock.physical_closure_verified is False
      and shock.chain_promotion_blocked
      and candidate_shock.shock.status.value == 'upstream_field_failure'
      and candidate_shock.shock.sample_count == 1
      and candidate_shock.shock.failed_sample_index == 1
      and candidate_shock.shock.failed_point_m is not None
      and candidate_shock.coupling.status is MocCausticBridgeStatus.DOMAIN_GAP
      and candidate_shock.coupling.sampled_count == 1
      and candidate_shock.coupling.first_missing_sample_index == 1
      and candidate_shock.coupling.first_missing_point_m == candidate_shock.shock.failed_point_m
      and candidate_shock.upstream_coupling_verified is False
      and candidate_shock.physical_closure_verified is False
      and candidate_shock.chain_promotion_blocked
      and invariant_shock.shock.status.value == 'upstream_field_failure'
      and invariant_shock.coupling.status is MocCausticBridgeStatus.DOMAIN_GAP
      and invariant_shock.coupling.first_missing_sample_index == 4
      and invariant_shock.upstream_coupling_verified is False
      and invariant_shock.physical_closure_verified is False
      and invariant_shock.chain_promotion_blocked
      and planner_report is not None
      and planner_report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
      and planner_report['planning_only'] is True
      and planner_report['production_claim_allowed'] is False
      and planner_report['step_count'] == 1
      and planner_report['chain']['status'] == MocChainStatus.SOLVER_TERMINATED.value
      and planner_report['chain']['termination_reason'] == MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE.value
      and planner_report['chain']['physical_termination'] is False
      and planner_report['chain']['cell_count'] == 1
      and planner_measurement is not None
      and planner_measurement.converged
      and planner_measurement.termination_verified
      and planner_measurement.fidelity_isolation_verified
      and planner_measurement.physical_termination is False
      and planner_measurement.production_claim_allowed is False
      and candidate_planner_report is not None
      and candidate_planner_report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
      and candidate_planner_report['planning_only'] is True
      and candidate_planner_report['production_claim_allowed'] is False
      and candidate_planner_report['step_count'] == 1
      and candidate_planner_report['chain']['status'] == MocChainStatus.SOLVER_TERMINATED.value
      and candidate_planner_report['chain']['termination_reason'] == MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value
      and candidate_planner_report['chain']['physical_termination'] is False
      and candidate_planner_report['chain']['cell_count'] == 1
      and candidate_planner_measurement is not None
      and candidate_planner_measurement.converged
      and candidate_planner_measurement.termination_verified
      and candidate_planner_measurement.fidelity_isolation_verified
      and candidate_planner_measurement.physical_termination is False
      and candidate_planner_measurement.production_claim_allowed is False
      and candidate_planner_report['chain']['diagnostics']['bridge_first_missing_sample_index'] == 1
      and candidate_planner_report['chain']['diagnostics']['bridge_first_missing_point_m'] == candidate_shock.coupling.first_missing_point_m
      and invariant_planner_report is not None
      and invariant_planner_report['planner_kind'] == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
      and invariant_planner_report['planning_only'] is True
      and invariant_planner_report['production_claim_allowed'] is False
      and invariant_planner_report['step_count'] == 1
      and invariant_planner_report['chain']['status'] == MocChainStatus.SOLVER_TERMINATED.value
      and invariant_planner_report['chain']['termination_reason'] == MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value
      and invariant_planner_report['chain']['physical_termination'] is False
      and invariant_planner_report['chain']['cell_count'] == 1
      and invariant_planner_measurement is not None
      and invariant_planner_measurement.converged
      and invariant_planner_measurement.termination_verified
      and invariant_planner_measurement.fidelity_isolation_verified
      and invariant_planner_measurement.physical_termination is False
      and invariant_planner_measurement.production_claim_allowed is False
      and physical_bridge_planner_report is not None
      and physical_bridge_planner_report['planner_kind']
      == MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
      and physical_bridge_planner_report['planning_only'] is True
      and physical_bridge_planner_report['production_claim_allowed'] is False
      and physical_bridge_planner_report['step_count'] == 1
      and physical_bridge_planner_report['chain']['status']
      == MocChainStatus.SOLVER_TERMINATED.value
      and physical_bridge_planner_report['chain']['physical_termination'] is False
      and physical_bridge_planner_report['chain']['cell_count'] == 1
      and physical_bridge_planner_report['chain']['termination_reason']
      in (
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value,
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE.value,
      )
      and physical_bridge_planner_report['chain']['diagnostics'][
        'upstream_source'
      ]['model'] == 'bounded-caustic-upstream-bridge'
      and physical_bridge_planner_measurement is not None
      and physical_bridge_planner_measurement.converged
      and physical_bridge_planner_measurement.termination_verified
      and physical_bridge_planner_measurement.fidelity_isolation_verified
      and physical_bridge_planner_measurement.physical_termination is False
      and physical_bridge_planner_measurement.production_claim_allowed is False
    )
    return {
      'status': 'diagnostic-bounded-caustic-upstream-bridge',
      'accepted': accepted,
      'bridge': bridge.as_report(),
      'bounded_source_audit': bounded_source_audit,
      'covered_path_audit': covered.as_report(),
      'gap_audit': gap.as_report(),
      'explicit_old_side_no_fallback_audit': no_fallback.as_report(),
      'shock': shock.as_report(),
      'candidate_shock': candidate_shock.as_report(),
      'invariant_shock': invariant_shock.as_report(),
      'planner': planner_report,
      'candidate_planner': candidate_planner_report,
      'invariant_planner': invariant_planner_report,
      'planner_measurement': (
        None if planner_measurement is None else planner_measurement.as_report()
      ),
      'candidate_planner_measurement': (
        None
        if candidate_planner_measurement is None
        else candidate_planner_measurement.as_report()
      ),
      'invariant_planner_measurement': (
        None
        if invariant_planner_measurement is None
        else invariant_planner_measurement.as_report()
      ),
      'physical_bridge_planner': physical_bridge_planner_report,
      'physical_bridge_planner_measurement': (
        None
        if physical_bridge_planner_measurement is None
        else physical_bridge_planner_measurement.as_report()
      ),
      'claim_status': (
        'bounded-old-family-restarted-family-bridge-and-planner-audit; '
        'physical-caustic-remesh-and-downstream-closure-pending'
      ),
    }
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return {
      'status': 'caustic-upstream-bridge-failure',
      'accepted': False,
      'bridge': None,
      'message': str(error),
      'claim_status': 'caustic-upstream-bridge-pending',
    }


def _caustic_upstream_continuation_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  old_family: Any,
) -> dict[str, Any]:
  """Audit solver-owned branch selection and the exact caustic seam."""

  if seed is None or old_family is None:
    return {
      'status': 'missing_seed_or_old_family',
      'accepted': False,
      'branch_audit': None,
      'continuation': None,
      'planner': None,
      'claim_status': 'caustic-upstream-continuation-pending',
  }
  try:
    planner = plan_caustic_upstream_continuation(
      old_family,
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=0,
      sample_count=6,
    )
    branch_audit = planner.branch_audit
    continuation = planner.continuation
    event_point = continuation.event_point_m
    event_sample_available = bool(
      event_point is not None
      and continuation.state_at(event_point) is not None
      and continuation.static_pressure_at(event_point) is not None
    )
    accepted = (
      branch_audit.status is (
        MocCausticUpstreamContinuationStatus.BRANCH_SELECTION_REQUIRED
      )
      and branch_audit.converged is False
      and branch_audit.bridge is None
      and len(branch_audit.restart_results) == 2
      and all(
        restart.converged
        and restart.caustic_handoff_verified
        for restart in branch_audit.restart_results
      )
      and continuation.status is (
        MocCausticUpstreamContinuationStatus.CONVERGED_BOUNDED_CONTINUATION
      )
      and continuation.converged
      and continuation.seam_verified
      and continuation.state_sampling_available
      and continuation.selected_anchor_edge_index == 0
      and continuation.bridge is not None
      and continuation.bridge.fields_converged
      and event_sample_available
      and continuation.physical_closure_verified is False
      and continuation.chain_promotion_blocked
      and planner.branch_audit_verified
      and planner.resolved
      and planner.termination.reason is MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
      and planner.termination.physical_termination is False
      and planner.physical_closure_verified is False
      and planner.chain_promotion_blocked
    )
    return {
      'status': 'solver-owned-bounded-caustic-upstream-continuation',
      'accepted': accepted,
      'event_point_m': event_point,
      'event_sample_available': event_sample_available,
      'branch_audit': branch_audit.as_report(),
      'continuation': continuation.as_report(),
      'planner': planner.as_report(),
      'claim_status': (
        'bounded-solver-owned-caustic-upstream-continuation; '
        'shock-branch-physics-and-physical-closure-pending'
      ),
    }
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return {
      'status': 'caustic-upstream-continuation-failure',
      'accepted': False,
      'branch_audit': None,
      'continuation': None,
      'planner': None,
      'message': str(error),
      'claim_status': 'caustic-upstream-continuation-pending',
    }


def _caustic_family_band_terminal_refinement_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
) -> dict[str, Any]:
  """Check shock/zone behavior as the terminal marcher is refined."""

  if seed is None:
    return {
      'status': 'missing_seed',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-family-band-terminal-refinement-pending',
    }
  cases: list[dict[str, Any]] = []
  for anchor_edge_index in (0, 1):
    restart = restart_characteristic_family_from_caustic(
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=6,
    )
    band = restart.family_band
    if band is None or not band.converged:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': False,
        'resolutions': [],
        'message': 'missing converged family band',
      })
      continue
    start_point = (
      0.5 * (band.input_edge_points_m[0][0] + band.input_edge_points_m[1][0]),
      0.5 * (band.input_edge_points_m[0][1] + band.input_edge_points_m[1][1]),
    )
    resolutions: list[dict[str, Any]] = []
    for sample_count in (5, 7, 9, 11):
      try:
        result = solve_marched_attached_shock_from_caustic_family_band(
          band,
          start_point,
          sample_count=sample_count,
        )
        terminal = result.terminal_normal_shock
        resolution = {
          'sample_count': sample_count,
          'status': result.status.value,
          'converged': result.converged,
          'physical_terminal_verified': result.physical_terminal_verified,
          'physical_closure_verified': result.physical_closure_verified,
          'chain_promotion_blocked': result.chain_promotion_blocked,
          'shock_sample_count': (
            None if result.shock is None else result.shock.sample_count
          ),
          'shock_fit_sample_count': (
            None
            if result.shock_fit is None
            else len(result.shock_fit.boundary_states)
          ),
          'maximum_shock_angle_residual_rad': (
            None
            if result.shock_fit is None
            else result.shock_fit.maximum_shock_angle_residual_rad
          ),
          'zone_cell_count': None if result.zone is None else result.zone.cell_count,
          'zone_topology_forms_closed_zone': (
            None
            if result.zone is None
            else result.zone.topology.forms_closed_zone
          ),
          'zone_physical_closure_status': (
            None if result.zone is None else result.zone.physical_closure_status
          ),
          'terminal_shock_point_m': (
            None if terminal is None else terminal.shock_point_m
          ),
          'terminal_downstream_mach': (
            None if terminal is None else terminal.downstream_mach
          ),
        }
        resolution['accepted'] = (
          result.status.value == 'converged_open_caustic_band_terminal_field'
          and result.converged
          and result.physical_terminal_verified
          and result.physical_closure_verified is False
          and result.chain_promotion_blocked
          and result.shock is not None
          and result.shock.sample_count == sample_count - 1
          and result.shock_fit is not None
          and result.shock_fit.converged
          and result.shock_fit.maximum_shock_angle_residual_rad is not None
          and result.zone is not None
          and result.zone.converged
          and result.zone.cell_count == sample_count * (sample_count - 3) // 2
          and result.zone.topology.forms_closed_zone
          and result.zone.physical_closure_status == 'open'
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        resolution = {
          'sample_count': sample_count,
          'accepted': False,
          'status': 'exception',
          'message': f'caustic-band refinement raised: {error}',
        }
      resolutions.append(resolution)
    cases.append({
      'anchor_edge_index': anchor_edge_index,
      'start_point_m': start_point,
      'accepted': all(case['accepted'] is True for case in resolutions),
      'resolutions': resolutions,
    })
  return {
    'status': 'diagnostic-caustic-band-terminal-refinement',
    'accepted': all(case['accepted'] is True for case in cases),
    'cases': cases,
    'claim_status': (
      'open-post-shock-zone-refinement-only; mixed-regime-closure-and-'
      'chain-promotion-pending'
    ),
  }


def _caustic_family_band_terminal_measurement_probe(
  seed: Any,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
) -> dict[str, Any]:
  """Run the independent cell operator and retain its open-zone rejection."""

  if seed is None:
    return {
      'status': 'missing_seed',
      'accepted': False,
      'cases': [],
      'claim_status': 'caustic-family-band-terminal-measurement-pending',
    }
  cases: list[dict[str, Any]] = []
  for anchor_edge_index in (0, 1):
    restart = restart_characteristic_family_from_caustic(
      seed,
      total_pressure_Pa,
      ambient_pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=6,
    )
    band = restart.family_band
    if band is None or not band.converged:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': False,
        'measurement': None,
      })
      continue
    start_point = (
      0.5 * (band.input_edge_points_m[0][0] + band.input_edge_points_m[1][0]),
      0.5 * (band.input_edge_points_m[0][1] + band.input_edge_points_m[1][1]),
    )
    result = solve_marched_attached_shock_from_caustic_family_band(
      band,
      start_point,
      sample_count=9,
    )
    if result.shock_fit is None or result.continuation is None or result.zone is None:
      cases.append({
        'anchor_edge_index': anchor_edge_index,
        'accepted': False,
        'measurement': None,
        'message': 'open terminal field did not expose measurement inputs',
      })
      continue
    observation = MocShockCellObservation(
      cell_index=1,
      shock_boundary_points_m=tuple(
        sample.point_m for sample in result.shock_fit.boundary_states
      ),
      centerline_boundary_points_m=tuple(
        reversed(tuple(
          (state.x_m, state.y_m)
          for state in result.continuation.centerline_states
        ))
      ),
      cells=result.zone.cells,
      upstream_total_pressure_Pa=tuple(
        sample.upstream_total_pressure_Pa
        for sample in result.shock_fit.boundary_states
      ),
      downstream_total_pressure_Pa=tuple(
        sample.downstream_total_pressure_Pa
        for sample in result.shock_fit.boundary_states
      ),
    )
    measurement = measure_moc_shock_cell(observation)
    report = measurement.as_report()
    cases.append({
      'anchor_edge_index': anchor_edge_index,
      'accepted': (
        result.converged
        and result.physical_closure_verified is False
        and measurement.converged is False
        and measurement.status.value == 'geometry_failure'
        and measurement.message == 'shock and centerline boundaries must share their endpoint'
      ),
      'measurement': report,
      'expected_open_zone_rejection': True,
    })
  return {
    'status': 'diagnostic-independent-measurement-rejects-open-terminal-zone',
    'accepted': all(case['accepted'] is True for case in cases),
    'cases': cases,
    'claim_status': (
      'independent-cell-measurement-preserves-open-terminal-boundary; '
      'physical-cell-acceptance-pending'
    ),
  }


def _reflected_zone_shock_coupling_probe(
  reflected_zone: Any,
  reflected_boundary: Any,
  reflected_source_strip: Any,
  ambient_pressure_Pa: float,
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
  reflected_zone_solver = solve_marched_attached_shock_from_reflected_zone(
    reflected_zone,
    start,
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / start[1]),
    ),
    sample_count=9,
  )
  reflected_zone_ambient_solver = (
    solve_marched_attached_shock_with_ambient_pressure_closure_from_reflected_zone(
      reflected_zone,
      start,
      ambient_pressure_Pa,
      -0.05,
      0.02,
      sample_count=9,
    )
  )
  return {
    'status': result.status.value,
    'sample_count': result.sample_count,
    'shock_start_m': start,
    'last_valid_point_m': result.shock_points_m[-1] if result.shock_points_m else None,
    'message': result.message,
    'coupling': coupling.as_report(),
    'reflected_zone_solver': reflected_zone_solver.as_report(),
    'reflected_zone_solver_expected_bounded_failure': (
      reflected_zone_solver.shock.status.value == 'upstream_field_failure'
      and not reflected_zone_solver.upstream_coupling_verified
      and reflected_zone_solver.coupling.first_missing_sample_index == 1
    ),
    'reflected_zone_ambient_solver': reflected_zone_ambient_solver.as_report(),
    'reflected_zone_ambient_solver_expected_bounded_failure': (
      reflected_zone_ambient_solver.closure.status.value == 'ambient_closure_field_failure'
      and not reflected_zone_ambient_solver.upstream_coupling_verified
      and reflected_zone_ambient_solver.coupling.first_missing_sample_index == 1
    ),
    'claim_status': (
      'reflected-field-domain-bounded-shock-solver; downstream-boundary-and-'
      'shock-path-extension-pending'
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
  reflected_centerline_reflection_extension = (
    extend_source_characteristic_strip_centerline_reflection(
      reflected_boundary.centerline_states,
      reflected_boundary.boundary_states,
      fan_exit.total_pressure_Pa,
      fan_ambient.pressure_Pa,
      additional_sample_count=1,
    )
  )
  caustic_shock_seed = (
    None
    if (
      reflected_centerline_reflection_extension.remesh is None
      or reflected_centerline_reflection_extension.remesh.caustic_event is None
    )
    else build_caustic_shock_seed(
      reflected_centerline_reflection_extension.remesh.caustic_event,
      fan_exit.total_pressure_Pa,
    )
  )
  caustic_shock_resolution = (
    None
    if caustic_shock_seed is None
    else resolve_caustic_shock_seed(caustic_shock_seed)
  )
  caustic_shock_bridge = _caustic_shock_bridge_probe(caustic_shock_seed)
  caustic_shock_remesh_execution = _caustic_shock_remesh_execution_probe(
    caustic_shock_seed,
    reflected_source_strip,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
  )
  caustic_family_restart = _caustic_family_restart_probe(
    caustic_shock_seed,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
  )
  caustic_family_band_shock = _caustic_family_band_shock_probe(
    caustic_shock_seed,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
  )
  caustic_family_band_origin_envelope = (
    _caustic_family_band_origin_envelope_probe(
      caustic_shock_seed,
      fan_exit.total_pressure_Pa,
      fan_ambient.pressure_Pa,
    )
  )
  caustic_family_band_terminal_field = _caustic_family_band_terminal_field_probe(
    caustic_shock_seed,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
  )
  caustic_family_band_terminal_refinement = (
    _caustic_family_band_terminal_refinement_probe(
      caustic_shock_seed,
      fan_exit.total_pressure_Pa,
      fan_ambient.pressure_Pa,
    )
  )
  caustic_family_band_terminal_measurement = (
    _caustic_family_band_terminal_measurement_probe(
      caustic_shock_seed,
      fan_exit.total_pressure_Pa,
      fan_ambient.pressure_Pa,
    )
  )
  reflected_zone_shock_coupling = _reflected_zone_shock_coupling_probe(
    reflected_zone,
    reflected_boundary,
    reflected_source_strip,
    fan_ambient.pressure_Pa,
  )
  ambient_pressure_closure_probe = _ambient_pressure_closure_probe()
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
  sampled_post_shock_zone = assemble_post_shock_characteristic_zone(
    sampled_continuation,
    assemble_post_shock_first_layer(sampled_continuation),
    sampled_shock_fit.boundary_states,
  )
  post_shock_zone_chain_planner = _post_shock_zone_chain_planner_probe(
    sampled_post_shock_zone,
    shock_seeded_field,
  )
  shock_seeded_ambient_boundary = validate_post_shock_ambient_boundary(
    shock_seeded_field,
    _shock_seeded_field_fit(),
    fan_ambient.pressure_Pa,
  )
  shock_seeded_refinement_probe = _shock_seeded_field_refinement_probe()
  solver_generated_shock = _solver_generated_shock_fixture()
  source_strip_chain_planner = _source_strip_chain_planner_probe(
    reflected_centerline_reflection_extension,
    solver_generated_shock.field,
    (
      reflected_boundary.boundary_points_m[-1]
      if reflected_boundary.boundary_points_m
      else (0.0, 0.0)
    ),
  )
  source_strip_chain_sequence_planner = _source_strip_chain_sequence_planner_probe(
    reflected_centerline_reflection_extension,
    solver_generated_shock.field,
    (
      reflected_boundary.boundary_points_m[-1]
      if reflected_boundary.boundary_points_m
      else (0.0, 0.0)
    ),
  )
  caustic_family_band_chain_planner = _caustic_family_band_chain_planner_probe(
    caustic_shock_seed,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
    solver_generated_shock.field,
  )
  caustic_family_band_invariant_chain = _caustic_family_band_invariant_chain_probe(
    caustic_shock_seed,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
    solver_generated_shock.field,
  )
  caustic_bridge_physical_seed = None
  if (
    solver_generated_shock.shock_fit is not None
    and solver_generated_shock.shock_fit.converged
    and solver_generated_shock.shock_fit.boundary_states
    and solver_generated_shock.upstream_states
    and solver_generated_shock.upstream_pressure_Pa
  ):
    physical_shock_fit_first = solver_generated_shock.shock_fit.boundary_states[0]
    physical_upstream = solver_generated_shock.upstream_states[0]
    physical_upstream_pressure = solver_generated_shock.upstream_pressure_Pa[0]
    physical_ambient_pressure = physical_shock_fit_first.downstream_total_pressure_Pa / (
      1.0
      + 0.5 * (physical_shock_fit_first.state.gamma - 1.0)
      * physical_shock_fit_first.state.mach**2
    ) ** (
      physical_shock_fit_first.state.gamma
      / (physical_shock_fit_first.state.gamma - 1.0)
    )
    caustic_bridge_physical_seed = (
      solve_marched_attached_shock_with_ambient_centerline_physical_field(
        lambda point: replace(
          physical_upstream,
          x_m=point[0],
          y_m=point[1],
        ),
        lambda _point: physical_upstream_pressure,
        physical_shock_fit_first.point_m,
        physical_ambient_pressure,
        0.02,
        0.12,
        sample_count=9,
      ).field
    )
  caustic_upstream_bridge = _caustic_upstream_bridge_probe(
    caustic_shock_seed,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
    reflected_source_strip,
    solver_generated_shock.field,
    caustic_bridge_physical_seed,
  )
  caustic_upstream_continuation = _caustic_upstream_continuation_probe(
    caustic_shock_seed,
    fan_exit.total_pressure_Pa,
    fan_ambient.pressure_Pa,
    reflected_source_strip,
  )
  reflected_zone_chain_boundary_probe = _reflected_zone_chain_boundary_probe(
    reflected_zone,
    solver_generated_shock.field,
  )
  ambient_shock_strip_probe = _ambient_shock_strip_probe(solver_generated_shock)
  ambient_attachment_closure_probe = _ambient_attachment_closure_probe(
    solver_generated_shock,
  )
  ambient_attachment_transition_probe = _ambient_attachment_transition_probe(
    solver_generated_shock,
  )
  solver_generated_shock_refinement_probe = _solver_generated_shock_refinement_probe()
  terminal_reflection_patch_refinement_probe = _terminal_reflection_patch_refinement_probe()
  terminal_composite_refinement_probe = _terminal_composite_refinement_probe(
    solver_generated_shock,
  )
  mixed_regime_boundary_probe = _mixed_regime_boundary_probe(
    solver_generated_shock,
  )
  solver_generated_chain_reference = None
  solver_generated_chain_observations: list[dict[str, Any]] = []
  solver_generated_chain_measurement_observations: list[MocShockCellObservation] = []
  solver_generated_chain_measurement = None
  solver_generated_chain_planner = None
  solver_generated_chain_planner_measurement = None
  solver_generated_chain_refinement_measurement = None
  solver_generated_field_coupled_chain_planner = None
  solver_generated_field_coupled_chain_planner_measurement = None
  solver_generated_invariant_field_coupled_chain_planner = None
  solver_generated_invariant_field_coupled_chain_planner_measurement = None
  ambient_pressure_field_coupled_chain_planner = None
  if solver_generated_shock.field is not None and solver_generated_shock.field.converged:
    (
      solver_generated_chain_reference,
      solver_generated_chain_observations,
      solver_generated_chain_measurement_observations,
      solver_generated_chain_planner,
    ) = _solver_generated_chain_reference(
      solver_generated_shock.field,
    )
    solver_generated_chain_planner_measurement = measure_moc_chain_planner(
      solver_generated_chain_planner,
    )
    solver_generated_chain_refinement_measurement = (
      _solver_generated_chain_refinement_probe()
    )
    solver_generated_field_coupled_chain_planner = (
      _solver_generated_field_coupled_chain_planner(solver_generated_shock.field)
    )
    if solver_generated_field_coupled_chain_planner is not None:
      solver_generated_field_coupled_chain_planner_measurement = (
        measure_moc_chain_planner(solver_generated_field_coupled_chain_planner)
      )
    solver_generated_invariant_field_coupled_chain_planner = (
      _solver_generated_invariant_field_coupled_chain_planner(
        solver_generated_shock.field
      )
    )
    if solver_generated_invariant_field_coupled_chain_planner is not None:
      solver_generated_invariant_field_coupled_chain_planner_measurement = (
        measure_moc_chain_planner(
          solver_generated_invariant_field_coupled_chain_planner
        )
      )
    ambient_pressure_field_coupled_chain_planner = (
      _ambient_pressure_field_coupled_chain_planner(solver_generated_shock.field)
    )
    solver_generated_chain_measurement = measure_moc_shock_cell_chain(
      solver_generated_chain_measurement_observations,
    )
  caustic_upstream_remesh_chain_sequence = (
    _caustic_upstream_remesh_chain_sequence_probe(
      caustic_shock_seed,
      fan_exit.total_pressure_Pa,
      solver_generated_shock.field,
    )
  )
  solver_generated_chain_terminal_probe = _solver_generated_chain_terminal_probe(
    solver_generated_shock.field
    if solver_generated_shock.field is not None
    else _shock_seeded_field_fixture(),
  )
  (
    shock_cell_chain_mock,
    shock_cell_chain_mock_observations,
    shock_cell_chain_measurement_observations,
    shock_cell_chain_planner,
  ) = _shock_cell_chain_planner_mock(
    shock_seeded_field,
  )
  shock_cell_chain_planner_measurement = measure_moc_chain_planner(
    shock_cell_chain_planner,
  )
  shock_cell_chain_trace_validation = [
    {
      'cell_index': cell.cell_index,
      **_planner_boundary_validation(cell),
    }
    for cell in shock_cell_chain_mock.cells
  ]
  shock_seeded_fit = _shock_seeded_field_fit()
  shock_seeded_measurement = measure_moc_shock_cell(
    MocShockCellObservation(
      cell_index=1,
      shock_boundary_points_m=shock_seeded_field.shock_boundary_points_m,
      centerline_boundary_points_m=shock_seeded_field.centerline_boundary_points_m,
      cells=shock_seeded_field.cells,
      upstream_total_pressure_Pa=tuple(
        sample.upstream_total_pressure_Pa
        for sample in shock_seeded_fit.boundary_states
      ),
      downstream_total_pressure_Pa=tuple(
        sample.downstream_total_pressure_Pa
        for sample in shock_seeded_fit.boundary_states
      ),
    )
  )
  shock_cell_chain_measurement = measure_moc_shock_cell_chain(
    shock_cell_chain_measurement_observations,
  )
  shock_cell_chain_strict_gate = continue_post_shock_characteristic_chain(
    shock_seeded_field,
    lambda _current, _index, _handoff: None,
    start_x_m=0.7,
    end_x_m=1.0,
    require_upstream_shock_coupling=True,
  )
  solver_generated_measurement = measure_moc_shock_cell(
    MocShockCellObservation(
      cell_index=1,
      shock_boundary_points_m=solver_generated_shock.shock_points_m,
      centerline_boundary_points_m=(
        solver_generated_shock.field.centerline_boundary_points_m
        if solver_generated_shock.field is not None
        else ()
      ),
      cells=(
        solver_generated_shock.field.cells
        if solver_generated_shock.field is not None
        else ()
      ),
      upstream_total_pressure_Pa=(
        tuple(
          sample.upstream_total_pressure_Pa
          for sample in solver_generated_shock.shock_fit.boundary_states
        )
        if solver_generated_shock.shock_fit is not None
        else ()
      ),
      downstream_total_pressure_Pa=(
        tuple(
          sample.downstream_total_pressure_Pa
          for sample in solver_generated_shock.shock_fit.boundary_states
        )
        if solver_generated_shock.shock_fit is not None
        else ()
      ),
    )
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
  solver_generated_chain_planner_report = (
    None
    if solver_generated_chain_planner is None
    else solver_generated_chain_planner.as_report()
  )
  solver_generated_chain_fixture_report = (
    None
    if solver_generated_chain_planner_report is None
    else solver_generated_chain_planner_report.get('diagnostics', {}).get(
      'solver_generated_chain_reference'
    )
  )
  solver_generated_field_coupled_chain_planner_report = (
    None
    if solver_generated_field_coupled_chain_planner is None
    else solver_generated_field_coupled_chain_planner.as_report()
  )
  solver_generated_invariant_field_coupled_chain_planner_report = (
    None
    if solver_generated_invariant_field_coupled_chain_planner is None
    else solver_generated_invariant_field_coupled_chain_planner.as_report()
  )
  shock_cell_chain_mock_report = shock_cell_chain_mock.as_report()
  shock_cell_chain_planner_report = shock_cell_chain_planner.as_report()
  shock_cell_chain_fixture_report = shock_cell_chain_planner_report[
    'diagnostics'
  ]['prescribed_chain_mock']
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
  terminal_reflection_patch_refinement_failures = [
    case for case in terminal_reflection_patch_refinement_probe
    if (
      case.get('status') != 'converged_open_terminal_reflection_patch'
      or not case.get('patch_converged')
      or not case.get('combined_topology_forms_closed_zone')
      or case.get('combined_topology_nonmanifold_edge_count')
      or not case.get('input_trace_converged')
      or not case.get('outgoing_trace_converged')
      or case.get('shock_probe_status') != 'subsonic_terminal_required'
      or case.get('shock_probe_coupling_status') != 'converged_terminal_reflection_patch_field'
      or case.get('shock_probe_coupling_sampled_count') != case.get('shock_probe_sample_count')
      or case.get('physical_closure_verified')
      or not case.get('physical_terminal_verified')
      or case.get('first_cell_composite_status') != 'converged_closed_supersonic_composite'
      or case.get('first_cell_composite_topology_closed') is not True
      or case.get('first_cell_composite_boundary_conditions_verified') is not True
      or case.get('first_cell_composite_physical_closure_verified') is not False
      or not isinstance(case.get('first_cell_composite_measurement'), dict)
      or case['first_cell_composite_measurement'].get('status') != 'converged'
    )
  ]
  terminal_composite_refinement_failures = [
    case for case in terminal_composite_refinement_probe
    if _terminal_composite_refinement_case_failed(case)
  ]
  solver_generated_chain_failure = (
    solver_generated_chain_reference is None
    or solver_generated_chain_planner is None
    or not solver_generated_chain_reference.resolved
    or solver_generated_chain_reference.cell_count != 5
    or solver_generated_chain_reference.physical_termination
    or solver_generated_chain_report is None
    or solver_generated_chain_fixture_report is None
    or solver_generated_chain_fixture_report.get('claim_fidelity_ceiling') != (
      MocChainGeometryFidelity.RESOLVED_PLANAR_MOC.value
    )
    or solver_generated_chain_fixture_report.get('free_boundary_verified') is not False
    or solver_generated_chain_fixture_report.get(
      'physical_chain_promotion_allowed'
    ) is not False
    or solver_generated_chain_fixture_report.get('upstream_pressure_model') != (
      'normalized-shock-height-resampling-of-exact-incoming-handoff'
    )
    or solver_generated_chain_report.get('cell_geometry') is None
    or len(solver_generated_chain_report['cell_geometry']) != 5
    or any(
      not cell['boundary_geometry']['shock_boundary_points_m']
      for cell in solver_generated_chain_report['cell_geometry']
    )
    or any(
      not cell.carries_state
      for cell in solver_generated_chain_reference.cells
    )
    or not solver_generated_chain_pressure_lineage_ok
    or solver_generated_chain_planner.planner_kind is not MocChainPlannerKind.SOLVER_GENERATED_REFERENCE
    or not solver_generated_chain_planner.as_report()['planning_only']
    or solver_generated_chain_planner.production_claim_allowed
    or len(solver_generated_chain_planner.steps) != 5
    or solver_generated_chain_planner.handoff_links_verified is not True
    or solver_generated_chain_planner_measurement is None
    or not solver_generated_chain_planner_measurement.converged
    or solver_generated_chain_planner_measurement.handoff_links_verified is not True
    or not solver_generated_chain_planner_measurement.termination_verified
    or not solver_generated_chain_planner_measurement.fidelity_isolation_verified
    or solver_generated_chain_planner_measurement.physical_termination is not False
    or solver_generated_chain_planner_measurement.production_claim_allowed
    or solver_generated_chain_refinement_measurement is None
    or not solver_generated_chain_refinement_measurement.converged
    or not solver_generated_chain_refinement_measurement.pressure_loss_verified
    or not solver_generated_chain_refinement_measurement.refinement_convergence_verified
    or solver_generated_chain_refinement_measurement.termination_sensitivity_verified is not True
    or solver_generated_chain_refinement_measurement.handoff_links_verified is not True
    or solver_generated_chain_measurement is None
    or not solver_generated_chain_measurement.converged
    or solver_generated_chain_measurement.handoff_links_verified is not True
  )
  solver_generated_chain_terminal_failure = (
    solver_generated_chain_terminal_probe.get('expected_physical_termination') is not True
  )
  solver_generated_field_coupled_chain_failure = (
    solver_generated_field_coupled_chain_planner is None
    or solver_generated_field_coupled_chain_planner.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
    or not solver_generated_field_coupled_chain_planner.as_report()['planning_only']
    or solver_generated_field_coupled_chain_planner.production_claim_allowed
    or not solver_generated_field_coupled_chain_planner.chain.physical_termination
    or not solver_generated_field_coupled_chain_planner.chain.resolved
    or solver_generated_field_coupled_chain_planner.chain.cell_count != 1
    or solver_generated_field_coupled_chain_planner.chain.termination_reason is not MocChainTerminationReason.PHYSICAL_TERMINATION
    or len(solver_generated_field_coupled_chain_planner.steps) != 1
    or solver_generated_field_coupled_chain_planner_measurement is None
    or not solver_generated_field_coupled_chain_planner_measurement.converged
    or not solver_generated_field_coupled_chain_planner_measurement.termination_verified
    or not solver_generated_field_coupled_chain_planner_measurement.fidelity_isolation_verified
    or solver_generated_field_coupled_chain_planner.steps[0].boundary_kind is not MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
    or solver_generated_field_coupled_chain_planner.chain.diagnostics.get('termination_model') != 'normal-shock-terminal'
    or solver_generated_field_coupled_chain_planner.chain.diagnostics.get('upstream_field_model') != 'bounded-post-shock-characteristic-field'
    or solver_generated_field_coupled_chain_planner.diagnostics.get('field_coupled_chain_reference', {}).get('upstream_state_model') != 'bounded-previous-post-shock-field'
    or solver_generated_field_coupled_chain_planner.diagnostics.get('upstream_field_replacement_policy') != 'replace-only-after-complete-field-coupled-solve'
  )
  solver_generated_invariant_field_coupled_chain_failure = (
    solver_generated_invariant_field_coupled_chain_planner is None
    or solver_generated_invariant_field_coupled_chain_planner.planner_kind is not MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
    or not solver_generated_invariant_field_coupled_chain_planner.as_report()['planning_only']
    or solver_generated_invariant_field_coupled_chain_planner.production_claim_allowed
    or not solver_generated_invariant_field_coupled_chain_planner.chain.physical_termination
    or not solver_generated_invariant_field_coupled_chain_planner.chain.resolved
    or solver_generated_invariant_field_coupled_chain_planner.chain.cell_count != 1
    or solver_generated_invariant_field_coupled_chain_planner.chain.termination_reason is not MocChainTerminationReason.PHYSICAL_TERMINATION
    or len(solver_generated_invariant_field_coupled_chain_planner.steps) != 1
    or solver_generated_invariant_field_coupled_chain_planner_measurement is None
    or not solver_generated_invariant_field_coupled_chain_planner_measurement.converged
    or not solver_generated_invariant_field_coupled_chain_planner_measurement.termination_verified
    or not solver_generated_invariant_field_coupled_chain_planner_measurement.fidelity_isolation_verified
    or solver_generated_invariant_field_coupled_chain_planner.steps[0].boundary_kind is not MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
    or solver_generated_invariant_field_coupled_chain_planner.chain.diagnostics.get('termination_model') != 'normal-shock-terminal'
    or solver_generated_invariant_field_coupled_chain_planner.chain.diagnostics.get('shock_condition_model') != 'explicit-downstream-characteristic-invariant'
  )
  ambient_pressure_field_coupled_chain_failure = (
    ambient_pressure_field_coupled_chain_planner is None
    or ambient_pressure_field_coupled_chain_planner.get('accepted') is not True
  )
  source_strip_chain_planner_failure = (
    source_strip_chain_planner.get('accepted') is not True
  )
  source_strip_chain_sequence_planner_failure = (
    source_strip_chain_sequence_planner.get('accepted') is not True
  )
  caustic_upstream_remesh_chain_sequence_failure = (
    caustic_upstream_remesh_chain_sequence.get('accepted') is not True
  )
  mixed_regime_boundary_failure = (
    mixed_regime_boundary_probe.get('accepted') is not True
    or mixed_regime_boundary_probe.get('physical_closure_verified') is not False
    or mixed_regime_boundary_probe.get('chain_promotion_blocked') is not True
  )
  reflected_zone_assembly_failure = (
    not reflected_zone.converged
    or reflected_zone.state_sampling_available is not True
    or reflected_zone.physical_closure_verified is not False
    or reflected_zone.chain_promotion_blocked is not True
  )
  reflected_zone_chain_boundary_failure = (
    reflected_zone_chain_boundary_probe.get('accepted') is not True
    or reflected_zone_chain_boundary_probe.get('physical_termination') is not False
    or reflected_zone_chain_boundary_probe.get('status') != 'solver-terminated'
    or reflected_zone_chain_boundary_probe.get('termination_reason') != 'upstream-field-boundary'
  )
  post_shock_zone_chain_planner_failure = (
    post_shock_zone_chain_planner.get('accepted') is not True
  )
  ambient_axis_closure_probe_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get('ambient_axis_closure_probe_accepted') is not True
  )
  ambient_axis_closure_shoot_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get('ambient_axis_closure_shoot_probe_accepted')
    is not True
  )
  ambient_axis_closure_shoot_reference_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_axis_closure_shoot_reference_accepted'
    ) is not True
  )
  ambient_physical_field_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get('ambient_physical_field_probe_accepted')
    is not True
  )
  ambient_physical_field_reference_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_physical_field_reference_accepted'
    ) is not True
  )
  ambient_centerline_physical_field_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_field_accepted'
    ) is not True
  )
  ambient_centerline_physical_field_refinement_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_field_refinement_accepted'
    ) is not True
  )
  ambient_centerline_physical_chain_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_chain_probe_accepted'
    ) is not True
  )
  ambient_centerline_physical_chain_mock_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_chain_mock_accepted'
    ) is not True
  )
  ambient_centerline_physical_generated_chain_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_generated_chain_accepted'
    ) is not True
  )
  ambient_centerline_physical_reflected_source_chain_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_reflected_source_chain_accepted'
    ) is not True
  )
  ambient_centerline_physical_terminal_source_chain_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_terminal_source_chain_accepted'
    ) is not True
  )
  ambient_centerline_physical_terminal_patch_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_terminal_patch_planner_accepted'
    ) is not True
  )
  ambient_centerline_physical_terminal_patch_mixed_regime_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_terminal_patch_mixed_regime_planner_accepted'
    ) is not True
  )
  ambient_centerline_physical_terminal_patch_ambient_closure_chain_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_terminal_patch_ambient_closure_chain_accepted'
    ) is not True
  )
  ambient_centerline_physical_terminal_patch_refinement_failure = (
    ambient_shock_strip_probe.get('accepted') is True
    and ambient_shock_strip_probe.get(
      'ambient_centerline_physical_terminal_patch_refinement_accepted'
    ) is not True
  )
  terminal_patch_chain_probe = ambient_shock_strip_probe.get(
    'terminal_reflection_patch_chain_probe',
  )
  terminal_patch_chain_failure = (
    not isinstance(terminal_patch_chain_probe, dict)
    or terminal_patch_chain_probe.get('expected_physical_termination') is not True
    or terminal_patch_chain_probe.get('planner_expected_physical_termination') is not True
  )
  first_cell_composite_probe = ambient_shock_strip_probe.get(
    'first_cell_composite',
  )
  first_cell_terminal_closure_probe = ambient_shock_strip_probe.get(
    'first_cell_terminal_closure',
  )
  first_cell_composite_failure = (
    not isinstance(first_cell_composite_probe, dict)
    or first_cell_composite_probe.get('status')
    != 'converged_closed_supersonic_composite'
    or first_cell_composite_probe.get('topology_closed') is not True
    or first_cell_composite_probe.get('physical_boundary_conditions_verified') is not True
    or first_cell_composite_probe.get('physical_closure_verified') is not False
    or first_cell_composite_probe.get('chain_promotion_blocked') is not True
  )
  first_cell_terminal_closure_failure = (
    not isinstance(first_cell_terminal_closure_probe, dict)
    or first_cell_terminal_closure_probe.get('status')
    != 'converged_first_cell_supersonic_region'
    or first_cell_terminal_closure_probe.get('converged') is not True
    or first_cell_terminal_closure_probe.get('supersonic_region_closed') is not True
    or first_cell_terminal_closure_probe.get('physical_closure_verified') is not False
    or first_cell_terminal_closure_probe.get('mixed_regime_field_complete') is not False
    or first_cell_terminal_closure_probe.get('chain_promotion_blocked') is not True
    or first_cell_terminal_closure_probe.get('physical_termination_verified') is not False
    or not isinstance(
      first_cell_terminal_closure_probe.get('downstream_shock'),
      dict,
    )
    or first_cell_terminal_closure_probe['downstream_shock'].get(
      'physical_terminal_verified'
    ) is not True
    or not isinstance(
      first_cell_terminal_closure_probe.get('terminal_field'),
      dict,
    )
    or first_cell_terminal_closure_probe['terminal_field'].get(
      'terminal_shock_boundary_coverage_verified'
    ) is not True
  )
  first_cell_terminal_closure_planner_probe = ambient_shock_strip_probe.get(
    'first_cell_terminal_closure_planner',
  )
  first_cell_terminal_closure_planner_failure = (
    not isinstance(first_cell_terminal_closure_planner_probe, dict)
    or first_cell_terminal_closure_planner_probe.get('planner_kind')
    != MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK.value
    or first_cell_terminal_closure_planner_probe.get('planning_only') is not True
    or first_cell_terminal_closure_planner_probe.get('production_claim_allowed') is not False
    or first_cell_terminal_closure_planner_probe.get('resolved') is not True
    or first_cell_terminal_closure_planner_probe.get('physical_closure_verified') is not True
    or first_cell_terminal_closure_planner_probe.get('physical_termination') is not True
    or first_cell_terminal_closure_planner_probe.get('chain_promotion_blocked') is not True
    or not isinstance(
      first_cell_terminal_closure_planner_probe.get('termination'),
      dict,
    )
    or first_cell_terminal_closure_planner_probe['termination'].get(
      'reason'
    ) != MocChainTerminationReason.PHYSICAL_TERMINATION.value
    or not isinstance(
      first_cell_terminal_closure_planner_probe.get('mixed_regime_closure'),
      dict,
    )
    or first_cell_terminal_closure_planner_probe['mixed_regime_closure'].get(
      'status'
    ) != 'converged_mixed_regime_closure'
  )
  first_cell_terminal_closure_free_boundary_planner_probe = (
    ambient_shock_strip_probe.get(
      'first_cell_terminal_closure_free_boundary_planner',
    )
  )
  first_cell_terminal_closure_free_boundary_measurement_probe = (
    ambient_shock_strip_probe.get(
      'first_cell_terminal_closure_free_boundary_measurement',
    )
  )
  first_cell_terminal_closure_free_boundary_refinement_measurement_probe = (
    ambient_shock_strip_probe.get(
      'first_cell_terminal_closure_free_boundary_refinement_measurement',
    )
  )
  first_cell_terminal_closure_free_boundary_planner_failure = (
    not isinstance(first_cell_terminal_closure_free_boundary_planner_probe, dict)
    or first_cell_terminal_closure_free_boundary_planner_probe.get('planner_kind')
    != MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH.value
    or first_cell_terminal_closure_free_boundary_planner_probe.get('planning_only')
    is not True
    or first_cell_terminal_closure_free_boundary_planner_probe.get(
      'production_claim_allowed'
    ) is not False
    or first_cell_terminal_closure_free_boundary_planner_probe.get('resolved')
    is not True
    or first_cell_terminal_closure_free_boundary_planner_probe.get(
      'physical_closure_verified'
    ) is not True
    or first_cell_terminal_closure_free_boundary_planner_probe.get(
      'physical_termination'
    ) is not True
    or first_cell_terminal_closure_free_boundary_planner_probe.get(
      'chain_promotion_blocked'
    ) is not True
    or not isinstance(
      first_cell_terminal_closure_free_boundary_planner_probe.get(
        'mixed_regime_closure'
      ),
      dict,
    )
    or first_cell_terminal_closure_free_boundary_planner_probe[
      'mixed_regime_closure'
    ].get('status') != 'converged_mixed_regime_closure'
    or not isinstance(
      first_cell_terminal_closure_free_boundary_planner_probe.get('diagnostics'),
      dict,
    )
    or first_cell_terminal_closure_free_boundary_planner_probe['diagnostics'].get(
      'solver_generated_mixed_regime_result',
      {},
    ).get('converged') is not True
    or not isinstance(
      first_cell_terminal_closure_free_boundary_measurement_probe,
      dict,
    )
    or first_cell_terminal_closure_free_boundary_measurement_probe.get('status')
    != MocMixedRegimeFreeBoundaryMeasurementStatus.CONVERGED.value
    or first_cell_terminal_closure_free_boundary_measurement_probe.get(
      'converged'
    ) is not True
    or first_cell_terminal_closure_free_boundary_measurement_probe.get(
      'physical_closure_verified'
    ) is not True
    or first_cell_terminal_closure_free_boundary_measurement_probe.get(
      'chain_promotion_blocked'
    ) is not True
    or first_cell_terminal_closure_free_boundary_measurement_probe.get(
      'production_claim_allowed'
    ) is not False
  )
  first_cell_terminal_closure_free_boundary_refinement_measurement_failure = (
    not isinstance(
      first_cell_terminal_closure_free_boundary_refinement_measurement_probe,
      dict,
    )
    or first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
      'status'
    ) != MocMixedRegimeFreeBoundaryRefinementMeasurementStatus.CONVERGED.value
    or first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
      'converged'
    ) is not True
    or first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
      'physical_closure_verified'
    ) is not True
    or first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
      'canonical_reflected_moc_closure_verified'
    ) is not False
    or first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
      'chain_promotion_blocked'
    ) is not True
    or first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
      'production_claim_allowed'
    ) is not False
    or not isinstance(
      first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
        'checks'
      ),
      dict,
    )
    or not all(
      value is True
      for value in first_cell_terminal_closure_free_boundary_refinement_measurement_probe[
        'checks'
      ].values()
    )
  )
  caustic_family_restart_failure = (
    caustic_family_restart.get('accepted') is not True
  )
  caustic_shock_bridge_failure = (
    caustic_shock_bridge.get('accepted') is not True
  )
  caustic_shock_remesh_execution_failure = (
    caustic_shock_remesh_execution.get('accepted') is not True
  )
  caustic_family_band_shock_failure = (
    caustic_family_band_shock.get('accepted') is not True
  )
  caustic_family_band_chain_planner_failure = (
    caustic_family_band_chain_planner.get('accepted') is not True
  )
  caustic_family_band_invariant_chain_failure = (
    caustic_family_band_invariant_chain.get('accepted') is not True
  )
  caustic_upstream_bridge_failure = (
    caustic_upstream_bridge.get('accepted') is not True
  )
  caustic_upstream_continuation_failure = (
    caustic_upstream_continuation.get('accepted') is not True
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
  normal_shock_terminal = solve_normal_shock_terminal(
    CharacteristicState(
      x_m=1.25,
      y_m=0.0,
      theta_rad=0.1,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_pressure_Pa=100000.0,
    shock_point_m=(1.25, 0.0),
  )
  marched_subsonic_terminal = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(point[0], point[1], 0.0, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_rad=0.0,
    sample_count=5,
  )
  marched_strong_subsonic_boundary = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(point[0], point[1], -0.2, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_rad=0.0,
    branch=ShockBranch.STRONG,
    sample_count=5,
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
    'normal_shock_terminal_foundation': {
      **normal_shock_terminal.as_report(),
      'upstream_total_pressure_Pa': normal_shock_terminal.upstream_total_pressure_Pa,
      'downstream_total_pressure_Pa': normal_shock_terminal.downstream_total_pressure_Pa,
      'claim_status': 'typed-subsonic-terminal-diagnostic; mixed-regime-field-closure-pending',
    },
    'marched_subsonic_terminal_boundary': {
      **marched_subsonic_terminal.as_report(),
      'terminal_model_verified': marched_subsonic_terminal.terminal_model_verified,
      'claim_status': 'explicit-supersonic-moc-validity-boundary; chain-promotion-blocked',
    },
    'marched_strong_subsonic_boundary': {
      **marched_strong_subsonic_boundary.as_report(),
      'subsonic_boundary_verified': marched_strong_subsonic_boundary.subsonic_boundary_verified,
      'terminal_model_verified': marched_strong_subsonic_boundary.terminal_model_verified,
      'claim_status': (
        'typed-strong-attached-subsonic-seam; no-supersonic-moc-state-fabricated; '
        'chain-promotion-blocked'
      ),
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
      **reflected_zone.as_report(),
      'boundary_edge_count': reflected_zone.topology.boundary_edge_count,
      'boundary_component_count': reflected_zone.topology.boundary_component_count,
      'forms_closed_zone': reflected_zone.topology.forms_closed_zone,
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
    'reflected_source_strip_centerline_reflection_extension': {
      **reflected_centerline_reflection_extension.as_report(),
      'caustic_shock_seed': (
        None
        if caustic_shock_seed is None
        else caustic_shock_seed.as_report()
      ),
      'caustic_shock_resolution': (
        None
        if caustic_shock_resolution is None
        else caustic_shock_resolution.as_report()
      ),
      'caustic_shock_bridge': caustic_shock_bridge,
      'caustic_shock_remesh_execution': caustic_shock_remesh_execution,
      'caustic_family_restart': caustic_family_restart,
      'caustic_family_band_shock': caustic_family_band_shock,
      'caustic_family_band_origin_envelope': caustic_family_band_origin_envelope,
      'caustic_family_band_terminal_field': caustic_family_band_terminal_field,
      'caustic_family_band_chain_planner': caustic_family_band_chain_planner,
      'caustic_family_band_invariant_chain': caustic_family_band_invariant_chain,
      'caustic_upstream_bridge': caustic_upstream_bridge,
      'caustic_upstream_continuation': caustic_upstream_continuation,
      'caustic_family_band_terminal_refinement': caustic_family_band_terminal_refinement,
      'caustic_family_band_terminal_measurement': caustic_family_band_terminal_measurement,
      'claim_status': (
        'centerline-C-minus-reflection-boundary-law; '
        'triangular-domain-remesh-or-shock-closure-pending'
      ),
    },
    'terminal_source_window_invariant_closure': terminal_source_window_invariant_closure,
    'ambient_pressure_closure_probe': ambient_pressure_closure_probe,
    'reflected_zone_shock_coupling': reflected_zone_shock_coupling,
    'reflected_zone_chain_boundary_probe': reflected_zone_chain_boundary_probe,
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
    'post_shock_zone_chain_planner': post_shock_zone_chain_planner,
    'solver_generated_source_strip_chain_planner': source_strip_chain_planner,
    'solver_generated_source_strip_chain_sequence_planner': (
      source_strip_chain_sequence_planner
    ),
    'caustic_upstream_remesh_chain_sequence': (
      caustic_upstream_remesh_chain_sequence
    ),
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
      'upstream_shock_coupling_verified': (
        solver_generated_shock.field.upstream_shock_coupling_verified
        if solver_generated_shock.field is not None
        else False
      ),
      'shock_closure_status': (
        solver_generated_shock.field.shock_closure_status
        if solver_generated_shock.field is not None
        else None
      ),
      'message': solver_generated_shock.message,
      'measurement_operator': solver_generated_measurement.as_report(),
      'claim_status': 'solver-generated-boundary-conditioned-field; upstream-field-coupling-pending',
    },
    'solver_generated_ambient_shock_strip': ambient_shock_strip_probe,
    'solver_generated_terminal_patch_chain_probe': terminal_patch_chain_probe,
    'solver_generated_first_cell_composite': first_cell_composite_probe,
    'solver_generated_first_cell_terminal_closure': first_cell_terminal_closure_probe,
    'solver_generated_first_cell_terminal_closure_planner': (
      {
        'status': 'missing',
        'accepted': False,
        'planner': None,
      }
      if not isinstance(first_cell_terminal_closure_planner_probe, dict)
      else {
        'status': first_cell_terminal_closure_planner_probe.get(
          'planner_kind',
          'missing',
        ),
        'accepted': not first_cell_terminal_closure_planner_failure,
        'planner': first_cell_terminal_closure_planner_probe,
      }
    ),
    'solver_generated_first_cell_terminal_closure_free_boundary_planner': (
      {
        'status': 'missing',
        'accepted': False,
        'planner': None,
      }
      if not isinstance(first_cell_terminal_closure_free_boundary_planner_probe, dict)
      else {
        'status': first_cell_terminal_closure_free_boundary_planner_probe.get(
          'planner_kind',
          'missing',
        ),
        'accepted': not first_cell_terminal_closure_free_boundary_planner_failure,
        'planner': first_cell_terminal_closure_free_boundary_planner_probe,
      }
    ),
    'solver_generated_first_cell_terminal_closure_free_boundary_measurement': (
      {
        'status': 'missing',
        'accepted': False,
        'measurement': None,
      }
      if not isinstance(
        first_cell_terminal_closure_free_boundary_measurement_probe,
        dict,
      )
      else {
        'status': first_cell_terminal_closure_free_boundary_measurement_probe.get(
          'status',
          'missing',
        ),
        'accepted': (
          first_cell_terminal_closure_free_boundary_measurement_probe.get(
            'status'
          ) == MocMixedRegimeFreeBoundaryMeasurementStatus.CONVERGED.value
        ),
        'measurement': first_cell_terminal_closure_free_boundary_measurement_probe,
      }
    ),
    'ambient_attachment_closure_probe': ambient_attachment_closure_probe,
    'ambient_attachment_transition_probe': ambient_attachment_transition_probe,
    'solver_generated_shock_refinement': {
      'status': (
        'diagnostic-all-solver-generated-resolutions-converged'
        if not solver_generated_shock_refinement_failures
        else 'diagnostic-solver-generated-resolution-failure'
      ),
      'cases': solver_generated_shock_refinement_probe,
      'claim_status': 'solver-generated-boundary-refinement-only; upstream-field-coupling-pending',
    },
    'terminal_reflection_patch_refinement': {
      'status': (
        'diagnostic-terminal-patch-resolutions-reach-mixed-regime-gate'
        if not terminal_reflection_patch_refinement_failures
        else 'diagnostic-terminal-patch-resolution-failure'
      ),
      'cases': terminal_reflection_patch_refinement_probe,
      'claim_status': (
        'terminal-patch-upstream-coupling-refinement-only; '
        'mixed-regime-downstream-field-pending'
      ),
    },
    'terminal_composite_refinement': {
      'status': (
        'diagnostic-terminal-composite-resolutions-reach-supersonic-terminal-gate'
        if not terminal_composite_refinement_failures
        else 'diagnostic-terminal-composite-resolution-failure'
      ),
      'cases': terminal_composite_refinement_probe,
      'claim_status': (
        'supersonic-terminal-topology-and-boundary-coverage-refinement-only; '
        'mixed-regime-downstream-field-pending'
      ),
    },
    'mixed_regime_boundary_contract': mixed_regime_boundary_probe,
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
      'claim_fidelity_ceiling': (
        None
        if solver_generated_chain_fixture_report is None
        else solver_generated_chain_fixture_report.get('claim_fidelity_ceiling')
      ),
      'free_boundary_verified': (
        None
        if solver_generated_chain_fixture_report is None
        else solver_generated_chain_fixture_report.get('free_boundary_verified')
      ),
      'physical_chain_promotion_allowed': (
        None
        if solver_generated_chain_fixture_report is None
        else solver_generated_chain_fixture_report.get(
          'physical_chain_promotion_allowed'
        )
      ),
      'upstream_pressure_model': (
        None
        if solver_generated_chain_fixture_report is None
        else solver_generated_chain_fixture_report.get('upstream_pressure_model')
      ),
      'cell_geometry': (
        None
        if solver_generated_chain_report is None
        else solver_generated_chain_report['cell_geometry']
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
      'measurement_operator': solver_generated_measurement.as_report(),
      'chain_measurement_operator': (
        None
        if solver_generated_chain_measurement is None
        else solver_generated_chain_measurement.as_report()
      ),
      'strict_upstream_coupling_mode': True,
      'claim_status': 'strict-upstream-coupled-chain-reference; reflected-field-coupling-pending',
    },
    'solver_generated_chain_refinement': (
      None
      if solver_generated_chain_refinement_measurement is None
      else solver_generated_chain_refinement_measurement.as_report()
    ),
    'solver_generated_chain_planner': {
      'planner_kind': (
        None
        if solver_generated_chain_planner is None
        else solver_generated_chain_planner.planner_kind.value
      ),
      'planning_only': (
        None
        if solver_generated_chain_planner_report is None
        else solver_generated_chain_planner_report['planning_only']
      ),
      'production_claim_allowed': (
        None
        if solver_generated_chain_planner is None
        else solver_generated_chain_planner.production_claim_allowed
      ),
      'planner_step_count': (
        None
        if solver_generated_chain_planner is None
        else len(solver_generated_chain_planner.steps)
      ),
      'handoff_links_verified': (
        None
        if solver_generated_chain_planner is None
        else solver_generated_chain_planner.handoff_links_verified
      ),
      'planner_steps': (
        []
        if solver_generated_chain_planner is None
        else [step.as_report() for step in solver_generated_chain_planner.steps]
      ),
      'diagnostics': (
        {}
        if solver_generated_chain_planner_report is None
        else solver_generated_chain_planner_report['diagnostics']
      ),
      'claim_status': (
        None
        if solver_generated_chain_planner is None
        else solver_generated_chain_planner.claim_status
      ),
      'planner_measurement': (
        None
        if solver_generated_chain_planner_measurement is None
        else solver_generated_chain_planner_measurement.as_report()
      ),
    },
    'solver_generated_chain_terminal_probe': {
      **solver_generated_chain_terminal_probe,
      'accepted': not solver_generated_chain_terminal_failure,
    },
    'solver_generated_field_coupled_chain_planner': {
      'reference': (
        {}
        if solver_generated_field_coupled_chain_planner is None
        else dict(
          solver_generated_field_coupled_chain_planner.diagnostics.get(
            'field_coupled_chain_reference',
            {},
          )
        )
      ),
      'upstream_field_replacement_policy': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.diagnostics.get(
          'upstream_field_replacement_policy'
        )
      ),
      'planner_kind': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.planner_kind.value
      ),
      'planning_only': (
        None
        if solver_generated_field_coupled_chain_planner_report is None
        else solver_generated_field_coupled_chain_planner_report['planning_only']
      ),
      'production_claim_allowed': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.production_claim_allowed
      ),
      'planner_step_count': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else len(solver_generated_field_coupled_chain_planner.steps)
      ),
      'planner_steps': (
        []
        if solver_generated_field_coupled_chain_planner is None
        else [
          step.as_report()
          for step in solver_generated_field_coupled_chain_planner.steps
        ]
      ),
      'status': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.chain.status.value
      ),
      'termination_reason': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.chain.termination_reason.value
      ),
      'physical_termination': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.chain.physical_termination
      ),
      'cell_count': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.chain.cell_count
      ),
      'resolved': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.chain.resolved
      ),
      'chain_diagnostics': (
        {}
        if solver_generated_field_coupled_chain_planner is None
        else dict(solver_generated_field_coupled_chain_planner.chain.diagnostics)
      ),
      'planner_measurement': (
        None
        if solver_generated_field_coupled_chain_planner_measurement is None
        else solver_generated_field_coupled_chain_planner_measurement.as_report()
      ),
      'accepted': not solver_generated_field_coupled_chain_failure,
      'claim_status': (
        None
        if solver_generated_field_coupled_chain_planner is None
        else solver_generated_field_coupled_chain_planner.claim_status
      ),
    },
    'solver_generated_invariant_field_coupled_chain_planner': {
      'planner': (
        None
        if solver_generated_invariant_field_coupled_chain_planner_report is None
        else solver_generated_invariant_field_coupled_chain_planner_report
      ),
      'planner_measurement': (
        None
        if solver_generated_invariant_field_coupled_chain_planner_measurement is None
        else solver_generated_invariant_field_coupled_chain_planner_measurement.as_report()
      ),
      'accepted': not solver_generated_invariant_field_coupled_chain_failure,
      'claim_status': (
        None
        if solver_generated_invariant_field_coupled_chain_planner is None
        else solver_generated_invariant_field_coupled_chain_planner.claim_status
      ),
    },
    'ambient_pressure_field_coupled_chain_planner': (
      {
        'status': 'missing',
        'accepted': False,
        'planner': None,
      }
      if ambient_pressure_field_coupled_chain_planner is None
      else ambient_pressure_field_coupled_chain_planner
    ),
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
      'continuation_boundary_kind': 'post-shock-field-perimeter',
      'physical_closure_status': shock_seeded_field.physical_closure_status,
      'shock_closure_status': shock_seeded_field.shock_closure_status,
      'upstream_shock_coupling_verified': shock_seeded_field.upstream_shock_coupling_verified,
      'message': shock_seeded_field.message,
      'measurement_operator': shock_seeded_measurement.as_report(),
      'claim_status': 'synthetic-prescribed-field-contract-only; canonical-free-boundary-pending',
    },
    'shock_seeded_ambient_boundary': {
      **shock_seeded_ambient_boundary.as_report(),
      'pressure_residuals': shock_seeded_ambient_boundary.pressure_residuals,
      'tangent_residuals': shock_seeded_ambient_boundary.tangent_residuals,
      'claim_status': (
        'explicit-outer-perimeter-gate; synthetic-field-rejected-until-'
        'ambient-pressure-and-tangency-coupling'
      ),
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
      'planner_kind': shock_cell_chain_planner.planner_kind.value,
      'planning_only': shock_cell_chain_planner_report['planning_only'],
      'production_claim_allowed': shock_cell_chain_planner.production_claim_allowed,
      'claim_fidelity_ceiling': shock_cell_chain_fixture_report[
        'claim_fidelity_ceiling'
      ],
      'boundary_provenance': shock_cell_chain_fixture_report[
        'boundary_provenance'
      ],
      'local_field_assembly': shock_cell_chain_fixture_report[
        'local_field_assembly'
      ],
      'free_boundary_verified': shock_cell_chain_fixture_report[
        'free_boundary_verified'
      ],
      'physical_chain_promotion_allowed': shock_cell_chain_fixture_report[
        'physical_chain_promotion_allowed'
      ],
      'geometry_schedule_model': shock_cell_chain_fixture_report[
        'geometry_schedule_model'
      ],
      'cell_axial_lengths_m': shock_cell_chain_fixture_report[
        'cell_axial_lengths_m'
      ],
      'shock_start_offsets_m': shock_cell_chain_fixture_report[
        'shock_start_offsets_m'
      ],
      'shock_geometry_scales_per_cell': shock_cell_chain_fixture_report[
        'shock_geometry_scales_per_cell'
      ],
      'per_cell_geometry_schedule': shock_cell_chain_fixture_report[
        'per_cell_geometry_schedule'
      ],
      'shock_geometry_scale_schedule': shock_cell_chain_fixture_report[
        'shock_geometry_scale_schedule'
      ],
      'upstream_pressure_model': shock_cell_chain_fixture_report[
        'upstream_pressure_model'
      ],
      'planner_step_count': len(shock_cell_chain_planner.steps),
      'handoff_links_verified': shock_cell_chain_planner.handoff_links_verified,
      'planner_steps': [
        step.as_report() for step in shock_cell_chain_planner.steps
      ],
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
      'cell_geometry': shock_cell_chain_mock_report['cell_geometry'],
      'observations': shock_cell_chain_mock_observations,
      'terminal_trace_validation': shock_cell_chain_trace_validation,
      'measurement_operator': shock_cell_chain_measurement.as_report(),
      'planner_measurement': shock_cell_chain_planner_measurement.as_report(),
      'strict_upstream_coupling_gate': {
        'status': shock_cell_chain_strict_gate.status.value,
        'termination_reason': shock_cell_chain_strict_gate.termination_reason.value,
        'message': shock_cell_chain_strict_gate.message,
        'expected_status': MocChainStatus.STATE_BOUNDARY.value,
        'claim_status': 'prescribed-seed-rejected-by-strict-upstream-coupling-gate',
      },
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
        'case': 'normal_shock_terminal_foundation',
        'status': normal_shock_terminal.status.value,
        'message': normal_shock_terminal.message,
      }
    ] if not normal_shock_terminal.converged or not normal_shock_terminal.subsonic else []),
    *([
      {
        'case': 'marched_subsonic_terminal_boundary',
        'status': marched_subsonic_terminal.status.value,
        'message': marched_subsonic_terminal.message,
      }
    ] if (
      marched_subsonic_terminal.status.value != 'subsonic_terminal_required'
      or not marched_subsonic_terminal.terminal_model_verified
    ) else []),
    *([
      {
        'case': 'marched_strong_subsonic_boundary',
        'status': marched_strong_subsonic_boundary.status.value,
        'message': marched_strong_subsonic_boundary.message,
      }
    ] if (
      marched_strong_subsonic_boundary.status.value != 'subsonic_terminal_required'
      or not marched_strong_subsonic_boundary.subsonic_boundary_verified
      or marched_strong_subsonic_boundary.terminal_model_verified
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
    ] if reflected_zone_assembly_failure else []),
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
        'case': 'post_shock_zone_chain_planner',
        'status': str(post_shock_zone_chain_planner.get('status', 'missing')),
        'message': str(post_shock_zone_chain_planner.get('message', '')),
      }
    ] if post_shock_zone_chain_planner_failure else []),
    *([
      {
        'case': 'shock_seeded_post_shock_field',
        'status': shock_seeded_field.status.value,
        'message': shock_seeded_field.message,
      }
    ] if not shock_seeded_field.converged else []),
    *([
      {
        'case': 'shock_seeded_measurement_operator',
        'status': shock_seeded_measurement.status.value,
        'message': shock_seeded_measurement.message,
      }
    ] if not shock_seeded_measurement.converged else []),
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
        'case': 'solver_generated_ambient_shock_strip',
        'status': ambient_shock_strip_probe['status'],
        'message': str(ambient_shock_strip_probe.get('message', '')),
      }
    ] if ambient_shock_strip_probe.get('accepted') is not True else []),
    *([
      {
        'case': 'solver_generated_ambient_axis_closure_probe',
        'status': str(
          ambient_shock_strip_probe.get('ambient_axis_closure', {}).get(
            'status',
            'missing',
          )
        ),
        'message': str(
          ambient_shock_strip_probe.get('ambient_axis_closure', {}).get(
            'message',
            '',
          )
        ),
      }
    ] if ambient_axis_closure_probe_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_axis_closure_shoot',
        'status': str(
          ambient_shock_strip_probe.get('ambient_axis_closure_shoot', {}).get(
            'status',
            'missing',
          )
        ),
        'message': str(
          ambient_shock_strip_probe.get('ambient_axis_closure_shoot', {}).get(
            'message',
            '',
          )
        ),
      }
    ] if ambient_axis_closure_shoot_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_axis_closure_shoot_reference',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_axis_closure_shoot_reference',
            {},
          ).get('status', 'missing')
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_axis_closure_shoot_reference',
            {},
          ).get('message', '')
        ),
      }
    ] if ambient_axis_closure_shoot_reference_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_physical_field',
        'status': str(
          ambient_shock_strip_probe.get('ambient_physical_field', {}).get(
            'status',
            'missing',
          )
        ),
        'message': str(
          ambient_shock_strip_probe.get('ambient_physical_field', {}).get(
            'message',
            '',
          )
        ),
      }
    ] if ambient_physical_field_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_physical_field_reference',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_physical_field_reference',
            {},
          ).get('status', 'missing')
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_physical_field_reference',
            {},
          ).get('message', '')
        ),
      }
    ] if ambient_physical_field_reference_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_physical_field',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_field',
            {},
          ).get('status', 'missing')
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_field',
            {},
          ).get('message', '')
        ),
      }
    ] if ambient_centerline_physical_field_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_physical_field_refinement',
        'status': 'refinement-gate-failed',
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_field_refinement',
            [],
          )
        ),
      }
    ] if ambient_centerline_physical_field_refinement_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_physical_chain',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_chain_probe',
            {},
          ).get('chain', {}).get('termination_reason', 'missing')
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_chain_probe',
            {},
          ).get('message', '')
        ),
      }
    ] if ambient_centerline_physical_chain_failure else []),
    *([
      {
        'case': 'prescribed_ambient_centerline_physical_chain_mock',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_chain_mock',
            {},
          ).get('chain', {}).get('termination_reason', 'missing')
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_chain_mock',
            {},
          ).get('chain', {}).get('message', '')
        ),
      }
    ] if ambient_centerline_physical_chain_mock_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_physical_chain_reference',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_generated_chain',
            {},
          ).get('chain', {}).get('termination_reason', 'missing')
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_generated_chain',
            {},
          ).get('chain', {}).get('message', '')
        ),
      }
    ] if ambient_centerline_physical_generated_chain_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_reflected_patch_source_chain',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_reflected_source_chain',
            {},
          ).get('planner', {}).get('chain', {}).get(
            'termination_reason',
            'missing',
          )
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_reflected_source_chain',
            {},
          ).get('planner', {}).get('chain', {}).get('message', '')
        ),
      }
    ] if ambient_centerline_physical_reflected_source_chain_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_normal_shock_terminal_source_chain',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_terminal_source_chain',
            {},
          ).get('planner', {}).get('chain', {}).get(
            'termination_reason',
            'missing',
          )
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_terminal_source_chain',
            {},
          ).get('planner', {}).get('chain', {}).get('message', '')
        ),
      }
    ] if ambient_centerline_physical_terminal_source_chain_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_physical_terminal_patch',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_terminal_patch_planner',
            {},
          ).get('chain', {}).get('termination_reason', 'missing')
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_terminal_patch_planner',
            {},
          ).get('message', '')
        ),
      }
    ] if ambient_centerline_physical_terminal_patch_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_physical_terminal_patch_mixed_regime',
        'status': 'mixed-regime-planner-gate-failed',
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_terminal_patch_mixed_regime_planner',
            {},
          )
        ),
      }
    ] if ambient_centerline_physical_terminal_patch_mixed_regime_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_physical_terminal_patch_ambient_closure_chain',
        'status': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_terminal_patch_ambient_closure_chain',
            {},
          ).get('chain', {}).get('termination_reason', 'missing')
        ),
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_terminal_patch_ambient_closure_chain',
            {},
          ).get('chain', {}).get('message', '')
        ),
      }
    ] if ambient_centerline_physical_terminal_patch_ambient_closure_chain_failure else []),
    *([
      {
        'case': 'solver_generated_ambient_centerline_physical_terminal_patch_refinement',
        'status': 'refinement-gate-failed',
        'message': str(
          ambient_shock_strip_probe.get(
            'ambient_centerline_physical_terminal_patch_refinement',
            [],
          )
        ),
      }
    ] if ambient_centerline_physical_terminal_patch_refinement_failure else []),
    *([
      {
        'case': 'solver_generated_terminal_patch_chain_probe',
        'status': (
          'missing'
          if not isinstance(terminal_patch_chain_probe, dict)
          else str(terminal_patch_chain_probe.get('status', 'missing'))
        ),
        'message': (
          'terminal-patch chain adapter did not return its expected typed '
          'physical termination'
          if not isinstance(terminal_patch_chain_probe, dict)
          else str(terminal_patch_chain_probe.get('message', ''))
        ),
      }
    ] if terminal_patch_chain_failure else []),
    *([
      {
        'case': 'solver_generated_first_cell_composite',
        'status': (
          'missing'
          if not isinstance(first_cell_composite_probe, dict)
          else str(first_cell_composite_probe.get('status', 'missing'))
        ),
        'message': (
          'first-cell strip/patch union did not pass its physical-boundary '
          'topology contract'
          if not isinstance(first_cell_composite_probe, dict)
          else str(first_cell_composite_probe.get('message', ''))
        ),
      }
    ] if first_cell_composite_failure else []),
    *([
      {
        'case': 'solver_generated_first_cell_terminal_closure',
        'status': (
          'missing'
          if not isinstance(first_cell_terminal_closure_probe, dict)
          else str(first_cell_terminal_closure_probe.get('status', 'missing'))
        ),
        'message': (
          'first-cell terminal shock adapter did not close the supersonic '
          'region from the exact outgoing handoff'
          if not isinstance(first_cell_terminal_closure_probe, dict)
          else str(first_cell_terminal_closure_probe.get('message', ''))
        ),
      }
    ] if first_cell_terminal_closure_failure else []),
    *([
      {
        'case': 'solver_generated_first_cell_terminal_closure_free_boundary_planner',
        'status': (
          'missing'
          if not isinstance(first_cell_terminal_closure_free_boundary_planner_probe, dict)
          else str(first_cell_terminal_closure_free_boundary_planner_probe.get('planner_kind', 'missing'))
        ),
        'message': (
          'solver-owned downstream free-boundary reference did not pass its '
          'height, condition, field, and exact-seam planner gates'
          if not isinstance(first_cell_terminal_closure_free_boundary_planner_probe, dict)
          else str(first_cell_terminal_closure_free_boundary_planner_probe.get('claim_status', ''))
        ),
      }
    ] if first_cell_terminal_closure_free_boundary_planner_failure else []),
    *([
      {
        'case': 'solver_generated_first_cell_terminal_closure_free_boundary_refinement_measurement',
        'status': (
          'missing'
          if not isinstance(
            first_cell_terminal_closure_free_boundary_refinement_measurement_probe,
            dict,
          )
          else str(
            first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
              'status',
              'missing',
            )
          )
        ),
        'message': (
          'solver-owned free-boundary refinement evidence did not retain '
          'fixed seam/parameters and stable declared resolutions'
          if not isinstance(
            first_cell_terminal_closure_free_boundary_refinement_measurement_probe,
            dict,
          )
          else str(
            first_cell_terminal_closure_free_boundary_refinement_measurement_probe.get(
              'message',
              '',
            )
          )
        ),
      }
    ] if first_cell_terminal_closure_free_boundary_refinement_measurement_failure else []),
    *([
      {
        'case': 'ambient_attachment_closure_probe',
        'status': ambient_attachment_closure_probe['status'],
        'message': str(ambient_attachment_closure_probe.get('message', '')),
      }
    ] if ambient_attachment_closure_probe.get('expected_open_strip') is not True else []),
    *([
      {
        'case': 'ambient_attachment_transition_probe',
        'status': ambient_attachment_transition_probe['status'],
        'message': str(ambient_attachment_transition_probe.get('message', '')),
      }
    ] if ambient_attachment_transition_probe.get('expected_physical_termination') is not True else []),
    *([
      {
        'case': 'solver_generated_measurement_operator',
        'status': solver_generated_measurement.status.value,
        'message': solver_generated_measurement.message,
      }
    ] if not solver_generated_measurement.converged else []),
    *([
      {
        'case': 'solver_generated_shock_refinement',
        'status': 'resolution_failure',
        'message': str(solver_generated_shock_refinement_failures),
      }
    ] if solver_generated_shock_refinement_failures else []),
    *([
      {
        'case': 'terminal_reflection_patch_refinement',
        'status': 'resolution_failure',
        'message': str(terminal_reflection_patch_refinement_failures),
      }
    ] if terminal_reflection_patch_refinement_failures else []),
    *([
      {
        'case': 'terminal_composite_refinement',
        'status': 'resolution_failure',
        'message': str(terminal_composite_refinement_failures),
      }
    ] if terminal_composite_refinement_failures else []),
    *([
      {
        'case': 'mixed_regime_boundary_contract',
        'status': str(mixed_regime_boundary_probe.get('status', 'missing')),
        'message': str(mixed_regime_boundary_probe.get('message', '')),
      }
    ] if mixed_regime_boundary_failure else []),
    *([
      {
        'case': 'reflected_zone_chain_boundary_probe',
        'status': str(reflected_zone_chain_boundary_probe.get('status', 'missing')),
        'message': str(reflected_zone_chain_boundary_probe.get('message', '')),
      }
    ] if reflected_zone_chain_boundary_failure else []),
    *([
      {
        'case': 'caustic_shock_bridge',
        'status': str(caustic_shock_bridge.get('status', 'missing')),
        'message': str(
          caustic_shock_bridge.get('bridge', {}).get('message', '')
          if isinstance(caustic_shock_bridge.get('bridge'), dict)
          else caustic_shock_bridge.get('claim_status', '')
        ),
      }
    ] if caustic_shock_bridge_failure else []),
    *([
      {
        'case': 'caustic_shock_remesh_execution',
        'status': str(caustic_shock_remesh_execution.get('status', 'missing')),
        'message': str(
          caustic_shock_remesh_execution.get('direct', {}).get('message', '')
          if isinstance(caustic_shock_remesh_execution.get('direct'), dict)
          else caustic_shock_remesh_execution.get('claim_status', '')
        ),
      }
    ] if caustic_shock_remesh_execution_failure else []),
    *([
      {
        'case': 'caustic_family_restart',
        'status': str(caustic_family_restart.get('status', 'missing')),
        'message': str(caustic_family_restart.get('message', '')),
      }
    ] if caustic_family_restart_failure else []),
    *([
      {
        'case': 'caustic_family_band_shock',
        'status': str(caustic_family_band_shock.get('status', 'missing')),
        'message': str(caustic_family_band_shock.get('message', '')),
      }
    ] if caustic_family_band_shock_failure else []),
    *([
      {
        'case': 'caustic_family_band_chain_planner',
        'status': str(caustic_family_band_chain_planner.get('status', 'missing')),
        'message': str(caustic_family_band_chain_planner.get('message', '')),
      }
    ] if caustic_family_band_chain_planner_failure else []),
    *([
      {
        'case': 'caustic_family_band_invariant_chain',
        'status': str(caustic_family_band_invariant_chain.get('status', 'missing')),
        'message': str(caustic_family_band_invariant_chain.get('message', '')),
      }
    ] if caustic_family_band_invariant_chain_failure else []),
    *([
      {
        'case': 'caustic_upstream_bridge',
        'status': str(caustic_upstream_bridge.get('status', 'missing')),
        'message': str(caustic_upstream_bridge.get('message', '')),
      }
    ] if caustic_upstream_bridge_failure else []),
    *([
      {
        'case': 'caustic_upstream_continuation',
        'status': str(caustic_upstream_continuation.get('status', 'missing')),
        'message': str(caustic_upstream_continuation.get('message', '')),
      }
    ] if caustic_upstream_continuation_failure else []),
    *([
      {
        'case': 'solver_generated_chain_reference',
        'status': (
          'missing'
          if solver_generated_chain_reference is None
          else solver_generated_chain_reference.status.value
        ),
        'message': (
          'solver-generated chain reference did not produce five resolved '
          'state-carrying cells'
          if solver_generated_chain_reference is not None
          else 'solver-generated chain reference could not be constructed'
        ),
      }
    ] if solver_generated_chain_failure else []),
    *([
      {
        'case': 'solver_generated_chain_terminal_probe',
        'status': str(solver_generated_chain_terminal_probe.get('status', 'missing')),
        'message': str(solver_generated_chain_terminal_probe.get('message', '')),
      }
    ] if solver_generated_chain_terminal_failure else []),
    *([
      {
        'case': 'solver_generated_field_coupled_chain_planner',
        'status': (
          'missing'
          if solver_generated_field_coupled_chain_planner is None
          else solver_generated_field_coupled_chain_planner.chain.status.value
        ),
        'message': (
          'solver-generated field-coupled planner did not reach its typed '
          'normal-shock terminal with one resolved state-carrying seed cell'
          if solver_generated_field_coupled_chain_planner is not None
          else 'solver-generated field-coupled planner could not be constructed'
        ),
      }
    ] if solver_generated_field_coupled_chain_failure else []),
    *([
      {
        'case': 'solver_generated_invariant_field_coupled_chain_planner',
        'status': (
          'missing'
          if solver_generated_invariant_field_coupled_chain_planner is None
          else solver_generated_invariant_field_coupled_chain_planner.chain.status.value
        ),
        'message': (
          'invariant-conditioned field-coupled planner did not preserve its '
          'typed physical-terminal and exact-handoff contract'
          if solver_generated_invariant_field_coupled_chain_planner is not None
          else 'invariant-conditioned field-coupled planner could not be constructed'
        ),
      }
    ] if solver_generated_invariant_field_coupled_chain_failure else []),
    *([
      {
        'case': 'ambient_pressure_field_coupled_chain_planner',
        'status': (
          'missing'
          if ambient_pressure_field_coupled_chain_planner is None
          else str(ambient_pressure_field_coupled_chain_planner.get('status', 'missing'))
        ),
        'message': (
          'ambient-pressure field planner did not preserve the bounded '
          'upstream-field stop contract'
        ),
      }
    ] if ambient_pressure_field_coupled_chain_failure else []),
    *([
      {
        'case': 'solver_generated_source_strip_chain_planner',
        'status': str(source_strip_chain_planner.get('status', 'missing')),
        'message': str(source_strip_chain_planner.get('message', '')),
      }
    ] if source_strip_chain_planner_failure else []),
    *([
      {
        'case': 'solver_generated_source_strip_chain_sequence_planner',
        'status': str(source_strip_chain_sequence_planner.get('status', 'missing')),
        'message': str(source_strip_chain_sequence_planner.get('message', '')),
      }
    ] if source_strip_chain_sequence_planner_failure else []),
    *([
      {
        'case': 'caustic_upstream_remesh_chain_sequence',
        'status': str(caustic_upstream_remesh_chain_sequence.get('status', 'missing')),
        'message': str(caustic_upstream_remesh_chain_sequence.get('message', '')),
      }
    ] if caustic_upstream_remesh_chain_sequence_failure else []),
    *([
      {
        'case': 'shock_cell_chain_planner_mock',
        'status': shock_cell_chain_mock.status.value,
        'message': shock_cell_chain_mock.message,
      }
    ] if (
      not shock_cell_chain_mock.resolved
      or shock_cell_chain_mock_report['continuation_boundary_maxima_nonincreasing'] is not True
      or shock_cell_chain_planner.handoff_links_verified is not True
      or not shock_cell_chain_measurement.converged
      or shock_cell_chain_measurement.handoff_links_verified is not True
      or not shock_cell_chain_planner_measurement.converged
      or shock_cell_chain_planner_measurement.handoff_links_verified is not True
      or not shock_cell_chain_planner_measurement.termination_verified
      or not shock_cell_chain_planner_measurement.fidelity_isolation_verified
      or shock_cell_chain_planner_measurement.physical_termination is not False
      or shock_cell_chain_planner_measurement.production_claim_allowed
      or shock_cell_chain_fixture_report['claim_fidelity_ceiling'] != (
        MocChainGeometryFidelity.PRESCRIBED_BOUNDARY_DIAGNOSTIC.value
      )
      or shock_cell_chain_fixture_report['geometry_schedule_model'] != (
        'explicit-per-cell-schedule'
      )
      or len(shock_cell_chain_fixture_report['per_cell_geometry_schedule']) != 4
      or shock_cell_chain_fixture_report['free_boundary_verified'] is not False
      or shock_cell_chain_fixture_report[
        'physical_chain_promotion_allowed'
      ] is not False
      or len(shock_cell_chain_mock_report['cell_geometry']) != shock_cell_chain_mock.cell_count
      or any(
        not cell['boundary_geometry']['shock_boundary_points_m']
        for cell in shock_cell_chain_mock_report['cell_geometry']
      )
    ) else []),
    *([
      {
        'case': 'shock_cell_chain_measurement_operator',
        'status': shock_cell_chain_measurement.status.value,
        'message': shock_cell_chain_measurement.message,
      }
    ] if not shock_cell_chain_measurement.converged else []),
    *([
      {
        'case': 'shock_cell_chain_planner_measurement_operator',
        'status': shock_cell_chain_planner_measurement.status.value,
        'message': shock_cell_chain_planner_measurement.message,
      }
    ] if not shock_cell_chain_planner_measurement.converged else []),
    *([
      {
        'case': 'shock_cell_chain_strict_upstream_coupling_gate',
        'status': shock_cell_chain_strict_gate.status.value,
        'message': shock_cell_chain_strict_gate.message,
      }
    ] if (
      shock_cell_chain_strict_gate.status is not MocChainStatus.STATE_BOUNDARY
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
      'replace the research terminal-patch downstream turn with a physically validated reflected-domain law for any further shock-cell transition',
      'replace the provisional constant-invariant boundary with a physically validated downstream closure and a straddling canonical bracket',
      'complete and independently validate the canonical reflected-MOC mixed-regime downstream closure after the open oblique supersonic patch; the affine projected potential reference remains research-only',
      'production next-cell shock fitting that consumes the typed state/total-pressure handoff without a geometric template',
      'grid/refinement convergence for the assembled reflected zone and mild attached-overexpanded cases',
      'external measurement-operator comparison using the independent MOC extraction before provider integration',
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
