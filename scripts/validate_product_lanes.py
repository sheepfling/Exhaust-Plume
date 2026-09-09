"""Run fidelity-specific local acceptance checks for the current product lanes."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from math import cos, exp, isclose, isfinite, pi, sin
from pathlib import Path
import sys
from types import SimpleNamespace
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))
####

from exhaust_plume import (  # noqa: E402
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  Pose,
  SPECTRAL_RADIANT_INTENSITY_V1,
  SPECTRAL_RAY_TRANSFER_V1,
  SpectralRayTransferRequest,
  VISUAL_SECTIONED_TUBE_V1,
  VisualSampling,
  VisualSectionedTubeRequest,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.contracts import (  # noqa: E402
  canonical_digest,
  SpectralSignatureRequest,
  run_visual_provider_conformance,
)
from exhaust_plume.geometry import SectionedTubeSupport, intersect_sectioned_tube  # noqa: E402
from exhaust_plume.models.gas import (  # noqa: E402
  FrozenMixtureGas,
  SpeciesDefinition,
  SpeciesMassFraction,
)
from exhaust_plume.models.shock_cells import (  # noqa: E402
  ShockCellSolveConfig,
  solve_first_cell_from_exit_state,
)
from exhaust_plume.models.integral import (  # noqa: E402
  IntegralStraightResult,
  IntegralStraightState,
)
from exhaust_plume.models.moc.primitives import CharacteristicState  # noqa: E402
from exhaust_plume.models.plume.curved_plume_closures import (  # noqa: E402
  CurvedPlumeResult,
  CurvedPlumeTermination,
)
from exhaust_plume.models.plume.curved_plume_state import (  # noqa: E402
  CurvedPlumeStation,
)
from exhaust_plume.models.shock_train import (  # noqa: E402
  GeometryFidelity,
  ShockCellMetrics,
  ShockTrainCell,
  ShockTrainResult,
  ShockTrainStatus,
)
from exhaust_plume.contracts.termination import (  # noqa: E402
  TerminationReason,
  TerminationReport,
)
from exhaust_plume.products import (  # noqa: E402
  LineRadiationProfile,
  LtePopulationClosure,
  LteTransition,
  GrayRadiationProfile,
  MissionFpaEvaluator,
  MissionSignatureEvaluator,
  MissionState,
  MissionTimeline,
  MissionVisualizationEvaluator,
  MODEL_VISUALIZATION_LANES,
  ModelSignatureSampling,
  ModelVisualizationLane,
  SectionedGrayRadiationProfile,
  SIGNATURE_ANGULAR_TIMELINE_SCHEMA,
  evaluate_model_signature,
  build_signature_angular_heatmap,
  standardize_all_model_visualizations,
  standardize_model_visualization,
)
from exhaust_plume.radiation import FarFieldRayIntegration, far_field_from_rays  # noqa: E402
from exhaust_plume.validation.measurement_operators import (  # noqa: E402
  BAND_INTEGRATION_OPERATOR_ID,
  PEAK_NORMALIZATION_OPERATOR_ID,
  SPECTRAL_SAMPLING_OPERATOR_ID,
  integrate_spectral_band_rows,
  peak_normalize_spectral_rows,
  sample_spectral_rows,
)
from exhaust_plume.validation.fpa_operators import (  # noqa: E402
  FPA_DIGITIZATION_OPERATOR_ID,
  DetectorResponse,
  FPA_PIXEL_DETECTOR_OPERATOR_ID,
  FpaCameraOptics,
  FpaDigitizationPolicy,
  FpaPixelGeometry,
  digitize_expected_electrons,
  integrate_ray_transfer_to_fpa,
)
from exhaust_plume.validation.fpa_visualization import (  # noqa: E402
  FpaDisplayLayer,
  FpaSourceReference,
  FpaVisualizationInput,
  FpaVisualizationSpec,
  project_fpa_view,
)
from exhaust_plume.validation.sensor_operators import (  # noqa: E402
  ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID,
  BANDPASS_DETECTOR_OPERATOR_ID,
  LOS_FOV_SPECTRUM_OPERATOR_ID,
  apply_atmospheric_path_transfer,
  integrate_bandpass_detector_rows,
  integrate_los_fov_spectrum,
)
from exhaust_plume.validation.lane_contracts import (  # noqa: E402
  validate_signature_table_result,
  validate_straight_visual_result,
)
from exhaust_plume.validation.spectral_comparisons import (  # noqa: E402
  INTRINSIC_SPECTRAL_RADIANT_INTENSITY_UNITS,
  RELATIVE_SPECTRAL_SHAPE_UNITS,
  SpectralCurve,
  SpectralMeasurementSpace,
  compare_declared_peak_normalized_spectral_shape,
)
from exhaust_plume.providers import (  # noqa: E402
  CurvedGrayRayTransferProvider,
  GrayRayTransferDefinition,
  GrayRayTransferProvider,
  LookupInterpolationPolicy,
  SignatureTableDefinition,
  SignatureTableProvider,
  ShockCellVisualDefinition,
  ShockCellVisualOperatingState,
  ShockCellVisualProvider,
  StraightAnalyticalDefinition,
  StraightAnalyticalOperatingState,
  StraightAnalyticalProvider,
)
try:
  from scripts.validate_external_corpus_alignment import preflight_corpus  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - direct script execution
  from validate_external_corpus_alignment import preflight_corpus  # noqa: E402
####


def _fixture() -> dict[str, Any]:
  return json.loads(
    (REPO_ROOT / 'tests' / 'fixtures' / 'physics' / 'first_mvp_regression_v1.json').read_text(
      encoding='utf-8',
    )
  )
####


def _analytical_components(exit_to_ambient_pressure_ratio: float) -> tuple[Any, Any]:
  values = _fixture()['gas']
  gas = CaloricallyPerfectGas.dry_air(gamma=float(values['gamma']))
  factor = 1.0 + (gas.gamma - 1.0) * float(values['mach'])**2 / 2.0
  total_pressure = (
    float(values['ambient_pressure_Pa'])
    * exit_to_ambient_pressure_ratio
    * factor**(gas.gamma / (gas.gamma - 1.0))
  )
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=float(values['mach']),
      total_pressure_Pa=total_pressure,
      total_temperature_K=float(values['total_temperature_K']),
      exit_radius_m=float(values['exit_radius_m']),
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(
      pressure_Pa=float(values['ambient_pressure_Pa']),
      temperature_K=float(values['ambient_temperature_K']),
    ),
    gas,
  )
  return exit_state, ambient
####


def _analytical_state(exit_to_ambient_pressure_ratio: float) -> StraightAnalyticalOperatingState:
  exit_state, ambient = _analytical_components(exit_to_ambient_pressure_ratio)
  return StraightAnalyticalOperatingState(nozzle_exit=exit_state, ambient=ambient)
####


def _shock_cell_state(exit_to_ambient_pressure_ratio: float) -> ShockCellVisualOperatingState:
  exit_state, ambient = _analytical_components(exit_to_ambient_pressure_ratio)
  return ShockCellVisualOperatingState(nozzle_exit=exit_state, ambient=ambient)
####


def _visual_request(frame_id: str) -> VisualSectionedTubeRequest:
  return VisualSectionedTubeRequest(
    output_frame_id=frame_id,
    sampling=VisualSampling(
      maximum_section_count=16,
      maximum_axial_extent_m=8.0,
    ),
    requested_channels=('core_radius_fraction', 'opacity_weight'),
  )
####


def _model_visualization_contract_inputs() -> dict[ModelVisualizationLane, object]:
  """Build small repository-local inputs for all five visual model lanes.

  These are contract fixtures, not observations.  Keeping them here makes the
  executable lane report exercise the same five-lane adapter that the product
  exposes, while the claim metadata continues to distinguish the basic lane
  from the reduced-order, integral, and research MOC lanes.
  """

  operating_state = _analytical_state(1.2)
  basic = solve_first_cell_from_exit_state(
    operating_state.nozzle_exit,
    operating_state.ambient,
    ShockCellSolveConfig(
      exit=operating_state.nozzle_exit,
      ambient=operating_state.ambient,
      expansion_characteristics=2,
      compression_characteristics=1,
      pressure_match_rtol=1.0e-4,
      max_cells=1,
    ),
  )
  ####

  reduced_metrics = tuple(
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
        if index == 1
        else GeometryFidelity.SCALED_REDUCED_ORDER
      ),
    )
    for index in (1, 2)
  )
  reduced = ShockTrainResult(
    cells=tuple(ShockTrainCell(metrics=metric) for metric in reduced_metrics),
    shock_train_end_x_m=4.0,
    supersonic_core_end_x_m=4.0,
    thermal_plume_end_x_m=4.0,
    termination=TerminationReport(
      reason=TerminationReason.SPATIAL_DOMAIN_LIMIT,
      is_physical=False,
      message='repository-local visual contract fixture',
    ),
    status=ShockTrainStatus.TRUNCATED,
    was_domain_truncated=True,
    calibration_id='repository-local-visual-contract-fixture-v1',
  )
  ####

  straight = IntegralStraightResult(
    states=tuple(
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
    ),
    termination_reason=TerminationReason.SPATIAL_DOMAIN_LIMIT,
    termination_x_m=2.0,
    termination_is_physical=False,
    conservation_residuals={
      'momentum_relative': 0.0,
      'total_enthalpy_relative': 0.0,
    },
  )
  ####

  curved = CurvedPlumeResult(
    stations=tuple(
      CurvedPlumeStation(
        arc_length_m=float(index),
        position_m=(float(index), 0.1 * index * index, 0.0),
        mass_flow_kgps=10.0,
        momentum_flux_N=(1_000.0, 0.0, 0.0),
        momentum_derivative_Npm=(0.0, 0.0, 0.0),
        velocity_mps=(100.0, 5.0, 0.0),
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
        ambient_velocity_mps=(0.0, 0.0, 0.0),
        ambient_temperature_K=300.0,
        ambient_density_kgpm3=1.0,
        relative_velocity_mps=(100.0, 5.0, 0.0),
        entrainment_kgpspm=0.1,
        curvature_per_m=0.01,
        slenderness_ratio=0.1,
      )
      for index in range(3)
    ),
    termination=CurvedPlumeTermination.DOMAIN_LIMIT,
    solver_message='repository-local visual contract fixture',
    function_evaluations=3,
  )
  ####

  class _ContractMocField:
    cells = (
      SimpleNamespace(
        vertices_xr_m=((0.5, 0.0), (1.0, 0.4), (1.5, 0.0)),
      ),
      SimpleNamespace(
        vertices_xr_m=((1.0, 0.0), (1.5, 0.0), (2.0, 0.2)),
      ),
    )
    shock_boundary_points_m = ((0.5, 0.4), (1.0, 0.3), (1.5, 0.0))
    ambient_boundary_points_m = ((1.5, 0.0), (1.75, 0.15), (2.0, 0.0))
    centerline_boundary_points_m = (
      (0.5, 0.0),
      (1.0, 0.0),
      (1.5, 0.0),
      (2.0, 0.0),
    )
    centerline_boundary_states = tuple(
      CharacteristicState(
        x_m=x,
        y_m=0.0,
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      )
      for x in (0.5, 1.0, 1.5, 2.0)
    )
    centerline_boundary_total_pressure_Pa = (
      200_000.0,
      190_000.0,
      180_000.0,
      170_000.0,
    )
    physical_closure_verified = True
    state_sampling_available = True

    @staticmethod
    def state_at(point: tuple[float, float]) -> CharacteristicState:
      return CharacteristicState(
        x_m=float(point[0]),
        y_m=float(point[1]),
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      )

    @staticmethod
    def total_pressure_at(_point: tuple[float, float]) -> float:
      return 180_000.0
    ####

  moc = SimpleNamespace(
    status='converged-global-physical-closure',
    field=_ContractMocField(),
    physical_closure_verified=True,
    state_sampling_available=True,
    production_claim_allowed=False,
  )
  return {
    ModelVisualizationLane.BASIC_SHOCK_CELL: basic,
    ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN: reduced,
    ModelVisualizationLane.STRAIGHT_INTEGRAL: straight,
    ModelVisualizationLane.CURVED_INTEGRAL: curved,
    ModelVisualizationLane.PLANAR_MOC: moc,
  }
####


def _run_model_visualization_lanes() -> dict[str, Any]:
  """Exercise the common renderer-neutral bundle for every visual lane."""

  bundles = standardize_all_model_visualizations(
    _model_visualization_contract_inputs(),
    frame_id='source-local',
    section_count=12,
  )
  expected_lanes = tuple(lane.value for lane in MODEL_VISUALIZATION_LANES)
  actual_lanes = tuple(bundle.lane.value for bundle in bundles)
  shape_passed = bool(
    actual_lanes == expected_lanes
    and all(len(bundle.sectioned_tube.sections) >= 2 for bundle in bundles)
    and all(bundle.sectioned_tube.frame_id == 'source-local' for bundle in bundles)
  )
  claim_separation_passed = bool(
    bundles[0].claims.production_claim_allowed
    and all(not bundle.claims.production_claim_allowed for bundle in bundles[1:])
  )
  serialization_passed = all(
    isinstance(bundle.model_dump(), dict)
    and bool(canonical_digest(bundle.model_dump()))
    for bundle in bundles
  )
  passed = shape_passed and claim_separation_passed and serialization_passed
  return {
    'lane_id': 'standardized-visualization-all-five-v1',
    'status': 'passed' if passed else 'failed',
    'lanes': list(actual_lanes),
    'bundle_count': len(bundles),
    'common_bundle_shape_passed': shape_passed,
    'claim_separation_passed': claim_separation_passed,
    'deterministic_bundle_serialization_passed': serialization_passed,
    'production_claim_allowed': {
      bundle.lane.value: bundle.claims.production_claim_allowed
      for bundle in bundles
    },
    'external_comparison': {
      'status': 'pending',
      'reason': (
        'These are repository-local contract fixtures; provider-bound visual '
        'observations remain a separate release gate.'
      ),
    },
    'claim_ceiling': (
      'Common renderer-neutral visualization contract only; reduced-order '
      'and planar-MOC bundles retain their declared non-production ceilings.'
    ),
  }
####


def _run_visual_lane() -> dict[str, Any]:
  pose = Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  provider_specs = (
    (
      StraightAnalyticalProvider(),
      StraightAnalyticalDefinition(nozzle_radius_m=1.0),
      _analytical_state,
      'source-local',
    ),
    (
      ShockCellVisualProvider(),
      ShockCellVisualDefinition(nozzle_radius_m=1.0),
      _shock_cell_state,
      'straight-axisymmetric-xr',
    ),
  )
  provider_reports: list[dict[str, Any]] = []
  case_summaries: list[dict[str, Any]] = []
  for provider, definition, state_factory, frame_id in provider_specs:
    request = _visual_request(frame_id)
    provider_case_invariants: list[dict[str, Any]] = []
    for ratio in (1.0, 1.2, 0.85):
      state = state_factory(ratio)
      session = provider.create_session(definition=definition)
      snapshot = session.create_snapshot(
        time_s=0.0,
        source_pose=pose,
        dynamic_state={'operating_state': state},
        ambient_state={},
      )
      result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, request)
      invariant_report = validate_straight_visual_result(
        result,
        request,
        expected_output_frame_id=frame_id,
      )
      provider_case_invariants.append(asdict(invariant_report))
      case_summaries.append({
        'exit_to_ambient_pressure_ratio': ratio,
        'section_count': len(result.sections),
        'output_channels': sorted(result.channels),
        'applicability': result.metadata.applicability.status.value,
        'provider_id': result.metadata.provenance.provider_id,
        'radiation_claim': result.metadata.claims.radiation.value,
        'local_geometry_invariants': asdict(invariant_report),
      })
    ####

    conformance = run_visual_provider_conformance(
      provider.descriptor,
      lambda provider=provider, definition=definition, state_factory=state_factory, pose=pose: provider.create_session(
        definition=definition,
      ).create_snapshot(
        time_s=0.0,
        source_pose=pose,
        dynamic_state={'operating_state': state_factory(1.2)},
        ambient_state={},
      ),
      request,
    )
    provider_reports.append({
      'provider_id': provider.descriptor.provider_id,
      'contract_conformance': conformance.passed,
      'deterministic_serialization': conformance.deterministic_serialization,
      'output_channels': case_summaries[-1]['output_channels'],
      'local_geometry_invariants': {
        'status': 'passed' if all(
          case['status'] == 'passed' for case in provider_case_invariants
        ) else 'failed',
        'cases': provider_case_invariants,
      },
    })
  ####
  standardized_lanes = _run_model_visualization_lanes()
  all_conformant = all(report['contract_conformance'] for report in provider_reports)
  all_deterministic = all(report['deterministic_serialization'] for report in provider_reports)
  all_geometry_invariants = all(
    report['local_geometry_invariants']['status'] == 'passed'
    for report in provider_reports
  )
  standardized_lanes_passed = standardized_lanes['status'] == 'passed'
  return {
    'lane_id': 'shock-cell-basic-v1',
    'product_id': VISUAL_SECTIONED_TUBE_V1.capability.wire_id,
    'provider_ids': [report['provider_id'] for report in provider_reports],
    'status': 'passed' if all(
      (all_conformant, all_deterministic, all_geometry_invariants, standardized_lanes_passed)
    ) else 'failed',
    'contract_conformance': all_conformant,
    'deterministic_serialization': all_deterministic,
    'local_geometry_invariants': 'passed' if all_geometry_invariants else 'failed',
    'standardized_model_lanes': standardized_lanes,
    'provider_reports': provider_reports,
    'cases': case_summaries,
    'external_comparison': {
      'status': 'pending',
      'reason': 'The current visual contract exposes geometry/display channels, while the recovered CJ gate requires explicit pressure/velocity/Mach feature operators.'
    },
    'claim_ceiling': 'Engineering-approximate straight visual geometry and named display features only.',
  }
####


def _run_mission_time_product_lane() -> dict[str, Any]:
  """Exercise prescribed-time composition across Visual, Signature, and FPA."""

  def mission_pose(time_s: float) -> Pose:
    return Pose(
      frame_id='world',
      translation_m=(10.0 * time_s, 2.0 * time_s, 100.0 * time_s),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    )
  ####

  timeline = MissionTimeline(tuple(
    MissionState(
      time_s=time_s,
      source_pose=mission_pose(time_s),
      geopotential_altitude_m=100.0 * time_s,
      throttle_fraction=1.0 - 0.05 * time_s,
      remaining_propellant_mass_kg=100.0 - 5.0 * time_s,
      operating_point_id=f'mission-{time_s:g}',
      dynamic_state={'engine_mode': 'boost' if time_s < 5.0 else 'sustain'},
      ambient_state={'atmosphere_model': 'declared-standard'},
    )
    for time_s in (0.0, 5.0, 10.0)
  ))
  mission_times_s = tuple(state.time_s for state in timeline.states)
  ####

  basic_result = _model_visualization_contract_inputs()[
    ModelVisualizationLane.BASIC_SHOCK_CELL
  ]
  visualization = standardize_model_visualization(
    basic_result,
    lane=ModelVisualizationLane.BASIC_SHOCK_CELL,
    frame_id='source-local',
    section_count=12,
  )
  visual_evaluator = MissionVisualizationEvaluator(
    timeline=timeline,
    visualization_at=lambda _state: visualization,
    request=VisualSectionedTubeRequest(
      output_frame_id=visualization.frame_id,
      sampling=VisualSampling(maximum_section_count=8),
    ),
  )
  visual_samples = tuple(
    visual_evaluator.sample_at(time_s) for time_s in mission_times_s
  )
  visual_passed = bool(
    tuple(sample.state.time_s for sample in visual_samples) == mission_times_s
    and all(
      sample.visual_product.metadata.snapshot.time_s == sample.state.time_s
      and sample.visual_product.metadata.snapshot.source_pose == sample.state.source_pose
      and sample.visual_product.metadata.provenance.metadata[
        'mission_timeline_schema'
      ] == 'plume.mission-timeline@1'
      for sample in visual_samples
    )
  )
  ####

  def optical_profile_for_state(state: MissionState) -> GrayRadiationProfile:
    throttle = state.throttle_fraction or 0.0
    return GrayRadiationProfile(
      wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
      source_function_w_sr_m=(2.0 * throttle, 3.0 * throttle, 4.0 * throttle),
      absorption_coefficient_per_m=(0.5, 1.0, 1.5),
      profile_id=f'mission-gray-{state.time_s:g}',
    )
  ####

  signature_evaluator = MissionSignatureEvaluator(
    timeline=timeline,
    visualization_at=lambda _state: visualization,
    optical_profile_at=optical_profile_for_state,
    sampling=ModelSignatureSampling(
      source_to_observer_directions=(
        (1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
      ),
      transverse_sample_count=5,
    ),
  )
  signature_timeline = signature_evaluator.evaluate_timeline(mission_times_s)
  signature_heatmap = build_signature_angular_heatmap(
    signature_timeline,
    time_s=5.0,
    wavelength_index=1,
  )
  signature_query = signature_evaluator.query_at(
    time_s=5.0,
    direction_index=0,
    wavelength_index=1,
  )
  signature_passed = bool(
    signature_timeline.times_s == mission_times_s
    and signature_heatmap.time_s == 5.0
    and signature_heatmap.valid_direction_count == 2
    and signature_query.source_result_id
    == signature_timeline.sample_at(5.0).result.metadata.result_id
    and signature_timeline.sample_at(0.0).result.spectral_radiant_intensity
    != signature_timeline.sample_at(5.0).result.spectral_radiant_intensity
    and all(
      sample.result.metadata.snapshot.time_s == sample.time_s
      for sample in signature_timeline.samples
    )
  )
  ####

  def ray_transfer_for_state(
    state: MissionState,
  ) -> tuple[tuple[float, ...], Any]:
    definition = _gray_definition()
    session = GrayRayTransferProvider().create_session(definition=definition)
    try:
      snapshot = session.create_snapshot(
        time_s=state.time_s,
        source_pose=state.source_pose,
        dynamic_state=state.snapshot_dynamic_state(),
        ambient_state=state.snapshot_ambient_state(),
      )
      result = snapshot.evaluate(
        SPECTRAL_RAY_TRANSFER_V1,
        SpectralRayTransferRequest(
          ray_frame_id='sensor',
          ray_origins_m=((-2.0, 0.0, 0.0), (-2.0, 2.0, 0.0)),
          ray_directions=((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
          ray_t_min_m=(0.0, 0.0),
          ray_t_max_m=(10.0, 10.0),
          wavelengths_m=definition.wavelengths_m,
        ),
      )
    finally:
      session.close()
    ####
    return definition.wavelengths_m, result
  ####

  def fpa_geometry(_state: MissionState) -> FpaPixelGeometry:
    return FpaPixelGeometry(
      width_px=2,
      height_px=1,
      ray_pixel_indices_row_col=((0, 0), (0, 1)),
      ray_collection_weights_m2_sr=(1.0e-6, 2.0e-6),
      camera_optics=FpaCameraOptics(
        camera_id='mission-camera-v1',
        focal_length_m=0.05,
        pixel_pitch_m=(5.0e-6, 5.0e-6),
        principal_point_px=(0.5, 0.0),
        aperture_area_m2=1.0e-4,
      ),
    )
  ####

  def fpa_detector(_state: MissionState) -> DetectorResponse:
    return DetectorResponse(
      wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
      quantum_efficiency=(0.5, 0.6, 0.7),
      optical_throughput=(0.8, 0.9, 1.0),
      response_id='mission-detector-v1',
    )
  ####

  digitization_policy = FpaDigitizationPolicy(
    electrons_per_count=1.0e12,
    bit_depth=16,
    policy_id='mission-adc-v1',
  )
  fpa_evaluator = MissionFpaEvaluator(
    timeline=timeline,
    ray_transfer_at=ray_transfer_for_state,
    geometry_at=fpa_geometry,
    detector_at=fpa_detector,
    exposure_s_at=lambda state: 1.0 + state.time_s / 10.0,
    digitization_policy_at=lambda _state: digitization_policy,
  )
  fpa_timeline = fpa_evaluator.evaluate_timeline(mission_times_s)
  fpa_initial = fpa_timeline.sample_at(0.0)
  fpa_midpoint = fpa_timeline.sample_at(5.0)
  fpa_projection = fpa_timeline.project_at(5.0)
  fpa_passed = bool(
    fpa_timeline.times_s == mission_times_s
    and fpa_initial.ray_transfer.metadata.snapshot.time_s == 0.0
    and fpa_midpoint.ray_transfer.metadata.snapshot.time_s == 5.0
    and fpa_midpoint.ray_transfer.metadata.snapshot.source_pose
    == fpa_midpoint.state.source_pose
    and fpa_midpoint.exposure_s == 1.5
    and fpa_midpoint.image.expected_electrons[0][0]
    > fpa_initial.image.expected_electrons[0][0]
    and fpa_midpoint.digitized_available
    and fpa_midpoint.inputs.operator_ids == (
      FPA_PIXEL_DETECTOR_OPERATOR_ID,
      FPA_DIGITIZATION_OPERATOR_ID,
    )
    and fpa_projection.selected_pixel.valid
  )
  ####

  passed = visual_passed and signature_passed and fpa_passed
  return {
    'lane_id': 'mission-time-product-composition-v1',
    'status': 'passed' if passed else 'failed',
    'mission_times_s': list(mission_times_s),
    'visualization': {
      'status': 'passed' if visual_passed else 'failed',
      'sample_count': len(visual_samples),
      'snapshot_times_s': [
        sample.visual_product.metadata.snapshot.time_s
        for sample in visual_samples
      ],
      'model_lane': visualization.lane_id,
    },
    'signature': {
      'status': 'passed' if signature_passed else 'failed',
      'timeline_schema': SIGNATURE_ANGULAR_TIMELINE_SCHEMA,
      'heatmap_time_s': signature_heatmap.time_s,
      'heatmap_valid_direction_count': signature_heatmap.valid_direction_count,
      'query_source_result_id': signature_query.source_result_id,
      'result_ids': [
        sample.result.metadata.result_id
        for sample in signature_timeline.samples
      ],
    },
    'focal_plane_array': {
      'status': 'passed' if fpa_passed else 'failed',
      'timeline_times_s': list(fpa_timeline.times_s),
      'operator_ids': list(fpa_midpoint.inputs.operator_ids),
      'camera_id': fpa_midpoint.geometry.camera_optics.camera_id,
      'midpoint_exposure_s': fpa_midpoint.exposure_s,
      'selected_pixel_valid': fpa_projection.selected_pixel.valid,
      'source_snapshot_ids': [
        sample.source.snapshot_id for sample in fpa_timeline.samples
      ],
    },
    'external_comparison': {
      'status': 'pending',
      'reason': (
        'The mission schedule and callbacks are repository-local fixtures; '
        'provider-bound trajectory, observer, detector, and atmospheric '
        'measurements remain a separate release gate.'
      ),
    },
    'claim_ceiling': (
      'Prescribed mission-time composition with exact source lineage only; '
      'no solved transient, trajectory, chemistry, detector-noise, or '
      'external product claim.'
    ),
  }
####


_SIGNATURE_ASSET_ID = 'repository-synthetic-signature-contract-fixture-v1'
_SIGNATURE_OPERATING_POINT_ID = 'repository-synthetic-contract-fixture'


def _signature_asset_payload() -> dict[str, Any]:
  return {
    'schema': 'exhaust-plume.signature-table-fixture@1',
    'asset_id': _SIGNATURE_ASSET_ID,
    'operating_point_id': _SIGNATURE_OPERATING_POINT_ID,
    'frame_id': 'source-local',
    'wavelengths_m': (1.0e-6, 2.0e-6, 3.0e-6),
    'direction_cosine_nodes': (-0.5, 0.0, 0.5),
    'spectral_radiant_intensity_w_sr_m': (
      (0.5, 1.5, 2.5),
      (1.0, 2.0, 3.0),
      (1.5, 2.5, 3.5),
    ),
    'absolute_standard_uncertainty_w_sr_m': (
      (0.05, 0.05, 0.05),
      (0.1, 0.1, 0.1),
      (0.15, 0.15, 0.15),
    ),
  }
####


def _signature_definition() -> SignatureTableDefinition:
  payload = _signature_asset_payload()
  return SignatureTableDefinition(
    frame_id=payload['frame_id'],
    wavelengths_m=payload['wavelengths_m'],
    direction_cosine_nodes=payload['direction_cosine_nodes'],
    spectral_radiant_intensity_w_sr_m=payload['spectral_radiant_intensity_w_sr_m'],
    absolute_standard_uncertainty_w_sr_m=payload['absolute_standard_uncertainty_w_sr_m'],
    asset_id=_SIGNATURE_ASSET_ID,
    operating_point_id=_SIGNATURE_OPERATING_POINT_ID,
    asset_sha256=canonical_digest(payload),
    wavelength_interpolation=LookupInterpolationPolicy.LINEAR,
    angular_interpolation=LookupInterpolationPolicy.LINEAR,
  )
####


def _run_lte_line_signature_probe() -> dict[str, Any]:
  """Exercise the source-bound LTE line bridge without claiming chemistry."""

  operating_state = _analytical_state(1.2)
  visual_solution = solve_first_cell_from_exit_state(
    operating_state.nozzle_exit,
    operating_state.ambient,
    ShockCellSolveConfig(
      exit=operating_state.nozzle_exit,
      ambient=operating_state.ambient,
      expansion_characteristics=2,
      compression_characteristics=1,
      pressure_match_rtol=1.0e-4,
      max_cells=1,
    ),
  )
  visualization = standardize_model_visualization(
    visual_solution,
    lane=ModelVisualizationLane.BASIC_SHOCK_CELL,
  )
  mixture = FrozenMixtureGas(
    mixture_id='product-lane-lte-population-v1',
    species=(
      SpeciesDefinition(
        species='product-lane-gas',
        molecular_weight_kg_per_mol=0.020,
        cp_JpkgK=1_000.0,
      ),
    ),
    species_mass_fractions=(SpeciesMassFraction(species='product-lane-gas', mass_fraction=1.0),),
    valid_temperature_range_K=(300.0, 2_000.0),
  )
  source_state = mixture.state_at(120_000.0, 1_200.0)
  population = LtePopulationClosure.from_state(
    LteTransition(
      species='product-lane-gas',
      center_wavelength_m=5.0e-6,
      lower_state_energy_J=0.0,
      upper_state_energy_J=1.0e-20,
      lower_degeneracy=1.0,
      upper_degeneracy=1.0,
      integrated_absorption_cross_section_m3=2.0e-28,
      molecular_mass_kg=4.65e-26,
      label='product-lane-lte-transition',
    ),
    source_state,
    partition_function=4.0,
    path_length_m=1.0,
  )
  line_profile = LineRadiationProfile(
    wavelengths_m=(4.5e-6, 5.0e-6, 5.5e-6),
    lines=(population.to_spectral_line(label='product-lane-lte-line'),),
    source_temperature_K=source_state.temperature_K,
    path_length_m=1.0,
    profile_id='product-lane-lte-line-profile-v1',
    source_mixture_state=source_state,
  )
  signature = evaluate_model_signature(
    visualization,
    line_profile,
    sampling=ModelSignatureSampling(
      source_to_observer_directions=((1.0, 0.0, 0.0),),
      transverse_sample_count=5,
    ),
  )
  source = line_profile.source_function_w_sr_m
  opacity = line_profile.absorption_coefficient_per_m
  passed = (
    signature.metadata.claims.radiation.value == 'spectral_engineering'
    and signature.metadata.provenance.metadata['optical_profile_mode'] == 'lte-line-by-line-voigt'
    and signature.metadata.provenance.metadata['production_claim_allowed'] == 'false'
    and len(line_profile.lines) == 1
    and line_profile.as_report()['population_closure_count'] == 1
    and all(isfinite(value) and value > 0.0 for value in source)
    and opacity[1] > opacity[0]
    and opacity[1] > opacity[2]
    and any(
      isfinite(value) and value > 0.0
      for row in signature.spectral_radiant_intensity
      for value in row
    )
  )
  return {
    'status': 'passed' if passed else 'failed',
    'profile_id': line_profile.profile_id,
    'adapter_schema': signature.metadata.provenance.metadata['signature_adapter_schema'],
    'optical_profile_mode': signature.metadata.provenance.metadata['optical_profile_mode'],
    'line_count': len(line_profile.lines),
    'population_closure_count': line_profile.as_report()['population_closure_count'],
    'source_model': 'LTE-Planck-source-with-caller-bound-population',
    'line_shape_model': 'normalized-wavelength-domain-Voigt',
    'source_temperature_K': line_profile.source_temperature_K,
    'wavelengths_m': list(line_profile.wavelengths_m),
    'peak_absorption_coefficient_per_m': max(opacity),
    'radiation_claim': signature.metadata.claims.radiation.value,
    'production_claim_allowed': signature.metadata.provenance.metadata['production_claim_allowed'],
    'claim_status': line_profile.as_report()['claim_status'],
    'scope': 'caller-bound LTE population from explicit transition data and CHEM-0 state; no reactions, non-LTE inference, atmosphere, detector, or external validation',
  }
####


def _run_sensor_space_operator_probe() -> dict[str, Any]:
  """Exercise downstream sensor math without inventing an external case."""

  wavelengths = (1.0e-6, 2.0e-6, 3.0e-6)
  source = ((2.0, 4.0, 6.0), (4.0, 8.0, 12.0))
  path = apply_atmospheric_path_transfer(
    wavelengths,
    source,
    ((0.5, 0.5, 0.5), (0.25, 0.25, 0.25)),
    path_radiance=((1.0, 1.0, 1.0), (2.0, 2.0, 2.0)),
  )
  fov = integrate_los_fov_spectrum(
    wavelengths,
    ((1.0, 0.0, 0.0), (cos(0.2), sin(0.2), 0.0)),
    path.values,
    observer_direction=(1.0, 0.0, 0.0),
    solid_angle_weights_sr=(0.25, 0.75),
    fov_half_angle_rad=0.3,
    source_semantics=path.source_semantics,
  )
  band = integrate_bandpass_detector_rows(
    wavelengths,
    (fov.values,),
    wavelengths,
    (0.0, 1.0, 0.0),
    band_min_m=1.5e-6,
    band_max_m=2.5e-6,
    normalized_response=True,
    response_id='synthetic-bandpass-v1',
  )
  passed = (
    path.values == ((2.0, 3.0, 4.0), (3.0, 4.0, 5.0))
    and path.validity_mask == ((True, True, True), (True, True, True))
    and fov.selected_ray_indices == (0, 1)
    and fov.validity_mask == (True, True, True)
    and fov.values == (2.75, 3.75, 4.75)
    and band.validity_mask == (True,)
    and isclose(band.values[0], 3.75, rel_tol=1.0e-12, abs_tol=1.0e-12)
  )
  return {
    'status': 'passed' if passed else 'failed',
    'operator_ids': [
      ATMOSPHERE_PATH_TRANSFER_OPERATOR_ID,
      LOS_FOV_SPECTRUM_OPERATOR_ID,
      BANDPASS_DETECTOR_OPERATOR_ID,
    ],
    'path_transfer_passed': path.values == ((2.0, 3.0, 4.0), (3.0, 4.0, 5.0)),
    'los_fov_passed': fov.values == (2.75, 3.75, 4.75) and fov.validity_mask == (True, True, True),
    'bandpass_passed': band.validity_mask == (True,) and isclose(
      band.values[0], 3.75, rel_tol=1.0e-12, abs_tol=1.0e-12,
    ),
    'scope': 'synthetic downstream operator math only; no external observer, atmosphere, calibration, or detector asset',
    'claim_status': 'not_accepted',
  }
####


def _run_signature_lane() -> dict[str, Any]:
  provider = SignatureTableProvider()
  definition = _signature_definition()
  request = SpectralSignatureRequest(
    direction_frame_id='source-local',
    source_to_observer_directions=((0.5, 3**0.5 / 2.0, 0.0),),
    wavelengths_m=(1.5e-6, 2.5e-6),
  )
  snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  result = snapshot.evaluate(
    SPECTRAL_RADIANT_INTENSITY_V1,
    request,
  )
  probe_result = snapshot.evaluate(
    SPECTRAL_RADIANT_INTENSITY_V1,
    SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=((0.5, 3**0.5 / 2.0, 0.0),),
      wavelengths_m=definition.wavelengths_m,
    ),
  )
  expected = ((2.0, 3.0),)
  contract_passed = result.spectral_radiant_intensity == expected and all(result.validity_mask[0])
  invariant_report = validate_signature_table_result(
    result,
    request,
    expected_asset_id=definition.asset_id,
    expected_asset_sha256=definition.asset_sha256 or '',
  )
  operator_source_wavelengths = definition.wavelengths_m
  operator_source_values = ((1.0, 2.0, 3.0),)
  sampled = sample_spectral_rows(
    operator_source_wavelengths,
    operator_source_values,
    (1.5e-6, 2.5e-6),
  )
  normalized = peak_normalize_spectral_rows(
    sampled.wavelengths_m,
    sampled.values,
    validity_mask=sampled.validity_mask,
  )
  band = integrate_spectral_band_rows(
    operator_source_wavelengths,
    operator_source_values,
    1.5e-6,
    2.5e-6,
  )
  sensor_space = _run_sensor_space_operator_probe()
  intrinsic_curve = SpectralCurve(
    wavelengths_m=definition.wavelengths_m,
    values=probe_result.spectral_radiant_intensity[0],
    measurement_space=SpectralMeasurementSpace.INTRINSIC_RADIANT_INTENSITY,
    units=INTRINSIC_SPECTRAL_RADIANT_INTENSITY_UNITS,
    source_semantics='synthetic signature-table fixture output',
  )
  relative_curve = SpectralCurve(
    wavelengths_m=definition.wavelengths_m,
    values=(1.0 / 3.0, 2.0 / 3.0, 1.0),
    measurement_space=SpectralMeasurementSpace.RELATIVE_SHAPE,
    units=RELATIVE_SPECTRAL_SHAPE_UNITS,
    source_semantics='synthetic normalized diagnostic curve',
  )
  measurement_space_mismatch = compare_declared_peak_normalized_spectral_shape(
    intrinsic_curve,
    relative_curve,
  )
  same_space_shape = compare_declared_peak_normalized_spectral_shape(
    relative_curve,
    relative_curve,
  )
  measurement_space_guard_passed = (
    measurement_space_mismatch.status == 'blocked-measurement-space-mismatch'
    and same_space_shape.status == 'full-domain-computed'
  )
  measurement_space_operators_passed = (
    sampled.values == ((1.5, 2.5),)
    and sampled.validity_mask == ((True, True),)
    and normalized.values == ((0.6, 1.0),)
    and normalized.validity_mask == ((True, True),)
    and normalized.normalization_factors == (2.5,)
    and len(band.values) == 1
    and isclose(band.values[0], 2.0e-6, rel_tol=1.0e-12, abs_tol=1.0e-18)
    and band.validity_mask == (True,)
    and sensor_space['status'] == 'passed'
    and measurement_space_guard_passed
  )
  line_bridge = _run_lte_line_signature_probe()
  line_bridge_passed = line_bridge['status'] == 'passed'
  local_validation_passed = (
    contract_passed
    and invariant_report.status == 'passed'
    and measurement_space_operators_passed
    and measurement_space_guard_passed
    and line_bridge_passed
  )
  return {
    'lane_id': 'signature-table-mvp-v1',
    'product_id': SPECTRAL_RADIANT_INTENSITY_V1.capability.wire_id,
    'provider_id': provider.descriptor.provider_id,
    'status': 'passed' if local_validation_passed else 'failed',
    'contract_interpolation_passed': contract_passed,
    'local_contract_invariants': asdict(invariant_report),
    'measurement_space_operators': {
      'status': 'passed' if measurement_space_operators_passed else 'failed',
      'operator_ids': [
        SPECTRAL_SAMPLING_OPERATOR_ID,
        PEAK_NORMALIZATION_OPERATOR_ID,
        BAND_INTEGRATION_OPERATOR_ID,
        *sensor_space['operator_ids'],
      ],
      'sensor_sampling_passed': sampled.values == ((1.5, 2.5),),
      'peak_normalization_passed': normalized.values == ((0.6, 1.0),),
      'band_integration_passed': len(band.values) == 1 and isclose(
        band.values[0], 2.0e-6, rel_tol=1.0e-12, abs_tol=1.0e-18,
      ),
      'sensor_space_probe': sensor_space,
      'measurement_space_guard': {
        'status': 'passed' if measurement_space_guard_passed else 'failed',
        'cross_space_status': measurement_space_mismatch.status,
        'same_space_status': same_space_shape.status,
        'claim_status': 'diagnostic-only',
        'scope': 'measurement-space compatibility gate; no external curve is accepted by this fixture',
      },
      'scope': 'spectral-array and synthetic downstream sensor-operator math only; no external observer, atmosphere, detector, or source calibration',
    },
    'explicit_lte_line_source': line_bridge,
    'output_shape': [len(result.spectral_radiant_intensity), len(result.spectral_radiant_intensity[0])],
    'output_units': 'W sr^-1 m^-1',
    'wavelengths_m': list(definition.wavelengths_m),
    'measurement_probe': {
      'direction_unit': [0.5, 3**0.5 / 2.0, 0.0],
      'wavelengths_m': list(definition.wavelengths_m),
      'spectral_radiant_intensity_w_sr_m': list(probe_result.spectral_radiant_intensity[0]),
    },
    'validity_mask': result.validity_mask,
    'radiation_claim': result.metadata.claims.radiation.value,
    'asset_source': 'repository synthetic contract fixture',
    'asset_id': definition.asset_id,
    'asset_sha256': definition.asset_sha256,
    'external_comparison': {
      'status': 'pending',
      'reason': 'Recovered spectral observations are sensor-space or relative-shape products; generic LOS, path, and bandpass operators now pass synthetic probes, but the signature provider still lacks a corpus-bound observer, source-calibration, and detector scenario.'
    },
    'claim_ceiling': 'Versioned table/interpolation and caller-bound LTE line-source/population spectral engineering only; no reactions, non-LTE inference, atmosphere, detector, or external validation claim.',
  }
####


def _gray_definition() -> GrayRayTransferDefinition:
  return GrayRayTransferDefinition(
    frame_id='sensor',
    support=SectionedTubeSupport(
      frame_id='sensor',
      centers_m=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
      radii_m=(1.0, 1.0),
    ),
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    source_function_w_sr_m=(2.0, 4.0, 8.0),
    absorption_coefficient_per_m=(0.5, 1.0, 2.0),
  )
####


def _run_optical_lane() -> dict[str, Any]:
  provider = GrayRayTransferProvider()
  definition = _gray_definition()
  pose = Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0), (-2.0, 2.0, 0.0)),
    ray_directions=((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    ray_t_min_m=(0.0, 0.0),
    ray_t_max_m=(10.0, 10.0),
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
  )
  first_snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=pose,
    dynamic_state={},
    ambient_state={},
  )
  second_snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=pose,
    dynamic_state={},
    ambient_state={},
  )
  first = first_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  second = second_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  expected_transmittance = tuple(exp(-2.0 * coefficient) for coefficient in definition.absorption_coefficient_per_m)
  expected_source = tuple(
    source * (1.0 - transmission)
    for source, transmission in zip(definition.source_function_w_sr_m, expected_transmittance)
  )
  sectioned_profile = SectionedGrayRadiationProfile(
    wavelengths_m=definition.wavelengths_m,
    source_function_w_sr_m_by_section=(
      (1.0, 2.0, 3.0),
      (3.0, 4.0, 5.0),
    ),
    absorption_coefficient_per_m_by_section=(
      definition.absorption_coefficient_per_m,
      definition.absorption_coefficient_per_m,
    ),
    profile_id='product-lane-sectioned-gray-probe',
  )
  sectioned_definition = GrayRayTransferDefinition(
    frame_id='sensor',
    support=SectionedTubeSupport(
      frame_id='sensor',
      centers_m=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
      radii_m=(1.0, 1.0, 1.0),
    ),
    wavelengths_m=sectioned_profile.wavelengths_m,
    source_function_w_sr_m_by_section=sectioned_profile.source_function_w_sr_m_by_section,
    absorption_coefficient_per_m_by_section=sectioned_profile.absorption_coefficient_per_m_by_section,
    asset_id='product-lane-sectioned-gray-definition',
  )
  sectioned_snapshot = provider.create_session(definition=sectioned_definition).create_snapshot(
    time_s=0.0,
    source_pose=pose,
    dynamic_state={},
    ambient_state={},
  )
  sectioned_request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0),),
    ray_directions=((1.0, 0.0, 0.0),),
    ray_t_min_m=(0.0,),
    ray_t_max_m=(10.0,),
    wavelengths_m=sectioned_profile.wavelengths_m,
  )
  sectioned = sectioned_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, sectioned_request)
  section_transmittance = tuple(exp(-coefficient) for coefficient in definition.absorption_coefficient_per_m)
  expected_sectioned_transmittance = tuple(value * value for value in section_transmittance)
  expected_sectioned_source = tuple(
    (near + far * transmission) * (1.0 - transmission)
    for near, far, transmission in zip(
      sectioned_profile.source_function_w_sr_m_by_section[0],
      sectioned_profile.source_function_w_sr_m_by_section[1],
      section_transmittance,
    )
  )
  piecewise_axial_passed = (
    sectioned.metadata.provenance.metadata['optical_property_mode'] == 'piecewise-axial-section'
    and sectioned.metadata.provenance.metadata['optical_property_section_count'] == '2'
    and all(isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12) for actual, expected in zip(sectioned.source_spectral_radiance[0], expected_sectioned_source))
    and all(isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12) for actual, expected in zip(sectioned.background_transmittance[0], expected_sectioned_transmittance))
  )
  def curved_support(section_count: int) -> SectionedTubeSupport:
    centers = tuple(
      (
        5.0 * cos(index * pi / (2.0 * (section_count - 1))),
        5.0 * sin(index * pi / (2.0 * (section_count - 1))),
        0.0,
      )
      for index in range(section_count)
    )
    return SectionedTubeSupport(
      frame_id='sensor',
      centers_m=centers,
      radii_m=(0.4,) * section_count,
    )
  ####

  spatial_refinement_lengths = []
  for section_count in (3, 5, 9, 17):
    intervals = intersect_sectioned_tube(
      (-1.0, 2.5, 0.0),
      (1.0, 0.0, 0.0),
      curved_support(section_count),
      t_max_m=12.0,
    )
    spatial_refinement_lengths.append(sum(interval.t_exit_m - interval.t_enter_m for interval in intervals))
  ####
  straight_refinement_lengths = []
  for section_count in (2, 3, 5, 9):
    straight_support = SectionedTubeSupport(
      frame_id='sensor',
      centers_m=tuple((2.0 * index / (section_count - 1), 0.0, 0.0) for index in range(section_count)),
      radii_m=(1.0,) * section_count,
    )
    straight_intervals = intersect_sectioned_tube(
      (-2.0, 0.0, 0.0),
      (1.0, 0.0, 0.0),
      straight_support,
      t_max_m=10.0,
    )
    straight_refinement_lengths.append(sum(interval.t_exit_m - interval.t_enter_m for interval in straight_intervals))
  ####
  spatial_refinement_passed = all(isclose(length, 4.0, rel_tol=0.0, abs_tol=1.0e-12) for length in straight_refinement_lengths)
  coarse_request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0),),
    ray_directions=((1.0, 0.0, 0.0),),
    ray_t_min_m=(0.0,),
    ray_t_max_m=(10.0,),
    wavelengths_m=(1.0e-6, 3.0e-6),
  )
  fine_request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0),),
    ray_directions=((1.0, 0.0, 0.0),),
    ray_t_min_m=(0.0,),
    ray_t_max_m=(10.0,),
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
  )
  coarse = first_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, coarse_request)
  fine = first_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, fine_request)
  spectral_endpoint_error = max(
    abs(coarse.source_spectral_radiance[0][index] - fine.source_spectral_radiance[0][2 * index])
    for index in (0, 1)
  )
  spectral_refinement_passed = spectral_endpoint_error <= 1.0e-12
  sensor_space = _run_sensor_space_operator_probe()
  analytic_passed = (
    all(isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12) for actual, expected in zip(first.source_spectral_radiance[0], expected_source))
    and all(isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12) for actual, expected in zip(first.background_transmittance[0], expected_transmittance))
    and first.optical_depth is not None
    and all(isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12) for actual, expected in zip(first.optical_depth[0], (1.0, 2.0, 4.0)))
    and first.hit_mask == (True, False)
    and piecewise_axial_passed
  )
  return {
    'lane_id': 'optical-transfer-v1',
    'product_id': SPECTRAL_RAY_TRANSFER_V1.capability.wire_id,
    'provider_id': provider.descriptor.provider_id,
    'status': 'passed' if analytic_passed else 'failed',
    'analytic_slab_and_chord_passed': analytic_passed,
    'piecewise_axial_transfer_passed': piecewise_axial_passed,
    'piecewise_axial_section_count': 2,
    'deterministic_serialization': first.model_dump(mode='json') == second.model_dump(mode='json'),
    'spatial_refinement': {
      'straight_section_counts': [2, 3, 5, 9],
      'straight_exact_chord_lengths_m': straight_refinement_lengths,
      'passed': spatial_refinement_passed,
      'curved_section_counts': [3, 5, 9, 17],
      'curved_capsule_path_lengths_m': spatial_refinement_lengths,
      'curved_status': 'nonmonotonic-observed-not-promoted',
      'note': 'the provider gate uses the exact straight cylinder; curved-support refinement is recorded as geometry-only evidence and is not advertised as converged',
    },
    'spectral_refinement': {
      'coarse_wavelength_count': 2,
      'fine_wavelength_count': 3,
      'endpoint_max_abs_delta': spectral_endpoint_error,
      'passed': spectral_refinement_passed,
      'note': 'linear property interpolation consistency, not chemistry or source-model validation',
    },
    'hit_mask': first.hit_mask,
    'intersection_intervals_m': first.plume_intersection_t_m,
    'wavelengths_m': list(definition.wavelengths_m),
    'measurement_probe': {
      'ray_index': 0,
      'wavelengths_m': list(definition.wavelengths_m),
      'source_spectral_radiance_w_m2_sr_m': list(first.source_spectral_radiance[0]),
      'validity_mask': list(first.validity_mask[0]),
    },
    'sensor_space_operators': sensor_space,
    'radiation_claim': first.metadata.claims.radiation.value,
    'external_comparison': {
      'status': 'pending',
      'reason': 'The gray provider is analytically validated and generic downstream sensor operators pass synthetic probes, but the recovered external gates still require provider-bound observer, path, band, and scenario assets.',
    },
    'claim_ceiling': 'Homogeneous or piecewise-axial gray transfer through a straight support only; no chemistry, atmosphere, detector, or FPA claim.',
  }
####


def _curved_optical_support(section_count: int) -> SectionedTubeSupport:
  if section_count < 3:
    raise ValueError('curved optical support requires at least three sections')
  ####
  centers = tuple(
    (
      5.0 * cos(index * pi / (2.0 * (section_count - 1))),
      5.0 * sin(index * pi / (2.0 * (section_count - 1))),
      0.0,
    )
    for index in range(section_count)
  )
  return SectionedTubeSupport(
    frame_id='sensor',
    centers_m=centers,
    radii_m=(0.4,) * section_count,
  )
####


def _run_curved_optical_lane() -> dict[str, Any]:
  """Record the curved transfer boundary without promoting its geometry."""

  provider = CurvedGrayRayTransferProvider()
  support = _curved_optical_support(5)
  definition = GrayRayTransferDefinition(
    frame_id='sensor',
    support=support,
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    source_function_w_sr_m=(2.0, 4.0, 6.0),
    absorption_coefficient_per_m=(0.5, 1.0, 1.5),
    asset_id='product-lane-curved-gray-definition',
    allow_curved_support=True,
  )
  pose = Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-1.0, 2.5, 0.0), (-1.0, 4.5, 0.0)),
    ray_directions=((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    ray_t_min_m=(0.0, 0.0),
    ray_t_max_m=(12.0, 12.0),
    wavelengths_m=definition.wavelengths_m,
  )
  session = provider.create_session(definition=definition)
  try:
    first_snapshot = session.create_snapshot(
      time_s=0.0,
      source_pose=pose,
      dynamic_state={},
      ambient_state={},
    )
    second_snapshot = session.create_snapshot(
      time_s=0.0,
      source_pose=pose,
      dynamic_state={},
      ambient_state={},
    )
    first = first_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
    second = second_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  finally:
    session.close()
  ####
  provider_identity_passed = (
    first.metadata.provenance.provider_id == 'plume.curved-gray-ray-transfer'
    and first.metadata.provenance.metadata['support_geometry'].startswith('curved')
    and support.is_straight is False
  )
  deterministic_passed = first.model_dump(mode='json') == second.model_dump(mode='json')
  transfer_contract_passed = (
    first.hit_mask == (True, True)
    and all(all(isfinite(value) for value in row) for row in first.source_spectral_radiance)
    and all(all(0.0 <= value <= 1.0 for value in row) for row in first.background_transmittance)
    and all(mask == (True, True, True) for mask in first.validity_mask)
  )
  refinement_counts = (3, 5, 9, 17)
  refinement_lengths = []
  for section_count in refinement_counts:
    intervals = intersect_sectioned_tube(
      (-1.0, 2.5, 0.0),
      (1.0, 0.0, 0.0),
      _curved_optical_support(section_count),
      t_max_m=12.0,
    )
    refinement_lengths.append(sum(interval.t_exit_m - interval.t_enter_m for interval in intervals))
  ####
  local_diagnostic_passed = provider_identity_passed and deterministic_passed and transfer_contract_passed
  return {
    'lane_id': 'curved-optical-transfer-v1',
    'product_id': SPECTRAL_RAY_TRANSFER_V1.capability.wire_id,
    'provider_id': provider.descriptor.provider_id,
    'status': 'diagnostic-only' if local_diagnostic_passed else 'failed',
    'provider_identity_passed': provider_identity_passed,
    'transfer_contract_passed': transfer_contract_passed,
    'deterministic_serialization': deterministic_passed,
    'hit_mask': first.hit_mask,
    'intersection_intervals_m': first.plume_intersection_t_m,
    'wavelengths_m': list(definition.wavelengths_m),
    'measurement_probe': {
      'ray_index': 0,
      'wavelengths_m': list(definition.wavelengths_m),
      'source_spectral_radiance_w_m2_sr_m': list(first.source_spectral_radiance[0]),
      'validity_mask': list(first.validity_mask[0]),
    },
    'spatial_refinement': {
      'section_counts': list(refinement_counts),
      'capsule_path_lengths_m': refinement_lengths,
      'status': 'nonmonotonic-observed-not-promoted',
      'passed': False,
      'note': 'piecewise capsule geometry is retained as a diagnostic; nonmonotonic refinement prevents a converged curved-path claim',
    },
    'external_comparison': {
      'status': 'pending',
      'reason': 'No provider-bound curved observer/path/scenario measurement asset is available; this lane remains an experimental gray-transfer diagnostic.',
    },
    'claim_ceiling': 'Gray engineering transfer through conservative piecewise capsule supports only; no resolved curved-flow radiation, chemistry, atmosphere, detector, or FPA claim.',
  }
####


def _run_fpa_boundary() -> dict[str, Any]:
  matrix = json.loads((REPO_ROOT / 'docs' / 'solver_fidelity_matrix_v1.json').read_text(encoding='utf-8'))
  lanes = {lane['lane_id']: lane for lane in matrix['lanes']}
  fpa = lanes['focal-plane-array-v1']
  optical = lanes['optical-transfer-v1']
  passed = (
    fpa['provider_ids'] == []
    and optical['provider_ids'] == ['plume.gray-ray-transfer']
    and fpa['focal_plane_array'] == 'downstream-adapter'
    and 'plume.optical.spectral-ray-transfer@1' in fpa['requires']
    and 'detector-response-contract' in fpa['requires']
    and FPA_PIXEL_DETECTOR_OPERATOR_ID in fpa['implemented_boundary_operator_ids']
    and FPA_DIGITIZATION_OPERATOR_ID in fpa['implemented_boundary_operator_ids']
  )
  pose = Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  provider = GrayRayTransferProvider()
  definition = _gray_definition()
  request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-2.0, 2.0, 0.0)),
    ray_directions=((1.0, 0.0, 0.0),) * 3,
    ray_t_min_m=(0.0, 0.0, 0.0),
    ray_t_max_m=(10.0, 10.0, 10.0),
    wavelengths_m=definition.wavelengths_m,
  )
  snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=pose,
    dynamic_state={},
    ambient_state={},
  )
  ray_result = snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  camera = FpaCameraOptics(
    camera_id='synthetic-camera-optics-v1',
    focal_length_m=0.05,
    pixel_pitch_m=(5.0e-6, 5.0e-6),
    principal_point_px=(0.5, 0.5),
    aperture_area_m2=1.0e-4,
  )
  pixel_geometry = FpaPixelGeometry(
    width_px=2,
    height_px=1,
    ray_pixel_indices_row_col=((0, 0), (0, 0), (0, 1)),
    ray_collection_weights_m2_sr=(0.25, 0.75, 1.0),
    camera_optics=camera,
  )
  detector = DetectorResponse(
    wavelengths_m=definition.wavelengths_m,
    quantum_efficiency=(1.0, 1.0, 1.0),
    optical_throughput=(1.0, 1.0, 1.0),
    dark_current_e_per_s=1.0,
    read_noise_std_e=0.5,
  )
  image = integrate_ray_transfer_to_fpa(
    definition.wavelengths_m,
    ray_result.source_spectral_radiance,
    geometry=pixel_geometry,
    detector=detector,
    exposure_s=1.0,
    validity_mask=ray_result.validity_mask,
  )
  repeat = integrate_ray_transfer_to_fpa(
    definition.wavelengths_m,
    ray_result.source_spectral_radiance,
    geometry=pixel_geometry,
    detector=detector,
    exposure_s=1.0,
    validity_mask=ray_result.validity_mask,
  )
  digitization_policy = FpaDigitizationPolicy(
    electrons_per_count=1.0e12,
    offset_counts=1.0,
    bit_depth=16,
    policy_id='synthetic-adc-v1',
  )
  digitized = digitize_expected_electrons(image, policy=digitization_policy)
  digitized_repeat = digitize_expected_electrons(image, policy=digitization_policy)
  source_reference = FpaSourceReference.from_ray_result(ray_result)
  visualization_input = FpaVisualizationInput(
    image=image,
    source=source_reference,
    detector_response=detector,
    digitized=digitized,
    digitization_policy=digitization_policy,
    camera_optics=camera,
  )
  expected_view = project_fpa_view(
    visualization_input,
    FpaVisualizationSpec.for_source(
      source_reference,
      view_kind='fpa.expected-electrons',
      selection={'row_index': 0, 'column_index': 1},
      display_layer=FpaDisplayLayer.EXPECTED_ELECTRONS,
    ),
  )
  digitized_view = project_fpa_view(
    visualization_input,
    FpaVisualizationSpec.for_source(
      source_reference,
      view_kind='fpa.digitized-counts',
      display_layer=FpaDisplayLayer.DIGITIZED_COUNTS,
    ),
  )
  pixel_detector_passed = (
    image.source_semantics == 'source-only'
    and image.validity_mask == ((True, True),)
    and image.expected_electrons[0][0] > image.expected_electrons[0][1]
    and image == repeat
    and image.operator_id == FPA_PIXEL_DETECTOR_OPERATOR_ID
    and image.camera_optics_id == camera.camera_id
    and image.camera_mapping_model_id == camera.mapping_model_id
  )
  digitization_passed = (
    digitized == digitized_repeat
    and digitized.validity_mask == image.validity_mask
    and digitized.source_operator_id == FPA_PIXEL_DETECTOR_OPERATOR_ID
    and digitized.digitization_policy_id == digitization_policy.policy_id
    and digitized.operator_id == FPA_DIGITIZATION_OPERATOR_ID
    and digitized.camera_optics_id == camera.camera_id
    and digitized.camera_mapping_model_id == camera.mapping_model_id
  )
  visualization_passed = (
    expected_view.schema == 'plume.visualization.fpa-view@1'
    and expected_view.display_layer is FpaDisplayLayer.EXPECTED_ELECTRONS
    and expected_view.layer_values == image.expected_electrons
    and expected_view.selected_pixel.column_index == 1
    and expected_view.selected_pixel.expected_electrons == image.expected_electrons[0][1]
    and digitized_view.display_layer is FpaDisplayLayer.DIGITIZED_COUNTS
    and digitized_view.layer_values == tuple(
      tuple(float(value) for value in row)
      for row in digitized.counts
    )
    and digitized_view.operator_ids == (
      FPA_PIXEL_DETECTOR_OPERATOR_ID,
      FPA_DIGITIZATION_OPERATOR_ID,
    )
  )
  boundary_passed = passed and pixel_detector_passed and digitization_passed and visualization_passed
  return {
    'lane_id': 'focal-plane-array-v1',
    'status': 'boundary-validated-downstream' if boundary_passed else 'failed',
    'provider_advertised': False,
    'ray_provider_prerequisite_present': optical['provider_ids'] != [],
    'ray_signature_adapter_present': True,
    'pixel_detector_operator_id': FPA_PIXEL_DETECTOR_OPERATOR_ID,
    'pixel_detector_contract_passed': pixel_detector_passed,
    'camera_optics_id': camera.camera_id,
    'camera_mapping_model_id': camera.mapping_model_id,
    'camera_optics_contract_passed': image.camera_optics_id == camera.camera_id,
    'digitization_operator_id': FPA_DIGITIZATION_OPERATOR_ID,
    'digitization_policy_id': digitization_policy.policy_id,
    'digitization_contract_passed': digitization_passed,
    'visualization_projection_contract_passed': visualization_passed,
    'visualization_source_content_sha256': source_reference.content_sha256,
    'visualization_operator_ids': digitized_view.operator_ids,
    'visualization_selected_pixel': {
      'row_index': expected_view.selected_pixel.row_index,
      'column_index': expected_view.selected_pixel.column_index,
      'expected_electrons': expected_view.selected_pixel.expected_electrons,
    },
    'digitized_counts': digitized.counts,
    'digitized_validity_mask': digitized.validity_mask,
    'digitized_saturated_mask': digitized.saturated_mask,
    'pixel_grid_shape': [1, 2],
    'pixel_validity_mask': image.validity_mask,
    'source_semantics': image.source_semantics,
    'claim_ceiling': 'Deterministic expected-electron and expected-ADC-count adapters only; no externally validated FPA image, measured detector-count, noise-realization, or detection claim.',
  }
####


def _run_cross_product_consistency() -> dict[str, Any]:
  """Validate the bounded ray-to-signature operator with synthetic rays."""

  provider = GrayRayTransferProvider()
  definition = _gray_definition()
  pose = Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-2.0, 2.0, 0.0)),
    ray_directions=((1.0, 0.0, 0.0),) * 3,
    ray_t_min_m=(0.0, 0.0, 0.0),
    ray_t_max_m=(10.0, 10.0, 10.0),
    wavelengths_m=(1.5e-6, 2.5e-6),
  )
  snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=pose,
    dynamic_state={},
    ambient_state={},
  )
  ray_result = snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  integration = FarFieldRayIntegration(
    direction_frame_id='sensor',
    source_to_observer_directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ray_direction_indices=(0, 0, 1),
    ray_projected_area_weights_m2=(0.25, 0.75, 1.0),
  )
  first = far_field_from_rays(request, ray_result, integration)
  second = far_field_from_rays(request, ray_result, integration)
  expected = ray_result.source_spectral_radiance[0]
  integration_error = max(
    abs(actual - target)
    for actual, target in zip(first.spectral_radiant_intensity[0], expected, strict=True)
  )
  passed = (
    integration_error <= 1.0e-12
    and first.spectral_radiant_intensity[1] == (0.0, 0.0)
    and first.validity_mask == ((True, True), (True, True))
    and first.metadata.provenance.parent_result_ids == (ray_result.metadata.result_id,)
    and first.metadata.provenance.metadata['wavelength_grid_digest_sha256']
    and first.model_dump(mode='json') == second.model_dump(mode='json')
  )
  return {
    'lane_id': 'ray-to-signature-consistency-v1',
    'status': 'passed' if passed else 'failed',
    'adapter_id': 'plume.adapter.far-field-from-rays',
    'registry_operator_id': 'op.ray.projected-area-signature',
    'corpus_cross_product_rule_id': 'MVP-X-001',
    'external_adapter_id': 'adapter.far_field_from_rays@1',
    'operator_mapping_status': 'semantic-match-reviewed-for-synthetic-rule-only',
    'ray_provider_id': provider.descriptor.provider_id,
    'product_id': 'plume.signature.spectral-radiant-intensity@1',
    'orthographic_area_integration_passed': integration_error <= 1.0e-12,
    'miss_group_zero_passed': first.spectral_radiant_intensity[1] == (0.0, 0.0),
    'wavelength_grid_identity_preserved': bool(first.metadata.provenance.metadata['wavelength_grid_digest_sha256']),
    'snapshot_lineage_preserved': first.metadata.provenance.parent_result_ids == (ray_result.metadata.result_id,),
    'deterministic_serialization': first.model_dump(mode='json') == second.model_dump(mode='json'),
    'radiation_claim': first.metadata.claims.radiation.value,
    'claim_derivation': first.metadata.claims.derivation.value,
    'external_comparison': {
      'status': 'synthetic-only',
      'reason': 'The adapter operator and generic sensor-space helpers are verified against homogeneous gray fixtures; recovered comparisons remain blocked by missing provider-bound scenario assets, while the exact external namespace remains distinct despite complete scoped semantic review.',
    },
    'claim_ceiling': 'Synthetic orthographic ray-to-signature consistency only; no experimental signature, atmosphere, detector, image, or FPA claim.',
  }
####


def _external_summary(path: Path | None) -> dict[str, Any]:
  if path is None:
    return {'status': 'not-provided'}
  ####
  report = preflight_corpus(path)
  operator_reconciliation = report.get('operator_reconciliation', {})
  archive = {
    key: value for key, value in report['archive'].items()
    if key != 'path'
  }
  return {
    'status': report['status'],
    'archive': archive,
    'content_counts': report.get('content_counts', {}),
    'gate_statuses': report.get('alignment', {}).get('validation_gate_statuses', {}),
    'operator_crosswalk_status': operator_reconciliation.get('crosswalk_status'),
    'semantic_crosswalk_status': operator_reconciliation.get('semantic_crosswalk_status'),
    'unreviewed_external_operator_count': len(operator_reconciliation.get('unreviewed_external_only', [])),
    'release_blockers': report.get('release_blockers', []),
  }
####


def _run_check(name: str, function: Callable[[], dict[str, Any]]) -> dict[str, Any]:
  try:
    return function()
  except Exception as error:  # pragma: no cover - failure report path
    return {
      'lane_id': name,
      'status': 'failed',
      'error_type': type(error).__name__,
      'error': str(error),
    }
  ####
####


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', type=Path)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  visual = _run_check('shock-cell-basic-v1', _run_visual_lane)
  signature = _run_check('signature-table-mvp-v1', _run_signature_lane)
  optical = _run_check('optical-transfer-v1', _run_optical_lane)
  curved_optical = _run_check('curved-optical-transfer-v1', _run_curved_optical_lane)
  cross_product = _run_check('ray-to-signature-consistency-v1', _run_cross_product_consistency)
  fpa = _run_check('focal-plane-array-v1', _run_fpa_boundary)
  mission_time = _run_check(
    'mission-time-product-composition-v1',
    _run_mission_time_product_lane,
  )
  local_passed = all(
    result['status'] in {'passed', 'boundary-validated-downstream'}
    for result in (visual, signature, optical, cross_product, fpa, mission_time)
  )
  report = {
    'report_id': 'exhaust-plume-product-lane-validation-v1',
    'local_status': 'passed' if local_passed else 'failed',
    'external_status': 'comparison-pending',
    'lanes': {
      'visual': visual,
      'signature': signature,
      'optical': optical,
      'curved_optical': curved_optical,
      'cross_product': cross_product,
      'focal_plane_array': fpa,
      'mission_time': mission_time,
    },
    'external_corpus': _external_summary(args.corpus),
    'release_ready': False,
  }
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if args.output is not None:
    args.output.write_text(serialized, encoding='utf-8')
  ####
  print(serialized, end='')
  return 0 if local_passed else 1
####


if __name__ == '__main__':
  raise SystemExit(main())
####
