from __future__ import annotations

from dataclasses import replace
from math import cos, sin

import numpy as np
import pytest

import exhaust_plume.models.moc.coupled_euler_free_boundary as coupled_euler
from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientPhysicalFieldResult,
  MocAmbientPhysicalFieldStatus,
  MocBoundedUpstreamFieldSource,
  MocChainBoundarySample,
  MocChainContinuationPolicy,
  MocChainTerminationReason,
  MocPostShockChainCellSolve,
  MocReflectedDomainRemeshRequest,
  MocReflectedDomainAlternatingSourceStatus,
  MocReflectedDomainAlternatingPhysicalFieldStatus,
  MocReflectedDomainSolverOwnedFirstCellStatus,
  MocReflectedDomainGlobalShockRemeshStatus,
  MocReflectedDomainGlobalEulerShockBoundaryStatus,
  MocReflectedDomainGlobalPhysicalClosureStatus,
  MocReflectedDomainGlobalPhysicalClosureResult,
  MocReflectedDomainGlobalCoupledDownstreamStatus,
  MocReflectedDomainGlobalPhysicalFieldHandoff,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus,
  MocReflectedDomainDownstreamBoundaryStatus,
  MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  MocReflectedDomainCoupledEulerInletBoundaryMode,
  MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus,
  MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus,
  MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus,
  MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus,
  MocTransonicShockGeometryRequest,
  MocTransonicShockGeometryStatus,
  MocTransonicShockInterfaceFieldProfileRequest,
  MocTransonicShockInterfaceFieldProfileStatus,
  MocTransonicShockInterfaceFieldPlacementRequest,
  MocTransonicShockInterfaceFieldPlacementStatus,
  MocTransonicShockInterfaceProfile,
  MocTransonicShockInterfaceSample,
  MocPhysicalFieldContinuationProfileRequest,
  MocPhysicalFieldContinuationProfileStatus,
  MocPhysicalFieldShockFrontConditionRequest,
  MocPhysicalFieldShockFrontConditionStatus,
  MocTransonicTransitionStatus,
  MocReflectedDomainMixedRegimeBoundaryStatus,
  MocReflectedDomainPromotionEvidence,
  MocProductionShockCellFitStatus,
  MocGlobalEulerContinuedChainReference,
  MocReflectedDomainOuterSourceStatus,
  MocReflectedDomainRemeshStatus,
  MocSolverGeneratedAmbientClosedPostShockChainReference,
  MocSourceStripContinuationStatus,
  MocTerminalReflectionPatchAmbientClosureChainReference,
  assemble_terminal_trace_centerline_patch,
  build_reflected_domain_mixed_regime_boundary_request,
  build_reflected_domain_coupled_euler_free_boundary_request,
  build_reflected_domain_remesh_request_from_outer_source,
  inverse_prandtl_meyer_angle_rad,
  plan_reflected_domain_remesh_ambient_closed_chain,
  plan_reflected_domain_alternating_source_chain,
  plan_reflected_domain_alternating_source_chain_from_physical_field,
  plan_reflected_domain_alternating_source_chain_sequence,
  plan_reflected_domain_solver_owned_first_cell_chain,
  plan_reflected_domain_global_shock_remesh_chain,
  plan_reflected_domain_global_shock_remesh_chain_from_physical_field,
  plan_reflected_domain_global_euler_continued_chain_reference,
  plan_reflected_domain_global_euler_continued_chain,
  plan_reflected_domain_remesh_shock_chain,
  plan_reflected_domain_remesh_shock_chain_sequence,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_reflected_domain_remesh,
  solve_reflected_domain_alternating_source,
  solve_reflected_domain_alternating_physical_field,
  solve_reflected_domain_solver_owned_first_cell,
  solve_reflected_domain_global_shock_remesh,
  solve_reflected_domain_global_euler_shock_boundary,
  solve_reflected_domain_global_physical_closure,
  solve_reflected_domain_global_coupled_downstream,
  build_reflected_domain_global_coupled_downstream_boundary_pressure_profile,
  build_reflected_domain_global_coupled_downstream_feedback_geometry_profile,
  build_reflected_domain_global_coupled_downstream_feedback_pressure_profile,
  measure_reflected_domain_global_coupled_downstream_boundary_response,
  solve_reflected_domain_coupled_euler_free_boundary,
  solve_reflected_domain_coupled_euler_free_boundary_from_mixed_regime_request,
  assess_reflected_domain_coupled_euler_subsonic_pressure_budget,
  assess_reflected_domain_coupled_euler_pressure_profile_compatibility,
  assess_reflected_domain_coupled_euler_transonic_transition,
  assess_reflected_domain_coupled_euler_control_section_compatibility,
  assess_reflected_domain_coupled_euler_transonic_frontier_compatibility,
  solve_reflected_domain_mixed_regime_boundary,
  fit_reflected_domain_production_shock_cell,
  build_moc_physical_field_continuation_profile,
  build_moc_physical_field_shock_front_condition,
  build_moc_transonic_shock_interface_profile_from_field,
  build_moc_transonic_shock_interface_profile_from_field_placement,
  moc_reflected_domain_global_physical_closure_fingerprint,
  solve_reflected_domain_outer_source_curve,
  solve_underexpanded_expansion_fan,
  solve_uniform_attached_shock_field,
)
from exhaust_plume.models.moc import solve_reflected_free_boundary
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.models.nozzle.exit_state import (
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.validation.moc_measurements import (
  MOC_PRODUCTION_SHOCK_CELL_FIT_OPERATOR_ID,
  MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase,
  MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus,
  MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus,
  MocReflectedDomainAlternatingSourceMeasurementStatus,
  MocReflectedDomainSolverOwnedFirstCellMeasurementStatus,
  MocReflectedDomainGlobalShockRemeshMeasurementStatus,
  MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus,
  MocReflectedDomainDownstreamBoundaryMeasurementStatus,
  MocReflectedDomainOuterSourceMeasurementStatus,
  MocReflectedDomainRemeshMeasurementStatus,
  MocShockCellMeasurementStatus,
  measure_moc_production_shock_cell_fit,
  measure_moc_reflected_domain_alternating_source,
  measure_moc_reflected_domain_alternating_physical_field_chain_refinement,
  measure_moc_reflected_domain_alternating_physical_field_chain,
  measure_moc_reflected_domain_alternating_physical_field,
  measure_moc_reflected_domain_solver_owned_first_cell,
  measure_moc_reflected_domain_global_shock_remesh,
  measure_moc_reflected_domain_global_euler_shock_boundary,
  measure_moc_reflected_domain_downstream_boundary,
  measure_moc_reflected_domain_outer_source_curve,
  measure_moc_reflected_domain_remesh,
)
from exhaust_plume.validation.moc_reflected_domain_mixed_regime import (
  MocReflectedDomainMixedRegimeBoundaryMeasurementStatus,
  MocReflectedDomainMixedRegimeBoundaryRefinementStatus,
  measure_reflected_domain_mixed_regime_boundary,
  measure_reflected_domain_mixed_regime_boundary_refinement,
  run_reflected_domain_mixed_regime_boundary_refinement,
)
from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus,
  measure_reflected_domain_coupled_euler_free_boundary,
)
from exhaust_plume.validation.moc_transonic_interface import (
  MocTransonicShockInterfaceFieldProfileAuditStatus,
  MocTransonicShockInterfaceFieldPlacementAuditStatus,
  MocTransonicShockInterfaceProfileAuditStatus,
  measure_moc_transonic_shock_interface_field_placement,
  measure_moc_transonic_shock_interface_profile_from_field,
  measure_moc_transonic_shock_interface_profile,
)
from exhaust_plume.validation.moc_field_continuation import (
  MocPhysicalFieldContinuationProfileAuditStatus,
  measure_moc_physical_field_continuation_profile,
)
from exhaust_plume.validation.moc_physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionAuditStatus,
  measure_moc_physical_field_shock_front_condition,
)
from exhaust_plume.validation.moc_coupled_euler_free_boundary_refinement import (
  MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus,
  measure_reflected_domain_coupled_euler_free_boundary_refinement,
  run_reflected_domain_coupled_euler_free_boundary_refinement,
)
from exhaust_plume.validation.moc_global_coupled_downstream_refinement import (
  MocReflectedDomainGlobalCoupledDownstreamRefinementStatus,
  run_reflected_domain_global_coupled_downstream_refinement,
)
from exhaust_plume.validation.moc_global_coupled_downstream_feedback import (
  MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus,
  run_reflected_domain_global_coupled_downstream_feedback,
)
from exhaust_plume.validation.moc_coupled_euler_pressure_continuation import (
  MocReflectedDomainCoupledEulerPressureContinuationStatus,
  measure_reflected_domain_coupled_euler_pressure_continuation,
  run_reflected_domain_coupled_euler_pressure_continuation,
)
from exhaust_plume.validation.moc_reflected_domain_refinement import (
  MocReflectedDomainGlobalEulerShockBoundaryCrossCase,
  MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus,
  MocReflectedDomainGlobalEulerShockBoundaryRefinementCase,
  MocReflectedDomainGlobalEulerShockBoundaryRefinementRun,
  MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus,
  measure_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement,
  measure_moc_reflected_domain_global_euler_shock_boundary_refinement,
  run_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement,
  run_moc_reflected_domain_global_euler_shock_boundary_refinement,
)


def _canonical_field():
  upstream = CharacteristicState(
    x_m=0.5,
    y_m=0.5,
    theta_rad=-0.2,
    mach=2.0,
    gamma=1.4,
  )
  shock = solve_marched_attached_shock_field(
    lambda point: replace(upstream, x_m=point[0], y_m=point[1]),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert shock.shock_fit is not None
  first = shock.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  result = solve_marched_attached_shock_with_ambient_centerline_physical_field(
    lambda point: replace(upstream, x_m=point[0], y_m=point[1]),
    lambda _point: 100000.0,
    (0.5, 0.5),
    ambient_pressure,
    0.02,
    0.12,
    sample_count=9,
  )
  assert result.field is not None
  assert result.field.physical_closure_verified
  return result.field
####


def _patch():
  field = _canonical_field()
  patch = assemble_terminal_trace_centerline_patch(
    field.as_open_shock_ambient_strip()
  )
  assert patch.converged
  return field, patch
####


def _request(*, declared_polarity=None, incoming_handoff=()):
  field, patch = _patch()
  anchor = patch.outgoing_trace_states[-1]
  total_pressure = patch.outgoing_trace_total_pressure_Pa[-1]
  centerline = []
  outer = []
  for index in range(6):
    k_plus = anchor.k_plus - 0.002 * index
    inversion = inverse_prandtl_meyer_angle_rad(-k_plus, anchor.gamma)
    assert inversion.value is not None
    axis_x = anchor.x_m + 0.015 * index
    axis_state = CharacteristicState(
      x_m=axis_x,
      y_m=0.0,
      theta_rad=0.0,
      mach=inversion.value,
      gamma=anchor.gamma,
    )
    theta = 0.06 - 0.004 * index
    outer_inversion = inverse_prandtl_meyer_angle_rad(
      theta - k_plus,
      anchor.gamma,
    )
    assert outer_inversion.value is not None
    outer_probe = CharacteristicState(
      x_m=axis_x,
      y_m=0.0,
      theta_rad=theta,
      mach=outer_inversion.value,
      gamma=anchor.gamma,
    )
    characteristic_angle = 0.5 * (
      axis_state.mu_rad
      + outer_probe.theta_rad
      + outer_probe.mu_rad
    )
    ordinate = 0.10 + 0.012 * index
    outer.append(
      CharacteristicState(
        x_m=axis_x + ordinate * cos(characteristic_angle) / sin(
          characteristic_angle
        ),
        y_m=ordinate,
        theta_rad=theta,
        mach=outer_inversion.value,
        gamma=anchor.gamma,
      )
    )
    centerline.append(axis_state)
  ####
  request = MocReflectedDomainRemeshRequest(
    reflection_patch=patch,
    centerline_source_states=tuple(centerline),
    outer_source_states=tuple(outer),
    total_pressure_Pa=total_pressure,
    incoming_handoff=tuple(incoming_handoff),
    declared_polarity=declared_polarity,
  )
  return field, patch, request
####


def _outer_source_fixture() -> tuple[NozzleExitState, AmbientState, object]:
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=2.0e6,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )
  fan = solve_underexpanded_expansion_fan(
    exit_state,
    ambient,
    characteristic_count=8,
  )
  reflected = solve_reflected_free_boundary(fan, exit_state, ambient)
  assert reflected.converged
  return exit_state, ambient, reflected
####


def _handoff(field):
  return tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      field.centerline_boundary_states,
      field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )
####


def _global_physical_closure_for_mixed_regime():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  return solve_reflected_domain_global_physical_closure(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )
####


def test_global_physical_field_binds_an_audited_profile_to_the_coupled_lane():
  closure = _global_physical_closure_for_mixed_regime()
  assert closure.global_euler is not None
  assert closure.global_euler.physical_field is not None
  assert closure.global_euler.physical_field.field is not None
  field = closure.global_euler.physical_field.field
  points = tuple(
    (5.5, ordinate)
    for ordinate in (
      0.0564,
      0.1027,
      0.1491,
      0.1955,
      0.2418,
      0.2882,
      0.3345,
      0.3809,
      0.4273,
      0.4736,
    )
  )
  bound = build_moc_transonic_shock_interface_profile_from_field(
    MocTransonicShockInterfaceFieldProfileRequest(
      field=field,
      sample_points_m=points,
      normal_alignment_tolerance_rad=0.03,
      profile_id='test-global-physical-field-x5.5',
    )
  )
  assert bound.status is (
    MocTransonicShockInterfaceFieldProfileStatus
    .CONVERGED_FIELD_BOUND_PROFILE
  )
  assert bound.converged
  assert bound.profile is not None
  assert bound.profile_build is not None
  assert bound.field_lineage_verified
  assert bound.field_sampling_verified
  assert bound.profile_build_verified
  audit = measure_moc_transonic_shock_interface_profile_from_field(bound)
  assert audit.status is MocTransonicShockInterfaceFieldProfileAuditStatus.VERIFIED
  assert audit.converged
  assert audit.field_lineage_verified
  assert audit.field_sampling_verified
  assert audit.profile_build_verified
  assert audit.maximum_state_residual == pytest.approx(0.0)
  assert audit.maximum_pressure_residual == pytest.approx(0.0)

  tampered = replace(
    bound,
    upstream_samples=(
      replace(bound.upstream_samples[0], mach=bound.upstream_samples[0].mach + 0.01),
      *bound.upstream_samples[1:],
    ),
  )
  tampered_audit = measure_moc_transonic_shock_interface_profile_from_field(
    tampered
  )
  assert not tampered_audit.converged
  assert not tampered_audit.field_sampling_verified

  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  coupled_request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=8,
    max_pseudo_iterations=400,
    max_shape_iterations=8,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE
    ),
    transonic_shock_interface_profile=bound.profile,
  )
  coupled = solve_reflected_domain_coupled_euler_free_boundary(coupled_request)
  assert coupled.status is not (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_PROFILE_FAILURE
  )
  assert coupled.conservative_states_by_cell
  assert coupled.transonic_shock_interface_profile_consumed
  # The interior profile starts a new field at its retained cross-section;
  # the first downstream boundary must preserve that exact handoff height
  # instead of reusing the upstream reference's unrelated outlet height.
  assert coupled.free_boundary_points_m
  assert coupled.free_boundary_points_m[0][1] == pytest.approx(
    bound.profile.upper_ordinate_m
  )
  assert coupled.free_boundary_points_m[1][1] >= (
    bound.profile.upper_ordinate_m - 1.0e-12
  )
  assert coupled.production_claim_allowed is False
####


def test_global_physical_field_uses_solver_owned_cross_section_placement():
  closure = _global_physical_closure_for_mixed_regime()
  assert closure.global_euler is not None
  assert closure.global_euler.physical_field is not None
  assert closure.global_euler.physical_field.field is not None
  field = closure.global_euler.physical_field.field
  placement = build_moc_transonic_shock_interface_profile_from_field_placement(
    MocTransonicShockInterfaceFieldPlacementRequest(field=field)
  )
  assert placement.status is (
    MocTransonicShockInterfaceFieldPlacementStatus
    .CONVERGED_SOLVER_PLACEMENT
  )
  assert placement.converged
  assert placement.profile is not None
  assert placement.cross_section_x_m is not None
  assert placement.lower_ordinate_m is not None
  assert placement.upper_ordinate_m is not None
  assert len(placement.sample_points_m) == 10
  assert placement.profile.cross_section_x_m == pytest.approx(
    placement.cross_section_x_m
  )
  assert placement.profile.lower_ordinate_m == pytest.approx(
    placement.lower_ordinate_m
  )
  assert placement.profile.upper_ordinate_m == pytest.approx(
    placement.upper_ordinate_m
  )
  audit = measure_moc_transonic_shock_interface_field_placement(placement)
  assert audit.status is MocTransonicShockInterfaceFieldPlacementAuditStatus.VERIFIED
  assert audit.converged
  assert audit.rederived
  assert audit.selected_candidate_verified
  assert audit.cross_section_verified
  assert audit.profile_verified
  assert not audit.full_field_cross_section_verified
  assert audit.maximum_sample_point_residual_m == pytest.approx(0.0)

  full_span_placement = build_moc_transonic_shock_interface_profile_from_field_placement(
    MocTransonicShockInterfaceFieldPlacementRequest(
      field=field,
      boundary_margin_fraction=0.0,
    )
  )
  assert full_span_placement.converged
  assert full_span_placement.lower_ordinate_m == pytest.approx(0.0)
  full_span_audit = measure_moc_transonic_shock_interface_field_placement(
    full_span_placement
  )
  assert full_span_audit.converged
  assert full_span_audit.full_field_cross_section_verified

  interior_request = build_reflected_domain_coupled_euler_free_boundary_request(
    build_reflected_domain_mixed_regime_boundary_request(closure),
    reference_total_temperature_K=1500.0,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
    ),
    transonic_shock_interface_field_placement=placement,
  )
  interior_coupled = solve_reflected_domain_coupled_euler_free_boundary(
    interior_request
  )
  assert interior_coupled.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_PLACEMENT_FAILURE
  )

  tampered = replace(
    full_span_placement,
    cross_section_x_m=full_span_placement.cross_section_x_m + 1.0e-3,
  )
  tampered_audit = measure_moc_transonic_shock_interface_field_placement(
    tampered
  )
  assert not tampered_audit.converged
  assert not tampered_audit.cross_section_verified

  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  tampered_request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
    ),
    transonic_shock_interface_field_placement=tampered,
  )
  tampered_coupled = solve_reflected_domain_coupled_euler_free_boundary(
    tampered_request
  )
  assert tampered_coupled.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_PLACEMENT_FAILURE
  )

  coupled_request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=8,
    max_pseudo_iterations=400,
    max_shape_iterations=8,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
    ),
    transonic_shock_interface_field_placement=full_span_placement,
  )
  coupled = solve_reflected_domain_coupled_euler_free_boundary(coupled_request)
  assert coupled.status is not (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_PLACEMENT_FAILURE
  )
  assert coupled.conservative_states_by_cell
  assert coupled.transonic_shock_interface_field_placement_consumed
  assert coupled.transonic_shock_interface_profile_consumed
  assert coupled.production_claim_allowed is False
####


def test_global_physical_field_continuation_preserves_oblique_post_shock_regime():
  closure = _global_physical_closure_for_mixed_regime()
  assert closure.global_euler is not None
  assert closure.global_euler.physical_field is not None
  assert closure.global_euler.physical_field.field is not None
  field = closure.global_euler.physical_field.field
  placement = build_moc_transonic_shock_interface_profile_from_field_placement(
    MocTransonicShockInterfaceFieldPlacementRequest(
      field=field,
      boundary_margin_fraction=0.0,
    )
  )
  assert placement.converged
  continuation = build_moc_physical_field_continuation_profile(
    MocPhysicalFieldContinuationProfileRequest(
      field=field,
      sample_points_m=placement.sample_points_m,
    )
  )

  assert continuation.status is (
    MocPhysicalFieldContinuationProfileStatus
    .CONVERGED_FIELD_CONTINUATION_PROFILE
  )
  assert continuation.converged
  assert continuation.profile is not None
  assert continuation.field_lineage_verified
  assert continuation.field_sampling_verified
  assert all(sample.mach > 1.0 for sample in continuation.profile.samples)
  assert continuation.profile.samples[-1].static_pressure_Pa == pytest.approx(
    field.ambient_boundary.ambient_pressure_Pa,
    rel=2.0e-3,
  )
  audit = measure_moc_physical_field_continuation_profile(continuation)
  assert audit.status is MocPhysicalFieldContinuationProfileAuditStatus.VERIFIED
  assert audit.converged
  assert audit.rederived
  assert audit.field_lineage_verified
  assert audit.field_sampling_verified
  assert audit.maximum_state_residual == pytest.approx(0.0)
  assert audit.maximum_total_pressure_residual_Pa == pytest.approx(0.0)
  assert continuation.physical_closure_verified is False
  assert continuation.chain_promotion_blocked
  assert continuation.production_claim_allowed is False

  normal_shock = build_moc_transonic_shock_interface_profile_from_field_placement(
    MocTransonicShockInterfaceFieldPlacementRequest(
      field=field,
      boundary_margin_fraction=0.0,
    )
  )
  assert normal_shock.profile is not None
  assert normal_shock.profile.downstream_samples[0].mach < 1.0
  assert continuation.profile.samples[0].mach > 1.0
  outside = build_moc_physical_field_continuation_profile(
    MocPhysicalFieldContinuationProfileRequest(
      field=field,
      sample_points_m=(
        (placement.cross_section_x_m, placement.lower_ordinate_m - 0.01),
        (placement.cross_section_x_m, placement.lower_ordinate_m + 0.01),
      ),
    )
  )
  assert outside.status is (
    MocPhysicalFieldContinuationProfileStatus.FIELD_SAMPLE_FAILURE
  )
  assert outside.converged is False
  tampered_profile = replace(
    continuation.profile,
    samples=(
      replace(
        continuation.profile.samples[0],
        mach=continuation.profile.samples[0].mach + 0.01,
      ),
      *continuation.profile.samples[1:],
    ),
  )
  tampered = replace(continuation, profile=tampered_profile)
  tampered_audit = measure_moc_physical_field_continuation_profile(tampered)
  assert tampered_audit.status is (
    MocPhysicalFieldContinuationProfileAuditStatus.RESULT_FAILURE
  )
  assert not tampered_audit.converged
  assert not tampered_audit.rederived

  front_condition = build_moc_physical_field_shock_front_condition(
    MocPhysicalFieldShockFrontConditionRequest(
      continuation_profile=continuation,
      condition_id='test-global-physical-field-shock-front',
    )
  )
  assert front_condition.status is (
    MocPhysicalFieldShockFrontConditionStatus
    .CONVERGED_SHOCK_FRONT_CONDITION
  )
  assert front_condition.converged
  assert front_condition.shock_front_verified
  assert front_condition.ambient_neighbor_verified
  assert front_condition.centerline_neighbor_verified
  assert front_condition.continuation_section_verified
  assert front_condition.coupled_inlet_profile is not None
  assert front_condition.coupled_inlet_profile_verified
  assert front_condition.coupled_inlet_profile.lower_ordinate_m == pytest.approx(
    0.0
  )
  assert front_condition.coupled_inlet_profile.upper_ordinate_m >= (
    continuation.profile.upper_ordinate_m
  )
  assert front_condition.coupled_inlet_profile.upper_ordinate_m > 0.5
  front_audit = measure_moc_physical_field_shock_front_condition(
    front_condition
  )
  assert front_audit.status is (
    MocPhysicalFieldShockFrontConditionAuditStatus.VERIFIED
  )
  assert front_audit.converged
  assert front_audit.rederived
  assert front_audit.field_lineage_verified
  assert front_audit.shock_front_verified
  assert front_audit.ambient_neighbor_verified
  assert front_audit.centerline_neighbor_verified
  assert front_audit.continuation_section_verified
  assert front_audit.coupled_inlet_profile_verified
  assert front_audit.maximum_point_residual_m == pytest.approx(0.0)
  assert front_audit.maximum_coupled_inlet_profile_residual_m == pytest.approx(
    0.0
  )
  tampered_front = replace(
    front_condition,
    shock_front_points_m=(
      (front_condition.shock_front_points_m[0][0] + 1.0e-3,
       front_condition.shock_front_points_m[0][1]),
      *front_condition.shock_front_points_m[1:],
    ),
  )
  tampered_front_audit = measure_moc_physical_field_shock_front_condition(
    tampered_front
  )
  assert tampered_front_audit.status is (
    MocPhysicalFieldShockFrontConditionAuditStatus.RESULT_FAILURE
  )
  assert not tampered_front_audit.converged
  assert not tampered_front_audit.shock_front_verified
  tampered_inlet_profile = replace(
    front_condition.coupled_inlet_profile,
    samples=(
      *front_condition.coupled_inlet_profile.samples[:-1],
      replace(
        front_condition.coupled_inlet_profile.samples[-1],
        mach=front_condition.coupled_inlet_profile.samples[-1].mach + 0.01,
      ),
    ),
  )
  tampered_inlet = replace(
    front_condition,
    coupled_inlet_profile=tampered_inlet_profile,
  )
  tampered_inlet_audit = measure_moc_physical_field_shock_front_condition(
    tampered_inlet
  )
  assert not tampered_inlet_audit.converged
  assert not tampered_inlet_audit.coupled_inlet_profile_verified

  interior_placement = build_moc_transonic_shock_interface_profile_from_field_placement(
    MocTransonicShockInterfaceFieldPlacementRequest(
      field=field,
      boundary_margin_fraction=0.1,
    )
  )
  assert interior_placement.converged
  interior_continuation = build_moc_physical_field_continuation_profile(
    MocPhysicalFieldContinuationProfileRequest(
      field=field,
      sample_points_m=interior_placement.sample_points_m,
    )
  )
  assert interior_continuation.converged
  assert interior_continuation.profile is not None
  interior_front_condition = build_moc_physical_field_shock_front_condition(
    MocPhysicalFieldShockFrontConditionRequest(
      continuation_profile=interior_continuation,
      condition_id='test-global-physical-field-interior-shock-front',
    )
  )
  assert interior_front_condition.converged
  assert interior_front_condition.coupled_inlet_profile is not None
  assert interior_front_condition.coupled_inlet_profile.upper_ordinate_m > (
    interior_continuation.profile.upper_ordinate_m
  )

  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  coupled_request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=8,
    max_pseudo_iterations=40,
    max_shape_iterations=2,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
    ),
    physical_field_continuation_profile=interior_continuation,
    physical_field_shock_front_condition=interior_front_condition,
  )
  coupled = solve_reflected_domain_coupled_euler_free_boundary(coupled_request)
  assert coupled.status is not (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_PHYSICAL_FIELD_CONTINUATION_FAILURE
  )
  assert coupled.x_stations_m[0] == pytest.approx(
    interior_continuation.profile.cross_section_x_m
  )
  assert coupled.free_boundary_points_m[0][1] == pytest.approx(
    interior_front_condition.coupled_inlet_profile.upper_ordinate_m
  )
  assert coupled.physical_field_continuation_profile_consumed
  assert coupled.physical_field_continuation_profile == interior_continuation
  assert coupled.inlet_boundary_states_consumed
  assert len(coupled.inlet_boundary_conservative_states_by_face) == 8
  assert coupled.transonic_shock_interface_profile is None
  assert coupled.production_claim_allowed is False
  coupled_audit = measure_reflected_domain_coupled_euler_free_boundary(coupled)
  assert coupled_audit.physical_field_continuation_profile_verified
  assert coupled_audit.physical_field_inlet_seam_verified
  assert coupled_audit.chain_promotion_blocked
  assert coupled_audit.production_claim_allowed is False
  tampered_inlet = replace(
    coupled,
    inlet_boundary_conservative_states_by_face=(
      (
        coupled.inlet_boundary_conservative_states_by_face[0][0] + 0.01,
        *coupled.inlet_boundary_conservative_states_by_face[0][1:],
      ),
      *coupled.inlet_boundary_conservative_states_by_face[1:],
    ),
  )
  tampered_inlet_audit = measure_reflected_domain_coupled_euler_free_boundary(
    tampered_inlet
  )
  assert tampered_inlet_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
    .PHYSICAL_FIELD_INLET_SEAM_FAILURE
  )
  assert not tampered_inlet_audit.physical_field_inlet_seam_verified
  exact_downstream = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=8,
    max_pseudo_iterations=40,
    max_shape_iterations=2,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
    ),
    physical_field_continuation_profile=interior_continuation,
    physical_field_shock_front_condition=interior_front_condition,
  )
  assert exact_downstream.closure_lineage_verified
  assert exact_downstream.global_coupling_verified is False
  assert exact_downstream.coupled_field is not None
  assert exact_downstream.coupled_field.request is not None
  assert exact_downstream.coupled_field.request.inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  )
  assert exact_downstream.coupled_field.request.physical_field_continuation_profile == (
    interior_continuation
  )
  assert exact_downstream.coupled_field.status is not (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE
  )
####


def _alternating_physical_chain_results(seed, sample_count):
  current = seed
  results = []
  for _ in range(2):
    strip = current.as_open_shock_ambient_strip(
      trace_position_tolerance_m=3.0e-3,
      trace_forward_tolerance_m=1.0e-4,
    )
    patch = assemble_terminal_trace_centerline_patch(
      strip,
      trace_position_tolerance_m=3.0e-3,
      trace_forward_tolerance_m=1.0e-4,
    )
    assert patch.converged
    ambient_pressure = current.ambient_boundary.ambient_pressure_Pa
    assert ambient_pressure is not None
    handoff = _handoff(current)
    source = solve_reflected_domain_alternating_source(
      patch,
      ambient_pressure,
      incoming_handoff=handoff,
    )
    assert source.converged
    result = solve_reflected_domain_alternating_physical_field(
      source,
      compression_amplitude_rad=0.05,
      use_outer_seed_attachment=True,
      sample_count=sample_count,
      shock_angle_tolerance_rad=0.02,
      incoming_handoff=handoff,
    )
    assert result.converged
    assert result.field is not None
    results.append(result)
    current = result.field
  ####
  return tuple(results)
####


def _reference_seed_field():
  result = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert result.field is not None
  return result.field
####


def test_reflected_domain_remesh_uses_a_new_outer_curve_after_the_single_c_minus_front():
  _field, patch, request = _request()

  result = solve_reflected_domain_remesh(request)

  assert result.status is MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD
  assert result.converged
  assert result.state_sampling_available
  assert result.incoming_trace_validation is not None
  assert result.incoming_trace_validation.converged
  assert result.incoming_trace_polarity is not None
  assert result.incoming_trace_polarity.converged
  assert result.reflection_seam_verified
  assert result.centerline_source_verified
  assert result.outer_source_verified
  assert result.source_field_verified
  assert result.source_strip is not None
  assert result.source_strip.topology.forms_closed_zone
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  continuation = result.as_source_continuation()
  assert continuation.status is MocSourceStripContinuationStatus.CONVERGED_EXTENDED
  assert continuation.strip is result.source_strip
  report = result.as_report()
  assert report['request']['incoming_trace_reused_as_outer_source'] is False
  assert report['request']['outer_source_is_new_curve'] is True
  assert report['request']['incoming_trace_family'] == 'C-'
  assert report['request']['centerline_source_family'] == 'C+'
  assert report['chain_termination_decision']['reason'] == (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE.value
  )
  assert patch.outgoing_trace_states[-1].y_m == pytest.approx(0.0)
####


def test_reflected_domain_remesh_rejects_reusing_the_single_c_minus_front_as_a_curve():
  _field, patch, request = _request()
  reused = patch.outgoing_trace_states[:6]
  changed = replace(
    request,
    outer_source_states=reused,
    centerline_source_states=request.centerline_source_states,
  )

  result = solve_reflected_domain_remesh(changed)

  assert result.status is MocReflectedDomainRemeshStatus.OUTER_SOURCE_FAILURE
  assert result.state_sampling_available is False
  assert 'single C- front cannot be reused' in result.message
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  )
####


def test_reflected_domain_remesh_measurement_rechecks_raw_bounded_field_data():
  _field, _patch, request = _request()
  remesh = solve_reflected_domain_remesh(request)
  assert remesh.converged

  tampered = replace(
    remesh,
    reflection_seam_verified=False,
    centerline_source_verified=False,
    outer_source_verified=False,
    source_field_verified=False,
  )
  measurement = measure_moc_reflected_domain_remesh(tampered)

  assert measurement.status is MocReflectedDomainRemeshMeasurementStatus.CONVERGED
  assert measurement.bounded_remesh_verified
  assert measurement.incoming_trace_verified
  assert measurement.polarity_verified
  assert measurement.reflection_seam_verified
  assert measurement.centerline_source_verified
  assert measurement.outer_source_verified
  assert measurement.total_pressure_verified
  assert measurement.source_topology_verified
  assert measurement.source_sampling_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
####


def test_reflected_domain_remesh_measurement_preserves_single_front_rejection():
  _field, patch, request = _request()
  reused = solve_reflected_domain_remesh(
    replace(
      request,
      outer_source_states=patch.outgoing_trace_states[:6],
    )
  )

  measurement = measure_moc_reflected_domain_remesh(reused)

  assert measurement.status is MocReflectedDomainRemeshMeasurementStatus.SOURCE_FAILURE
  assert measurement.converged is False
  assert measurement.outer_source_verified is False
  assert measurement.bounded_remesh_verified is False
####


def test_reflected_domain_remesh_rejects_a_wrong_reflection_anchor():
  _field, _patch, request = _request()
  changed_centerline = (
    replace(request.centerline_source_states[0], x_m=1.0),
    *request.centerline_source_states[1:],
  )

  result = solve_reflected_domain_remesh(
    replace(request, centerline_source_states=changed_centerline)
  )

  assert result.status is MocReflectedDomainRemeshStatus.REFLECTION_SEAM_FAILURE
  assert result.reflection_seam_verified is False
  assert result.chain_promotion_blocked
####


def test_reflected_domain_remesh_records_observed_polarity_without_promoting_it():
  _field, _patch, first = _request()
  observed = solve_reflected_domain_remesh(first).incoming_trace_polarity
  assert observed is not None
  _field, _patch, request = _request(declared_polarity=observed.status)

  result = solve_reflected_domain_remesh(request)

  assert result.converged
  assert result.incoming_trace_polarity is not None
  assert result.incoming_trace_polarity.status is observed.status
  assert result.as_report()['request']['declared_polarity'] == observed.status.value
####


def test_reflected_domain_remesh_exposes_a_bounded_physical_solver_source():
  _field, _patch, request = _request()
  remesh = solve_reflected_domain_remesh(request)

  source = MocBoundedUpstreamFieldSource.from_reflected_domain_remesh(remesh)

  assert source.model == 'bounded-reflected-domain-cauchy-remesh'
  assert source.preferred_start_point_m == pytest.approx(
    (
      request.outer_source_states[0].x_m,
      request.outer_source_states[0].y_m,
    )
  )
  assert source.domain_x_extent_m is not None
  assert source.domain_y_extent_m is not None
  start = source.preferred_start_point_m
  assert start is not None
  state = source.state_at(start)
  pressure = source.static_pressure_at(start)
  assert state is not None
  assert state.x_m == pytest.approx(start[0])
  assert state.y_m == pytest.approx(start[1])
  assert pressure is not None
  assert pressure > 0.0
  assert source.state_at(
    (
      source.domain_x_extent_m[1] + 0.1,
      source.domain_y_extent_m[1] + 0.1,
    )
  ) is None
  report = source.as_report()
  assert report['extrapolation_allowed'] is False
  assert report['upstream_coupling_verified'] is False
####


def test_reflected_domain_remesh_carries_source_family_total_pressure():
  _field, _patch, request = _request()
  total_pressure = request.total_pressure_Pa
  centerline_pressures = tuple(
    total_pressure * (1.0 - 0.002 * index)
    for index in range(len(request.centerline_source_states))
  )
  outer_pressures = tuple(
    total_pressure * (0.99 - 0.0015 * index)
    for index in range(len(request.outer_source_states))
  )
  variable_request = replace(
    request,
    centerline_total_pressure_Pa=centerline_pressures,
    outer_total_pressure_Pa=outer_pressures,
  )

  result = solve_reflected_domain_remesh(variable_request)

  assert result.converged
  assert result.source_strip is not None
  assert variable_request.variable_total_pressure
  assert result.source_strip.total_pressure_model == 'source-family-carried-total-pressure'
  assert result.source_strip.total_pressure_at(
    (
      variable_request.outer_source_states[3].x_m,
      variable_request.outer_source_states[3].y_m,
    )
  ) == pytest.approx(outer_pressures[3])
  assert all(
    node.total_pressure_Pa == pytest.approx(
      outer_pressures[node.boundary_index]
    )
    for node in result.source_strip.nodes
  )
  report = result.as_report()
  assert report['request']['variable_total_pressure'] is True
  assert report['request']['nonuniform_entropy_data_carried'] is True
  assert report['request']['nonuniform_entropy_remesh_solved'] is False
  assert report['physical_closure_verified'] is False
  measurement = measure_moc_reflected_domain_remesh(result)
  assert measurement.converged
  assert measurement.total_pressure_verified
  assert measurement.source_sampling_verified
  assert measurement.production_claim_allowed is False
####


def test_reflected_domain_outer_source_curve_is_solved_and_assembled():
  exit_state, ambient, reflected = _outer_source_fixture()

  result = solve_reflected_domain_outer_source_curve(
    reflected.centerline_states,
    reflected.boundary_states[0],
    ambient.pressure_Pa,
    exit_state.total_pressure_Pa,
  )

  assert result.status is MocReflectedDomainOuterSourceStatus.CONVERGED
  assert result.converged
  assert result.outer_source_curve_verified
  assert result.source_field_verified
  assert result.source_strip is not None
  assert result.source_strip.total_pressure_model == (
    'uniform-isentropic-source-strip'
  )
  assert len(result.point_results) == len(reflected.centerline_states) - 1
  assert all(point.converged for point in result.point_results)
  assert result.ambient_boundary is not None
  assert result.ambient_boundary.converged
  assert tuple(result.outer_source_states[1:]) == pytest.approx(
    reflected.boundary_states[1:]
  )
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  report = result.as_report()
  assert report['source_model'] == (
    'solver-owned-ambient-pressure-outer-source-march'
  )
  assert report['outer_source_curve_verified'] is True
  assert report['source_field_verified'] is True
  assert report['physical_closure_verified'] is False
  measurement = measure_moc_reflected_domain_outer_source_curve(result)
  assert measurement.status is MocReflectedDomainOuterSourceMeasurementStatus.CONVERGED
  assert measurement.bounded_source_verified
  assert measurement.ambient_boundary_verified
  assert measurement.source_sampling_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
####


def test_reflected_domain_alternating_source_band_closes_local_neighbor_seams():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None

  result = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )

  assert result.status is MocReflectedDomainAlternatingSourceStatus.CONVERGED
  assert result.converged
  assert result.source_field_verified
  assert result.reflection_anchor_verified
  assert result.alternating_seam_verified
  assert len(result.centerline_source_states) == 6
  assert len(result.outer_source_states) == 6
  assert len(result.centerline_results) == 6
  assert len(result.point_results) == 6
  assert all(item.converged for item in result.centerline_results)
  assert all(item.converged for item in result.point_results)
  assert result.node_count == 12
  assert result.cell_count == 10
  assert result.topology is not None
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.centerline_source_states[0] == pytest.approx(
    patch.outgoing_trace_states[-1]
  )
  assert result.outer_seed_state == patch.outgoing_trace_states[0]
  assert result.outer_source_states[0].x_m > result.centerline_source_states[0].x_m
  sample = result.state_at((2.2, 0.1))
  assert sample is not None
  assert result.total_pressure_at((2.2, 0.1)) == pytest.approx(
    patch.outgoing_trace_total_pressure_Pa[0]
  )
  assert result.state_at((1.0, -0.1)) is None
  report = result.as_report()
  assert report['source_model'] == (
    'solver-owned-alternating-family-ambient-pressure-remesh'
  )
  assert report['canonical_alternating_remesh_solved'] is False
  assert report['physical_closure_verified'] is False
  assert report['chain_promotion_blocked'] is True
  assert report['production_claim_allowed'] is False
  measurement = measure_moc_reflected_domain_alternating_source(result)
  assert measurement.status is (
    MocReflectedDomainAlternatingSourceMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.bounded_source_verified
  assert measurement.incoming_trace_verified
  assert measurement.reflection_anchor_verified
  assert measurement.centerline_recomputed_verified
  assert measurement.boundary_recomputed_verified
  assert measurement.alternating_seam_verified
  assert measurement.source_topology_verified
  assert measurement.source_sampling_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked is True
  assert measurement.production_claim_allowed is False
####


def test_reflected_domain_alternating_source_measurement_rejects_changed_raw_row():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  result = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  corrupted = replace(
    result,
    outer_source_states=(
      replace(result.outer_source_states[0], y_m=0.45),
      *result.outer_source_states[1:],
    ),
  )

  measurement = measure_moc_reflected_domain_alternating_source(corrupted)

  assert measurement.converged is False
  assert measurement.bounded_source_verified is False
  assert measurement.boundary_recomputed_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked is True
####


def test_reflected_domain_alternating_source_couples_to_physical_shock_field():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )

  result = solve_reflected_domain_alternating_physical_field(
    source,
    compression_amplitude_rad=0.05,
  )

  assert result.status is (
    MocReflectedDomainAlternatingPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
  )
  assert result.converged
  assert result.source_field_verified
  assert result.shock_curve_verified
  assert result.physical_closure_verified
  assert result.state_sampling_available
  assert result.upstream_coupling_verified
  assert result.chain_promotion_blocked is False
  assert result.production_claim_allowed is False
  assert result.field is not None
  assert result.field.shock_boundary_points_m[0][0] == pytest.approx(
    source.outer_source_states[0].x_m,
  )
  assert result.field.shock_boundary_points_m[0][1] == pytest.approx(
    source.outer_source_states[0].y_m,
  )
  assert result.field.shock_boundary_points_m[-1][1] == pytest.approx(0.0)
  assert result.field.physical_closure_verified
  report = result.as_report()
  assert report['continuation_law'] == (
    'alternating-source-local-compression-envelope'
  )
  assert report['canonical_reflected_domain_closed'] is False
  assert report['production_claim_allowed'] is False

  measurement = measure_moc_reflected_domain_alternating_physical_field(result)

  assert measurement.converged
  assert measurement.source_field_verified
  assert measurement.attachment_point_verified
  assert measurement.attachment_pressure_verified
  assert measurement.zero_strength_attachment_verified
  assert measurement.envelope_verified
  assert measurement.shock_curve_verified
  assert measurement.physical_field_verified
  assert measurement.state_sampling_verified
  assert measurement.upstream_coupling_verified
  assert measurement.incoming_handoff_verified
  assert measurement.bounded_physical_field_verified
  assert measurement.physical_closure_verified
  assert measurement.chain_promotion_blocked is True
  assert measurement.production_claim_allowed is False
####


def test_reflected_domain_alternating_physical_field_can_attach_at_retained_outer_seed():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )

  result = solve_reflected_domain_alternating_physical_field(
    source,
    compression_amplitude_rad=0.05,
    use_outer_seed_attachment=True,
    use_trace_referenced_profile=True,
  )

  assert result.status is (
    MocReflectedDomainAlternatingPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
  )
  assert result.converged
  assert result.field is not None
  assert result.start_point_m == pytest.approx(
    (source.outer_seed_state.x_m, source.outer_seed_state.y_m),
  )
  assert result.field.shock_boundary_points_m[0] == pytest.approx(
    result.start_point_m,
  )
  assert result.as_report()['attachment_source'] == (
    'outer-seed-reflection-interface'
  )
  assert result.as_report()['use_trace_referenced_profile'] is True
  assert result.continuation_law == (
    'reflected-trace-referenced-compression-envelope'
  )
  measurement = measure_moc_reflected_domain_alternating_physical_field(result)
  assert measurement.converged
  assert measurement.attachment_point_verified
  assert measurement.upstream_coupling_verified
####


def test_reflected_domain_alternating_source_chain_projects_fresh_bands_automatically():
  seed = _canonical_field()

  planner = plan_reflected_domain_alternating_source_chain_from_physical_field(
    seed,
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 4
  assert planner.chain.termination_reason is MocChainTerminationReason.MAX_CELL_LIMIT
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['source_derivation_automatic'] is True
  assert planner.diagnostics['use_outer_seed_attachment'] is True
  assert planner.diagnostics[
    'alternating_physical_field_chain_audit_accepted'
  ] is True
  assert planner.diagnostics['alternating_physical_field_chain_audit']['checks'] == {
    'source_geometry_freshness_verified': True,
    'handoff_links_verified': True,
    'fresh_domain_verified': True,
    'physical_closure_verified': True,
  }
  attempts = planner.diagnostics['alternating_source_attempts']
  assert len(attempts) == 3
  assert all(
    attempt['incoming_handoff_verified'] is True
    and attempt['fresh_source_band'] is True
    and attempt['fresh_source_geometry'] is True
    for attempt in attempts
  )
####


def test_reflected_domain_alternating_source_chain_one_cell_prefix_skips_source_projection():
  seed = _canonical_field()

  planner = plan_reflected_domain_alternating_source_chain_from_physical_field(
    seed,
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    total_cell_count=1,
    policy=MocChainContinuationPolicy(max_cells=1, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.chain.physical_termination is False
  assert planner.diagnostics['configured_total_cell_count'] == 1
  assert planner.diagnostics['alternating_source_initial_band'] is None
  assert planner.diagnostics['alternating_source_attempt_count'] == 0
  assert planner.diagnostics['alternating_source_attempts'] == []
  assert planner.production_claim_allowed is False
####


def test_solver_owned_first_cell_retains_auditable_no_bracket_without_geometry():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_solver_owned_first_cell(
    source,
    outer_source_index=2,
    target_centerline_index=3,
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    sample_count=9,
  )

  assert result.status is (
    MocReflectedDomainSolverOwnedFirstCellStatus.BOUNDARY_BRACKET_FAILURE
  )
  assert result.converged is False
  assert len(result.trials) == 2
  assert all(trial.physical_field is not None for trial in result.trials)
  assert all(trial.converged for trial in result.trials)
  assert result.selected_physical_field is not None
  assert result.local_physical_field_verified
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False

  measurement = measure_moc_reflected_domain_solver_owned_first_cell(result)

  assert measurement.status is (
    MocReflectedDomainSolverOwnedFirstCellMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.target_centerline_verified
  assert measurement.amplitude_bracket_verified
  assert measurement.trial_amplitudes_verified
  assert measurement.trial_residuals_verified
  assert measurement.selected_trial_verified
  assert measurement.selected_field_verified
  assert measurement.scalar_endpoint_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.canonical_free_boundary_verified is False
  assert measurement.canonical_euler_verified is False
  assert measurement.external_validation_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert measurement.fidelity_isolation_verified

  invalid = solve_reflected_domain_solver_owned_first_cell(
    source,
    compression_amplitude_lower_rad=float('nan'),
    compression_amplitude_upper_rad=0.03,
  )
  assert invalid.status is MocReflectedDomainSolverOwnedFirstCellStatus.INVALID_INPUT
  assert invalid.compression_amplitude_bracket is None
####


def test_solver_owned_first_cell_can_scan_only_inside_declared_bracket():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_solver_owned_first_cell(
    source,
    outer_source_index=2,
    target_centerline_index=3,
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    sample_count=9,
    maximum_bracket_scan_samples=3,
  )

  assert result.status is (
    MocReflectedDomainSolverOwnedFirstCellStatus.BOUNDARY_BRACKET_FAILURE
  )
  assert result.bracket_scan_sample_count == 3
  assert len(result.trials) == 5
  assert all(
    0.007 <= trial.compression_amplitude_rad <= 0.03
    for trial in result.trials
  )
  measurement = measure_moc_reflected_domain_solver_owned_first_cell(result)
  assert measurement.converged
  assert measurement.trial_amplitudes_verified
  assert measurement.trial_residuals_verified
  assert measurement.fidelity_isolation_verified
####


def test_solver_owned_first_cell_planner_preserves_typed_research_stop():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  handoff = _handoff(field)
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=handoff,
  )
  planner = plan_reflected_domain_solver_owned_first_cell_chain(
    field,
    source,
    start_x_m=0.5,
    end_x_m=1.0,
    outer_source_index=2,
    target_centerline_index=3,
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )
  assert planner.chain.physical_termination is False
  assert planner.handoff_links_verified is None
  assert planner.diagnostics[
    'solver_owned_first_cell_seed_handoff_verified'
  ] is True
  assert planner.diagnostics['solver_owned_first_cell_audit_accepted'] is True
  assert planner.diagnostics['solver_owned_first_cell']['status'] == (
    'solver_owned_first_cell_boundary_bracket_failure'
  )
  assert planner.diagnostics[
    'solver_owned_first_cell_independent_measurement'
  ]['status'] == 'converged'
  assert planner.production_claim_allowed is False
####


def test_solver_owned_first_cell_planner_rejects_mismatched_seed_handoff():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  planner = plan_reflected_domain_solver_owned_first_cell_chain(
    field,
    source,
    start_x_m=0.5,
    end_x_m=1.0,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.STATE_NOT_CARRIED
  )
  assert planner.diagnostics[
    'solver_owned_first_cell_seed_handoff_verified'
  ] is False
  assert planner.diagnostics['solver_owned_first_cell'] is None
  assert planner.diagnostics[
    'solver_owned_first_cell_independent_measurement'
  ] is None
####


def test_global_reflected_shock_remesh_retains_bounded_profile_sweep_without_closure():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )

  assert result.status is MocReflectedDomainGlobalShockRemeshStatus.NO_ENDPOINT_CLOSURE
  assert result.attempt_count == 2
  assert result.selected_attempt_index is not None
  assert result.selected_residual_m is not None
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )

  measurement = measure_moc_reflected_domain_global_shock_remesh(result)

  assert measurement.status is (
    MocReflectedDomainGlobalShockRemeshMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.attempt_count == 2
  assert measurement.source_field_verified
  assert measurement.attempt_identity_verified
  assert measurement.attempt_shape_verified
  assert measurement.attempt_residuals_verified
  assert measurement.selected_attempt_verified
  assert measurement.global_endpoint_verified is False
  assert measurement.no_endpoint_closure_verified
  assert measurement.physical_closure_verified is False
  assert measurement.fidelity_isolation_verified
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False

  tampered_attempt = replace(
    result.attempts[0],
    compression_envelope_skew=0.25,
  )
  tampered = replace(
    result,
    attempts=(tampered_attempt, *result.attempts[1:]),
  )
  tampered_measurement = measure_moc_reflected_domain_global_shock_remesh(
    tampered,
  )
  assert tampered_measurement.status is (
    MocReflectedDomainGlobalShockRemeshMeasurementStatus.ATTEMPT_FAILURE
  )
  assert tampered_measurement.attempt_identity_verified is False
####


def test_global_euler_shock_boundary_closes_continuous_source_frontier():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  global_result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )

  result = solve_reflected_domain_global_euler_shock_boundary(global_result)

  assert result.status is MocReflectedDomainGlobalEulerShockBoundaryStatus.CONVERGED
  assert result.converged
  assert result.physical_closure_verified
  assert result.source_frontier_verified
  assert result.selected_attempt_index == global_result.selected_attempt_index
  assert result.outer_source_index == 2
  assert result.target_centerline_index == 3
  assert result.source_frontier_state is not None
  assert result.source_frontier_state.y_m == pytest.approx(
    source.target_centerline_y_m,
  )
  assert result.source_frontier_state.theta_rad == pytest.approx(
    source.target_centerline_flow_angle_rad,
  )
  centerline_xs = tuple(
    state.x_m for state in source.centerline_source_states
  )
  assert centerline_xs[2] < result.source_frontier_state.x_m < centerline_xs[3]
  assert result.initial_shock_points_m != result.remeshed_shock_points_m
  assert result.first_endpoint_tangent_residual_rad == pytest.approx(0.0)
  assert result.last_endpoint_tangent_residual_rad == pytest.approx(0.0)
  assert result.shock_boundary is not None
  assert result.shock_boundary.converged
  assert result.shock_boundary.local_euler_verified
  assert result.shock_boundary.orientation.value == 'mixed-characteristic-boundary'
  assert result.shock_boundary.zero_strength_endpoints_allowed
  assert result.physical_field is not None
  assert result.physical_field.converged
  assert result.physical_field.physical_closure_verified
  assert result.incoming_handoff_verified
  assert result.incoming_handoff == source.incoming_handoff
  assert result.physical_field.incoming_handoff == source.incoming_handoff
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )

  measurement = measure_moc_reflected_domain_global_euler_shock_boundary(result)
  assert measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.local_euler_consistency_verified
  assert measurement.source_frontier_verified
  assert measurement.incoming_handoff_verified
  assert measurement.endpoint_tangents_verified
  assert measurement.upstream_sampling_verified
  assert measurement.source_frontier_sampling_verified
  assert measurement.source_frontier_sample_count == len(
    result.remeshed_shock_points_m
  )
  assert measurement.maximum_source_frontier_state_residual == pytest.approx(0.0)
  assert measurement.maximum_source_frontier_static_pressure_residual_Pa == pytest.approx(
    0.0,
    abs=1.0e-8,
  )
  assert measurement.maximum_source_frontier_total_pressure_residual_Pa == pytest.approx(
    0.0,
    abs=1.0e-8,
  )
  assert measurement.ambient_boundary_verified
  assert measurement.physical_closure_verified
  assert measurement.fidelity_isolation_verified

  tampered = replace(result, first_endpoint_tangent_residual_rad=0.25)
  tampered_measurement = (
    measure_moc_reflected_domain_global_euler_shock_boundary(tampered)
  )
  assert tampered_measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.GEOMETRY_FAILURE
  )
  assert tampered_measurement.endpoint_tangents_verified is False
  assert tampered_measurement.converged is False

  assert result.shock_boundary is not None
  tampered_total_pressure = (
    result.shock_boundary.upstream_total_pressure_Pa[0] + 1.0,
    *result.shock_boundary.upstream_total_pressure_Pa[1:],
  )
  tampered_frontier = replace(
    result,
    shock_boundary=replace(
      result.shock_boundary,
      upstream_total_pressure_Pa=tampered_total_pressure,
    ),
  )
  tampered_frontier_measurement = (
    measure_moc_reflected_domain_global_euler_shock_boundary(
      tampered_frontier,
    )
  )
  assert tampered_frontier_measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.FRONTIER_FAILURE
  )
  assert tampered_frontier_measurement.source_frontier_sampling_verified is False
  assert tampered_frontier_measurement.converged is False

  report = result.as_report()
  assert report['source_frontier_verified'] is True
  assert report['shock_boundary']['zero_strength_endpoints_allowed'] is True
  assert report['physical_field']['physical_closure_verified'] is True
  assert measurement.as_report()['checks']['source_frontier_sampling_verified'] is True
####


def test_global_physical_closure_carries_variable_entropy_and_gates_cell_promotion():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )

  closure = solve_reflected_domain_global_physical_closure(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )

  assert closure.status is (
    MocReflectedDomainGlobalPhysicalClosureStatus.CONVERGED_GLOBAL_PHYSICAL_CLOSURE
  )
  assert closure.converged
  assert closure.physical_closure_verified
  assert closure.source_frontier_verified
  assert closure.incoming_handoff_verified
  assert closure.variable_entropy_transport_verified
  assert closure.maximum_entropy_lineage_residual == pytest.approx(0.0)
  assert closure.cell_euler_residuals_verified
  assert closure.downstream_boundary_closure_verified is False
  assert closure.downstream_boundary_model.endswith('compression-envelope')
  assert closure.downstream_boundary is not None
  downstream_boundary = closure.downstream_boundary
  assert downstream_boundary.status is (
    MocReflectedDomainDownstreamBoundaryStatus.RESEARCH_COMPRESSION_ENVELOPE
  )
  assert downstream_boundary.model == closure.downstream_boundary_model
  assert downstream_boundary.sample_count >= 2
  assert downstream_boundary.samples_available
  assert downstream_boundary.geometry_verified
  assert downstream_boundary.closure_verified is False
  assert downstream_boundary.solver_owned
  assert downstream_boundary.boundary_condition_verified is False
  assert downstream_boundary.mixed_regime_field_verified is False
  assert closure.downstream_boundary_audit is not None
  assert closure.downstream_boundary_audit.converged
  assert closure.as_report()['downstream_boundary_audit']['converged'] is True
  downstream_measurement = measure_moc_reflected_domain_downstream_boundary(
    downstream_boundary,
  )
  assert downstream_measurement.status is (
    MocReflectedDomainDownstreamBoundaryMeasurementStatus.CONVERGED
  )
  assert downstream_measurement.converged
  assert downstream_measurement.model_verified
  assert downstream_measurement.status_verified
  assert downstream_measurement.solver_owned_verified
  assert downstream_measurement.sample_geometry_verified
  assert downstream_measurement.pressure_lineage_verified
  assert downstream_measurement.tangent_lineage_verified
  assert downstream_measurement.reported_residuals_verified
  assert downstream_measurement.research_only_verified
  assert downstream_measurement.physical_closure_verified is False
  assert downstream_measurement.chain_promotion_blocked
  assert downstream_measurement.production_claim_allowed is False
  assert downstream_measurement.as_report()['operator_id'] == (
    'op.moc.reflected-domain-downstream-boundary'
  )
  tampered_downstream_pressure = replace(
    downstream_boundary,
    boundary_static_pressure_Pa=tuple(
      value * 1.001
      for value in downstream_boundary.boundary_static_pressure_Pa
    ),
  )
  tampered_pressure_measurement = (
    measure_moc_reflected_domain_downstream_boundary(
      tampered_downstream_pressure,
    )
  )
  assert tampered_pressure_measurement.status is (
    MocReflectedDomainDownstreamBoundaryMeasurementStatus.PRESSURE_FAILURE
  )
  assert tampered_pressure_measurement.converged is False
  assert tampered_pressure_measurement.pressure_lineage_verified is False
  assert tampered_pressure_measurement.physical_closure_verified is False
  assert any(
    blocker.startswith('solver-owned downstream boundary closure')
    for blocker in closure.promotion_blockers
  )
  assert closure.as_report()['downstream_boundary_closure_verified'] is False
  assert closure.as_chain_termination_decision().diagnostics[
    'downstream_boundary_model'
  ].endswith('compression-envelope')
  assert closure.field_audit is not None
  # The legacy audit intentionally checks a uniform p0 lineage.  The new
  # closure gate checks each shock sample against its own entropy loss.
  assert closure.field_audit.entropy_lineage_verified is False
  closure_fingerprint = (
    moc_reflected_domain_global_physical_closure_fingerprint(closure)
  )
  assert closure_fingerprint == (
    moc_reflected_domain_global_physical_closure_fingerprint(closure)
  )
  refinement_evidence = MocReflectedDomainPromotionEvidence(
    closure_fingerprint=closure_fingerprint,
    refinement_evidence_id='refinement-run-test-global-euler-9',
  )
  evidence_bound = closure.bind_promotion_evidence(refinement_evidence)
  assert evidence_bound.promotion_evidence_bound
  assert evidence_bound.refinement_verified
  assert evidence_bound.canonical_euler_verified is False
  assert evidence_bound.production_promotion_gates[
    'refinement_verified'
  ] is True
  assert evidence_bound.production_claim_allowed is False
  assert closure.production_claim_allowed is False
  assert closure.chain_promotion_blocked
  assert closure.as_chain_termination_decision().reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )

  assert closure.global_euler is not None
  assert closure.global_euler.physical_field is not None
  closed_field = closure.global_euler.physical_field.field
  fit = fit_reflected_domain_production_shock_cell(
    evidence_bound,
    start_x_m=0.5,
    end_x_m=closed_field.ambient_boundary_points_m[-1][0] + 0.05,
    incoming_frontier=evidence_bound.incoming_handoff,
  )

  assert fit.status is MocProductionShockCellFitStatus.CONVERGED_LOCAL_FIT
  assert fit.local_fit_verified
  assert fit.frontier_verified
  assert fit.shock_fit_verified
  assert fit.candidate_field is closed_field
  assert fit.candidate_cell is not None
  assert fit.closure is evidence_bound
  assert fit.production_promotion_gates['refinement_verified'] is True
  assert fit.production_promotion_gates[
    'downstream_boundary_closure_verified'
  ] is False
  assert fit.production_claim_allowed is False
  assert fit.chain_promotion_blocked
  assert fit.as_chain_termination_decision().reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )
  fit_measurement = measure_moc_production_shock_cell_fit(fit)
  assert fit_measurement.status is MocShockCellMeasurementStatus.CONVERGED
  assert fit_measurement.operator_id == MOC_PRODUCTION_SHOCK_CELL_FIT_OPERATOR_ID
  assert fit_measurement.axial_length_m is not None
  assert fit_measurement.axial_length_m > 0.0
  assert fit_measurement.claim_status == 'not_accepted'
  assert 'external physical-length comparison' in fit_measurement.message
  tampered_fit = replace(
    fit,
    fitted_shock_points_m=tuple(
      (point[0] + 1.0e-3, point[1])
      for point in fit.fitted_shock_points_m
    ),
  )
  tampered_fit_measurement = measure_moc_production_shock_cell_fit(tampered_fit)
  assert tampered_fit_measurement.status is (
    MocShockCellMeasurementStatus.GEOMETRY_FAILURE
  )
  assert tampered_fit_measurement.converged is False
  with pytest.raises(ValueError, match='promotion'):
    fit.as_production_chain_cell()
  ####

  forged_downstream_boundary = replace(
    downstream_boundary,
    status=(
      MocReflectedDomainDownstreamBoundaryStatus
      .CONVERGED_SOLVER_OWNED_MIXED_REGIME
    ),
    boundary_condition_verified=True,
    mixed_regime_field_verified=True,
  )
  forged_closure = replace(
    closure,
    downstream_boundary=forged_downstream_boundary,
  )
  assert forged_downstream_boundary.closure_verified is False
  assert forged_closure.downstream_boundary_closure_verified is False
  assert forged_closure.production_claim_allowed is False

  fully_evidenced = closure.bind_promotion_evidence(
    MocReflectedDomainPromotionEvidence(
      closure_fingerprint=closure_fingerprint,
      canonical_free_boundary_evidence_id='canonical-free-boundary-test',
      canonical_euler_evidence_id='canonical-euler-test',
      refinement_evidence_id='refinement-run-test-global-euler-9',
      external_validation_evidence_id='external-validation-test',
    )
  )
  fully_evidenced_fit = replace(fit, closure=fully_evidenced)
  assert fully_evidenced_fit.local_fit_verified
  assert all(
    value
    for name, value in fully_evidenced_fit.production_promotion_gates.items()
    if name != 'downstream_boundary_closure_verified'
  )
  assert fully_evidenced_fit.production_promotion_gates[
    'downstream_boundary_closure_verified'
  ] is False
  assert fully_evidenced_fit.production_claim_allowed is False
  assert fully_evidenced_fit.chain_promotion_blocked
####


def test_global_mixed_regime_boundary_reference_is_bound_and_measured():
  closure = _global_physical_closure_for_mixed_regime()
  request = build_reflected_domain_mixed_regime_boundary_request(closure)
  assert request.upstream_handoff == closure.incoming_handoff
  assert len(request.perimeter_request.supersonic_patch) == 7

  reference_ambient_pressure = (
    0.98 * request.entropy_handoff.samples[0].downstream_total_pressure_Pa
  )
  request = replace(
    request,
    ambient_pressure_Pa=reference_ambient_pressure,
  )
  candidate = solve_reflected_domain_mixed_regime_boundary(request)

  assert candidate.status is (
    MocReflectedDomainMixedRegimeBoundaryStatus.CONVERGED_RESEARCH_REFERENCE
  )
  assert candidate.converged
  assert candidate.reference_verified
  assert candidate.solver_owned_reference_verified
  assert candidate.upstream_handoff_verified
  assert candidate.terminal_seam_verified
  assert candidate.boundary_condition_verified
  assert candidate.geometry_verified
  assert candidate.pressure_lineage_verified
  assert candidate.entropy_transport_verified
  assert candidate.tangency_verified
  assert candidate.conservative_euler_residuals_measured
  assert candidate.conservative_euler_residuals_verified
  assert candidate.residual_channel_coverage == {
    'mass': True,
    'streamwise_momentum': True,
    'transverse_momentum': True,
    'energy': True,
    'euler': True,
  }
  assert candidate.residual_channel_validity == candidate.residual_channel_coverage
  assert candidate.mixed_regime_field_verified is False
  assert candidate.physical_closure_verified is False
  assert candidate.downstream_boundary_closure_verified is False
  assert candidate.chain_promotion_blocked
  assert candidate.production_claim_allowed is False
  assert candidate.independent_measurement is not None
  assert candidate.independent_measurement.status is (
    MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.CONVERGED
  )
  assert candidate.independent_measurement.reference_verified
  assert candidate.independent_measurement.maximum_conservative_euler_residual == pytest.approx(
    candidate.reference.maximum_conservative_euler_residual,
  )
  report = candidate.as_report()
  assert report['independent_measurement']['checks']['terminal_seam_verified']
  assert report['residual_channel_coverage']['energy']
  assert report['physical_closure_verified'] is False
####


def test_global_mixed_regime_boundary_uses_typed_stop_for_actual_ambient_pressure():
  closure = _global_physical_closure_for_mixed_regime()
  request = build_reflected_domain_mixed_regime_boundary_request(closure)

  candidate = solve_reflected_domain_mixed_regime_boundary(request)

  assert candidate.status is (
    MocReflectedDomainMixedRegimeBoundaryStatus.FIELD_FAILURE
  )
  assert not candidate.converged
  assert candidate.reference is not None
  assert 'strict-subsonic' in candidate.message
  assert candidate.independent_measurement is None
  assert candidate.physical_closure_verified is False
  assert candidate.chain_promotion_blocked
####


def test_global_mixed_regime_boundary_rejects_reused_or_altered_frontier():
  closure = _global_physical_closure_for_mixed_regime()
  request = build_reflected_domain_mixed_regime_boundary_request(closure)
  altered_handoff = tuple(reversed(request.upstream_handoff))

  with pytest.raises(ValueError, match='upstream_handoff'):
    replace(request, upstream_handoff=altered_handoff)
  ####

  altered_section = replace(
    request.control_section,
    source='altered-control-section',
  )
  with pytest.raises(ValueError, match='control_section'):
    replace(request, control_section=altered_section)
  ####
####


def test_global_mixed_regime_boundary_measurement_rejects_field_mutation():
  closure = _global_physical_closure_for_mixed_regime()
  request = build_reflected_domain_mixed_regime_boundary_request(closure)
  request = replace(
    request,
    ambient_pressure_Pa=(
      0.98 * request.entropy_handoff.samples[0].downstream_total_pressure_Pa
    ),
  )
  candidate = solve_reflected_domain_mixed_regime_boundary(request)
  assert candidate.reference is not None
  assert candidate.reference.maximum_conservative_euler_residual is not None
  tampered_reference = replace(
    candidate.reference,
    maximum_conservative_euler_residual=(
      candidate.reference.maximum_conservative_euler_residual + 1.0
    ),
  )
  tampered_candidate = replace(
    candidate,
    reference=tampered_reference,
    independent_measurement=None,
  )

  measurement = measure_reflected_domain_mixed_regime_boundary(
    tampered_candidate,
  )

  assert measurement.status is (
    MocReflectedDomainMixedRegimeBoundaryMeasurementStatus.FIELD_FAILURE
  )
  assert not measurement.converged
  assert measurement.reference_measurement is not None
  assert measurement.reference_measurement.conservative_euler_residuals_verified is False
  assert measurement.conservative_euler_residuals_verified is False
  assert measurement.physical_closure_verified is False
####


def test_global_mixed_regime_boundary_refinement_reexecutes_without_promotion():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert source.converged

  run = run_reflected_domain_mixed_regime_boundary_refinement(
    source,
    (5, 7, 9),
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    shock_angle_tolerance_rad=0.02,
    geometry_tolerance_m=1.0e-2,
    outlet_height_tolerance_m=1.0e-2,
  )

  assert run.requested_resolutions == (5, 7, 9)
  assert len(run.closures) == 3
  assert len(run.requests) == 3
  assert len(run.cases) == 3
  assert run.fresh_solver_invocation_verified
  assert run.upstream_global_physical_closure_verified
  assert run.fidelity_isolation_verified
  assert run.measurement.status is (
    MocReflectedDomainMixedRegimeBoundaryRefinementStatus.CONVERGED
  )
  assert run.measurement.resolutions == (5, 7, 9)
  assert run.measurement.global_shock_sample_counts == (5, 7, 9)
  assert run.measurement.reference_axial_station_counts == (5, 7, 9)
  assert run.measurement.case_measurements_verified
  assert run.measurement.conservative_euler_evidence_verified
  assert run.measurement.geometry_sensitivity_verified
  assert run.measurement.outlet_height_stability_verified
  assert run.measurement.refinement_convergence_verified
  assert run.measurement.physical_closure_verified is False
  assert run.measurement.canonical_euler_verified is False
  assert run.measurement.external_validation_verified is False
  assert run.measurement.chain_promotion_blocked
  assert run.production_claim_allowed is False
  assert run.local_consistency_verified
  assert len(run.source_band_fingerprint) == 64
  assert len(run.configuration_fingerprint) == 64

  reversed_measurement = (
    measure_reflected_domain_mixed_regime_boundary_refinement(
      tuple(reversed(run.cases)),
    )
  )
  assert reversed_measurement.status is (
    MocReflectedDomainMixedRegimeBoundaryRefinementStatus.RESOLUTION_FAILURE
  )
  assert not reversed_measurement.converged
####


def test_coupled_euler_builder_preserves_global_closure_lineage():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  coupled_request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=20,
    max_shape_iterations=1,
    outlet_static_pressure_Pa=mixed_request.ambient_pressure_Pa,
  )

  assert coupled_request.mixed_regime_request == mixed_request
  assert coupled_request.source_closure_fingerprint == (
    mixed_request.closure_fingerprint
  )
  assert coupled_request.as_report()['source_closure_fingerprint'] == (
    mixed_request.closure_fingerprint
  )

  result = solve_reflected_domain_coupled_euler_free_boundary_from_mixed_regime_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=20,
    max_shape_iterations=1,
    outlet_static_pressure_Pa=mixed_request.ambient_pressure_Pa,
  )

  assert result.request is not None
  assert result.request.source_closure_fingerprint == (
    mixed_request.closure_fingerprint
  )
  assert result.production_claim_allowed is False
  assert result.downstream_boundary_closure_verified is False
####


def test_global_coupled_downstream_candidate_keeps_feedback_gate_explicit():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  result = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    ambient_pressure_Pa=mixed_request.control_section.samples[-1].static_pressure_Pa,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
  )

  assert result.status is (
    MocReflectedDomainGlobalCoupledDownstreamStatus
    .CONVERGED_LOCAL_COUPLED_FIELD
  )
  assert result.converged
  assert result.closure_lineage_verified
  assert result.local_coupled_field_verified
  assert result.coupled_field is not None
  assert result.coupled_field_audit is not None
  assert result.coupled_field_audit.converged
  assert result.global_coupling_verified is False
  assert result.downstream_boundary_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert result.as_report()['source_closure_fingerprint'] == (
    moc_reflected_domain_global_physical_closure_fingerprint(closure)
  )
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )
####


def test_global_coupled_downstream_derives_solver_owned_exact_field_handoff():
  closure = _global_physical_closure_for_mixed_regime()
  result = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=8,
    max_pseudo_iterations=400,
    max_shape_iterations=60,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
    ),
  )

  assert result.status is (
    MocReflectedDomainGlobalCoupledDownstreamStatus
    .CONVERGED_LOCAL_COUPLED_FIELD
  )
  assert result.converged
  assert result.physical_field_handoff is not None
  assert isinstance(
    result.physical_field_handoff,
    MocReflectedDomainGlobalPhysicalFieldHandoff,
  )
  assert result.physical_field_handoff.converged
  assert result.coupled_request is not None
  assert result.coupled_request.physical_field_continuation_profile == (
    result.physical_field_handoff.continuation_profile
  )
  assert result.coupled_request.physical_field_shock_front_condition == (
    result.physical_field_handoff.shock_front_condition
  )
  assert result.coupled_request.free_boundary_pressure_profile_source == (
    'solver-owned-physical-field-ambient-neighbor-pressure-profile-v1'
  )
  assert result.coupled_request.free_boundary_geometry_profile_source == (
    'solver-owned-physical-field-ambient-neighbor-geometry-profile-v1'
  )
  assert result.coupled_field is not None
  assert result.coupled_field.physical_field_continuation_profile_consumed
  assert result.coupled_field.physical_field_shock_front_condition_consumed
  assert result.coupled_field.free_boundary_pressure_profile_consumed
  assert result.coupled_field.free_boundary_geometry_profile_consumed
  assert result.coupled_field_audit is not None
  assert result.coupled_field_audit.physical_field_neighbor_profiles_verified
  assert result.coupled_field.request is not None
  tampered_request = replace(
    result.coupled_field.request,
    free_boundary_pressure_profile_Pa=(
      result.coupled_field.request.free_boundary_pressure_profile_Pa[0] + 1.0,
      *result.coupled_field.request.free_boundary_pressure_profile_Pa[1:],
    ),
  )
  tampered_field = replace(result.coupled_field, request=tampered_request)
  tampered_neighbor_audit = measure_reflected_domain_coupled_euler_free_boundary(
    tampered_field
  )
  assert tampered_neighbor_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
    .PHYSICAL_FIELD_NEIGHBOR_PROFILE_FAILURE
  )
  assert not tampered_neighbor_audit.physical_field_neighbor_profiles_verified
  assert result.global_coupling_verified is False
  assert result.downstream_boundary_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert result.as_report()['physical_field_handoff']['converged'] is True
####


def test_global_coupled_downstream_measures_boundary_overlap_without_promotion():
  closure = _global_physical_closure_for_mixed_regime()
  result = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=8,
    max_pseudo_iterations=400,
    max_shape_iterations=60,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
    ),
  )

  response = result.downstream_boundary_response
  assert response is not None
  assert response.status is (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
    .CONVERGED_LOCAL_OVERLAP
  )
  assert response.overlap_coverage_verified
  assert response.residuals_verified
  assert response.maximum_coordinate_residual_m <= response.coordinate_tolerance_m
  assert len(response.matched_x_stations_m) == len(
    response.coupled_boundary_points_m
  )
  assert len(response.coordinate_offsets_m) == len(response.matched_x_stations_m)
  assert len(response.tangent_offsets_rad) == len(response.matched_x_stations_m)
  assert len(response.pressure_offsets_Pa) == len(response.matched_x_stations_m)
  assert len(response.normal_velocity_values_m_s) == len(
    response.matched_x_stations_m
  )
  assert all(abs(value) <= response.coordinate_tolerance_m for value in response.coordinate_offsets_m)
  assert response.maximum_pressure_residual_Pa >= 0.0
  assert result.global_coupling_verified is False
  assert result.downstream_boundary_closure_verified is False
  assert result.production_claim_allowed is False

  independently_measured = (
    measure_reflected_domain_global_coupled_downstream_boundary_response(
      closure,
      result.coupled_field,
    )
  )
  assert independently_measured.as_report() == response.as_report()

  assert result.coupled_field is not None
  tampered = replace(
    result.coupled_field,
    free_boundary_points_m=(
      (
        result.coupled_field.free_boundary_points_m[0][0] - 1.0,
        result.coupled_field.free_boundary_points_m[0][1],
      ),
      *result.coupled_field.free_boundary_points_m[1:],
    ),
  )
  tampered_response = (
    measure_reflected_domain_global_coupled_downstream_boundary_response(
      closure,
      tampered,
    )
  )
  assert tampered_response.status is (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
    .COVERAGE_FAILURE
  )
  assert tampered_response.overlap_coverage_verified is False
  assert tampered_response.converged is False
####


def test_global_coupled_downstream_consumes_aligned_pressure_feedback_profile():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  ambient_pressure = mixed_request.control_section.samples[-1].static_pressure_Pa
  baseline = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    ambient_pressure_Pa=ambient_pressure,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
  )

  assert baseline.coupled_field is not None
  boundary_points = baseline.coupled_field.free_boundary_points_m
  cell_centers = tuple(
    0.5 * (first[0] + second[0])
    for first, second in zip(boundary_points, boundary_points[1:])
  )
  global_profile = (
    build_reflected_domain_global_coupled_downstream_boundary_pressure_profile(
      closure,
      cell_centers,
    )
  )
  assert isinstance(
    global_profile,
    MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  )
  assert global_profile.profile_verified
  assert global_profile.pressure_correction_fraction == pytest.approx(0.0)
  assert global_profile.as_report()['production_claim_allowed'] is False

  consumed = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    ambient_pressure_Pa=ambient_pressure,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    boundary_pressure_profile=global_profile,
  )
  assert consumed.boundary_pressure_profile == global_profile
  assert consumed.closure_lineage_verified
  assert consumed.coupled_request is not None
  assert consumed.coupled_request.free_boundary_pressure_profile_Pa == (
    global_profile.pressure_Pa
  )
  assert consumed.coupled_request.free_boundary_pressure_profile_x_stations_m == (
    global_profile.x_stations_m
  )
  assert consumed.coupled_field is not None
  assert consumed.coupled_field.free_boundary_pressure_profile_consumed
  assert consumed.coupled_field.as_report()[
    'free_boundary_pressure_profile_consumed'
  ] is True
  assert consumed.global_coupling_verified is False
  assert consumed.downstream_boundary_closure_verified is False
  assert consumed.production_claim_allowed is False

  assert baseline.downstream_boundary_response is not None
  feedback_profile = (
    build_reflected_domain_global_coupled_downstream_feedback_pressure_profile(
      closure,
      baseline.downstream_boundary_response,
      pressure_correction_fraction=0.25,
    )
  )
  assert feedback_profile.source_response_status == (
    baseline.downstream_boundary_response.status.value
  )
  assert feedback_profile.pressure_correction_fraction == pytest.approx(0.25)
  response_consumed = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    ambient_pressure_Pa=ambient_pressure,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    boundary_pressure_profile=feedback_profile,
  )
  assert response_consumed.coupled_field is not None
  assert response_consumed.closure_lineage_verified
  assert response_consumed.coupled_field.free_boundary_pressure_profile_consumed
  assert (
    response_consumed.coupled_field.free_boundary_pressure_profile_compatibility
    is not None
  )
  pressure_profile_compatibility = (
    response_consumed.coupled_field.free_boundary_pressure_profile_compatibility
  )
  assert pressure_profile_compatibility.status is (
    MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus
    .SOME_TARGETS_BELOW_ISENTROPIC_SUBSONIC_BOUNDS
  )
  assert pressure_profile_compatibility.below_bound_count > 0
  assert not pressure_profile_compatibility.all_targets_within_isentropic_subsonic_bounds
  assert (
    assess_reflected_domain_coupled_euler_pressure_profile_compatibility(
      response_consumed.coupled_request
    )
    == pressure_profile_compatibility
  )
  assert response_consumed.coupled_field_audit is not None
  assert response_consumed.coupled_field_audit.free_boundary_report_verified
  assert response_consumed.coupled_field_audit.pressure_profile_compatibility_verified
  assert response_consumed.boundary_pressure_profile == feedback_profile
  tampered_profile = replace(
    pressure_profile_compatibility,
    target_pressure_min_Pa=(
      pressure_profile_compatibility.target_pressure_min_Pa * 1.01
    ),
  )
  tampered_audit = measure_reflected_domain_coupled_euler_free_boundary(
    replace(
      response_consumed.coupled_field,
      free_boundary_pressure_profile_compatibility=tampered_profile,
    )
  )
  assert tampered_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
    .PRESSURE_PROFILE_COMPATIBILITY_FAILURE
  )
  assert not tampered_audit.pressure_profile_compatibility_verified
  assert response_consumed.global_coupling_verified is False
  assert response_consumed.downstream_boundary_closure_verified is False
  assert response_consumed.production_claim_allowed is False

  assert baseline.downstream_boundary_response is not None
  geometry_feedback_profile = (
    build_reflected_domain_global_coupled_downstream_feedback_geometry_profile(
      closure,
      baseline.downstream_boundary_response,
    )
  )
  assert isinstance(
    geometry_feedback_profile,
    MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile,
  )
  assert geometry_feedback_profile.profile_verified
  assert geometry_feedback_profile.lower_ordinate_m == pytest.approx(0.0)
  assert geometry_feedback_profile.boundary_y_m == tuple(
    point[1]
    for point in baseline.downstream_boundary_response.upstream_boundary_points_m
  )
  assert geometry_feedback_profile.as_report()['production_claim_allowed'] is False

  anchored_consumed = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    ambient_pressure_Pa=ambient_pressure,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    boundary_geometry_profile=geometry_feedback_profile,
  )
  assert anchored_consumed.status is (
    MocReflectedDomainGlobalCoupledDownstreamStatus
    .CONVERGED_LOCAL_COUPLED_FIELD
  )
  assert anchored_consumed.mixed_regime_request is not None
  assert anchored_consumed.mixed_regime_request.control_section_height_m == pytest.approx(
    geometry_feedback_profile.boundary_y_m[0]
    - geometry_feedback_profile.lower_ordinate_m
  )
  assert anchored_consumed.coupled_request is not None
  assert anchored_consumed.coupled_request.free_boundary_geometry_profile_lower_ordinate_m == pytest.approx(
    geometry_feedback_profile.lower_ordinate_m
  )
  assert anchored_consumed.coupled_field is not None
  assert anchored_consumed.coupled_field.free_boundary_geometry_profile_consumed
  assert anchored_consumed.downstream_boundary_response is not None
  assert anchored_consumed.downstream_boundary_response.maximum_coordinate_residual_m <= (
    anchored_consumed.downstream_boundary_response.coordinate_tolerance_m
  )

  full_pressure_feedback_profile = (
    build_reflected_domain_global_coupled_downstream_feedback_pressure_profile(
      closure,
      baseline.downstream_boundary_response,
      pressure_correction_fraction=1.0,
    )
  )
  fully_consumed = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    ambient_pressure_Pa=ambient_pressure,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    boundary_pressure_profile=full_pressure_feedback_profile,
    boundary_geometry_profile=geometry_feedback_profile,
  )
  assert fully_consumed.status is (
    MocReflectedDomainGlobalCoupledDownstreamStatus
    .CONVERGED_LOCAL_COUPLED_FIELD
  )
  assert fully_consumed.coupled_field is not None
  assert fully_consumed.coupled_field_audit is not None
  assert fully_consumed.coupled_field_audit.converged
  assert fully_consumed.coupled_field.free_boundary_pressure_profile_consumed
  assert fully_consumed.coupled_field.free_boundary_geometry_profile_consumed
  assert fully_consumed.downstream_boundary_response is not None
  assert fully_consumed.downstream_boundary_response.maximum_coordinate_residual_m <= (
    fully_consumed.downstream_boundary_response.coordinate_tolerance_m
  )

  baseline_geometry = baseline.coupled_field.free_boundary_points_m
  exact_geometry_profile = MocReflectedDomainGlobalCoupledDownstreamBoundaryGeometryProfile(
    source_closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
      closure
    ),
    x_stations_m=tuple(point[0] for point in baseline_geometry),
    boundary_y_m=tuple(point[1] for point in baseline_geometry),
  )
  geometry_consumed = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    ambient_pressure_Pa=ambient_pressure,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    boundary_geometry_profile=exact_geometry_profile,
  )
  assert geometry_consumed.status is (
    MocReflectedDomainGlobalCoupledDownstreamStatus
    .CONVERGED_LOCAL_COUPLED_FIELD
  )
  assert geometry_consumed.coupled_field is not None
  assert geometry_consumed.coupled_field.free_boundary_geometry_profile_consumed
  assert geometry_consumed.coupled_field_audit is not None
  assert geometry_consumed.coupled_field_audit.converged
  assert geometry_consumed.coupled_field_audit.free_boundary_geometry_profile_verified
  assert geometry_consumed.coupled_field_audit.local_consistency_verified
  assert geometry_consumed.boundary_geometry_profile == exact_geometry_profile
####


def test_global_coupled_downstream_response_refinement_keeps_feedback_gate_open():
  closure = _global_physical_closure_for_mixed_regime()
  run = run_reflected_domain_global_coupled_downstream_refinement(
    closure,
    reference_total_temperature_K=1500.0,
    resolutions=((6, 3), (8, 4)),
    max_pseudo_iterations=400,
    max_shape_iterations=60,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
    ),
  )

  assert run.requested_resolutions == ((6, 3), (8, 4))
  assert run.fresh_solver_invocation_verified
  assert run.fidelity_isolation_verified
  assert len(run.cases) == 2
  assert run.measurement.status is (
    MocReflectedDomainGlobalCoupledDownstreamRefinementStatus
    .CONVERGED_RESEARCH_LADDER
  )
  assert run.measurement.resolution_order_verified
  assert run.measurement.mesh_growth_verified
  assert run.measurement.case_audits_verified
  assert run.measurement.response_lineage_verified
  assert run.measurement.response_channels_finite
  assert run.measurement.overlap_coverage_verified
  assert run.measurement.overlap_residuals_verified
  assert run.measurement.global_coupling_verified is False
  assert run.measurement.downstream_boundary_closure_verified is False
  assert run.measurement.chain_promotion_blocked
  assert run.measurement.production_claim_allowed is False
  assert run.production_claim_allowed is False
  assert all(
    case.response is not None
    and case.response.status is (
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponseStatus
      .CONVERGED_LOCAL_OVERLAP
    )
    and case.response.residuals_verified
    and case.response.maximum_coordinate_residual_m
    <= case.response.coordinate_tolerance_m
    for case in run.cases
  )
####


def test_global_coupled_downstream_feedback_iteration_keeps_global_gate_open():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  ambient_pressure = mixed_request.control_section.samples[-1].static_pressure_Pa
  run = run_reflected_domain_global_coupled_downstream_feedback(
    closure,
    reference_total_temperature_K=1500.0,
    maximum_iterations=2,
    ambient_pressure_Pa=ambient_pressure,
    axial_station_count=7,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    pressure_update_tolerance_Pa=1.0e3,
  )

  assert run.requested_iterations == 2
  assert len(run.iterations) == 2
  assert run.fresh_solver_invocation_verified
  assert run.closure_lineage_verified
  assert run.configuration['geometry_feedback_frame_policy'] == (
    'solver-owned-first-ordinate-anchor-v1'
  )
  assert run.pressure_profile_lineage_verified
  assert run.pressure_profile_alignment_verified
  assert run.geometry_profile_lineage_verified
  assert run.geometry_profile_alignment_verified
  assert run.geometry_profile_consumption_verified
  assert run.response_lineage_verified
  assert run.response_channels_finite
  assert run.response_coverage_verified
  assert run.response_residuals_verified is False
  assert run.local_coupled_field_verified is False
  assert run.pressure_update_convergence_verified is False
  assert run.status is (
    MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.SOLVER_FAILURE
  )
  assert run.converged is False
  assert run.global_coupling_verified is False
  assert run.downstream_boundary_closure_verified is False
  assert run.chain_promotion_blocked
  assert run.production_claim_allowed is False

  first, second = run.iterations
  assert first.input_pressure_profile is None
  assert first.next_pressure_profile is not None
  assert first.input_geometry_profile is None
  assert first.next_geometry_profile is not None
  assert second.input_pressure_profile == first.next_pressure_profile
  assert second.input_geometry_profile == first.next_geometry_profile
  assert second.pressure_profile_consumption_verified
  assert second.result.boundary_pressure_profile == second.input_pressure_profile
  assert second.result.coupled_field is not None
  assert second.result.coupled_field.free_boundary_pressure_profile_consumed
  assert second.geometry_profile_consumption_verified
  assert second.result.boundary_geometry_profile == second.input_geometry_profile
  assert second.result.coupled_field.free_boundary_geometry_profile_consumed
  assert all(
    item.result.global_coupling_verified is False
    and item.result.downstream_boundary_closure_verified is False
    and item.result.chain_promotion_blocked
    and item.result.production_claim_allowed is False
    for item in run.iterations
  )
####


def test_global_coupled_downstream_feedback_reaches_local_pressure_fixed_point_only():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  ambient_pressure = mixed_request.control_section.samples[-1].static_pressure_Pa
  run = run_reflected_domain_global_coupled_downstream_feedback(
    closure,
    reference_total_temperature_K=1500.0,
    maximum_iterations=5,
    pressure_correction_fraction=1.0,
    ambient_pressure_Pa=ambient_pressure,
    axial_station_count=7,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    pressure_update_tolerance_Pa=1.0e3,
  )

  assert run.requested_iterations == 5
  assert len(run.iterations) == 5
  assert run.fresh_solver_invocation_verified
  assert run.closure_lineage_verified
  assert run.pressure_profile_lineage_verified
  assert run.geometry_profile_lineage_verified
  assert run.geometry_profile_consumption_verified
  assert run.response_lineage_verified
  assert run.response_channels_finite
  assert run.response_coverage_verified
  assert run.response_residuals_verified is False
  assert run.local_coupled_field_verified
  assert run.pressure_update_convergence_verified
  assert run.status is (
    MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.RESPONSE_FAILURE
  )
  assert run.converged is False
  assert run.global_coupling_verified is False
  assert run.downstream_boundary_closure_verified is False
  assert run.chain_promotion_blocked
  assert run.production_claim_allowed is False

  assert run.iterations[-1].maximum_pressure_update_Pa is not None
  assert run.iterations[-1].maximum_pressure_update_Pa <= (
    run.pressure_update_tolerance_Pa
  )
  assert all(item.local_coupled_field_verified for item in run.iterations)
  assert all(
    item.result.global_coupling_verified is False
    and item.result.downstream_boundary_closure_verified is False
    and item.result.chain_promotion_blocked
    and item.result.production_claim_allowed is False
    for item in run.iterations
  )
####


def test_global_coupled_downstream_candidate_retains_actual_frontier_failure():
  closure = _global_physical_closure_for_mixed_regime()
  result = solve_reflected_domain_global_coupled_downstream(
    closure,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=40,
    max_shape_iterations=2,
  )

  assert result.status is (
    MocReflectedDomainGlobalCoupledDownstreamStatus.COUPLED_SOLVER_FAILURE
  )
  assert result.converged is False
  assert result.closure_lineage_verified
  assert result.coupled_field is not None
  assert result.coupled_field.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .TRANSONIC_FRONTIER_FAILURE
  )
  assert result.coupled_field_audit is not None
  assert result.coupled_field_audit.converged is False
  assert result.global_coupling_verified is False
  assert result.downstream_boundary_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_global_coupled_euler_free_boundary_isolated_lane_keeps_actual_seam_open():
  closure = _global_physical_closure_for_mixed_regime()
  request = build_reflected_domain_mixed_regime_boundary_request(closure)
  coupled_request = MocReflectedDomainCoupledEulerFreeBoundaryRequest(
    mixed_regime_request=request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=8,
    outlet_static_pressure_Pa=request.ambient_pressure_Pa,
  )

  result = solve_reflected_domain_coupled_euler_free_boundary(coupled_request)

  if result.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus.TRANSONIC_FRONTIER_FAILURE
  ):
    assert result.converged is False
    assert not result.conservative_states_by_cell
    assert not result.conservative_euler_residuals_measured
    assert result.chain_promotion_blocked
    assert result.production_claim_allowed is False
    assert result.message.startswith('coupled Euler field requires a placed')
    assert result.subsonic_pressure_budget is not None
    assert result.subsonic_pressure_budget.status is (
      MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
      .BELOW_ISENTROPIC_SUBSONIC_BOUNDS
    )
    assert result.transonic_transition is not None
    assert result.transonic_transition_audit is not None
    assert result.transonic_transition_audit.converged
    assert result.control_section_compatibility is not None
    assert result.transonic_frontier_compatibility is not None
    assert result.transonic_frontier_compatibility.status is (
      MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .REQUIRED_UPSTREAM_NOT_RETAINED
    )
    assert result.transonic_frontier_compatibility.frontier_state_compatible is False
    assert result.transonic_frontier_compatibility.matching_sample_count == 0
    assert result.as_chain_termination_decision().reason is (
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    )
    audit = measure_reflected_domain_coupled_euler_free_boundary(result)
    assert audit.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE
    )
    assert audit.transonic_frontier_compatibility_verified
    assert audit.converged is False
    tampered = replace(
      result,
      transonic_frontier_compatibility=replace(
        result.transonic_frontier_compatibility,
        nearest_mach_residual=(
          result.transonic_frontier_compatibility.nearest_mach_residual + 0.01
        ),
      ),
    )
    tampered_audit = measure_reflected_domain_coupled_euler_free_boundary(
      tampered
    )
    assert tampered_audit.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE
    )
    assert not tampered_audit.transonic_frontier_compatibility_verified
    assert result.transonic_transition_audit is not None
    tampered_transition_audit = measure_reflected_domain_coupled_euler_free_boundary(
      replace(
        result,
        transonic_transition_audit=replace(
          result.transonic_transition_audit,
          shock_state_conservation_verified=False,
        ),
      )
    )
    assert tampered_transition_audit.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE
    )
    assert not tampered_transition_audit.transonic_transition_verified
    tampered_budget_audit = measure_reflected_domain_coupled_euler_free_boundary(
      replace(
        result,
        subsonic_pressure_budget=replace(
          result.subsonic_pressure_budget,
          reference_total_pressure_Pa=(
            result.subsonic_pressure_budget.reference_total_pressure_Pa * 1.01
          ),
        ),
      )
    )
    assert tampered_budget_audit.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE
    )
    assert not tampered_budget_audit.pressure_budget_verified
    return
  ####

  assert result.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus.FREE_BOUNDARY_FAILURE
  )
  assert result.coupled_euler_field_verified
  assert result.conservative_euler_residuals_measured
  assert result.conservative_euler_residuals_verified
  assert result.entropy_transport_verified
  assert result.maximum_entropy_transport_residual == pytest.approx(0.0)
  assert result.maximum_entropy_production_fraction is not None
  assert result.maximum_entropy_production_fraction > 0.0
  assert len(result.entropy_production_fraction_by_cell) == len(
    result.conservative_states_by_cell
  )
  assert max(result.entropy_production_fraction_by_cell) == pytest.approx(
    result.maximum_entropy_production_fraction
  )
  assert len(result.cell_vertices_by_cell_m) == len(
    result.conservative_states_by_cell
  )
  assert all(len(cell) == 4 for cell in result.cell_vertices_by_cell_m)
  assert result.free_boundary_condition_verified is False
  assert result.request is not None
  assert result.as_report()['request']['free_boundary_flux_model'] == (
    'specified-pressure-material-streamline-v1'
  )
  assert result.request.outlet_static_pressure_Pa == pytest.approx(
    request.ambient_pressure_Pa
  )
  assert result.as_report()['request']['outlet_static_pressure_Pa'] == pytest.approx(
    request.ambient_pressure_Pa
  )
  assert result.physical_closure_verified is False
  assert result.canonical_euler_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert result.maximum_free_boundary_pressure_residual_Pa is not None
  assert result.maximum_free_boundary_pressure_residual_Pa > 0.1 * request.ambient_pressure_Pa
  assert result.subsonic_pressure_budget is not None
  assert result.subsonic_pressure_budget.status is (
    MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
    .BELOW_ISENTROPIC_SUBSONIC_BOUNDS
  )
  assert not result.subsonic_pressure_budget.reachable_without_additional_entropy
  assert result.subsonic_pressure_budget.subsonic_static_pressure_lower_bound_Pa > (
    request.ambient_pressure_Pa
  )
  assert result.subsonic_pressure_budget.minimum_additional_total_pressure_loss_fraction > 0.4
  assert result.as_report()['subsonic_pressure_budget']['status'] == (
    'below-isentropic-subsonic-pressure-bounds'
  )
  assert result.transonic_transition is not None
  assert result.transonic_transition.status is (
    MocTransonicTransitionStatus.CONVERGED_NORMAL_SHOCK_REFERENCE
  )
  assert result.transonic_transition_audit is not None
  assert result.transonic_transition_audit.converged
  assert result.transonic_transition.shock_state is not None
  assert result.transonic_transition.shock_state.upstream_supersonic
  assert result.transonic_transition.shock_state.downstream_subsonic
  assert result.transonic_transition_audit.shock_state_verified
  assert result.as_report()['transonic_transition']['status'] == (
    'converged-normal-shock-pressure-reference'
  )
  assert result.control_section_compatibility is not None
  assert result.control_section_compatibility.status is (
    MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus
    .TARGET_BELOW_CONTROL_SECTION
  )
  assert not result.control_section_compatibility.pressure_seam_matched
  assert result.control_section_compatibility.transition_requires_supersonic_upstream
  assert result.control_section_compatibility.absolute_pressure_jump_Pa > 0.0
  assert result.as_report()['control_section_compatibility']['status'] == (
    'target-below-control-section-pressure'
  )
  assert result.transonic_frontier_compatibility is not None
  assert result.transonic_frontier_compatibility.status is (
    MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
    .REQUIRED_UPSTREAM_NOT_RETAINED
  )
  assert result.transonic_frontier_compatibility.frontier_state_compatible is False
  assert result.transonic_frontier_compatibility.frontier_sample_count == 9
  assert result.transonic_frontier_compatibility.matching_sample_count == 0
  assert result.transonic_frontier_compatibility.required_upstream_mach == pytest.approx(
    result.transonic_transition.required_upstream_mach
  )
  assert result.transonic_frontier_compatibility.nearest_mach_residual is not None
  assert result.transonic_frontier_compatibility.nearest_mach_residual > 1.0
  assert result.as_report()['transonic_frontier_compatibility']['status'] == (
    'transonic-required-upstream-state-not-retained-on-frontier'
  )
  transition = assess_reflected_domain_coupled_euler_transonic_transition(
    coupled_request
  )
  assert transition.status is (
    MocTransonicTransitionStatus.CONVERGED_NORMAL_SHOCK_REFERENCE
  )
  assert transition.transition_required
  assert transition.converged
  assert transition.as_report()['physical_closure_verified'] is False
  assert transition.as_report()['chain_promotion_blocked'] is True
  assert transition.as_report()['production_claim_allowed'] is False
  compatibility = assess_reflected_domain_coupled_euler_control_section_compatibility(
    coupled_request,
    transition,
  )
  assert compatibility == result.control_section_compatibility
  frontier_compatibility = (
    assess_reflected_domain_coupled_euler_transonic_frontier_compatibility(
      coupled_request,
      transition,
    )
  )
  assert frontier_compatibility == result.transonic_frontier_compatibility
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )
  audit = measure_reflected_domain_coupled_euler_free_boundary(result)
  assert audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.BOUNDARY_FAILURE
  )
  assert audit.residual_channels_recomputed
  assert audit.residual_report_verified
  assert audit.free_boundary_report_verified
  assert audit.pressure_budget_verified
  assert audit.transonic_frontier_compatibility_verified
  assert audit.control_section_compatibility_verified
  assert audit.entropy_report_verified
  assert audit.entropy_production_map_verified
  assert audit.entropy_transport_verified
  assert audit.promotion_flags_verified
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False
  tampered_channels = list(result.residual_channels_by_cell)
  tampered_channels[0] = (
    tampered_channels[0][0] + 1.0,
    *tampered_channels[0][1:],
  )
  tampered_audit = measure_reflected_domain_coupled_euler_free_boundary(
    replace(result, residual_channels_by_cell=tuple(tampered_channels))
  )
  assert tampered_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.RESIDUAL_FAILURE
  )
  tampered_budget = replace(
    result.subsonic_pressure_budget,
    reference_total_pressure_Pa=result.subsonic_pressure_budget.reference_total_pressure_Pa * 1.01,
  )
  pressure_budget_audit = measure_reflected_domain_coupled_euler_free_boundary(
    replace(result, subsonic_pressure_budget=tampered_budget)
  )
  assert pressure_budget_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.PRESSURE_BUDGET_FAILURE
  )
  assert not pressure_budget_audit.pressure_budget_verified
  tampered_frontier = replace(
    result.transonic_frontier_compatibility,
    nearest_mach_residual=result.transonic_frontier_compatibility.nearest_mach_residual
    + 0.01,
  )
  frontier_audit = measure_reflected_domain_coupled_euler_free_boundary(
    replace(result, transonic_frontier_compatibility=tampered_frontier)
  )
  assert frontier_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
    .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE
  )
  assert not frontier_audit.transonic_frontier_compatibility_verified
  tampered_transition = replace(
    result.transonic_transition,
    downstream_static_pressure_Pa=result.transonic_transition.downstream_static_pressure_Pa * 1.01,
  )
  transition_audit = measure_reflected_domain_coupled_euler_free_boundary(
    replace(result, transonic_transition=tampered_transition)
  )
  assert transition_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.TRANSONIC_TRANSITION_FAILURE
  )
  assert not transition_audit.transonic_transition_verified
  assert result.transonic_transition_audit is not None
  tampered_transition_audit = replace(
    result.transonic_transition_audit,
    shock_state_conservation_verified=False,
  )
  conservation_audit = measure_reflected_domain_coupled_euler_free_boundary(
    replace(result, transonic_transition_audit=tampered_transition_audit)
  )
  assert conservation_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
    .TRANSONIC_TRANSITION_FAILURE
  )
  assert not conservation_audit.transonic_transition_verified
  tampered_compatibility = measure_reflected_domain_coupled_euler_free_boundary(
    replace(
      result,
      control_section_compatibility=replace(
        result.control_section_compatibility,
        absolute_pressure_jump_Pa=(
          result.control_section_compatibility.absolute_pressure_jump_Pa * 1.1
        ),
      ),
    )
  )
  assert tampered_compatibility.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
    .CONTROL_SECTION_COMPATIBILITY_FAILURE
  )
  assert not tampered_compatibility.control_section_compatibility_verified
  assert result.maximum_entropy_production_fraction is not None
  tampered_entropy = measure_reflected_domain_coupled_euler_free_boundary(
    replace(
      result,
      maximum_entropy_production_fraction=(
        result.maximum_entropy_production_fraction * 1.01
      ),
    )
  )
  assert tampered_entropy.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.ENTROPY_FAILURE
  )
  assert not tampered_entropy.entropy_report_verified
  tampered_entropy_map = list(result.entropy_production_fraction_by_cell)
  tampered_entropy_map[0] += 1.0e-3
  tampered_entropy_map_audit = measure_reflected_domain_coupled_euler_free_boundary(
    replace(
      result,
      entropy_production_fraction_by_cell=tuple(tampered_entropy_map),
    )
  )
  assert tampered_entropy_map_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.ENTROPY_FAILURE
  )
  assert not tampered_entropy_map_audit.entropy_production_map_verified
  tampered_vertices = list(result.cell_vertices_by_cell_m)
  tampered_vertices[0] = (
    (tampered_vertices[0][0][0] + 1.0e-3, tampered_vertices[0][0][1]),
    *tampered_vertices[0][1:],
  )
  geometry_audit = measure_reflected_domain_coupled_euler_free_boundary(
    replace(result, cell_vertices_by_cell_m=tuple(tampered_vertices))
  )
  assert geometry_audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.GEOMETRY_FAILURE
  )
####


def test_coupled_euler_free_boundary_flux_has_no_mass_or_energy_transport():
  state = coupled_euler._conservative_from_primitive(
    density=1.2,
    velocity_u=240.0,
    velocity_v=35.0,
    pressure=180000.0,
    gamma=1.4,
  )

  flux, wave = coupled_euler._specified_pressure_wall_flux(
    state,
    boundary_pressure=101325.0,
    normal_x=0.6,
    normal_y=0.8,
    face_length=2.5,
    gamma=1.4,
    gas_constant=287.05,
  )

  assert flux[0] == pytest.approx(0.0)
  assert flux[3] == pytest.approx(0.0)
  assert flux[1] == pytest.approx(101325.0 * 0.6 * 2.5)
  assert flux[2] == pytest.approx(101325.0 * 0.8 * 2.5)
  assert wave > 0.0
####


def test_subsonic_characteristic_inlet_releases_the_outgoing_acoustic_mode():
  reference = coupled_euler._conservative_from_primitive(
    density=1.1,
    velocity_u=150.0,
    velocity_v=12.0,
    pressure=140000.0,
    gamma=1.4,
  )
  interior = coupled_euler._conservative_from_primitive(
    density=1.0,
    velocity_u=165.0,
    velocity_v=10.0,
    pressure=150000.0,
    gamma=1.4,
  )

  resolved = coupled_euler._subsonic_characteristic_inlet_state(
    interior,
    reference,
    gamma=1.4,
    gas_constant=287.05,
  )
  reference_rho, reference_u, reference_v, reference_pressure, reference_temperature, reference_sound = (
    coupled_euler._primitive_from_conservative(reference, 1.4, 287.05)
  )
  resolved_rho, resolved_u, resolved_v, resolved_pressure, resolved_temperature, resolved_sound = (
    coupled_euler._primitive_from_conservative(resolved, 1.4, 287.05)
  )
  _interior_rho, interior_u, _interior_v, _interior_pressure, _interior_temperature, interior_sound = (
    coupled_euler._primitive_from_conservative(interior, 1.4, 287.05)
  )
  reference_speed = (reference_u * reference_u + reference_v * reference_v) ** 0.5
  resolved_speed = (resolved_u * resolved_u + resolved_v * resolved_v) ** 0.5
  reference_mach = reference_speed / reference_sound
  resolved_mach = resolved_speed / resolved_sound
  reference_total_pressure = reference_pressure * (
    1.0 + 0.5 * (1.4 - 1.0) * reference_mach * reference_mach
  ) ** (1.4 / (1.4 - 1.0))
  resolved_total_pressure = resolved_pressure * (
    1.0 + 0.5 * (1.4 - 1.0) * resolved_mach * resolved_mach
  ) ** (1.4 / (1.4 - 1.0))
  reference_total_temperature = reference_temperature * (
    1.0 + 0.5 * (1.4 - 1.0) * reference_mach * reference_mach
  )
  resolved_total_temperature = resolved_temperature * (
    1.0 + 0.5 * (1.4 - 1.0) * resolved_mach * resolved_mach
  )

  assert resolved_rho > 0.0
  assert resolved_total_pressure == pytest.approx(reference_total_pressure)
  assert resolved_total_temperature == pytest.approx(reference_total_temperature)
  assert resolved_v / resolved_u == pytest.approx(reference_v / reference_u)
  assert resolved_u - 2.0 * resolved_sound / (1.4 - 1.0) == pytest.approx(
    interior_u - 2.0 * interior_sound / (1.4 - 1.0),
  )
####


def test_coupled_euler_request_retains_the_explicit_inlet_boundary_mode():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode.SUBSONIC_CHARACTERISTIC
    ),
  )

  assert request.inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode.SUBSONIC_CHARACTERISTIC
  )
  assert request.as_report()['inlet_boundary_mode'] == (
    'subsonic-characteristic'
  )
  assert request.downstream_length_m is None
  assert request.effective_downstream_length_m == pytest.approx(
    mixed_request.downstream_length_m
  )

  extended = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    downstream_length_m=0.6,
  )
  assert extended.downstream_length_m == pytest.approx(0.6)
  assert extended.effective_downstream_length_m == pytest.approx(0.6)
  assert extended.as_report()['effective_downstream_length_m'] == pytest.approx(
    0.6
  )
  with pytest.raises(ValueError, match='downstream_length_m'):
    build_reflected_domain_coupled_euler_free_boundary_request(
      mixed_request,
      reference_total_temperature_K=1500.0,
      downstream_length_m=0.0,
    )
  ####
####


def test_subsonic_characteristic_coupled_field_is_independently_auditable():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  compatible_request = replace(
    mixed_request,
    ambient_pressure_Pa=mixed_request.control_section.samples[-1].static_pressure_Pa,
  )
  request = build_reflected_domain_coupled_euler_free_boundary_request(
    compatible_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode.SUBSONIC_CHARACTERISTIC
    ),
  )

  result = solve_reflected_domain_coupled_euler_free_boundary(request)
  audit = measure_reflected_domain_coupled_euler_free_boundary(result)

  assert result.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .CONVERGED_LOCAL_PHYSICAL_CLOSURE
  )
  assert audit.status is MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.CONVERGED_LOCAL_AUDIT
  assert audit.converged
  assert audit.residual_report_verified
  assert result.canonical_euler_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_scalar_normal_shock_branch_field_is_locally_auditable_without_global_promotion():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  baseline_request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
  )
  transition = assess_reflected_domain_coupled_euler_transonic_transition(
    baseline_request
  )
  assert transition.shock_state is not None
  geometry_request = MocTransonicShockGeometryRequest(
    shock_state=transition.shock_state,
    shock_point_m=(mixed_request.control_section.points_m[0][0], 0.025),
    shock_normal_angle_rad=0.0,
  )
  request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
    outlet_static_pressure_Pa=mixed_request.ambient_pressure_Pa,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode.SCALAR_NORMAL_SHOCK_BRANCH
    ),
    transonic_shock_geometry=geometry_request,
  )

  result = solve_reflected_domain_coupled_euler_free_boundary(request)
  audit = measure_reflected_domain_coupled_euler_free_boundary(result)

  assert request.as_report()['inlet_boundary_mode'] == (
    'scalar-normal-shock-branch'
  )
  assert result.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .CONVERGED_LOCAL_PHYSICAL_CLOSURE
  )
  assert result.transonic_shock_geometry is not None
  assert result.transonic_shock_geometry.status is (
    MocTransonicShockGeometryStatus.VERIFIED
  )
  assert result.transonic_shock_geometry_audit is not None
  assert result.transonic_shock_geometry_audit.converged
  assert result.local_physical_closure_verified
  assert audit.status is MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.CONVERGED_LOCAL_AUDIT
  assert audit.transonic_shock_geometry_verified
  assert audit.local_consistency_verified
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_scalar_normal_shock_branch_requires_inlet_geometry_and_rejects_bad_binding():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  with pytest.raises(ValueError, match='requires transonic_shock_geometry'):
    build_reflected_domain_coupled_euler_free_boundary_request(
      mixed_request,
      reference_total_temperature_K=1500.0,
      inlet_boundary_mode=(
        MocReflectedDomainCoupledEulerInletBoundaryMode.SCALAR_NORMAL_SHOCK_BRANCH
      ),
    )
  ####

  baseline_request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
  )
  transition = assess_reflected_domain_coupled_euler_transonic_transition(
    baseline_request
  )
  assert transition.shock_state is not None
  bad_geometry = MocTransonicShockGeometryRequest(
    shock_state=transition.shock_state,
    shock_point_m=(mixed_request.control_section.points_m[0][0] + 0.01, 0.025),
    shock_normal_angle_rad=0.0,
  )
  request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode.SCALAR_NORMAL_SHOCK_BRANCH
    ),
    transonic_shock_geometry=bad_geometry,
  )

  result = solve_reflected_domain_coupled_euler_free_boundary(request)

  assert result.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus.INLET_SHOCK_BRANCH_FAILURE
  )
  assert result.converged is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def _shock_interface_profile_for_control_section(mixed_request, *, x_offset=0.0):
  gamma = float(mixed_request.control_section.samples[0].gamma)
  points = tuple(
    (point[0] + x_offset, point[1])
    for point in mixed_request.control_section.points_m
  )
  upstream_mach = 2.0
  downstream_mach = 0.6
  upstream_total_pressure = 1.2e6
  downstream_total_pressure = 0.95e6

  def static_pressure(total_pressure, mach):
    factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
    return total_pressure / factor ** (gamma / (gamma - 1.0))
  ####

  upstream_sample = tuple(
    MocTransonicShockInterfaceSample(
      point_m=point,
      mach=upstream_mach,
      flow_angle_rad=0.0,
      static_pressure_Pa=static_pressure(upstream_total_pressure, upstream_mach),
      total_pressure_Pa=upstream_total_pressure,
      gamma=gamma,
    )
    for point in points
  )
  downstream_sample = tuple(
    MocTransonicShockInterfaceSample(
      point_m=point,
      mach=downstream_mach,
      flow_angle_rad=0.0,
      static_pressure_Pa=static_pressure(downstream_total_pressure, downstream_mach),
      total_pressure_Pa=downstream_total_pressure,
      gamma=gamma,
    )
    for point in points
  )
  return MocTransonicShockInterfaceProfile(
    upstream_samples=upstream_sample,
    downstream_samples=downstream_sample,
    interface_normal_angle_rad=0.0,
  )
####


def test_coupled_euler_consumes_audited_spatial_shock_interface_profile():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  profile = _shock_interface_profile_for_control_section(mixed_request)
  profile_audit = measure_moc_transonic_shock_interface_profile(profile)
  assert profile_audit.status is (
    MocTransonicShockInterfaceProfileAuditStatus.VERIFIED
  )
  assert profile_audit.converged
  request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=20,
    max_shape_iterations=1,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .AUDITED_SHOCK_INTERFACE_PROFILE
    ),
    transonic_shock_interface_profile=profile,
  )

  result = solve_reflected_domain_coupled_euler_free_boundary(request)
  audit = measure_reflected_domain_coupled_euler_free_boundary(result)

  assert result.status is not (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_PROFILE_FAILURE
  )
  assert result.transonic_shock_interface_profile == profile
  assert result.transonic_shock_interface_profile_consumed
  assert result.as_report()['transonic_shock_interface_profile_consumed'] is True
  assert audit.transonic_shock_interface_profile_verified
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_coupled_euler_profile_rejects_interior_handoff_without_projection():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  profile = _shock_interface_profile_for_control_section(mixed_request, x_offset=0.02)
  request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .AUDITED_SHOCK_INTERFACE_PROFILE
    ),
    transonic_shock_interface_profile=profile,
  )

  result = solve_reflected_domain_coupled_euler_free_boundary(request)
  audit = measure_reflected_domain_coupled_euler_free_boundary(result)

  assert result.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_PROFILE_FAILURE
  )
  assert result.transonic_shock_interface_profile == profile
  assert result.transonic_shock_interface_profile_consumed is False
  assert audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
    .TRANSONIC_SHOCK_INTERFACE_PROFILE_FAILURE
  )
  assert 'interior to the field' in result.message
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_coupled_euler_interior_profile_starts_a_bound_downstream_field():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  profile = _shock_interface_profile_for_control_section(
    mixed_request,
    x_offset=0.02,
  )
  request = build_reflected_domain_coupled_euler_free_boundary_request(
    mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=20,
    max_shape_iterations=1,
    inlet_boundary_mode=(
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE
    ),
    transonic_shock_interface_profile=profile,
  )

  result = solve_reflected_domain_coupled_euler_free_boundary(request)
  audit = measure_reflected_domain_coupled_euler_free_boundary(result)

  assert result.status is not (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_PROFILE_FAILURE
  )
  assert result.x_stations_m[0] == pytest.approx(profile.cross_section_x_m)
  assert result.free_boundary_points_m[0][1] == pytest.approx(
    profile.upper_ordinate_m
  )
  assert result.transonic_shock_interface_profile == profile
  assert result.transonic_shock_interface_profile_consumed
  assert audit.transonic_shock_interface_profile_verified
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
####


def test_coupled_euler_entropy_gate_allows_production_but_rejects_loss():
  inlet = coupled_euler._conservative_from_primitive(
    1.0,
    100.0,
    0.0,
    100000.0,
    1.4,
  )
  production = coupled_euler._conservative_from_primitive(
    0.95,
    100.0,
    0.0,
    100000.0,
    1.4,
  )
  loss = coupled_euler._conservative_from_primitive(
    1.1,
    100.0,
    0.0,
    100000.0,
    1.4,
  )
  production_loss, production_gain, production_verified = (
    coupled_euler._entropy_diagnostics(
      np.asarray((production,)),
      (inlet,),
      1.4,
      287.05,
    )
  )
  loss_residual, loss_gain, loss_verified = coupled_euler._entropy_diagnostics(
    np.asarray((loss,)),
    (inlet,),
    1.4,
    287.05,
  )

  assert production_loss == pytest.approx(0.0)
  assert production_gain > 0.0
  assert production_verified
  assert loss_residual > 0.05
  assert loss_gain == pytest.approx(0.0)
  assert not loss_verified
####


def test_global_coupled_euler_free_boundary_converges_only_for_compatible_research_case():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  compatible_request = replace(
    mixed_request,
    ambient_pressure_Pa=mixed_request.control_section.samples[-1].static_pressure_Pa,
  )
  coupled_request = MocReflectedDomainCoupledEulerFreeBoundaryRequest(
    mixed_regime_request=compatible_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
  )

  result = solve_reflected_domain_coupled_euler_free_boundary(coupled_request)

  assert result.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONVERGED_LOCAL_PHYSICAL_CLOSURE
  )
  assert result.converged
  assert result.physical_closure_verified
  assert result.coupled_euler_field_verified
  assert result.free_boundary_condition_verified
  assert result.entropy_transport_verified
  assert result.subsonic_pressure_budget is not None
  assert result.subsonic_pressure_budget.status is (
    MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
    .WITHIN_ISENTROPIC_SUBSONIC_BOUNDS
  )
  assert result.transonic_transition is not None
  assert result.transonic_transition.status is (
    MocTransonicTransitionStatus.TARGET_REACHABLE_WITHOUT_SHOCK
  )
  assert result.transonic_transition_audit is not None
  assert result.transonic_transition_audit.converged
  assert result.transonic_transition.shock_state is None
  assert result.transonic_transition_audit.shock_state_verified
  assert result.control_section_compatibility is not None
  assert result.control_section_compatibility.status is (
    MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus
    .PRESSURE_MATCHED
  )
  assert result.control_section_compatibility.pressure_seam_matched
  assert result.control_section_compatibility.absolute_pressure_jump_Pa == pytest.approx(
    0.0
  )
  assert result.transonic_frontier_compatibility is not None
  assert result.transonic_frontier_compatibility.status is (
    MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
    .NOT_REQUIRED
  )
  assert result.transonic_frontier_compatibility.frontier_sample_count == 9
  assert result.transonic_frontier_compatibility.frontier_state_compatible is False
  direct_budget = assess_reflected_domain_coupled_euler_subsonic_pressure_budget(
    coupled_request
  )
  assert direct_budget == result.subsonic_pressure_budget
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert len(result.free_boundary_points_m) == 9
  assert len(result.conservative_states_by_cell) == 32
  assert result.residual_channel_coverage == {
    'mass': True,
    'streamwise_momentum': True,
    'transverse_momentum': True,
    'energy': True,
    'euler': True,
  }
  assert len(result.cell_vertices_by_cell_m) == len(
    result.conservative_states_by_cell
  )
  assert result.as_report()['claim_status'].startswith('research-only')
  audit = measure_reflected_domain_coupled_euler_free_boundary(result)
  assert audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.CONVERGED_LOCAL_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.residual_channels_recomputed
  assert audit.residual_report_verified
  assert audit.free_boundary_report_verified
  assert audit.pressure_budget_verified
  assert audit.control_section_compatibility_verified
  assert audit.promotion_flags_verified
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False
####


def test_global_coupled_euler_free_boundary_refinement_keeps_actual_seam_open():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  coupled_request = MocReflectedDomainCoupledEulerFreeBoundaryRequest(
    mixed_regime_request=mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=8,
  )

  run = run_reflected_domain_coupled_euler_free_boundary_refinement(
    coupled_request,
    ((6, 3), (8, 4), (10, 5)),
  )

  assert run.requested_resolutions == ((6, 3), (8, 4), (10, 5))
  assert len(run.cases) == 3
  assert run.fresh_solver_invocation_verified
  assert run.fidelity_isolation_verified
  assert run.measurement.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.CASE_FAILURE
  )
  assert run.measurement.resolution_order_verified
  assert run.measurement.mesh_growth_verified
  assert run.measurement.case_audits_verified
  assert run.measurement.conservative_residuals_finite
  assert run.measurement.boundary_diagnostics_finite
  assert run.measurement.pressure_budget_diagnostics_verified
  assert run.measurement.entropy_production_maps_verified
  assert len(run.measurement.maximum_entropy_production_fractions) == 3
  assert run.measurement.local_closure_verified is False
  assert run.measurement.fidelity_isolation_verified
  assert run.measurement.physical_closure_verified is False
  assert run.measurement.canonical_euler_verified is False
  assert run.measurement.external_validation_verified is False
  assert run.measurement.chain_promotion_blocked
  assert run.measurement.production_claim_allowed is False
  assert run.production_claim_allowed is False
  assert len(run.configuration_fingerprint) == 64
  assert all(
    case.audit.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE
    )
    for case in run.cases
  )
####


def test_global_coupled_euler_free_boundary_compatible_refinement_is_local_only():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  compatible_request = replace(
    mixed_request,
    ambient_pressure_Pa=mixed_request.control_section.samples[-1].static_pressure_Pa,
  )
  coupled_request = MocReflectedDomainCoupledEulerFreeBoundaryRequest(
    mixed_regime_request=compatible_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
  )

  run = run_reflected_domain_coupled_euler_free_boundary_refinement(
    coupled_request,
    ((6, 3), (8, 4)),
  )

  assert run.measurement.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus
    .CONVERGED_RESEARCH_LADDER
  )
  assert run.measurement.converged
  assert run.measurement.local_consistency_verified
  assert run.measurement.resolution_order_verified
  assert run.measurement.mesh_growth_verified
  assert run.measurement.case_audits_verified
  assert run.measurement.conservative_residuals_finite
  assert run.measurement.boundary_diagnostics_finite
  assert run.measurement.pressure_budget_diagnostics_verified
  assert run.measurement.entropy_production_maps_verified
  assert len(run.measurement.maximum_entropy_production_fractions) == 2
  assert run.measurement.local_closure_verified
  assert run.measurement.fidelity_isolation_verified
  assert run.measurement.physical_closure_verified is False
  assert run.measurement.canonical_free_boundary_verified is False
  assert run.measurement.canonical_euler_verified is False
  assert run.measurement.external_validation_verified is False
  assert run.measurement.chain_promotion_blocked
  assert run.measurement.production_claim_allowed is False
  reversed_measurement = measure_reflected_domain_coupled_euler_free_boundary_refinement(
    tuple(reversed(run.cases))
  )
  assert reversed_measurement.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryRefinementStatus.RESOLUTION_FAILURE
  )
  assert not reversed_measurement.converged
####


def test_coupled_euler_pressure_continuation_reconciles_boundary_seam_without_promotion():
  closure = _global_physical_closure_for_mixed_regime()
  mixed_request = build_reflected_domain_mixed_regime_boundary_request(closure)
  coupled_request = MocReflectedDomainCoupledEulerFreeBoundaryRequest(
    mixed_regime_request=mixed_request,
    reference_total_temperature_K=1500.0,
    axial_cell_count=8,
    transverse_cell_count=4,
    max_pseudo_iterations=400,
    max_shape_iterations=12,
  )
  compatible_pressure = (
    mixed_request.control_section.samples[-1].static_pressure_Pa
  )
  actual_pressure = mixed_request.ambient_pressure_Pa

  run = run_reflected_domain_coupled_euler_pressure_continuation(
    coupled_request,
    (compatible_pressure, actual_pressure),
  )

  assert run.requested_target_ambient_pressures_Pa == (
    compatible_pressure,
    actual_pressure,
  )
  assert run.fresh_solver_invocation_verified
  assert run.fidelity_isolation_verified
  assert run.source_closure_fingerprint == mixed_request.closure_fingerprint
  assert run.measurement.status is (
    MocReflectedDomainCoupledEulerPressureContinuationStatus.CASE_FAILURE
  )
  assert run.measurement.pressure_order_verified
  assert run.measurement.source_closure_identity_verified
  assert run.measurement.case_audits_verified
  assert run.measurement.diagnostics_finite
  assert run.measurement.pressure_budget_trend_verified
  assert run.measurement.independent_evidence_verified
  assert run.measurement.local_closure_verified is False
  assert run.independent_evidence_verified
  assert run.converged is False
  assert run.production_claim_allowed is False
  assert run.measurement.chain_promotion_blocked
  assert run.measurement.physical_closure_verified is False
  assert run.measurement.canonical_euler_verified is False
  assert run.measurement.external_validation_verified is False
  assert run.measurement.minimum_additional_total_pressure_loss_fractions[0] == (
    pytest.approx(0.0)
  )
  assert run.measurement.minimum_additional_total_pressure_loss_fractions[1] > 0.4
  assert run.cases[0].local_closure_verified
  assert run.cases[1].local_closure_verified is False
  assert run.cases[1].audit.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
    .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE
  )
  assert run.as_report()['measurement']['independent_evidence_verified']
  assert run.as_report()['cases'][1]['target_ambient_pressure_Pa'] == pytest.approx(
    actual_pressure
  )

  reversed_measurement = measure_reflected_domain_coupled_euler_pressure_continuation(
    tuple(reversed(run.cases))
  )
  assert reversed_measurement.status is (
    MocReflectedDomainCoupledEulerPressureContinuationStatus.PRESSURE_ORDER_FAILURE
  )
  assert reversed_measurement.pressure_order_verified is False
  assert reversed_measurement.source_closure_identity_verified
  assert reversed_measurement.case_audits_verified
  assert reversed_measurement.independent_evidence_verified is False
####


def test_global_physical_closure_rejects_evidence_for_a_different_field():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  closure = solve_reflected_domain_global_physical_closure(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )
  assert closure.physical_closure_verified
  assert closure.global_euler is not None
  changed_euler = replace(closure.global_euler, message='different-run')
  changed_closure = replace(closure, global_euler=changed_euler)
  evidence = MocReflectedDomainPromotionEvidence(
    closure_fingerprint=(
      moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ),
    refinement_evidence_id='refinement-run-test-global-euler-9',
  )

  with pytest.raises(ValueError, match='does not match'):
    changed_closure.bind_promotion_evidence(evidence)
  ####
####


def test_global_physical_closure_requires_evidence_for_promoted_gate():
  with pytest.raises(ValueError, match='matching promotion evidence'):
    replace(
      MocReflectedDomainGlobalPhysicalClosureResult(
        status=MocReflectedDomainGlobalPhysicalClosureStatus.INVALID_INPUT,
        source_band=None,
        global_remesh=None,
        global_euler=None,
      ),
      refinement_verified=True,
    )
  ####
####


def test_production_shock_cell_fit_requires_the_exact_typed_frontier():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  closure = solve_reflected_domain_global_physical_closure(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )
  assert closure.global_euler is not None
  assert closure.global_euler.physical_field is not None
  closed_field = closure.global_euler.physical_field.field
  bad_frontier = tuple(
    replace(sample, total_pressure_Pa=sample.total_pressure_Pa * 1.001)
    if index == 0
    else sample
    for index, sample in enumerate(closure.incoming_handoff)
  )

  fit = fit_reflected_domain_production_shock_cell(
    closure,
    start_x_m=0.5,
    end_x_m=closed_field.ambient_boundary_points_m[-1][0] + 0.05,
    incoming_frontier=bad_frontier,
  )

  assert fit.status is MocProductionShockCellFitStatus.FRONTIER_FAILURE
  assert fit.frontier_verified is False
  assert fit.candidate_cell is None
  assert fit.production_claim_allowed is False
####


def test_global_euler_field_can_seed_a_research_continued_chain_reference():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  global_remesh = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )
  global_result = solve_reflected_domain_global_euler_shock_boundary(
    global_remesh,
  )
  assert global_result.converged
  assert global_result.physical_field is not None
  assert global_result.physical_field.field is not None

  planner = plan_reflected_domain_global_euler_continued_chain_reference(
    global_result,
    start_x_m=0.5,
    end_x_m=(
      global_result.physical_field.field.ambient_boundary_points_m[-1][0]
      + 6.0
    ),
    reference=MocTerminalReflectionPatchAmbientClosureChainReference(
      total_cell_count=2,
    ),
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 2
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.chain.physical_termination is False
  assert planner.handoff_links_verified is True
  assert planner.production_claim_allowed is False
  assert planner.diagnostics[
    'global_euler_continued_chain_source_measurement'
  ]['checks']['incoming_handoff_verified'] is True
  assert planner.diagnostics[
    'global_euler_continued_chain_independent_measurement'
  ]['handoff']['links_verified'] is True
  assert planner.diagnostics[
    'global_euler_continued_chain_audit_accepted'
  ] is True
  assert planner.diagnostics[
    'global_euler_continued_chain_research_physical_cell_count'
  ] == 1
  assert planner.diagnostics[
    'global_euler_continued_chain_fidelity_transition'
  ].startswith('global-exact-euler-local-research-seed')
  assert planner.diagnostics['chain_promotion_blocked'] is True
  assert planner.diagnostics['canonical_euler_verified'] is False
####


def test_global_euler_fresh_source_continuation_re_solves_each_cell():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  global_remesh = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )
  global_result = solve_reflected_domain_global_euler_shock_boundary(
    global_remesh,
  )
  assert global_result.converged
  assert global_result.physical_field is not None
  assert global_result.physical_field.field is not None

  seed_end_x_m = (
    global_result.physical_field.field.ambient_boundary_points_m[-1][0]
  )
  planner = plan_reflected_domain_global_euler_continued_chain(
    global_result,
    start_x_m=0.5,
    end_x_m=seed_end_x_m + 8.0,
    reference=MocGlobalEulerContinuedChainReference(
      total_cell_count=3,
      outer_source_indices=(0,),
      target_centerline_indices=(1,),
      compression_envelope_skews=(-0.75,),
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(
      max_cells=4,
      require_state_carry=True,
    ),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.chain.physical_termination is False
  assert planner.handoff_links_verified is True
  assert planner.production_claim_allowed is False

  steps = planner.diagnostics[
    'global_euler_continued_chain_steps'
  ]
  assert len(steps) == 2
  assert all(step['accepted'] for step in steps)
  assert all(
    step['global_shock_remesh_measurement']['status'] == 'converged'
    and step['global_euler_measurement']['status'] == 'converged'
    and step['intercell_bridge']['verified']
    for step in steps
  )
  fingerprints = planner.diagnostics[
    'global_euler_continued_chain_source_band_fingerprints'
  ]
  assert len(fingerprints) == 2
  assert len(set(fingerprints)) == 2
  assert planner.diagnostics[
    'global_euler_continued_chain_captured_field_count'
  ] == 3
  assert planner.diagnostics[
    'global_euler_continued_chain_independent_measurement'
  ]['status'] == 'converged'
  assert planner.diagnostics[
    'global_euler_continued_chain_independent_measurement'
  ]['intercell_bridges']['verified'] is True
  assert planner.diagnostics[
    'global_euler_continued_chain_planner_measurement'
  ]['status'] == 'converged'
  assert planner.diagnostics[
    'global_euler_continued_chain_audit_accepted'
  ] is True
  assert planner.diagnostics['chain_promotion_blocked'] is True
  assert planner.diagnostics['canonical_euler_verified'] is False
####


def test_global_euler_continued_chain_reference_rejects_unaudited_seed():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(patch, ambient_pressure)
  global_remesh = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )
  global_result = solve_reflected_domain_global_euler_shock_boundary(
    global_remesh,
  )
  tampered = replace(global_result, source_frontier_verified=False)

  with pytest.raises(ValueError, match='locally converged global field'):
    plan_reflected_domain_global_euler_continued_chain_reference(
      tampered,
      start_x_m=0.5,
      end_x_m=8.0,
    )
  ####
####


def test_global_euler_shock_boundary_refinement_audits_resolution_ladder():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(patch, ambient_pressure)
  cases = []
  for resolution in (5, 9, 11):
    global_result = solve_reflected_domain_global_shock_remesh(
      source,
      outer_source_indices=(2,),
      target_centerline_indices=(3,),
      compression_amplitude_lower_rad=0.007,
      compression_amplitude_upper_rad=0.03,
      compression_envelope_skews=(0.0,),
      sample_count=resolution,
      shock_angle_tolerance_rad=0.02,
    )
    cases.append(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementCase(
        resolution=resolution,
        result=solve_reflected_domain_global_euler_shock_boundary(
          global_result,
        ),
      )
    )
  ####

  measurement = measure_moc_reflected_domain_global_euler_shock_boundary_refinement(
    tuple(cases),
  )

  assert measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.local_consistency_verified
  assert measurement.resolutions == (5, 9, 11)
  assert measurement.shock_sample_counts == (5, 9, 11)
  assert measurement.field_cell_counts == (19, 53, 76)
  assert measurement.residual_nonincreasing_verified
  assert measurement.residual_decrease_verified
  assert measurement.endpoint_tangents_verified
  assert measurement.source_frontier_convergence_verified
  assert measurement.physical_closure_verified
  assert measurement.fidelity_isolation_verified
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert measurement.as_report()['canonical_euler_verified'] is False
  assert measurement.as_report()['external_validation_verified'] is False

  tampered_cases = (
    *cases[:-1],
    replace(
      cases[-1],
      result=replace(
        cases[-1].result,
        first_endpoint_tangent_residual_rad=0.25,
      ),
    ),
  )
  tampered_measurement = (
    measure_moc_reflected_domain_global_euler_shock_boundary_refinement(
      tampered_cases,
    )
  )
  assert tampered_measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.CASE_FAILURE
  )
  assert tampered_measurement.case_audits_verified is False
  assert tampered_measurement.audits[-1].endpoint_tangents_verified is False
  assert tampered_measurement.converged is False
####


def test_global_euler_refinement_runner_reexecutes_each_resolution_without_promotion():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(patch, ambient_pressure)

  run = run_moc_reflected_domain_global_euler_shock_boundary_refinement(
    source,
    (5, 9, 11),
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(0.0,),
    shock_angle_tolerance_rad=0.02,
  )

  assert isinstance(
    run,
    MocReflectedDomainGlobalEulerShockBoundaryRefinementRun,
  )
  assert run.requested_resolutions == (5, 9, 11)
  assert len(run.closures) == 3
  assert len(run.cases) == 3
  assert run.fresh_solver_invocation_verified
  assert run.local_physical_closure_verified
  assert run.fidelity_isolation_verified
  assert run.measurement.converged
  assert run.local_consistency_verified
  assert run.chain_promotion_blocked
  assert run.production_claim_allowed is False
  assert len(run.source_band_fingerprint) == 64
  assert len(run.configuration_fingerprint) == 64
  report = run.as_report()
  assert report['requested_resolutions'] == [5, 9, 11]
  assert report['configuration']['requested_resolutions'] == [5, 9, 11]
  assert report['checks']['chain_promotion_blocked'] is True
  assert report['checks']['production_claim_allowed'] is False
####


def test_global_euler_refinement_runner_retains_missing_resolution_as_failure():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(patch, ambient_pressure)

  run = run_moc_reflected_domain_global_euler_shock_boundary_refinement(
    source,
    (1,),
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_envelope_skews=(0.0,),
  )

  assert run.fresh_solver_invocation_verified
  assert run.cases == ()
  assert run.measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.CASE_FAILURE
  )
  assert run.local_consistency_verified is False
  assert run.chain_promotion_blocked
  assert run.as_report()['closures'][0]['global_euler_retained'] is False
####


def test_global_euler_cross_case_measurement_rejects_duplicate_source_inputs():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(patch, ambient_pressure)
  single_run = run_moc_reflected_domain_global_euler_shock_boundary_refinement(
    source,
    (5, 9),
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_envelope_skews=(0.0,),
    shock_angle_tolerance_rad=0.02,
  )
  cases = (
    MocReflectedDomainGlobalEulerShockBoundaryCrossCase(
      case_id='reflected-a',
      regime='reflected',
      source_band=source,
      resolutions=(5, 9),
    ),
    MocReflectedDomainGlobalEulerShockBoundaryCrossCase(
      case_id='reflected-b',
      regime='reflected',
      source_band=source,
      resolutions=(5, 9),
    ),
  )

  measurement = (
    measure_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement(
      cases,
      (single_run, single_run),
    )
  )

  assert measurement.status is (
    MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus.SOURCE_FAILURE
  )
  assert measurement.case_ids_verified
  assert measurement.source_bindings_verified
  assert measurement.distinct_source_band_fingerprints_verified is False
  assert measurement.converged is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  report = measurement.as_report()
  assert report['physical_closure_verified'] is False
  assert report['external_validation_verified'] is False
####


def test_global_euler_cross_case_runner_keeps_case_ladders_separate():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  reflected_source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    source_sample_count=6,
  )
  resampled_source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    source_sample_count=7,
  )
  cases = (
    MocReflectedDomainGlobalEulerShockBoundaryCrossCase(
      case_id='reflected-source',
      regime='reflected',
      source_band=reflected_source,
      resolutions=(5, 9),
    ),
    MocReflectedDomainGlobalEulerShockBoundaryCrossCase(
      case_id='mild-attached-source',
      regime='mild-attached',
      source_band=resampled_source,
      resolutions=(5, 9),
    ),
  )

  run = (
    run_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement(
      cases,
      outer_source_indices=(2,),
      target_centerline_indices=(3,),
      compression_envelope_skews=(0.0,),
      shock_angle_tolerance_rad=0.02,
    )
  )

  assert len(run.runs) == 2
  assert run.fresh_solver_invocation_verified
  assert run.runs[0].source_band_fingerprint != run.runs[1].source_band_fingerprint
  assert run.measurement.case_ids == (
    'reflected-source',
    'mild-attached-source',
  )
  assert run.measurement.requested_resolutions == ((5, 9), (5, 9))
  assert run.measurement.distinct_source_band_fingerprints_verified
  assert run.downstream_boundary_closure_verified is False
  assert run.as_report()['checks']['downstream_boundary_closure_verified'] is False
  downstream_models = run.as_report()['measurement']['downstream_boundary_models']
  assert len(downstream_models) == 2
  assert all(len(models) == 2 for models in downstream_models)
  assert all(
    isinstance(model, str) and model
    for models in downstream_models
    for model in models
  )
  assert all(
    closure['downstream_boundary_closure_verified'] is False
    and closure['downstream_boundary_model']
    and closure['promotion_blockers']
    and closure['production_promotion_gates']['downstream_boundary_closure_verified'] is False
    for case_run in run.as_report()['runs']
    for closure in case_run['closures']
  )
  assert run.chain_promotion_blocked
  assert run.production_claim_allowed is False
  assert run.as_report()['measurement']['external_validation_verified'] is False
####


def test_global_euler_shock_boundary_rejects_invalid_tolerance_as_typed_result():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(patch, ambient_pressure)
  global_result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(0.0,),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
  )

  result = solve_reflected_domain_global_euler_shock_boundary(
    global_result,
    pressure_tolerance=0.0,
  )

  assert result.status is MocReflectedDomainGlobalEulerShockBoundaryStatus.INVALID_INPUT
  assert result.converged is False
  assert result.global_remesh is global_result
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.INVALID_INPUT
  )
####


def test_global_reflected_shock_remesh_rejects_duplicate_profile_shapes():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(0,),
    target_centerline_indices=(1,),
    compression_envelope_skews=(0.0, 0.0),
  )

  assert result.status is MocReflectedDomainGlobalShockRemeshStatus.INVALID_INPUT
  assert result.attempts == ()
  measurement = measure_moc_reflected_domain_global_shock_remesh(result)
  assert measurement.status is (
    MocReflectedDomainGlobalShockRemeshMeasurementStatus.INVALID_INPUT
  )
  assert measurement.converged is False
####


def test_global_reflected_shock_remesh_retains_invalid_attempts_without_bridging_them():
  _field, patch = _patch()
  ambient_pressure = _field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  result = solve_reflected_domain_global_shock_remesh(
    source,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0, 0.75),
    sample_count=9,
    # Keep this fixture a mixed valid/invalid attempt case with an explicit
    # geometry gate rather than relying on platform-specific last-bit drift.
    shock_angle_tolerance_rad=0.008,
  )

  assert result.status is MocReflectedDomainGlobalShockRemeshStatus.ATTEMPT_FAILURE
  assert result.attempt_count == 3
  assert result.selected_attempt_index is not None
  assert result.selected_residual_m is not None
  assert any(
    attempt.first_cell_result.status is MocReflectedDomainSolverOwnedFirstCellStatus.FIELD_FAILURE
    for attempt in result.attempts
  )
  measurement = measure_moc_reflected_domain_global_shock_remesh(result)
  assert measurement.status is (
    MocReflectedDomainGlobalShockRemeshMeasurementStatus.ATTEMPT_FAILURE
  )
  assert measurement.attempt_identity_verified
  assert measurement.attempt_shape_verified is False
  assert measurement.no_endpoint_closure_verified is False
  assert measurement.chain_promotion_blocked
####


def test_global_reflected_shock_remesh_planner_preserves_research_stop():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  handoff = _handoff(field)
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=handoff,
  )
  planner = plan_reflected_domain_global_shock_remesh_chain(
    field,
    source,
    start_x_m=0.5,
    end_x_m=1.0,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )
  assert planner.chain.physical_termination is False
  assert planner.diagnostics[
    'global_reflected_shock_remesh_seed_handoff_verified'
  ] is True
  assert planner.diagnostics['global_reflected_shock_remesh_audit_accepted'] is True
  assert planner.diagnostics[
    'global_reflected_shock_remesh_euler_audit_accepted'
  ] is False
  euler_audits = planner.diagnostics[
    'global_reflected_shock_remesh_euler_audits'
  ]
  assert len(euler_audits) == 2
  assert all(
    row['field_available']
    and row['audit']['status'] == 'euler_audit_shock_jump_failure'
    for row in euler_audits
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_euler_boundary_accepted'
  ] is False
  boundary_curves = planner.diagnostics[
    'global_reflected_shock_remesh_euler_boundary_curves'
  ]
  assert len(boundary_curves) == 2
  assert all(
    row['field_available']
    and row['curve'] is not None
    and row['curve']['chain_promotion_blocked']
    for row in boundary_curves
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_euler_geometry_reconciliation_accepted'
  ] is True
  geometry_reconciliations = planner.diagnostics[
    'global_reflected_shock_remesh_euler_geometry_reconciliations'
  ]
  assert len(geometry_reconciliations) == 2
  assert all(
    row['field_available']
    and row['geometry_reconciliation']['status'] == 'converged_local_euler_shock'
    and row['geometry_reconciliation']['local_euler_verified']
    and row['geometry_reconciliation']['orientation'] == (
      'mixed-characteristic-boundary'
    )
    for row in geometry_reconciliations
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_euler_ambient_physical_field_accepted'
  ] is False
  ambient_physical_fields = planner.diagnostics[
    'global_reflected_shock_remesh_euler_ambient_physical_fields'
  ]
  assert len(ambient_physical_fields) == 2
  assert all(
    row['field_available']
    and row['geometry_reconciliation_verified']
    and row['ambient_physical_field']['status'] == (
      'euler_physical_ambient_boundary_failure'
    )
    and not row['ambient_physical_field']['physical_closure_verified']
    for row in ambient_physical_fields
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_accepted'
  ] is True
  global_euler_closure = planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure'
  ]
  assert global_euler_closure['status'] == (
    'converged_global_euler_shock_field'
  )
  assert global_euler_closure['physical_closure_verified'] is True
  assert global_euler_closure['incoming_handoff_verified'] is True
  assert planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_independent_audit_accepted'
  ] is True
  global_euler_measurement = planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_independent_measurement'
  ]
  assert global_euler_measurement['status'] == 'converged'
  assert global_euler_measurement['checks']['source_frontier_verified'] is True
  assert global_euler_measurement['checks']['incoming_handoff_verified'] is True
  assert global_euler_measurement['checks']['physical_closure_verified'] is True
  assert planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_required_for_promotion'
  ] is True
  assert planner.diagnostics[
    'global_reflected_shock_remesh_independent_measurement'
  ]['status'] == 'converged'
  assert planner.production_claim_allowed is False
####


def test_global_reflected_shock_remesh_physical_field_adapter_derives_fresh_source():
  field = _canonical_field()
  planner = plan_reflected_domain_global_shock_remesh_chain_from_physical_field(
    field,
    start_x_m=0.5,
    end_x_m=1.0,
    outer_source_indices=(2,),
    target_centerline_indices=(3,),
    compression_amplitude_lower_rad=0.007,
    compression_amplitude_upper_rad=0.03,
    compression_envelope_skews=(-0.75, 0.0),
    sample_count=9,
    shock_angle_tolerance_rad=0.02,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_from_physical_field'
  ] is True
  assert planner.diagnostics['source_projection_automatic'] is True
  assert planner.diagnostics['source_projection_verified'] is True
  assert planner.diagnostics['source_projection_handoff_verified'] is True
  assert planner.diagnostics['source_projection_strip']['status'] == (
    'converged_open_shock_ambient_strip'
  )
  assert planner.diagnostics['source_projection_reflection_patch']['status'] == (
    'converged_open_terminal_reflection_patch'
  )
  assert planner.diagnostics['source_projection_source_band']['source_field_verified'] is True
  assert planner.diagnostics['global_reflected_shock_remesh']['status'] == (
    'global_reflected_shock_no_endpoint_closure'
  )
  assert planner.diagnostics[
    'global_reflected_shock_remesh_independent_measurement'
  ]['status'] == 'converged'
  assert planner.diagnostics[
    'global_reflected_shock_remesh_global_euler_closure_accepted'
  ] is True
  assert planner.diagnostics['physical_chain_cell_count'] == 0
  assert planner.diagnostics['chain_promotion_blocked'] is True
  assert planner.production_claim_allowed is False
####


def test_global_reflected_shock_remesh_physical_field_adapter_typed_projection_stop():
  field = _canonical_field()
  planner = plan_reflected_domain_global_shock_remesh_chain_from_physical_field(
    field,
    start_x_m=0.5,
    end_x_m=1.0,
    source_sample_count=2,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is MocChainTerminationReason.INVALID_INPUT
  assert planner.diagnostics['source_projection_automatic'] is True
  assert planner.diagnostics['source_projection_verified'] is False
  assert planner.diagnostics['source_projection_source_band']['status'] == (
    'invalid_input'
  )
  assert 'global_reflected_shock_remesh' not in planner.diagnostics
  assert planner.diagnostics['physical_chain_cell_count'] == 0
  assert planner.diagnostics['chain_promotion_blocked'] is True
  assert planner.production_claim_allowed is False
####


def test_reflected_domain_alternating_physical_field_chain_refinement_is_research_only():
  seed = _canonical_field()
  coarse = MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase(
    resolution=17,
    results=_alternating_physical_chain_results(seed, 17),
  )
  fine = MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase(
    resolution=33,
    results=_alternating_physical_chain_results(seed, 33),
  )

  measurement = (
    measure_moc_reflected_domain_alternating_physical_field_chain_refinement(
      (coarse, fine),
      endpoint_tolerance_m=1.0e-3,
      shock_spacing_tolerance_m=1.0e-4,
      area_tolerance_m2=1.5e-3,
      maximum_radius_tolerance_m=5.0e-4,
    )
  )

  assert measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.resolutions == (17, 33)
  assert measurement.field_count == 2
  assert measurement.resolution_order_verified
  assert measurement.resolution_metadata_verified
  assert measurement.field_count_consistent
  assert measurement.geometry_shape_verified
  assert measurement.solver_configuration_consistent
  assert measurement.source_geometry_freshness_verified
  assert measurement.pressure_loss_verified
  assert measurement.handoff_metadata_complete
  assert measurement.handoff_links_verified is True
  assert measurement.fresh_domain_verified
  assert measurement.refinement_convergence_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert measurement.as_report()['physical_closure_verified'] is False

  reversed_measurement = (
    measure_moc_reflected_domain_alternating_physical_field_chain_refinement(
      (fine, coarse),
    )
  )
  assert reversed_measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.RESOLUTION_FAILURE
  )
  assert reversed_measurement.converged is False

  shape_mismatch = MocReflectedDomainAlternatingPhysicalFieldChainRefinementCase(
    resolution=33,
    results=(fine.results[0],),
  )
  shape_measurement = (
    measure_moc_reflected_domain_alternating_physical_field_chain_refinement(
      (coarse, shape_mismatch),
    )
  )
  assert shape_measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainRefinementMeasurementStatus.CONSISTENCY_FAILURE
  )
  assert shape_measurement.field_count_consistent is False
  assert shape_measurement.converged is False
####


def test_reflected_domain_alternating_physical_field_rejects_unverified_source():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  corrupted = replace(
    source,
    status=MocReflectedDomainAlternatingSourceStatus.FIELD_FAILURE,
  )

  result = solve_reflected_domain_alternating_physical_field(
    corrupted,
    compression_amplitude_rad=0.05,
  )

  assert result.status is (
    MocReflectedDomainAlternatingPhysicalFieldStatus.SOURCE_FIELD_FAILURE
  )
  assert result.converged is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True

  measurement = measure_moc_reflected_domain_alternating_physical_field(result)
  assert measurement.converged is False
  assert measurement.source_field_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked is True
####


def test_reflected_domain_alternating_physical_field_chain_rejects_nonfresh_domain():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  first_source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert first_source.converged
  first_result = solve_reflected_domain_alternating_physical_field(
    first_source,
    compression_amplitude_rad=0.05,
    incoming_handoff=_handoff(field),
  )
  assert first_result.converged
  assert first_result.field is not None

  second_source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    source_sample_count=5,
    incoming_handoff=_handoff(first_result.field),
  )
  assert second_source.converged
  second_result = solve_reflected_domain_alternating_physical_field(
    second_source,
    compression_amplitude_rad=0.05,
    incoming_handoff=_handoff(first_result.field),
  )
  assert second_result.converged
  assert second_result.field is not None

  measurement = measure_moc_reflected_domain_alternating_physical_field_chain(
    (first_result, second_result),
  )

  assert measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.DOMAIN_FAILURE
  )
  assert measurement.converged is False
  assert measurement.field_count == 2
  assert len(measurement.field_measurements) == 2
  assert measurement.source_geometry_freshness_verified
  assert measurement.handoff_link_count == 1
  assert measurement.handoff_links_verified is True
  assert measurement.fresh_domain_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.physical_field_chain_measurement is not None
  assert measurement.physical_field_chain_measurement.converged is False
  assert measurement.physical_field_chain_measurement.status.value == 'domain_failure'
  assert measurement.chain_promotion_blocked is True
  assert measurement.production_claim_allowed is False
####


def test_reflected_domain_alternating_physical_field_chain_rejects_copied_geometry():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert source.converged
  first_result = solve_reflected_domain_alternating_physical_field(
    source,
    compression_amplitude_rad=0.05,
    incoming_handoff=_handoff(field),
  )
  assert first_result.converged
  assert first_result.field is not None
  copied_source = replace(
    source,
    incoming_handoff=_handoff(first_result.field),
  )
  copied_result = solve_reflected_domain_alternating_physical_field(
    copied_source,
    compression_amplitude_rad=0.05,
    incoming_handoff=_handoff(first_result.field),
  )
  assert copied_result.converged

  measurement = measure_moc_reflected_domain_alternating_physical_field_chain(
    (first_result, copied_result),
  )

  assert measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.SOURCE_FRESHNESS_FAILURE
  )
  assert measurement.converged is False
  assert measurement.source_geometry_freshness_verified is False
  assert measurement.chain_promotion_blocked is True
  assert measurement.production_claim_allowed is False
####


def test_reflected_domain_alternating_physical_field_chain_rejects_missing_source_band():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  assert source.converged
  result = solve_reflected_domain_alternating_physical_field(
    source,
    compression_amplitude_rad=0.05,
  )
  assert result.converged
  missing_source = replace(result, source_band=None)

  measurement = measure_moc_reflected_domain_alternating_physical_field_chain(
    (missing_source,),
  )

  assert measurement.status is (
    MocReflectedDomainAlternatingPhysicalFieldChainMeasurementStatus.SOURCE_FAILURE
  )
  assert measurement.converged is False
  assert measurement.source_geometry_freshness_verified is False
  assert measurement.chain_promotion_blocked is True
####


def test_reflected_domain_alternating_source_planner_carries_one_cell_handoff():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )
  seed = _canonical_field()

  planner = plan_reflected_domain_alternating_source_chain(
    seed,
    source,
    start_x_m=0.5,
    end_x_m=2.0,
    compression_amplitude_rad=0.05,
  )

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.production_claim_allowed is False
  assert planner.chain.resolved
  assert planner.chain.cell_count == 2
  assert planner.chain.physical_termination is False
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert len(planner.steps) == 2
  assert planner.steps[0].result_kind == 'physical-field-solve-returned'
  assert planner.steps[0].incoming_handoff_link_verified is None
  assert planner.steps[1].result_kind == 'termination-returned'
  assert planner.handoff_links_verified is True
  assert planner.diagnostics['one_step_domain'] is True
  assert planner.diagnostics['use_trace_referenced_profile'] is False
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['physical_closure_pending'] is True
  incoming_points = planner.chain.cells[1].diagnostics['boundary_geometry'][
    'incoming_handoff_points_m'
  ]
  assert incoming_points == [
    [sample.state.x_m, sample.state.y_m]
    for sample in planner.chain.cells[0].continuation_boundary
  ]
####


def test_reflected_domain_alternating_source_planner_can_opt_into_trace_profile():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
  )

  planner = plan_reflected_domain_alternating_source_chain(
    _canonical_field(),
    source,
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    use_outer_seed_attachment=True,
    use_trace_referenced_profile=True,
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 2
  assert planner.diagnostics['use_outer_seed_attachment'] is True
  assert planner.diagnostics['use_trace_referenced_profile'] is True
####


def test_reflected_domain_alternating_source_sequence_requires_fresh_bands_and_carries_multiple_cells():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  initial_source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert initial_source.converged

  callback_calls = []

  def source_band_at(current_field, current, next_cell_index, incoming_handoff):
    callback_calls.append((current_field, current.cell_index, next_cell_index))
    if next_cell_index > 3:
      return None
    ####
    source = solve_reflected_domain_alternating_source(
      patch,
      ambient_pressure,
      source_sample_count=7 - next_cell_index,
      incoming_handoff=incoming_handoff,
    )
    assert source.converged
    return source
  ####

  planner = plan_reflected_domain_alternating_source_chain_sequence(
    field,
    initial_source,
    source_band_at,
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert planner.chain.resolved
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.handoff_links_verified is True
  assert [step.result_kind for step in planner.steps] == [
    'physical-field-solve-returned',
    'physical-field-solve-returned',
    'termination-returned',
  ]
  assert len(callback_calls) == 2
  attempts = planner.diagnostics['alternating_source_attempts']
  assert len(attempts) == 3
  assert all(
    attempt['incoming_handoff_verified'] is True
    and attempt['fresh_source_band'] is True
    and attempt['fresh_source_geometry'] is True
    for attempt in attempts[:2]
  )
  assert attempts[-1]['provider_result'] is None
  assert planner.diagnostics['alternating_source_reuse_policy'] == (
    'fresh-alternating-source-band-and-exact-incoming-handoff-required-per-cell'
  )
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['external_validation_pending'] is True
  alternating_field_chain_audit = planner.diagnostics[
    'alternating_physical_field_chain_audit'
  ]
  assert alternating_field_chain_audit['status'] == 'domain_failure'
  assert planner.diagnostics[
    'alternating_physical_field_chain_audit_accepted'
  ] is False
  assert alternating_field_chain_audit['checks'] == {
    'source_geometry_freshness_verified': True,
    'handoff_links_verified': True,
    'fresh_domain_verified': False,
    'physical_closure_verified': False,
  }
####


def test_reflected_domain_alternating_source_sequence_rejects_copied_geometry():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  source = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    incoming_handoff=_handoff(field),
  )
  assert source.converged

  planner = plan_reflected_domain_alternating_source_chain_sequence(
    field,
    source,
    lambda _field, _current, _next, incoming: replace(
      source,
      incoming_handoff=incoming,
    ),
    start_x_m=0.5,
    end_x_m=1.0,
    compression_amplitude_rad=0.05,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert planner.chain.cell_count == 2
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  attempt = planner.diagnostics['alternating_source_attempts'][-1]
  assert attempt['role'] == 'alternating-source-band-freshness-gate'
  assert attempt['incoming_handoff_verified'] is True
  assert attempt['fresh_source_band'] is True
  assert attempt['fresh_source_geometry'] is False
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
####


def test_reflected_domain_alternating_source_band_carries_explicit_pressure_row():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None
  pressure = patch.outgoing_trace_total_pressure_Pa[0]
  pressure_row = tuple(pressure * (1.0 - 0.005 * index) for index in range(6))

  result = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    pressure,
    centerline_total_pressure_Pa=pressure_row,
  )

  assert result.converged
  assert result.source_field_verified
  assert result.centerline_total_pressure_Pa == pytest.approx(pressure_row)
  assert result.outer_total_pressure_Pa == pytest.approx(pressure_row)
  assert result.total_pressure_at(
    (
      result.outer_source_states[3].x_m,
      result.outer_source_states[3].y_m,
    )
  ) == pytest.approx(pressure_row[3])
  assert result.as_report()['total_pressure_range_Pa'][0] == pytest.approx(
    pressure_row[-1]
  )
####


def test_reflected_domain_alternating_source_band_rejects_a_nonexact_seed():
  field, patch = _patch()
  ambient_pressure = field.ambient_boundary.ambient_pressure_Pa
  assert ambient_pressure is not None

  result = solve_reflected_domain_alternating_source(
    patch,
    ambient_pressure,
    outer_seed_state=replace(patch.outgoing_trace_states[0], x_m=1.4),
  )

  assert result.status is MocReflectedDomainAlternatingSourceStatus.SEED_FAILURE
  assert result.source_field_verified is False
  assert result.physical_closure_verified is False
####


def test_reflected_domain_outer_source_curve_carries_explicit_pressure_rows():
  exit_state, ambient, reflected = _outer_source_fixture()
  total_pressure = exit_state.total_pressure_Pa
  centerline_pressures = tuple(
    total_pressure * (1.0 - 0.001 * index)
    for index in range(len(reflected.centerline_states))
  )

  result = solve_reflected_domain_outer_source_curve(
    reflected.centerline_states,
    reflected.boundary_states[0],
    ambient.pressure_Pa,
    total_pressure,
    centerline_total_pressure_Pa=centerline_pressures,
  )

  assert result.converged
  assert result.source_field_verified
  assert result.source_strip is not None
  assert result.source_strip.total_pressure_model == (
    'source-family-carried-total-pressure'
  )
  assert result.centerline_total_pressure_Pa == pytest.approx(
    centerline_pressures
  )
  assert result.outer_total_pressure_Pa[0] == pytest.approx(total_pressure)
  assert result.outer_total_pressure_Pa[1:] == pytest.approx(
    centerline_pressures[1:]
  )
  assert result.source_strip.total_pressure_at(
    (
      result.outer_source_states[3].x_m,
      result.outer_source_states[3].y_m,
    )
  ) == pytest.approx(result.outer_total_pressure_Pa[3])
  assert result.as_report()['total_pressure_range_Pa'][1] == pytest.approx(
    total_pressure
  )
  measurement = measure_moc_reflected_domain_outer_source_curve(result)
  assert measurement.converged
  assert measurement.pressure_lineage_verified
####


def test_reflected_domain_outer_source_curve_rejects_nonambient_seed():
  exit_state, ambient, reflected = _outer_source_fixture()
  bad_seed = replace(reflected.boundary_states[0], mach=2.0)

  result = solve_reflected_domain_outer_source_curve(
    reflected.centerline_states,
    bad_seed,
    ambient.pressure_Pa,
    exit_state.total_pressure_Pa,
  )

  assert result.status is MocReflectedDomainOuterSourceStatus.SEED_FAILURE
  assert result.converged is False
  assert result.outer_source_curve_verified is False
  assert result.source_field_verified is False
  assert result.point_results == ()
####


def test_reflected_domain_outer_source_curve_binds_into_a_fresh_remesh_request():
  _field, patch, request = _request()
  seed = request.outer_source_states[0]
  ambient_pressure = 101325.0
  seed_pressure = ambient_pressure * (
    1.0 + 0.5 * (seed.gamma - 1.0) * seed.mach * seed.mach
  ) ** (seed.gamma / (seed.gamma - 1.0))
  generated = solve_reflected_domain_outer_source_curve(
    request.centerline_source_states,
    seed,
    ambient_pressure,
    request.total_pressure_Pa,
    previous_boundary_total_pressure_Pa=seed_pressure,
  )
  assert generated.converged

  bound_request = build_reflected_domain_remesh_request_from_outer_source(
    patch,
    generated,
    incoming_handoff=request.incoming_handoff,
  )

  assert bound_request.centerline_source_states == (
    generated.centerline_source_states
  )
  assert bound_request.outer_source_states == generated.outer_source_states
  assert bound_request.centerline_total_pressure_Pa == pytest.approx(
    generated.centerline_total_pressure_Pa
  )
  assert bound_request.outer_total_pressure_Pa == pytest.approx(
    generated.outer_total_pressure_Pa
  )
  remesh = solve_reflected_domain_remesh(bound_request)
  assert remesh.converged
  assert remesh.source_field_verified
  assert remesh.request is bound_request
####


def test_reflected_domain_ambient_closed_planner_connects_fresh_remeshes_to_physical_solver(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request(incoming_handoff=_handoff(seed))
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  assert initial_remesh.converged
  solver_calls = []
  remesh_calls = []

  def fake_physical_solver(
    _state_at,
    _pressure_at,
    start_point_m,
    ambient_pressure_Pa,
    _lower,
    _upper,
    **kwargs,
  ):
    incoming = tuple(kwargs['incoming_handoff'])
    solver_calls.append((start_point_m, ambient_pressure_Pa, incoming))
    field = replace(
      seed,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
    )
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
      axis_closure_shoot=None,
      field=field,
      message='manufactured accepted physical-field solver result',
    )
  ####

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )

  def remesh_at(current_field, current, next_cell_index, incoming_handoff):
    remesh_calls.append(
      (current_field, current.cell_index, next_cell_index, incoming_handoff)
    )
    _field, _patch, request = _request(incoming_handoff=incoming_handoff)
    offset = 0.001 * len(remesh_calls)
    request = replace(
      request,
      outer_source_states=tuple(
        replace(state, x_m=state.x_m + offset)
        for state in request.outer_source_states
      ),
    )
    return solve_reflected_domain_remesh(request)
  ####

  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    remesh_at,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=3,
      cell_axial_length_m=0.4,
      ambient_pressure_Pa=101325.0,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.handoff_links_verified is True
  assert planner.production_claim_allowed is False
  assert len(solver_calls) == 2
  assert len(remesh_calls) == 1
  assert remesh_calls[0][0] is not seed
  assert planner.diagnostics['reflected_domain_remesh_attempt_count'] == 2
  assert all(
    attempt['fresh_remesh'] is True
    and attempt['fresh_source_field'] is True
    and attempt['incoming_handoff_verified'] is True
    for attempt in planner.diagnostics['reflected_domain_remesh_attempts']
  )
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['free_boundary_verified'] is False
  assert planner.diagnostics['physical_chain_promotion_allowed'] is False
  assert planner.diagnostics['external_validation_pending'] is True
####


def test_reflected_domain_ambient_closed_planner_rejects_mismatched_initial_handoff(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request()
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  solver_called = False

  def fake_physical_solver(*_args, **_kwargs):
    nonlocal solver_called
    solver_called = True
    raise AssertionError('physical solver must not run after a handoff failure')
  ####

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )
  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    lambda *_args: initial_remesh,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=2,
      cell_axial_length_m=0.4,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert solver_called is False
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is MocChainTerminationReason.STATE_NOT_CARRIED
  assert planner.steps[0].result_termination_reason is (
    MocChainTerminationReason.STATE_NOT_CARRIED
  )
  attempt = planner.diagnostics['reflected_domain_remesh_attempts'][0]
  assert attempt['role'] == 'reflected-domain-remesh-handoff-seam'
  assert attempt['incoming_handoff_verified'] is False
####


def test_reflected_domain_ambient_closed_planner_rejects_reused_remesh(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request(incoming_handoff=_handoff(seed))
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  assert initial_remesh.converged
  solver_calls = 0

  def fake_physical_solver(*_args, **kwargs):
    nonlocal solver_calls
    solver_calls += 1
    incoming = tuple(kwargs['incoming_handoff'])
    field = replace(
      seed,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
    )
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
      axis_closure_shoot=None,
      field=field,
    )
  ####

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )
  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    lambda *_args: initial_remesh,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=3,
      cell_axial_length_m=0.4,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert solver_calls == 1
  assert planner.chain.cell_count == 2
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.steps[-1].result_termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  attempt = planner.diagnostics['reflected_domain_remesh_attempts'][-1]
  assert attempt['role'] == 'reflected-domain-remesh-freshness-gate'
  assert attempt['fresh_remesh'] is False
  assert attempt['fresh_source_field'] is False
####


def test_reflected_domain_one_step_planner_keeps_the_remesh_below_physical_claims():
  _field, _patch, request = _request()
  field = _reference_seed_field()
  remesh = solve_reflected_domain_remesh(request)

  planner = plan_reflected_domain_remesh_shock_chain(
    field,
    remesh,
    start_point_m=request.outer_source_states[0].x_m,
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.production_claim_allowed is False
  assert planner.diagnostics['one_step_domain'] is True
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['reflected_domain_remesh']['status'] == (
    MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD.value
  )
  assert planner.chain.physical_termination is False
####


def test_terminal_reflection_reference_report_keeps_chain_promotion_blocked():
  report = MocTerminalReflectionPatchAmbientClosureChainReference().as_report()

  assert report['planning_only'] is True
  assert report['production_claim_allowed'] is False
  assert report['physical_chain_promotion_allowed'] is False
####


def test_reflected_domain_sequence_requires_exact_handoff_for_each_new_remesh(
  monkeypatch: pytest.MonkeyPatch,
):
  _field, _patch, first_request = _request(incoming_handoff=_handoff(_canonical_field()))
  field = _reference_seed_field()
  first = solve_reflected_domain_remesh(first_request)
  assert first.converged
  calls = []

  def fake_source_solver(
    current,
    _next_cell_index,
    incoming_handoff,
    _source_strip,
    **kwargs,
  ):
    del kwargs
    next_field_result = solve_uniform_attached_shock_field(
      CharacteristicState(
        current.end_x_m + 0.01,
        0.25,
        -0.2,
        2.0,
        1.4,
      ),
      100000.0,
      (current.end_x_m + 0.01, 0.25),
      outer_downstream_flow_angle_rad=0.05,
      sample_count=9,
    )
    assert next_field_result.field is not None
    next_field = next_field_result.field
    incoming = tuple(incoming_handoff)
    field_with_handoff = replace(
      next_field,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
      upstream_boundary_total_pressure_Pa=(
        min(sample.total_pressure_Pa for sample in incoming),
      ) * len(next_field.upstream_boundary_states),
    )
    return MocPostShockChainCellSolve(
      field=field_with_handoff,
      end_x_m=current.end_x_m + 0.2,
    )
  ####

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_chain_cell_from_source_strip_or_termination',
    fake_source_solver,
  )

  def remesh_at(current, next_cell_index, incoming_handoff):
    calls.append((current.cell_index, next_cell_index, incoming_handoff))
    _field, _patch, request = _request(incoming_handoff=incoming_handoff)
    return solve_reflected_domain_remesh(request)
  ####

  planner = plan_reflected_domain_remesh_shock_chain_sequence(
    field,
    first,
    remesh_at,
    start_point_at=lambda _current, _index, candidate: (
      candidate.request.outer_source_states[0].x_m,
      candidate.request.outer_source_states[0].y_m,
    ),
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert calls
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['reflected_domain_remesh_attempt_count'] >= 2
  assert planner.diagnostics['reflected_domain_reuse_policy'] == (
    'fresh-reflected-domain-remesh-required-per-cell'
  )
  assert planner.chain.physical_termination is False

  missing_provenance = plan_reflected_domain_remesh_shock_chain_sequence(
    field,
    first,
    lambda _current, _index, _handoff: first,
    start_point_at=lambda _current, _index, candidate: (
      candidate.request.outer_source_states[0].x_m,
      candidate.request.outer_source_states[0].y_m,
    ),
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )
  assert missing_provenance.chain.termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  assert missing_provenance.diagnostics['reflected_domain_remesh_attempts'][0][
    'role'
  ] == 'initial-reflected-domain-remesh'
####
