"""Visual-only provider for the fidelity-isolated reduced-order shock train."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import isfinite
from typing import Any, Mapping

from exhaust_plume.api.v1 import (
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ImmutableProductSnapshot,
  InvalidProductRequestError,
  OperatingStateDomainError,
  Pose,
  ProductOutsideApplicabilityError,
  ProviderClosedError,
  ProviderConfigurationError,
  ProviderDescriptor,
  RadiationClaim,
  SessionMetadata,
  SnapshotMetadata,
  TimeModel,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualSection,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  canonical_digest,
)
from exhaust_plume.contracts.termination import TerminationReason
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.models.shock_cells import ShockCellSolveConfig, SolverStatus, solve_shock_cells
from exhaust_plume.models.shock_train import (
  ShockTrainCalibration,
  ShockTrainResult,
  ShockTrainStatus,
  ShockTrainTerminationPolicy,
  solve_shock_train,
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

__all__ = (
  'ShockTrainVisualConfiguration',
  'ShockTrainVisualDefinition',
  'ShockTrainVisualOperatingState',
  'ShockTrainVisualProvider',
  'ShockTrainVisualSession',
)


ShockTrainVisualDefinition = ShockCellAnalyticalDefinition
ShockTrainVisualOperatingState = ShockCellAnalyticalOperatingState


@dataclass(frozen=True, slots=True)
class ShockTrainVisualConfiguration:
  """Configuration for one explicit reduced-order visual lane.

  ``calibration`` intentionally has no built-in engineering default.  A
  caller must identify the closure source and applicability range before the
  provider can continue past the resolved first cell.
  """

  provider_id: str = 'plume.shock-train-reduced-order'
  provider_version: str = '0.1.0'
  num_expansion_lines: int = 2
  num_compression_lines: int = 1
  pressure_match_rtol: float = 1.0e-4
  permit_strong_shock_branch: bool = False
  permit_legacy_parabola_fallback: bool = False
  calibration: ShockTrainCalibration | None = None
  termination_policy: ShockTrainTerminationPolicy = field(default_factory=ShockTrainTerminationPolicy)
  minimum_visual_radius_m: float = 1.0e-6

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('shock-train visual provider identity must not be empty')
    ####
    if isinstance(self.num_expansion_lines, bool) or self.num_expansion_lines < 2:
      raise ProviderConfigurationError('num_expansion_lines must be an integer >= 2')
    ####
    if isinstance(self.num_compression_lines, bool) or self.num_compression_lines < 1:
      raise ProviderConfigurationError('num_compression_lines must be an integer >= 1')
    ####
    if not isfinite(self.pressure_match_rtol) or self.pressure_match_rtol <= 0.0:
      raise ProviderConfigurationError('pressure_match_rtol must be finite and positive')
    ####
    if not isfinite(self.minimum_visual_radius_m) or self.minimum_visual_radius_m <= 0.0:
      raise ProviderConfigurationError('minimum_visual_radius_m must be finite and positive')
    ####
  ####

  def solver_config(self, operating_state: ShockTrainVisualOperatingState) -> ShockCellSolveConfig:
    """Return the one-cell seed configuration; train limits stay separate."""

    return ShockCellSolveConfig(
      exit=operating_state.nozzle_exit,
      ambient=operating_state.ambient,
      expansion_characteristics=self.num_expansion_lines,
      compression_characteristics=self.num_compression_lines,
      pressure_match_rtol=self.pressure_match_rtol,
      max_cells=1,
      permit_strong_shock_branch=self.permit_strong_shock_branch,
      permit_legacy_parabola_fallback=self.permit_legacy_parabola_fallback,
    )
  ####
####


def _descriptor(configuration: ShockTrainVisualConfiguration) -> ProviderDescriptor:
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(VISUAL_SECTIONED_TUBE_CAPABILITY,),
    provider_definition_schema_id='plume.visual.shock-train-definition.v1',
    dynamic_state_schema_id='plume.visual.shock-train-operating-state.v1',
    configuration_schema_id='plume.visual.shock-train-configuration.v1',
    supported_morphologies=('straight', 'axisymmetric'),
    deterministic=True,
    notes=(
      'one resolved first cell followed by explicitly scaled reduced-order train geometry',
      'visual sectioned-tube output only; no signature or ray-transfer capability',
      'fidelity profile: shock-cell-reduced-order-v1',
      'explicit calibration and termination policy required; no universal closure defaults',
    ),
  )
####


def _prescribed_configuration(
    configuration: ShockTrainVisualConfiguration,
    result: ShockTrainResult,
) -> PrescribedVisualConfiguration:
  if not result.cells and result.termination_reason is TerminationReason.NO_PRESSURE_MISMATCH:
    reasons = (
      'matched flow has no finite shock-train construction; requested axial extent defines the display',
      f'calibration identity: {result.calibration_id}',
    )
    warnings = (
      'matched-flow geometry is a constant-radius display tube over the requested axial domain',
      'appearance channels are not spectral radiance or signature predictions',
    )
  else:
    reasons = (
      'geometry contains one resolved first cell and scaled reduced-order downstream cells',
      f'calibration identity: {result.calibration_id}',
    )
    warnings = (
      'reduced-order continuation is an engineering-approximate visual envelope, not resolved MOC geometry',
      'appearance channels are not spectral radiance or signature predictions',
    )
  if result.status is ShockTrainStatus.TRUNCATED:
    warnings += ('the configured safety limit truncated the train; no physical endpoint is inferred',)
  elif result.status is ShockTrainStatus.PHYSICALLY_TERMINATED:
    warnings += (f'physical termination is modeled as {result.termination_reason.value}',)
  return PrescribedVisualConfiguration(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    geometry_claim=GeometryClaim.ENGINEERING_APPROXIMATE,
    radiation_claim=RadiationClaim.APPEARANCE_ONLY,
    time_model=TimeModel.STEADY,
    derivation=Derivation.ADAPTED,
    consistency=ConsistencyLevel.INDEPENDENT,
    applicability_status=ApplicabilityStatus.MARGINAL,
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
      'matched shock-train visual output requires sampling.maximum_axial_extent_m'
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
      'shock_weight': tuple(0.0 for _ in sections),
    },
  )
####


def _interpolate_station(
    left: tuple[float, float, float],
    right: tuple[float, float, float],
    station_x_m: float,
) -> tuple[float, float, float]:
  if right[0] <= left[0]:
    return (station_x_m, left[1], left[2])
  fraction = (station_x_m - left[0]) / (right[0] - left[0])
  return (
    station_x_m,
    left[1] + fraction * (right[1] - left[1]),
    left[2] + fraction * (right[2] - left[2]),
  )
####


def _train_stations(
    result: ShockTrainResult,
    *,
    maximum_axial_extent_m: float | None,
) -> tuple[tuple[float, float, float], ...]:
  """Build ``(x, radius, pressure-amplitude)`` stations and clip them."""

  if not result.cells:
    return ()
  ####
  stations: list[tuple[float, float, float]] = []
  for cell in result.cells:
    metrics = cell.metrics
    radius = max(0.0, metrics.effective_core_diameter_m / 2.0)
    amplitude = max(0.0, metrics.pressure_oscillation_ratio)
    if not stations:
      stations.append((metrics.start_x_m, radius, amplitude))
    stations.append((metrics.end_x_m, radius, amplitude))
  ####
  stations = sorted(stations, key=lambda station: station[0])
  unique: list[tuple[float, float, float]] = []
  for station in stations:
    if unique and abs(station[0] - unique[-1][0]) <= 1.0e-12:
      unique[-1] = station
    else:
      unique.append(station)
    ####
  ####
  if len(unique) < 2:
    return ()
  ####
  final_x_m = unique[-1][0]
  limit_m = final_x_m if maximum_axial_extent_m is None else min(final_x_m, maximum_axial_extent_m)
  if limit_m <= 0.0:
    return ()
  ####
  clipped: list[tuple[float, float, float]] = [station for station in unique if station[0] < limit_m - 1.0e-12]
  if not clipped:
    clipped.append((0.0, unique[0][1], unique[0][2]))
  elif clipped[0][0] > 0.0:
    clipped.insert(0, (0.0, clipped[0][1], clipped[0][2]))
  ####
  if limit_m < final_x_m - 1.0e-12:
    right_index = next(index for index, station in enumerate(unique) if station[0] >= limit_m)
    left = unique[max(0, right_index - 1)]
    right = unique[right_index]
    clipped.append(_interpolate_station(left, right, limit_m))
  elif not clipped or clipped[-1][0] < final_x_m - 1.0e-12:
    clipped.append(unique[-1])
  ####
  return tuple(station for station in clipped if station[0] >= 0.0)
####


def _visual_definition_from_train(
    result: ShockTrainResult,
    *,
    frame_id: str,
    maximum_axial_extent_m: float | None,
    minimum_radius_m: float,
) -> PrescribedVisualDefinition:
  stations = _train_stations(result, maximum_axial_extent_m=maximum_axial_extent_m)
  if len(stations) < 2:
    raise ProductOutsideApplicabilityError('shock-train result did not contain two finite visual stations')
  ####
  maximum_radius = max(station[1] for station in stations)
  if maximum_radius <= 0.0:
    raise ProductOutsideApplicabilityError('shock-train result contained no positive coherent-core radius')
  ####
  maximum_amplitude = max(station[2] for station in stations)
  amplitude_scale = maximum_amplitude if maximum_amplitude > 0.0 else 1.0
  sections = tuple(
    VisualSection(
      arc_length_m=station[0],
      center_m=(station[0], 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=max(minimum_radius_m, station[1]),
      radius_minor_m=max(minimum_radius_m, station[1]),
    )
    for station in stations
  )
  normalized_radius = tuple(min(1.0, max(0.0, station[1] / maximum_radius)) for station in stations)
  normalized_amplitude = tuple(min(1.0, max(0.0, station[2] / amplitude_scale)) for station in stations)
  return PrescribedVisualDefinition(
    frame_id=frame_id,
    sections=sections,
    channels={
      'core_radius_fraction': normalized_radius,
      'opacity_weight': normalized_amplitude,
      'shock_weight': normalized_amplitude,
    },
  )
####


def _result_digest_payload(result: ShockTrainResult) -> dict[str, Any]:
  return {
    'status': result.status.value,
    'termination_reason': result.termination_reason.value,
    'cell_count': result.cell_count,
    'shock_train_end_x_m': result.shock_train_end_x_m,
    'calibration_id': result.calibration_id,
    'diagnostics': repr(dict(result.diagnostics)),
  }
####


class _ShockTrainVisualEvaluator:
  def __init__(
      self,
      definition: ShockTrainVisualDefinition,
      configuration: ShockTrainVisualConfiguration,
      result: ShockTrainResult,
      exit_state: NozzleExitState,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
    self._result = result
    self._exit_state = exit_state
  ####

  def evaluate(
      self,
      request: VisualSectionedTubeRequest,
      snapshot: SnapshotMetadata,
  ) -> VisualSectionedTubeResult:
    if request.output_frame_id != self._definition.plume_frame_id:
      raise ProductOutsideApplicabilityError(
        f'shock-train visual provider supports output frame {self._definition.plume_frame_id!r}, '
        f'not {request.output_frame_id!r}'
      )
    ####
    if self._result.status in {
        ShockTrainStatus.INVALID_INPUT,
        ShockTrainStatus.NUMERICAL_FAILURE,
        ShockTrainStatus.MODEL_VALIDITY_EXCEEDED,
    }:
      raise ProductOutsideApplicabilityError(
        'shock-train result is outside the visual provider applicability domain: '
        f'{self._result.termination.message}'
      )
    ####
    if not self._result.cells and self._result.termination_reason is TerminationReason.NO_PRESSURE_MISMATCH:
      visual_definition = _matched_definition(
        self._exit_state,
        extent_m=request.sampling.maximum_axial_extent_m,
        section_count=request.sampling.maximum_section_count,
        frame_id=self._definition.plume_frame_id,
      )
    else:
      visual_definition = _visual_definition_from_train(
        self._result,
        frame_id=self._definition.plume_frame_id,
        maximum_axial_extent_m=request.sampling.maximum_axial_extent_m,
        minimum_radius_m=self._configuration.minimum_visual_radius_m,
      )
    ####
    return _evaluate_prescribed_definition(
      visual_definition,
      _prescribed_configuration(self._configuration, self._result),
      request,
      snapshot,
    )
  ####
####


class ShockTrainVisualProvider:
  """Canonical visual provider for the calibrated reduced-order train lane."""

  def __init__(self, configuration: ShockTrainVisualConfiguration | None = None) -> None:
    self._configuration = configuration or ShockTrainVisualConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: ShockTrainVisualDefinition,
      configuration: ShockTrainVisualConfiguration | None = None,
  ) -> 'ShockTrainVisualSession':
    if not isinstance(definition, ShockCellAnalyticalDefinition):
      raise ProviderConfigurationError('definition must be ShockTrainVisualDefinition')
    ####
    selected_configuration = configuration or self._configuration
    if selected_configuration != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return ShockTrainVisualSession(self._descriptor, definition, selected_configuration)
  ####
####


class ShockTrainVisualSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: ShockTrainVisualDefinition,
      configuration: ShockTrainVisualConfiguration,
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

  def _validate_operating_state(self, operating_state: ShockTrainVisualOperatingState) -> None:
    if not isinstance(operating_state, ShockCellAnalyticalOperatingState):
      raise OperatingStateDomainError('operating_state must be ShockTrainVisualOperatingState')
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
      raise OperatingStateDomainError('shock-train visual provider requires zero exit flow angle')
    ####
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
      raise ProviderClosedError('shock-train visual session is closed')
    ####
    if not isfinite(time_s):
      raise ProviderConfigurationError('time_s must be finite')
    ####
    if self._configuration.calibration is None:
      raise ProviderConfigurationError(
        'shock-train visual provider requires an explicit ShockTrainCalibration'
      )
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
        "dynamic_state must contain a ShockTrainVisualOperatingState under 'operating_state'"
      )
    ####
    if abs(operating_state.time_s - time_s) > 1.0e-12:
      operating_state = replace(operating_state, time_s=time_s)
    ####
    self._validate_operating_state(operating_state)
    first_cell = solve_shock_cells(self._configuration.solver_config(operating_state))
    if first_cell.status in {SolverStatus.INVALID_INPUT, SolverStatus.NUMERICAL_FAILURE, SolverStatus.OUTSIDE_MODEL_VALIDITY}:
      raise OperatingStateDomainError(str(first_cell.details.get('solver_diagnostics_v1', 'first-cell solver failed')))
    ####
    result = solve_shock_train(
      first_cell,
      self._configuration.calibration,
      self._configuration.termination_policy,
    )
    if result.status in {ShockTrainStatus.NUMERICAL_FAILURE, ShockTrainStatus.MODEL_VALIDITY_EXCEEDED}:
      raise OperatingStateDomainError(result.termination.message)
    ####
    dynamic_digest = canonical_digest({'operating_state': operating_state})
    ambient_digest = canonical_digest({'ambient': operating_state.ambient})
    provider_digest = canonical_digest({
      'definition': self._definition,
      'configuration': self._configuration,
      'first_cell_status': first_cell.status.value,
      'train': _result_digest_payload(result),
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
    return ImmutableProductSnapshot(
      metadata=metadata,
      _evaluators={VISUAL_SECTIONED_TUBE_CAPABILITY: _ShockTrainVisualEvaluator(
        self._definition,
        self._configuration,
        result,
        operating_state.nozzle_exit,
      )},
    )
  ####

  def close(self) -> None:
    self._closed = True
  ####
####
