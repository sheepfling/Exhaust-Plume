"""Canonical visual-product provider for the bounded straight shock-cell model."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite, pi
from typing import Any, Mapping, Sequence

from exhaust_plume.api.v1 import (
  ApplicabilityReport,
  ApplicabilityStatus,
  AxisymmetricZone,
  AxisymmetricZoneField,
  AxisymmetricZoneFieldRequest,
  AxisymmetricZoneFieldResult,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ImmutableProductSnapshot,
  InvalidProductRequestError,
  MODEL_LANE_VISUALIZATION_CAPABILITY,
  ModelLaneVisualizationRequest,
  ModelLaneVisualizationResult,
  OperatingStateDomainError,
  Pose,
  ProductOutsideApplicabilityError,
  ProviderClosedError,
  ProviderConfigurationError,
  ProviderDescriptor,
  ProjectedAreaCapability,
  ProductClaims,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SessionMetadata,
  SnapshotMetadata,
  SpatialSupport,
  SPATIAL_PROJECTED_AREA_CAPABILITY,
  SPATIAL_PROJECTED_AREA_V1,
  SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
  SPATIAL_AXISYMMETRIC_ZONE_FIELD_V1,
  SPATIAL_LOCAL_FIELD_CAPABILITY,
  SPATIAL_SUPPORT_CAPABILITY,
  SPATIAL_SUPPORT_V1,
  ProjectedAreaRequest,
  ProjectedAreaResult,
  SpatialSupportRequest,
  SpatialSupportResult,
  TimeModel,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualSection,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  bind_axisymmetric_zone_field_result,
  canonical_digest,
  bind_projected_area_result,
  bind_spatial_support_result,
)
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.models.shock_cells import (
  ShockCellSolveConfig,
  ShockCellSolveResult,
  SolverStatus,
  solve_shock_cells,
)
from exhaust_plume.providers.prescribed_visual import (
  PrescribedVisualConfiguration,
  PrescribedVisualDefinition,
  _evaluate_prescribed_definition,
)
from exhaust_plume.providers.shock_diamond import (
  ShockCellAnalyticalDefinition,
  ShockCellAnalyticalOperatingState,
)
from exhaust_plume.products.model_visualization import (
  ModelVisualizationLane,
  evaluate_model_lane_visualization,
)
from exhaust_plume.providers.model_lane_local_field import ModelLaneLocalFieldEvaluator
from exhaust_plume.validation.visual_comparisons import VisualFeatureSeries

__all__ = (
  'SHOCK_CELL_MACH_DISK_FEATURE_OPERATOR_ID',
  'ShockCellVisualConfiguration',
  'ShockCellVisualDefinition',
  'ShockCellVisualOperatingState',
  'ShockCellVisualProvider',
  'ShockCellVisualSession',
)


SHOCK_CELL_MACH_DISK_FEATURE_OPERATOR_ID = (
  'operator.model.shock-cell-basic.mach-disk-endpoint-diagnostic-v1'
)


ShockCellVisualDefinition = ShockCellAnalyticalDefinition
ShockCellVisualOperatingState = ShockCellAnalyticalOperatingState


@dataclass(frozen=True, slots=True)
class ShockCellVisualConfiguration:
  """Canonical provider configuration for one bounded visual construction."""

  provider_id: str = 'plume.shock-cell-analytical'
  provider_version: str = '1.0.0'
  num_expansion_lines: int = 2
  num_compression_lines: int = 1
  maximum_construction_passes: int = 1
  pressure_match_rtol: float = 1.0e-4
  permit_strong_shock_branch: bool = False
  permit_legacy_parabola_fallback: bool = False

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('shock-cell visual provider identity must not be empty')
    ####
    if isinstance(self.num_expansion_lines, bool) or self.num_expansion_lines < 2:
      raise ProviderConfigurationError('num_expansion_lines must be an integer >= 2')
    ####
    if isinstance(self.num_compression_lines, bool) or self.num_compression_lines < 1:
      raise ProviderConfigurationError('num_compression_lines must be an integer >= 1')
    ####
    if isinstance(self.maximum_construction_passes, bool) or self.maximum_construction_passes < 0:
      raise ProviderConfigurationError('maximum_construction_passes must be an integer >= 0')
    ####
    if not isfinite(self.pressure_match_rtol) or self.pressure_match_rtol <= 0.0:
      raise ProviderConfigurationError('pressure_match_rtol must be finite and positive')
    ####
  ####

  def solver_config(self, operating_state: ShockCellVisualOperatingState) -> ShockCellSolveConfig:
    return ShockCellSolveConfig(
      exit=operating_state.nozzle_exit,
      ambient=operating_state.ambient,
      expansion_characteristics=self.num_expansion_lines,
      compression_characteristics=self.num_compression_lines,
      pressure_match_rtol=self.pressure_match_rtol,
      max_cells=self.maximum_construction_passes,
      permit_strong_shock_branch=self.permit_strong_shock_branch,
      permit_legacy_parabola_fallback=self.permit_legacy_parabola_fallback,
    )
  ####
####


def _descriptor(configuration: ShockCellVisualConfiguration) -> ProviderDescriptor:
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(
      VISUAL_SECTIONED_TUBE_CAPABILITY,
      MODEL_LANE_VISUALIZATION_CAPABILITY,
      SPATIAL_LOCAL_FIELD_CAPABILITY,
      SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY,
      SPATIAL_SUPPORT_CAPABILITY,
      SPATIAL_PROJECTED_AREA_CAPABILITY,
    ),
    provider_definition_schema_id='plume.visual.shock-cell-definition.v1',
    dynamic_state_schema_id='plume.visual.shock-cell-operating-state.v1',
    configuration_schema_id='plume.visual.shock-cell-configuration.v1',
    supported_morphologies=('straight', 'axisymmetric'),
    deterministic=True,
    notes=(
      'bounded straight calorically-perfect shock-cell construction',
      'basic shock-cell geometry, declared support, and nozzle-exit reference-area capabilities',
      'no spectral Signature or ray-transfer capability',
      'fidelity profile: shock-cell-basic-v1',
    ),
  )
####


def _prescribed_configuration(
    configuration: ShockCellVisualConfiguration,
    *,
    status: ApplicabilityStatus,
    reasons: tuple[str, ...],
    warnings: tuple[str, ...],
) -> PrescribedVisualConfiguration:
  return PrescribedVisualConfiguration(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    geometry_claim=GeometryClaim.ENGINEERING_APPROXIMATE,
    radiation_claim=RadiationClaim.APPEARANCE_ONLY,
    time_model=TimeModel.STEADY,
    derivation=Derivation.ADAPTED,
    consistency=ConsistencyLevel.INDEPENDENT,
    applicability_status=status,
    applicability_reasons=reasons,
    warnings=warnings,
  )
####


def _matched_definition(
    exit_state: NozzleExitState,
    *,
    extent_m: float | None,
    section_count: int,
    frame_id: str,
) -> PrescribedVisualDefinition:
  if extent_m is None or not isfinite(extent_m) or extent_m <= 0.0:
    raise InvalidProductRequestError(
      'matched shock-cell visual output requires sampling.maximum_axial_extent_m'
    )
  ####
  sections = tuple(
    VisualSection(
      arc_length_m=extent_m * index / (section_count - 1),
      center_m=(extent_m * index / (section_count - 1), 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=exit_state.radius_m,
      radius_minor_m=exit_state.radius_m,
    )
    for index in range(section_count)
  )
  return PrescribedVisualDefinition(
    frame_id=frame_id,
    sections=sections,
    channels={
      'core_radius_fraction': tuple(1.0 for _ in sections),
      'opacity_weight': tuple(1.0 for _ in sections),
    },
  )
####


def _solution_digest_payload(solution: ShockCellSolveResult) -> dict[str, Any]:
  return {
    'regime': solution.regime.value,
    'status': solution.status.value,
    'termination_reason': solution.termination_reason.value,
    'pressure_residual': solution.pressure_residual,
    'zone_count': len(solution.zones),
    'details': repr(dict(solution.details)),
  }
####


def _diagnostic_mach_disk_position_m(solution: ShockCellSolveResult) -> float:
  """Return the endpoint of the modeled centerline-compression region.

  The basic solver does not resolve a physical Mach disk.  The selected
  endpoint is therefore an explicitly named diagnostic proxy: the maximum
  axial coordinate of the first modeled region labelled ``Centerline
  Compression``.  Callers must retain the diagnostic claim ceiling.
  """

  candidates = tuple(
    zone
    for zone in solution.zones
    if 'centerline compression' in (zone.region_label or '').lower()
  )
  if not candidates:
    raise ValueError(
      'basic shock-cell solution retained no centerline-compression region '
      'from which to derive a diagnostic feature'
    )
  ####
  endpoint = max(
    float(max(float(point[0]) for point in zone.vertices_xr_m))
    for zone in candidates
  )
  if not isfinite(endpoint) or endpoint < 0.0:
    raise ValueError('diagnostic Mach-disk endpoint must be finite and nonnegative')
  ####
  return endpoint
####


class _ShockCellVisualEvaluator:
  def __init__(
      self,
      definition: ShockCellVisualDefinition,
      configuration: ShockCellVisualConfiguration,
      solution: ShockCellSolveResult,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
    self._solution = solution
  ####

  def evaluate(
      self,
      request: VisualSectionedTubeRequest,
      snapshot: SnapshotMetadata,
  ) -> VisualSectionedTubeResult:
    if request.output_frame_id != self._definition.plume_frame_id:
      raise ProductOutsideApplicabilityError(
        f'shock-cell visual provider supports output frame {self._definition.plume_frame_id!r}, '
        f'not {request.output_frame_id!r}'
      )
    ####
    if self._solution.status in {
        SolverStatus.INVALID_INPUT,
        SolverStatus.NUMERICAL_FAILURE,
        SolverStatus.OUTSIDE_MODEL_VALIDITY,
    }:
      raise ProductOutsideApplicabilityError(
        'shock-cell solution is outside the visual provider applicability domain: '
        f'{self._solution.details}'
      )
    ####
    if self._solution.regime.value == 'matched':
      visual_definition = _matched_definition(
        self._solution.exit_state,
        extent_m=request.sampling.maximum_axial_extent_m,
        section_count=request.sampling.maximum_section_count,
        frame_id=self._definition.plume_frame_id,
      )
      visual_configuration = _prescribed_configuration(
        self._configuration,
        status=ApplicabilityStatus.MARGINAL,
        reasons=('matched flow has no finite shock-cell endpoint; requested axial domain defines the visual extent',),
        warnings=('matched-flow geometry is a constant-radius display tube over the requested axial domain',),
      )
    else:
      if not self._solution.zones:
        raise ProductOutsideApplicabilityError(
          'shock-cell solution did not produce a finite closed zone'
        )
      ####
      from exhaust_plume.products.workflow_visual import visual_definition_from_shock_cells
      visual_definition = visual_definition_from_shock_cells(
        self._solution,
        frame_id=self._definition.plume_frame_id,
        section_count=request.sampling.maximum_section_count,
        maximum_axial_extent_m=request.sampling.maximum_axial_extent_m,
      )
      visual_configuration = _prescribed_configuration(
        self._configuration,
        status=ApplicabilityStatus.MARGINAL,
        reasons=(
          'geometry is adapted from a bounded analytical shock-cell construction',
          'construction terminates at the configured cell limit; no physical endpoint is inferred',
        ),
        warnings=(
          'geometry is an engineering-approximate display envelope and is not a conservative plume boundary',
        ),
      )
    ####
    return _evaluate_prescribed_definition(
      visual_definition,
      visual_configuration,
      request,
      snapshot,
    )
  ####
####


class _ShockCellModelLaneEvaluator:
  def __init__(
      self,
      definition: ShockCellVisualDefinition,
      configuration: ShockCellVisualConfiguration,
      solution: ShockCellSolveResult,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
    self._solution = solution
  ####

  def evaluate(
      self,
      request: ModelLaneVisualizationRequest,
      snapshot: SnapshotMetadata,
  ) -> ModelLaneVisualizationResult:
    return evaluate_model_lane_visualization(
      self._solution,
      ModelVisualizationLane.BASIC_SHOCK_CELL,
      request,
      snapshot,
      frame_id=self._definition.plume_frame_id,
      provider_id=self._configuration.provider_id,
      provider_version=self._configuration.provider_version,
    )
  ####
####


class _ShockCellSpatialSupportEvaluator:
  def __init__(
      self,
      definition: ShockCellVisualDefinition,
      configuration: ShockCellVisualConfiguration,
      session: SessionMetadata,
      solution: ShockCellSolveResult,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
    self._session = session
    self._solution = solution
  ####

  def evaluate(
      self,
      request: SpatialSupportRequest,
      snapshot: SnapshotMetadata,
  ) -> SpatialSupportResult:
    if not isinstance(request, SpatialSupportRequest):
      raise InvalidProductRequestError('spatial-support capability requires SpatialSupportRequest')
    ####
    points = tuple(
      (float(point[0]), float(point[1]))
      for zone in self._solution.zones
      for point in zone.vertices_xr_m
    )
    if points:
      x_min = min(point[0] for point in points)
      x_max = max(point[0] for point in points)
      radial_max = max(abs(point[1]) for point in points)
      definition = (
        'AABB of the solver-produced x-r polygons embedded in plume-frame z=0; '
        'bounds describe this modeled 2D section and do not claim a 3D plume envelope'
      )
    else:
      x_min = x_max = 0.0
      radial_max = self._solution.exit_state.radius_m
      definition = (
        'no finite solver zones; nozzle-exit section only, embedded in plume-frame z=0; '
        'no downstream plume extent is inferred'
      )
    ####
    support = SpatialSupport(
      plume_frame_aabb_min_m=(x_min, -radial_max, 0.0),
      plume_frame_aabb_max_m=(x_max, radial_max, 0.0),
      characteristic_extent_m=max(1.0e-12, x_max - x_min, 2.0 * radial_max),
      support_definition=definition,
      is_conservative=True,
    )
    metadata = _spatial_result_metadata(
      SPATIAL_SUPPORT_V1.capability,
      request,
      snapshot,
      self._definition,
      self._configuration,
      self._session,
      warnings=(
        'basic shock-cell output is engineering approximate and exploratory',
        'support bounds apply to the retained x-r section and are not a physical 3D boundary',
      ),
    )
    return bind_spatial_support_result(support, metadata)
  ####
####


class _ShockCellZoneFieldEvaluator:
  def __init__(
      self,
      definition: ShockCellVisualDefinition,
      configuration: ShockCellVisualConfiguration,
      session: SessionMetadata,
      solution: ShockCellSolveResult,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
    self._session = session
    self._solution = solution
  ####

  def evaluate(
      self,
      request: AxisymmetricZoneFieldRequest,
      snapshot: SnapshotMetadata,
  ) -> AxisymmetricZoneFieldResult:
    if not isinstance(request, AxisymmetricZoneFieldRequest):
      raise InvalidProductRequestError(
        'axisymmetric-zone-field capability requires AxisymmetricZoneFieldRequest'
      )
    ####
    if not self._solution.zones:
      raise ProductOutsideApplicabilityError(
        'matched-flow shock-cell solution has no retained finite zones'
      )
    ####
    zones = tuple(
      AxisymmetricZone(
        zone_id=zone.zone_id,
        polygon_xr_m=zone.vertices_xr_m,
        static_pressure_Pa=zone.flow.static_pressure,
        static_temperature_K=zone.flow.static_temperature,
        density_kgpm3=zone.flow.static_density,
        mach=zone.flow.mach,
        phase=zone.region_type or 'closed-zone',
        cell_index=zone.cell_index,
        geometry_status=zone.geometry_status,
        region_type=zone.region_type,
        region_label=zone.region_label,
        shock_angle_rad=zone.shock_angle_rad,
        turn_angle_rad=zone.turn_angle_rad,
      )
      for zone in self._solution.zones
    )
    field = AxisymmetricZoneField(zones=zones)
    metadata = _spatial_result_metadata(
      SPATIAL_AXISYMMETRIC_ZONE_FIELD_V1.capability,
      request,
      snapshot,
      self._definition,
      self._configuration,
      self._session,
      warnings=(
        'basic shock-cell zones are engineering approximate and exploratory',
        'zones are finite modeled regions in the x-r plane and are not a continuous or 3D plume field',
        'shock and turn angles are included only where the retained solver zone declares them',
      ),
    )
    return bind_axisymmetric_zone_field_result(field, metadata)
  ####
####


class _ShockCellProjectedAreaEvaluator:
  def __init__(
      self,
      definition: ShockCellVisualDefinition,
      configuration: ShockCellVisualConfiguration,
      session: SessionMetadata,
      solution: ShockCellSolveResult,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
    self._session = session
    self._solution = solution
  ####

  def evaluate(
      self,
      request: ProjectedAreaRequest,
      snapshot: SnapshotMetadata,
  ) -> ProjectedAreaResult:
    if not isinstance(request, ProjectedAreaRequest):
      raise InvalidProductRequestError('projected-area capability requires ProjectedAreaRequest')
    ####
    reference_area = pi * self._solution.exit_state.radius_m**2
    projected_area = ProjectedAreaCapability(
      reference_area_m2=reference_area,
      closed_zone_count=len(self._solution.zones),
    )
    metadata = _spatial_result_metadata(
      SPATIAL_PROJECTED_AREA_V1.capability,
      request,
      snapshot,
      self._definition,
      self._configuration,
      self._session,
      warnings=(
        'reference area is the nozzle-exit disk area and is not view-direction dependent',
        'basic shock-cell output is engineering approximate and exploratory',
      ),
    )
    return bind_projected_area_result(projected_area, metadata)
  ####
####


def _spatial_result_metadata(
    capability: Any,
  request: SpatialSupportRequest | ProjectedAreaRequest | AxisymmetricZoneFieldRequest,
    snapshot: SnapshotMetadata,
    definition: ShockCellVisualDefinition,
    configuration: ShockCellVisualConfiguration,
    session: SessionMetadata,
    *,
    warnings: tuple[str, ...],
) -> ResultMetadata:
  request_digest = canonical_digest(request)
  return ResultMetadata(
    capability=capability,
    result_id=canonical_digest({
      'snapshot_id': snapshot.snapshot_id,
      'request_digest_sha256': request_digest,
      'capability': capability.wire_id,
    })[:24],
    request_digest_sha256=request_digest,
    snapshot=snapshot,
    output_frame_id=definition.plume_frame_id,
    claims=ProductClaims(
      geometry=GeometryClaim.ENGINEERING_APPROXIMATE,
      radiation=RadiationClaim.NOT_APPLICABLE,
      time_model=TimeModel.STEADY,
      derivation=Derivation.NATIVE,
      consistency=ConsistencyLevel.INDEPENDENT,
    ),
    applicability=ApplicabilityReport(
      status=ApplicabilityStatus.MARGINAL,
      reasons=(
        'bounded basic shock-cell lane; supporting spatial outputs inherit its exploratory claim ceiling',
      ),
    ),
    provenance=ResultProvenance(
      model_lineage_id='shock-cell-basic-v1',
      provider_id=session.provider_id,
      provider_version=session.provider_version,
      configuration_digest_sha256=session.configuration_digest_sha256,
      metadata={
        'definition_digest_sha256': canonical_digest(definition),
        'provider_configuration_digest_sha256': canonical_digest(configuration),
      },
    ),
    warnings=warnings,
  )
####


class ShockCellVisualProvider:
  """Canonical provider for the straight shock-cell visual product."""

  def __init__(self, configuration: ShockCellVisualConfiguration | None = None) -> None:
    self._configuration = configuration or ShockCellVisualConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: ShockCellVisualDefinition,
      configuration: ShockCellVisualConfiguration | None = None,
  ) -> ShockCellVisualSession:
    if not isinstance(definition, ShockCellAnalyticalDefinition):
      raise ProviderConfigurationError('definition must be ShockCellVisualDefinition')
    ####
    selected_configuration = configuration or self._configuration
    if selected_configuration != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return ShockCellVisualSession(self._descriptor, definition, selected_configuration)
  ####
####


class ShockCellVisualSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: ShockCellVisualDefinition,
      configuration: ShockCellVisualConfiguration,
  ) -> None:
    self._descriptor = descriptor
    self._definition = definition
    self._configuration = configuration
    self._closed = False
    configuration_digest = canonical_digest(configuration)
    self._metadata = SessionMetadata(
      session_id=canonical_digest({
        'provider': descriptor.provider_id,
        'version': descriptor.provider_version,
        'definition': definition,
        'configuration': configuration_digest,
      })[:24],
      provider_id=descriptor.provider_id,
      provider_version=descriptor.provider_version,
      configuration_digest_sha256=configuration_digest,
    )
  ####

  @property
  def metadata(self) -> SessionMetadata:
    return self._metadata
  ####

  def _validate_operating_state(self, operating_state: ShockCellVisualOperatingState) -> None:
    if not isinstance(operating_state, ShockCellAnalyticalOperatingState):
      raise OperatingStateDomainError('operating_state must be ShockCellVisualOperatingState')
    ####
    if not isinstance(operating_state.nozzle_exit, NozzleExitState):
      raise OperatingStateDomainError('operating_state.nozzle_exit must be NozzleExitState')
    ####
    if not isinstance(operating_state.ambient, AmbientState):
      raise OperatingStateDomainError('operating_state.ambient must be AmbientState')
    ####
    tolerance = max(1.0e-12, self._definition.nozzle_radius_m * 1.0e-10)
    if abs(operating_state.nozzle_exit.radius_m - self._definition.nozzle_radius_m) > tolerance:
      raise OperatingStateDomainError('operating-state nozzle radius does not match the provider definition')
    ####
    if abs(operating_state.nozzle_exit.flow_angle_rad) > 1.0e-12:
      raise OperatingStateDomainError('shock-cell visual provider requires zero exit flow angle')
    ####
  ####

  def _solve_operating_state(
      self,
      operating_state: ShockCellVisualOperatingState,
  ) -> ShockCellSolveResult:
    self._validate_operating_state(operating_state)
    solution = solve_shock_cells(self._configuration.solver_config(operating_state))
    if solution.status in {
        SolverStatus.INVALID_INPUT,
        SolverStatus.NUMERICAL_FAILURE,
        SolverStatus.OUTSIDE_MODEL_VALIDITY,
    }:
      raise OperatingStateDomainError(
        str(solution.details.get('solver_diagnostics_v1', 'shock-cell solver failed'))
      )
    ####
    return solution
  ####

  def build_mach_disk_feature_series(
      self,
      operating_states: Sequence[ShockCellVisualOperatingState],
      *,
      scenario_id: str,
      branch_ids: Sequence[str],
  ) -> VisualFeatureSeries:
    """Build a diagnostic feature series from explicit model operating states.

    The caller supplies every branch identifier.  This method never infers a
    hysteresis branch from row order, pressure ordering, or the solver regime.
    The returned ``mach_disk_position_m`` is the basic solver's centerline-
    compression endpoint proxy, not a resolved physical Mach-disk observable.
    """

    states = tuple(operating_states)
    branches = tuple(str(branch) for branch in branch_ids)
    if not states:
      raise ValueError('operating_states must contain at least one state')
    ####
    if len(states) != len(branches) or any(not branch.strip() for branch in branches):
      raise ValueError(
        'branch_ids must contain one non-empty explicit branch ID per operating state'
      )
    ####
    coordinates: list[float] = []
    values: list[float] = []
    for state in states:
      solution = self._solve_operating_state(state)
      if solution.regime.value != 'underexpanded':
        raise OperatingStateDomainError(
          'diagnostic Mach-disk feature extraction currently requires an '
          'underexpanded basic-solver state'
        )
      ####
      coordinates.append(float(state.nozzle_exit.total_pressure_Pa))
      values.append(_diagnostic_mach_disk_position_m(solution))
    ####
    for branch in set(branches):
      branch_coordinates = tuple(
        coordinate
        for coordinate, candidate_branch in zip(coordinates, branches, strict=True)
        if candidate_branch == branch
      )
      if len(branch_coordinates) != len(set(branch_coordinates)):
        raise ValueError(
          f'branch {branch!r} contains duplicate operating-pressure coordinates'
        )
      ####
    ####
    source_id = (
      f'{self._descriptor.provider_id}:{self._metadata.session_id}:'
      'mach-disk-diagnostic-proxy'
    )
    return VisualFeatureSeries(
      feature_id='mach_disk_position_m',
      coordinate_id='nozzle_exit_total_pressure_Pa',
      coordinate_unit='Pa',
      feature_unit='m',
      coordinates=tuple(coordinates),
      values=tuple(values),
      source_id=source_id,
      scenario_id=scenario_id,
      coordinate_frame_id=self._definition.plume_frame_id,
      measurement_space='physical-geometry-diagnostic',
      operator_id=SHOCK_CELL_MACH_DISK_FEATURE_OPERATOR_ID,
      branch_ids=branches,
      model_lane_id='shock-cell-basic-v1',
    )
  ####

  def create_snapshot(
      self,
      *,
      time_s: float,
      source_pose: Pose,
      dynamic_state: Mapping[str, Any],
      ambient_state: Mapping[str, Any],
  ) -> ImmutableProductSnapshot:
    if self._closed:
      raise ProviderClosedError('shock-cell visual session is closed')
    ####
    if not isfinite(time_s):
      raise ProviderConfigurationError('time_s must be finite')
    ####
    operating_state = dynamic_state.get('operating_state')
    if operating_state is None:
      nozzle_exit = dynamic_state.get('nozzle_exit')
      ambient = ambient_state.get('ambient')
      if not isinstance(nozzle_exit, NozzleExitState) or not isinstance(ambient, AmbientState):
        raise ProviderConfigurationError(
          "dynamic_state must contain 'nozzle_exit' and ambient_state must contain 'ambient'"
        )
      ####
      operating_state = ShockCellAnalyticalOperatingState(
        nozzle_exit=nozzle_exit,
        ambient=ambient,
        time_s=time_s,
      )
    ####
    if not isinstance(operating_state, ShockCellAnalyticalOperatingState):
      raise ProviderConfigurationError(
        "dynamic_state must contain a ShockCellVisualOperatingState under 'operating_state'"
      )
    ####
    if abs(operating_state.time_s - time_s) > 1.0e-12:
      operating_state = replace(operating_state, time_s=time_s)
    ####
    solution = self._solve_operating_state(operating_state)
    dynamic_digest = canonical_digest({'operating_state': operating_state})
    ambient_digest = canonical_digest({'ambient': operating_state.ambient})
    provider_digest = canonical_digest({
      'definition': self._definition,
      'configuration': self._configuration,
      'solution': _solution_digest_payload(solution),
    })
    snapshot_id = canonical_digest({
      'session': self._metadata.session_id,
      'time_s': time_s,
      'source_pose': source_pose,
      'dynamic': dynamic_digest,
      'ambient': ambient_digest,
      'provider': provider_digest,
    })[:24]
    metadata = SnapshotMetadata(
      snapshot_id=snapshot_id,
      session_id=self._metadata.session_id,
      time_s=time_s,
      source_pose=source_pose,
      dynamic_state_digest_sha256=dynamic_digest,
      ambient_state_digest_sha256=ambient_digest,
      provider_state_digest_sha256=provider_digest,
    )
    evaluators = {
      VISUAL_SECTIONED_TUBE_CAPABILITY: _ShockCellVisualEvaluator(
        self._definition,
        self._configuration,
        solution,
      ),
      SPATIAL_SUPPORT_CAPABILITY: _ShockCellSpatialSupportEvaluator(
        self._definition,
        self._configuration,
        self._metadata,
        solution,
      ),
      SPATIAL_PROJECTED_AREA_CAPABILITY: _ShockCellProjectedAreaEvaluator(
        self._definition,
        self._configuration,
        self._metadata,
        solution,
      ),
    }
    if solution.zones:
      evaluators[SPATIAL_AXISYMMETRIC_ZONE_FIELD_CAPABILITY] = _ShockCellZoneFieldEvaluator(
        self._definition,
        self._configuration,
        self._metadata,
        solution,
      )
      model_lane_evaluator = _ShockCellModelLaneEvaluator(
        self._definition,
        self._configuration,
        solution,
      )
      evaluators[MODEL_LANE_VISUALIZATION_CAPABILITY] = model_lane_evaluator
      evaluators[SPATIAL_LOCAL_FIELD_CAPABILITY] = ModelLaneLocalFieldEvaluator(
        model_lane_evaluator,
      )
    ####
    return ImmutableProductSnapshot(metadata=metadata, _evaluators=evaluators)
  ####

  def close(self) -> None:
    self._closed = True
  ####
####
