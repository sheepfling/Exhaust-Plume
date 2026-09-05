from __future__ import annotations

from dataclasses import dataclass
import json
from math import pow
from types import SimpleNamespace

import numpy as np
import pytest

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  Pose,
  ShockCellSolveConfig,
  VisualSampling,
  VisualSectionedTubeRequest,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
  solve_shock_cells,
)
from exhaust_plume.api.v1 import SnapshotMetadata
from exhaust_plume.contracts.termination import TerminationReason, TerminationReport
from exhaust_plume.models.integral import IntegralStraightResult, IntegralStraightState
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.plume.curved_plume_closures import CurvedPlumeResult, CurvedPlumeTermination
from exhaust_plume.models.plume.curved_plume_state import CurvedPlumeStation
from exhaust_plume.models.shock_train import (
  GeometryFidelity,
  ShockCellMetrics,
  ShockTrainCell,
  ShockTrainResult,
  ShockTrainStatus,
)
from exhaust_plume.products import (
  MODEL_VISUALIZATION_LANES,
  ModelVisualizationLane,
  evaluate_standardized_model_visualization,
  standardize_all_model_visualizations,
  standardize_model_visualization,
)


def _basic_result():
  gas = CaloricallyPerfectGas.dry_air()
  mach = 3.0
  ambient_pressure = 100_000.0
  total_pressure = ambient_pressure * 1.1 * pow(
    1.0 + (gas.gamma - 1.0) * mach**2 / 2.0,
    gas.gamma / (gas.gamma - 1.0),
  )
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=mach,
      total_pressure_Pa=total_pressure,
      total_temperature_K=800.0,
      exit_radius_m=1.0,
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=ambient_pressure, temperature_K=300.0),
    gas,
  )
  return solve_shock_cells(ShockCellSolveConfig(
    exit=exit_state,
    ambient=ambient,
    max_cells=1,
    expansion_characteristics=2,
    compression_characteristics=1,
  ))
####


def _reduced_result() -> ShockTrainResult:
  metrics = tuple(
    ShockCellMetrics(
      cell_index=index,
      start_x_m=float(index - 1) * 2.0,
      end_x_m=float(index) * 2.0,
      length_m=2.0,
      effective_core_diameter_m=2.0 - 0.2 * index,
      core_mach=2.5 - 0.1 * index,
      mean_pressure_Pa=100_000.0 - 5_000.0 * index,
      maximum_pressure_Pa=110_000.0 - 5_000.0 * index,
      minimum_pressure_Pa=90_000.0 - 5_000.0 * index,
      pressure_oscillation_ratio=0.5 / index,
      mean_pressure_residual=0.01,
      inlet_total_pressure_Pa=100_000.0,
      outlet_total_pressure_Pa=99_000.0,
      geometry_fidelity=(
        GeometryFidelity.RESOLVED_FIRST_CELL
        if index == 1 else GeometryFidelity.SCALED_REDUCED_ORDER
      ),
    )
    for index in (1, 2)
  )
  return ShockTrainResult(
    cells=tuple(ShockTrainCell(metrics=metric) for metric in metrics),
    shock_train_end_x_m=4.0,
    supersonic_core_end_x_m=4.0,
    thermal_plume_end_x_m=4.0,
    termination=TerminationReport(
      reason=TerminationReason.SPATIAL_DOMAIN_LIMIT,
      is_physical=False,
      message='test display limit',
    ),
    status=ShockTrainStatus.TRUNCATED,
    was_domain_truncated=True,
    calibration_id='test-calibration-v1',
  )
####


def _straight_result() -> IntegralStraightResult:
  states = tuple(
    IntegralStraightState(
      x_m=float(index),
      mass_flow_rate_kg_s=1.0 + index,
      momentum_flux_N=100.0 + index,
      total_enthalpy_flux_W=1_000.0 + index,
      velocity_mps=100.0 - index,
      temperature_K=300.0 + index,
      pressure_Pa=100_000.0,
      density_kgpm3=1.0,
      radius_m=0.5 + 0.1 * index,
      species_mass_fractions=(),
    )
    for index in range(3)
  )
  return IntegralStraightResult(
    states=states,
    termination_reason=TerminationReason.SPATIAL_DOMAIN_LIMIT,
    termination_x_m=2.0,
    termination_is_physical=False,
    conservation_residuals={'momentum_relative': 0.0, 'total_enthalpy_relative': 0.0},
  )
####


def _curved_result() -> CurvedPlumeResult:
  stations = tuple(
    CurvedPlumeStation(
      arc_length_m=float(index),
      position_m=np.asarray((float(index), 0.1 * index * index, 0.0)),
      mass_flow_kgps=10.0,
      momentum_flux_N=np.asarray((1_000.0, 0.0, 0.0)),
      momentum_derivative_Npm=np.asarray((0.0, 0.0, 0.0)),
      velocity_mps=np.asarray((100.0, 5.0, 0.0)),
      total_energy_flow_W=1.0e6,
      exhaust_mass_flow_kgps=1.0,
      exhaust_mass_fraction=0.5,
      temperature_K=1_000.0 - index,
      pressure_Pa=100_000.0,
      density_kgpm3=1.0,
      specific_heat_JpkgK=1_000.0,
      gas_constant_JpkgK=287.0,
      area_m2=1.0,
      radius_m=0.5 + 0.1 * index,
      ambient_velocity_mps=np.asarray((0.0, 0.0, 0.0)),
      ambient_temperature_K=300.0,
      ambient_density_kgpm3=1.0,
      relative_velocity_mps=np.asarray((100.0, 5.0, 0.0)),
      entrainment_kgpspm=0.1,
      curvature_per_m=0.01,
      slenderness_ratio=0.1,
    )
    for index in range(3)
  )
  return CurvedPlumeResult(
    stations=stations,
    termination=CurvedPlumeTermination.DOMAIN_LIMIT,
    solver_message='test display limit',
    function_evaluations=3,
  )
####


@dataclass(frozen=True)
class _MocCell:
  vertices_xr_m: tuple[tuple[float, float], ...]
####


class _MocField:
  cells = (
    _MocCell(((0.5, 0.0), (1.0, 0.4), (1.5, 0.0))),
    _MocCell(((1.0, 0.0), (1.5, 0.0), (2.0, 0.2))),
  )
  nodes = ()
  shock_boundary_points_m = ((0.5, 0.4), (1.0, 0.3), (1.5, 0.0))
  ambient_boundary_points_m = ((1.5, 0.0), (1.75, 0.15), (2.0, 0.0))
  centerline_boundary_points_m = ((0.5, 0.0), (1.0, 0.0), (1.5, 0.0), (2.0, 0.0))
  centerline_boundary_states = tuple(
    CharacteristicState(x_m=x, y_m=0.0, theta_rad=0.0, mach=2.0, gamma=1.4)
    for x in (0.5, 1.0, 1.5, 2.0)
  )
  centerline_boundary_total_pressure_Pa = (200_000.0, 190_000.0, 180_000.0, 170_000.0)
  physical_closure_verified = True
  state_sampling_available = True

  def state_at(self, point: tuple[float, float]) -> CharacteristicState:
    return CharacteristicState(x_m=point[0], y_m=point[1], theta_rad=0.0, mach=2.0, gamma=1.4)
  ####

  def total_pressure_at(self, _point: tuple[float, float]) -> float:
    return 180_000.0
  ####
####


class _MocResult:
  status = 'converged-global-physical-closure'
  field = _MocField()
  physical_closure_verified = True
  state_sampling_available = True
  production_claim_allowed = False
  production_promotion_gates = {
    'physical_closure_verified': True,
    'canonical_free_boundary_verified': False,
    'refinement_verified': False,
  }
####


class _AttachmentField(_MocField):
  nodes = tuple(
    SimpleNamespace(
      state=CharacteristicState(
        x_m=x_value,
        y_m=0.0,
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=200_000.0 - 10_000.0 * index,
    )
    for index, x_value in enumerate((0.5, 1.0, 1.5))
  )
  continuation_boundary = ()
  physical_closure_verified = False
  production_claim_allowed = False
####


_AttachmentField.continuation_boundary = tuple(
  SimpleNamespace(state=node.state, total_pressure_Pa=node.total_pressure_Pa)
  for node in _AttachmentField.nodes
)


class _AttachmentResult:
  request = SimpleNamespace(upstream_field=_AttachmentField())
  status = 'converged-bounded-transonic-shock-field-attachment'
  selected_node_index = 1
  selected_point_m = (1.0, 0.0)
  attachment_verified = True
  physical_closure_verified = False
  production_claim_allowed = False
  geometry = SimpleNamespace(
    status='verified-normal-shock-geometry-binding',
    geometry_verified=True,
    shock_point_m=(1.0, 0.0),
    shock_normal_angle_rad=0.0,
    normal_alignment_residual_rad=0.0,
    mass_flux_residual=1.0e-12,
    momentum_flux_residual=2.0e-12,
    energy_flux_residual=3.0e-12,
    upstream_normal_velocity_m_s=500.0,
    downstream_normal_velocity_m_s=100.0,
  )
  geometry_audit = SimpleNamespace(
    field_match_verified=True,
    geometry_binding_verified=True,
  )
  mach_residual = 0.0
  flow_angle_residual_rad = 0.0
  gamma_residual = 0.0
  static_pressure_residual = 0.0
  total_pressure_residual = 0.0
####


def _coupled_euler_result() -> SimpleNamespace:
  control_section = SimpleNamespace(
    points_m=((0.0, 0.0), (0.0, 1.0)),
    samples=(SimpleNamespace(gamma=1.4), SimpleNamespace(gamma=1.4)),
  )
  request = SimpleNamespace(
    mixed_regime_request=SimpleNamespace(control_section=control_section),
    source_closure_fingerprint='coupled-closure-test-fingerprint',
  )
  vertices = (
    ((0.0, 0.0), (1.0, 0.0), (1.0, 0.55), (0.0, 0.5)),
    ((0.0, 0.5), (1.0, 0.55), (1.0, 1.1), (0.0, 1.0)),
    ((1.0, 0.0), (2.0, 0.0), (2.0, 0.6), (1.0, 0.55)),
    ((1.0, 0.55), (2.0, 0.6), (2.0, 1.2), (1.0, 1.1)),
  )
  return SimpleNamespace(
    status='coupled-euler-free-boundary-failure',
    request=request,
    x_stations_m=(0.0, 1.0, 2.0),
    free_boundary_points_m=((0.0, 1.0), (1.0, 1.1), (2.0, 1.2)),
    cell_vertices_by_cell_m=vertices,
    cell_centers_m=((0.5, 0.25), (0.5, 0.8), (1.5, 0.275), (1.5, 0.9)),
    mach_by_cell=(0.8, 0.9, 1.0, 1.1),
    static_pressure_by_cell_Pa=(200_000.0, 190_000.0, 180_000.0, 170_000.0),
    density_by_cell_kg_m3=(1.0, 0.95, 0.9, 0.85),
    temperature_by_cell_K=(700.0, 680.0, 660.0, 640.0),
    velocity_u_by_cell_m_s=(120.0, 130.0, 140.0, 150.0),
    velocity_v_by_cell_m_s=(1.0, 2.0, 3.0, 4.0),
    total_pressure_by_cell_Pa=(210_000.0, 200_000.0, 190_000.0, 180_000.0),
    entropy_proxy_by_cell=(100.0, 101.0, 102.0, 103.0),
    entropy_production_fraction_by_cell=(0.0, 0.01, 0.02, 0.03),
    physical_closure_verified=False,
    state_sampling_available=True,
    production_claim_allowed=False,
    coupled_euler_field_verified=True,
    free_boundary_condition_verified=False,
    entropy_transport_verified=True,
    conservative_euler_residuals_measured=True,
    conservative_euler_residuals_verified=True,
    chain_promotion_blocked=True,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    maximum_conservative_euler_residual=0.001,
    maximum_free_boundary_pressure_residual_Pa=20_000.0,
    maximum_free_boundary_normal_velocity_residual_fraction=0.02,
    maximum_shape_residual_m=0.0005,
    maximum_entropy_transport_residual=0.01,
    maximum_entropy_production_fraction=0.03,
    pseudo_iteration_count=12,
    shape_iteration_count=3,
    subsonic_pressure_budget=SimpleNamespace(
      status='below-isentropic-subsonic-pressure-bounds',
      reachable_without_additional_entropy=False,
      target_static_pressure_Pa=100_000.0,
      reference_total_pressure_Pa=400_000.0,
      subsonic_static_pressure_lower_bound_Pa=212_000.0,
      subsonic_static_pressure_upper_bound_Pa=400_000.0,
      total_pressure_compatibility_ratio=0.5,
      minimum_additional_total_pressure_loss_fraction=0.5,
    ),
    control_section_compatibility=SimpleNamespace(
      status='target-below-control-section-pressure',
      pressure_seam_matched=False,
      control_section_outer_static_pressure_Pa=300_000.0,
      control_section_outer_total_pressure_Pa=400_000.0,
      control_section_outer_mach=0.67,
      target_minus_control_section_pressure_Pa=-200_000.0,
      absolute_pressure_jump_Pa=200_000.0,
      absolute_pressure_jump_fraction=2.0 / 3.0,
      transition_requires_supersonic_upstream=True,
    ),
    transonic_transition=SimpleNamespace(
      status='converged-normal-shock-pressure-reference',
      sonic_static_pressure_Pa=212_000.0,
      required_upstream_mach=3.0,
      upstream_static_pressure_Pa=60_000.0,
      downstream_static_pressure_Pa=100_000.0,
      downstream_mach=0.475,
      downstream_total_pressure_Pa=210_000.0,
      total_pressure_ratio=0.525,
      entropy_increase_JpkgK=180.0,
      pressure_residual_Pa=1.0e-8,
      shock_state=SimpleNamespace(
        upstream_static_temperature_K=500.0,
        downstream_static_temperature_K=800.0,
        upstream_density_kg_m3=0.4,
        downstream_density_kg_m3=0.8,
        upstream_sound_speed_m_s=450.0,
        downstream_sound_speed_m_s=570.0,
        upstream_speed_m_s=1350.0,
        downstream_speed_m_s=270.75,
      ),
    ),
    transonic_transition_audit=SimpleNamespace(
      shock_state_verified=True,
      shock_state_conservation_verified=True,
      shock_state_mass_flux_residual=1.0e-12,
      shock_state_momentum_flux_residual=2.0e-12,
      shock_state_energy_flux_residual=3.0e-12,
    ),
    transonic_shock_geometry=SimpleNamespace(
      status='verified-normal-shock-geometry-binding',
      geometry_verified=True,
      shock_point_m=(0.0, 0.5),
      shock_normal_angle_rad=0.0,
      normal_alignment_residual_rad=0.0,
      mass_flux_residual=1.0e-12,
      momentum_flux_residual=2.0e-12,
      energy_flux_residual=3.0e-12,
      upstream_normal_velocity_m_s=1350.0,
      downstream_normal_velocity_m_s=270.75,
    ),
    transonic_shock_interface_consumed=True,
    transonic_shock_interface=SimpleNamespace(
      status='converged-bounded-transonic-shock-interface',
      interface_verified=True,
      physical_closure_verified=False,
      chain_promotion_blocked=True,
      production_claim_allowed=False,
      placement_verified=True,
      geometry_verified=True,
      upstream_lineage_verified=True,
      downstream_state_verified=True,
      upstream_sample=SimpleNamespace(
        mach=3.0,
        flow_angle_rad=0.0,
        static_pressure_Pa=60_000.0,
        total_pressure_Pa=400_000.0,
        gamma=1.4,
      ),
      downstream_sample=SimpleNamespace(
        mach=0.475,
        flow_angle_rad=0.0,
        static_pressure_Pa=100_000.0,
        total_pressure_Pa=210_000.0,
        gamma=1.4,
      ),
      shock_geometry=SimpleNamespace(
        shock_point_m=(0.0, 0.5),
        shock_normal_angle_rad=0.0,
      ),
      independent_measurement=SimpleNamespace(converged=True),
    ),
    transonic_shock_interface_profile_consumed=True,
    transonic_shock_interface_profile=SimpleNamespace(
      profile_id='test-spatial-shock-interface-profile-v1',
      cross_section_x_m=0.0,
      lower_ordinate_m=0.0,
      upper_ordinate_m=1.0,
      interface_normal_angle_rad=0.0,
      upstream_samples=(
        SimpleNamespace(point_m=(0.0, 0.0)),
        SimpleNamespace(point_m=(0.0, 0.5)),
        SimpleNamespace(point_m=(0.0, 1.0)),
      ),
      downstream_samples=(
        SimpleNamespace(point_m=(0.0, 0.0)),
        SimpleNamespace(point_m=(0.0, 0.5)),
        SimpleNamespace(point_m=(0.0, 1.0)),
      ),
    ),
  )
####


def test_all_five_model_lanes_share_one_bundle_shape() -> None:
  results = {
    ModelVisualizationLane.BASIC_SHOCK_CELL: _basic_result(),
    ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN: _reduced_result(),
    ModelVisualizationLane.STRAIGHT_INTEGRAL: _straight_result(),
    ModelVisualizationLane.CURVED_INTEGRAL: _curved_result(),
    ModelVisualizationLane.PLANAR_MOC: _MocResult(),
  }

  bundles = standardize_all_model_visualizations(results, section_count=12)

  assert tuple(bundle.lane for bundle in bundles) == MODEL_VISUALIZATION_LANES
  assert all(len(bundle.sectioned_tube.sections) >= 2 for bundle in bundles)
  assert all(bundle.sectioned_tube.frame_id == 'source-local' for bundle in bundles)
  assert bundles[0].claims.production_claim_allowed
  assert not bundles[1].claims.production_claim_allowed
  assert not bundles[-1].claims.production_claim_allowed
  assert len(bundles[0].fields) == 1
  assert len(bundles[-1].fields[0].polygons_xr_m) == 2
  assert {path.path_id for path in bundles[-1].paths} >= {
    'moc-shock-boundary',
    'moc-ambient-boundary',
    'moc-centerline-boundary',
  }
  json.dumps([bundle.model_dump() for bundle in bundles], allow_nan=False)
####


def test_moc_field_values_can_remain_masked_without_becoming_zero() -> None:
  class MaskedField(_MocField):
    def state_at(self, _point: tuple[float, float]) -> None:
      return None
    ####

    def total_pressure_at(self, _point: tuple[float, float]) -> None:
      return None
    ####
  ####

  class MaskedResult(_MocResult):
    field = MaskedField()
  ####

  bundle = standardize_model_visualization(MaskedResult())
  assert bundle.fields[0].channels['mach'] == (None, None)
  assert 'state samples were unavailable' in bundle.warnings[-1]
####


def test_moc_global_euler_visualization_exposes_solver_owned_shock_parameters() -> None:
  curve = SimpleNamespace(
    shock_points_m=((0.5, 0.4), (1.0, 0.3), (1.5, 0.15), (2.0, 0.0)),
    shock_angles_rad=(0.1, 0.15, 0.2, 0.25),
    beta_rad=(0.4, 0.42, 0.44, 0.46),
    target_downstream_flow_angles_rad=(0.0, 0.01, 0.02, 0.03),
    upstream_static_pressure_Pa=(200_000.0, 190_000.0, 180_000.0, 170_000.0),
    downstream_static_pressure_Pa=(160_000.0, 152_000.0, 144_000.0, 136_000.0),
    upstream_total_pressure_Pa=(220_000.0, 209_000.0, 198_000.0, 187_000.0),
    downstream_total_pressure_Pa=(198_000.0, 188_100.0, 178_200.0, 168_300.0),
    shock_jump_mass_residuals=(1.0e-9, 2.0e-9, 3.0e-9, 4.0e-9),
    shock_jump_momentum_residuals=(2.0e-9, 3.0e-9, 4.0e-9, 5.0e-9),
    shock_jump_energy_residuals=(3.0e-9, 4.0e-9, 5.0e-9, 6.0e-9),
    tangent_residuals_rad=(1.0e-10, 2.0e-10, 3.0e-10, 4.0e-10),
    orientation='mixed-characteristic-boundary',
  )
  physical = SimpleNamespace(
    maximum_entropy_residual=0.01,
    physical_closure_verified=True,
    field=_MocField(),
  )
  global_euler = SimpleNamespace(
    status='converged_global_euler_shock_field',
    shock_boundary=curve,
    physical_field=physical,
    converged=True,
    physical_closure_verified=True,
    source_frontier_verified=True,
    incoming_handoff_verified=True,
    production_claim_allowed=False,
  )
  result = SimpleNamespace(
    status='converged_global_physical_closure',
    global_euler=global_euler,
    production_claim_allowed=False,
  )

  bundle = standardize_model_visualization(
    result,
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  channels = {channel.channel_id: channel for channel in bundle.section_channels}
  assert channels['shock_height'].values == pytest.approx((0.4, 0.3, 0.15, 0.0))
  assert channels['shock_static_pressure_ratio'].values == pytest.approx(
    (0.8, 0.8, 0.8, 0.8),
  )
  assert channels['shock_total_pressure_ratio'].values == pytest.approx(
    (0.9, 0.9, 0.9, 0.9),
  )
  assert channels['shock_jump_residual'].values == pytest.approx(
    (3.0e-9, 4.0e-9, 5.0e-9, 6.0e-9),
  )
  assert bundle.diagnostics['global_euler_status'] == 'converged_global_euler_shock_field'
  assert bundle.diagnostics['global_euler_physical_closure_verified'] is True
  assert bundle.diagnostics['shock_boundary_orientation'] == 'mixed-characteristic-boundary'
  assert bundle.diagnostics['shock_jump_residual_maximum'] == pytest.approx(6.0e-9)
  assert bundle.claims.production_claim_allowed is False
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_moc_production_fit_visualization_exposes_candidate_boundary_without_promotion() -> None:
  class ProductionFitResult(_MocResult):
    candidate_field = _MocField()
    fitted_shock_points_m = _MocField.shock_boundary_points_m
    status = 'converged_local_production_shock_cell_fit'
    local_fit_verified = True
    chain_promotion_blocked = True
    production_claim_allowed = False
    start_x_m = 0.5
    end_x_m = 2.0
  ####

  bundle = standardize_model_visualization(
    ProductionFitResult(),
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  assert bundle.model_id == 'planar-moc-production-shock-cell-fit'
  assert 'moc-production-fit-shock-boundary' in {
    path.path_id for path in bundle.paths
  }
  assert bundle.diagnostics['production_fit_status'] == (
    'converged_local_production_shock_cell_fit'
  )
  assert bundle.diagnostics['production_fit_local_fit_verified'] is True
  assert bundle.diagnostics['production_fit_solver_shock_axial_span_m'] == pytest.approx(1.0)
  assert bundle.diagnostics['production_fit_requested_axial_length_m'] == pytest.approx(1.5)
  assert bundle.diagnostics['production_fit_physical_length_accepted'] is False
  assert bundle.claims.production_claim_allowed is False
  assert any('not an accepted physical shock-cell length' in warning for warning in bundle.warnings)
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_moc_production_fit_visualization_rejects_unordered_candidate_boundary() -> None:
  class UnorderedProductionFitResult(_MocResult):
    candidate_field = _MocField()
    fitted_shock_points_m = ((2.0, 0.0), (1.5, 0.2), (1.0, 0.3))
    status = 'converged_local_production_shock_cell_fit'
    local_fit_verified = True
    chain_promotion_blocked = True
    production_claim_allowed = False
  ####

  bundle = standardize_model_visualization(
    UnorderedProductionFitResult(),
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  assert 'moc-production-fit-shock-boundary' not in {
    path.path_id for path in bundle.paths
  }
  assert bundle.diagnostics['production_fit_solver_shock_path_sample_count'] == 0
  assert 'production_fit_solver_shock_axial_span_m' not in bundle.diagnostics
  assert any('not strictly downstream ordered' in warning for warning in bundle.warnings)
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_moc_mixed_regime_visualization_retains_reference_overlays() -> None:
  global_euler = SimpleNamespace(
    physical_field=SimpleNamespace(
      field=_MocField(),
      physical_closure_verified=True,
    ),
  )
  closure = SimpleNamespace(global_euler=global_euler)
  reference = SimpleNamespace(
    status='converged-solver-owned-variable-entropy-free-boundary-reference',
    model='solver-owned-streamline-variable-entropy-free-boundary-reference',
    converged=True,
    reference_verified=True,
    solver_owned_reference_verified=True,
    source_streamline_mapping_verified=True,
    entropy_transport_verified=True,
    continuity_verified=True,
    free_boundary_condition_verified=True,
    field_topology_verified=True,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    request=SimpleNamespace(
      terminal_point_m=(0.5, 0.4),
      supersonic_patch=(
        SimpleNamespace(point_m=(0.6, 0.35)),
        SimpleNamespace(point_m=(0.8, 0.25)),
      ),
    ),
    handoff=SimpleNamespace(
      samples=(
        SimpleNamespace(point_m=(0.6, 0.35)),
        SimpleNamespace(point_m=(0.8, 0.25)),
      ),
    ),
    control_section=SimpleNamespace(
      points_m=((0.52, 0.4), (0.52, 0.55), (0.52, 0.7)),
    ),
    free_boundary_points_m=((1.5, 0.2), (1.0, 0.3), (0.5, 0.4)),
    boundary=SimpleNamespace(
      perimeter_points_m=((0.5, 0.4), (1.5, 0.0), (1.5, 0.2), (0.5, 0.4)),
    ),
    axial_station_count=7,
    transverse_station_count=4,
    iteration_count=5,
    maximum_free_boundary_pressure_residual_Pa=2.0e-4,
    maximum_free_boundary_tangent_residual_rad=3.0e-5,
    maximum_continuity_residual=4.0e-3,
    maximum_entropy_advection_residual=5.0e-3,
    maximum_conservative_euler_residual=6.0e-3,
    maximum_mass_flow_residual=7.0e-4,
    outlet_height_m=0.2,
  )
  result = SimpleNamespace(
    closure=closure,
    reference=reference,
    physical_closure_verified=False,
    production_claim_allowed=False,
  )

  bundle = standardize_model_visualization(
    result,
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  assert bundle.model_id == 'planar-moc-mixed-regime-reference'
  assert {path.path_id for path in bundle.paths} >= {
    'moc-mixed-regime-supersonic-patch',
    'moc-mixed-regime-entropy-handoff',
    'moc-mixed-regime-control-section',
    'moc-mixed-regime-free-boundary',
    'moc-mixed-regime-perimeter',
    'moc-mixed-regime-terminal-seam',
  }
  assert bundle.diagnostics['mixed_regime_reference_converged'] is True
  assert bundle.diagnostics['mixed_regime_reference_chain_promotion_blocked'] is True
  assert bundle.diagnostics['mixed_regime_reference_maximum_conservative_euler_residual'] == pytest.approx(6.0e-3)
  assert bundle.diagnostics['mixed_regime_reference_overlay_path_count'] == 6
  assert bundle.claims.production_claim_allowed is False
  assert any('mixed-regime overlays are solver-owned scalar' in warning for warning in bundle.warnings)
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_coupled_euler_visualization_retains_mesh_and_physical_channels() -> None:
  bundle = standardize_model_visualization(
    _coupled_euler_result(),
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  assert bundle.model_id == 'planar-moc-coupled-euler-free-boundary'
  assert len(bundle.fields) == 1
  assert len(bundle.fields[0].polygons_xr_m) == 4
  assert {path.path_id for path in bundle.paths} >= {
    'moc-ambient-boundary',
    'moc-centerline-boundary',
    'moc-transonic-shock-branch',
    'moc-coupled-transonic-shock-interface-normal',
    'moc-coupled-transonic-shock-interface-profile',
  }
  channels = {channel.channel_id: channel for channel in bundle.section_channels}
  assert channels['static_pressure'].unit == 'Pa'
  assert channels['density'].unit == 'kg m^-3'
  assert channels['temperature'].values == pytest.approx((700.0, 680.0, 660.0))
  assert bundle.diagnostics['coupled_euler_free_boundary_condition_verified'] is False
  assert bundle.diagnostics['coupled_euler_source_closure_fingerprint'] == (
    'coupled-closure-test-fingerprint'
  )
  assert bundle.diagnostics['coupled_euler_maximum_conservative_euler_residual'] == pytest.approx(0.001)
  assert bundle.diagnostics['coupled_euler_subsonic_pressure_budget_status'] == (
    'below-isentropic-subsonic-pressure-bounds'
  )
  assert bundle.diagnostics['coupled_euler_subsonic_pressure_budget_reachable'] is False
  assert bundle.diagnostics[
    'coupled_euler_control_section_seam_status'
  ] == 'target-below-control-section-pressure'
  assert bundle.diagnostics['coupled_euler_control_section_seam_matched'] is False
  assert bundle.diagnostics[
    'coupled_euler_absolute_pressure_jump_Pa'
  ] == pytest.approx(200_000.0)
  assert bundle.diagnostics[
    'coupled_euler_transition_requires_supersonic_upstream'
  ] is True
  assert bundle.diagnostics['coupled_euler_transonic_transition_status'] == (
    'converged-normal-shock-pressure-reference'
  )
  assert bundle.diagnostics['coupled_euler_transonic_shock_state_available'] is True
  assert bundle.diagnostics['coupled_euler_transonic_shock_geometry_status'] == (
    'verified-normal-shock-geometry-binding'
  )
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_interface_status'
  ] == 'converged-bounded-transonic-shock-interface'
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_interface_consumed'
  ] is True
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_interface_profile_consumed'
  ] is True
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_interface_profile_sample_count'
  ] == 3
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_interface_profile_cross_section_x_m'
  ] == pytest.approx(0.0)
  assert any('spatial shock-interface profile' in warning for warning in bundle.warnings)
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_interface_downstream_mach'
  ] == pytest.approx(0.475)
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_branch_marker_only'
  ] is True
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_geometry_downstream_normal_velocity_m_s'
  ] == pytest.approx(270.75)
  assert bundle.diagnostics['coupled_euler_transonic_shock_state_verified'] is True
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_state_conservation_verified'
  ] is True
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_state_energy_flux_residual'
  ] == pytest.approx(3.0e-12)
  assert bundle.diagnostics[
    'coupled_euler_transonic_shock_state_upstream_speed_m_s'
  ] == pytest.approx(1350.0)
  assert bundle.diagnostics[
    'coupled_euler_pressure_budget_minimum_additional_total_pressure_loss_fraction'
  ] == pytest.approx(0.5)
  assert bundle.diagnostics[
    'coupled_euler_maximum_entropy_production_fraction'
  ] == pytest.approx(0.03)
  assert bundle.diagnostics['coupled_euler_near_sonic_mach_half_width'] == pytest.approx(0.05)
  assert bundle.fields[0].channels['entropy_production_fraction'] == pytest.approx(
    (0.0, 0.01, 0.02, 0.03)
  )
  assert bundle.fields[0].channels['near_sonic_mask'] == pytest.approx(
    (0.0, 0.0, 1.0, 0.0)
  )
  assert bundle.claims.production_claim_allowed is False
  assert any(
    'coupled-Euler/free-boundary channels are research diagnostics' in warning
    for warning in bundle.warnings
  )
  assert any(
    'caller-bound scalar branch diagnostic' in warning
    for warning in bundle.warnings
  )
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_transonic_attachment_visualization_retains_field_and_attachment_evidence() -> None:
  bundle = standardize_model_visualization(
    _AttachmentResult(),
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  assert bundle.model_id == 'planar-moc-transonic-field-attachment'
  assert len(bundle.fields) == 1
  assert len(bundle.fields[0].polygons_xr_m) == 2
  assert {path.path_id for path in bundle.paths} >= {
    'moc-centerline-boundary',
    'moc-incoming-frontier',
    'moc-transonic-shock-branch',
    'moc-transonic-attachment-node',
  }
  assert bundle.diagnostics['moc_transonic_attachment_verified'] is True
  assert bundle.diagnostics['moc_transonic_attachment_selected_node_index'] == 1
  assert bundle.diagnostics['moc_transonic_attachment_field_match_verified'] is True
  assert bundle.diagnostics['moc_transonic_attachment_geometry_binding_verified'] is True
  assert bundle.claims.production_claim_allowed is False
  assert any(
    'bounded solver-owned field attachment diagnostic' in warning
    for warning in bundle.warnings
  )
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_transonic_transport_visualization_retains_bounded_trace_and_lineage() -> None:
  class TransportResult:
    request = _AttachmentResult.request
    attachment = _AttachmentResult()
    status = 'converged-bounded-transonic-characteristic-transport'
    termination = 'bounded-field-boundary'
    samples = (
      SimpleNamespace(point_m=(1.0, 0.0)),
      SimpleNamespace(point_m=(1.1, 0.1)),
    )
    segments = (SimpleNamespace(),)
    bounded_transport_verified = True
    physical_closure_verified = False
    production_claim_allowed = False
    maximum_geometry_residual = 0.002
    maximum_compatibility_residual = 0.001
    maximum_pressure_residual = 1.0e-12
    first_unavailable_point_m = (1.2, 0.2)
  ####

  bundle = standardize_model_visualization(
    TransportResult(),
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  assert bundle.model_id == 'planar-moc-transonic-characteristic-transport'
  assert 'moc-transonic-characteristic-transport' in {
    path.path_id for path in bundle.paths
  }
  assert bundle.diagnostics['moc_transonic_transport_verified'] is True
  assert bundle.diagnostics['moc_transonic_transport_sample_count'] == 2
  assert bundle.diagnostics['moc_transonic_transport_segment_count'] == 1
  assert bundle.diagnostics['moc_transonic_transport_maximum_geometry_residual'] == pytest.approx(0.002)
  assert bundle.diagnostics['moc_transonic_transport_first_unavailable_x_m'] == pytest.approx(1.2)
  assert bundle.claims.production_claim_allowed is False
  assert any(
    'transport trace are bounded solver-owned diagnostics' in warning
    for warning in bundle.warnings
  )
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_transonic_frontier_placement_visualization_retains_frontier_and_seams() -> None:
  class TransportResult:
    request = _AttachmentResult.request
    attachment = _AttachmentResult()
    status = 'converged-bounded-transonic-characteristic-transport'
    termination = 'bounded-field-boundary'
    samples = (
      SimpleNamespace(point_m=(1.0, 0.0)),
      SimpleNamespace(point_m=(1.1, 0.1)),
    )
    segments = (SimpleNamespace(),)
    bounded_transport_verified = True
    physical_closure_verified = False
    production_claim_allowed = False
  ####

  class PlacementResult:
    request = SimpleNamespace(
      transport=TransportResult(),
      target_frontier=(
        SimpleNamespace(point_m=(1.0, 0.2)),
        SimpleNamespace(point_m=(1.1, 0.1)),
        SimpleNamespace(point_m=(1.3, -0.1)),
      ),
      frontier_kind='post-shock-field-perimeter',
      frontier_fidelity='resolved-planar-moc',
    )
    status = 'converged-bounded-transonic-placement'
    placement_verified = True
    intersection_point_m = (1.1, 0.1)
    physical_closure_verified = False
    chain_promotion_blocked = True
    production_claim_allowed = False
    transport_segment_index = 0
    frontier_segment_index = 0
    transport_fraction = 1.0
    frontier_fraction = 0.0
    state_seam_residual = 0.0
    pressure_seam_residual = 0.0
    shock_geometry = SimpleNamespace(
      shock_point_m=(1.1, 0.1),
      shock_normal_angle_rad=0.0,
    )
  ####

  bundle = standardize_model_visualization(
    PlacementResult(),
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  assert bundle.model_id == 'planar-moc-transonic-frontier-placement'
  assert {path.path_id for path in bundle.paths} >= {
    'moc-transonic-characteristic-transport',
    'moc-transonic-placement-frontier',
    'moc-transonic-placement-intersection',
  }
  assert bundle.diagnostics['moc_transonic_placement_verified'] is True
  assert bundle.diagnostics['moc_transonic_placement_frontier_sample_count'] == 3
  assert bundle.diagnostics['moc_transonic_placement_state_seam_residual'] == pytest.approx(0.0)
  assert bundle.diagnostics['moc_transonic_placement_chain_promotion_blocked'] is True
  assert bundle.claims.production_claim_allowed is False
  assert any(
    'transonic placement marker, frontier, and transport trace' in warning
    for warning in bundle.warnings
  )
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_transonic_interface_visualization_retains_both_regime_samples() -> None:
  class TransportResult:
    request = _AttachmentResult.request
    attachment = _AttachmentResult()
    status = 'converged-bounded-transonic-characteristic-transport'
    termination = 'bounded-field-boundary'
    samples = (
      SimpleNamespace(point_m=(1.0, 0.0)),
      SimpleNamespace(point_m=(1.1, 0.1)),
    )
    segments = (SimpleNamespace(),)
    bounded_transport_verified = True
    physical_closure_verified = False
    production_claim_allowed = False
  ####

  class PlacementResult:
    request = SimpleNamespace(
      transport=TransportResult(),
      target_frontier=(
        SimpleNamespace(point_m=(1.0, 0.2)),
        SimpleNamespace(point_m=(1.1, 0.1)),
      ),
      frontier_kind='post-shock-field-perimeter',
      frontier_fidelity='resolved-planar-moc',
    )
    status = 'converged-bounded-transonic-placement'
    placement_verified = True
    intersection_point_m = (1.1, 0.1)
    physical_closure_verified = False
    chain_promotion_blocked = True
    production_claim_allowed = False
    transport_segment_index = 0
    frontier_segment_index = 0
    transport_fraction = 1.0
    frontier_fraction = 0.0
    state_seam_residual = 0.0
    pressure_seam_residual = 0.0
  ####

  class InterfaceResult:
    request = SimpleNamespace(placement=PlacementResult())
    status = 'converged-bounded-transonic-shock-interface'
    interface_verified = True
    placement_verified = True
    geometry_verified = True
    upstream_lineage_verified = True
    downstream_state_verified = True
    physical_closure_verified = False
    chain_promotion_blocked = True
    production_claim_allowed = False
    shock_geometry = SimpleNamespace(
      shock_point_m=(1.1, 0.1),
      shock_normal_angle_rad=0.0,
    )
    upstream_sample = SimpleNamespace(
      mach=2.0,
      flow_angle_rad=0.0,
      static_pressure_Pa=100_000.0,
      total_pressure_Pa=1_000_000.0,
      gamma=1.4,
    )
    downstream_sample = SimpleNamespace(
      mach=0.6,
      flow_angle_rad=0.0,
      static_pressure_Pa=250_000.0,
      total_pressure_Pa=800_000.0,
      gamma=1.4,
    )
    independent_measurement = SimpleNamespace(converged=True)
  ####

  bundle = standardize_model_visualization(
    InterfaceResult(),
    lane=ModelVisualizationLane.PLANAR_MOC,
    section_count=8,
  )

  assert bundle.model_id == 'planar-moc-transonic-shock-interface'
  assert {path.path_id for path in bundle.paths} >= {
    'moc-transonic-shock-interface-normal',
    'moc-transonic-placement-frontier',
    'moc-transonic-placement-intersection',
  }
  assert bundle.diagnostics['moc_transonic_interface_verified'] is True
  assert bundle.diagnostics['moc_transonic_interface_upstream_mach'] == pytest.approx(2.0)
  assert bundle.diagnostics['moc_transonic_interface_downstream_mach'] == pytest.approx(0.6)
  assert bundle.diagnostics['moc_transonic_interface_audit_verified'] is True
  assert bundle.claims.production_claim_allowed is False
  assert any(
    'transonic interface, placement marker' in warning
    for warning in bundle.warnings
  )
  json.dumps(bundle.model_dump(), allow_nan=False)
####


def test_canonical_visual_result_retains_lane_metadata() -> None:
  bundle = standardize_model_visualization(_curved_result(), section_count=8)
  snapshot = SnapshotMetadata(
    snapshot_id='snapshot-visual-test',
    session_id='session-visual-test',
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state_digest_sha256='dynamic',
    ambient_state_digest_sha256='ambient',
    provider_state_digest_sha256='provider',
  )
  request = VisualSectionedTubeRequest(
    output_frame_id='source-local',
    sampling=VisualSampling(maximum_section_count=8),
    requested_channels=('temperature', 'curvature'),
  )

  result = evaluate_standardized_model_visualization(bundle, request, snapshot)

  assert result.metadata.capability.wire_id == 'plume.visual.sectioned-tube@1'
  assert result.metadata.provenance.metadata['model_lane'] == 'washed-integral-v1'
  assert result.metadata.provenance.metadata['validation_level'] == 'UNVERIFIED'
  assert result.channels['temperature'][0] == pytest.approx(1_000.0)
####


def test_all_lane_collection_requires_exactly_the_five_declared_keys() -> None:
  with pytest.raises(ValueError, match='missing'):
    standardize_all_model_visualizations({
      ModelVisualizationLane.BASIC_SHOCK_CELL: _basic_result(),
    })
  ####

  with pytest.raises(ValueError, match='unknown model visualization lane'):
    standardize_all_model_visualizations({
      'not-a-model-lane': _basic_result(),
    })
  ####
####
