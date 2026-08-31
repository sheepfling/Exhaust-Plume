"""Canonical visual-product provider for the bounded straight shock-cell model."""

from __future__ import annotations

from dataclasses import dataclass, replace
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

__all__ = (
  'ShockCellVisualConfiguration',
  'ShockCellVisualDefinition',
  'ShockCellVisualOperatingState',
  'ShockCellVisualProvider',
  'ShockCellVisualSession',
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
    supported_capabilities=(VISUAL_SECTIONED_TUBE_CAPABILITY,),
    provider_definition_schema_id='plume.visual.shock-cell-definition.v1',
    dynamic_state_schema_id='plume.visual.shock-cell-operating-state.v1',
    configuration_schema_id='plume.visual.shock-cell-configuration.v1',
    supported_morphologies=('straight', 'axisymmetric'),
    deterministic=True,
    notes=(
      'bounded straight calorically-perfect shock-cell construction',
      'visual sectioned-tube output only; no signature or ray-transfer capability',
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
    self._validate_operating_state(operating_state)
    solution = solve_shock_cells(self._configuration.solver_config(operating_state))
    if solution.status in {SolverStatus.NUMERICAL_FAILURE, SolverStatus.OUTSIDE_MODEL_VALIDITY}:
      raise OperatingStateDomainError(str(solution.details.get('solver_diagnostics_v1', 'shock-cell solver failed')))
    ####
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
    return ImmutableProductSnapshot(
      metadata=metadata,
      _evaluators={VISUAL_SECTIONED_TUBE_CAPABILITY: _ShockCellVisualEvaluator(
        self._definition,
        self._configuration,
        solution,
      )},
    )
  ####

  def close(self) -> None:
    self._closed = True
  ####
####
