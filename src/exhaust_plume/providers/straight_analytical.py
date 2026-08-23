"""First MVP straight analytical provider for the sectioned-tube product.

The provider is deliberately narrow: one steady, straight, axisymmetric,
calorically-perfect, inviscid near-field construction backed by the existing
first-cell solver.  It publishes only the renderer-neutral visual capability;
signature and ray-transfer products are separate, unsupported capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from typing import Any, Mapping

from exhaust_plume.contracts import (
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ImmutableProductSnapshot,
  InvalidProductRequestError,
  Pose,
  ProductOutsideApplicabilityError,
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
from exhaust_plume.contracts.errors import (
  OperatingStateDomainError,
  ProviderClosedError,
  ProviderConfigurationError,
)
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.models.shock_cells import (
  AnalyticalFirstCellSolution,
  ShockCellSolveConfig,
  SolverStatus,
  solve_first_cell_from_exit_state,
)
from exhaust_plume.providers.prescribed_visual import (
  PrescribedVisualConfiguration,
  PrescribedVisualDefinition,
  _evaluate_prescribed_definition,
)

__all__ = (
  'StraightAnalyticalConfiguration',
  'StraightAnalyticalDefinition',
  'StraightAnalyticalOperatingState',
  'StraightAnalyticalPlumeProviderV0',
  'StraightAnalyticalProvider',
  'StraightAnalyticalSession',
)
####


@dataclass(frozen=True, slots=True)
class StraightAnalyticalDefinition:
  """Provider definition for one equivalent circular exit plane."""

  nozzle_radius_m: float
  plume_frame_id: str = 'source-local'

  def __post_init__(self) -> None:
    if not isfinite(self.nozzle_radius_m) or self.nozzle_radius_m <= 0.0:
      raise ProviderConfigurationError('nozzle_radius_m must be finite and positive')
    if not self.plume_frame_id:
      raise ProviderConfigurationError('plume_frame_id must not be empty')
  ####


@dataclass(frozen=True, slots=True)
class StraightAnalyticalConfiguration:
  """Numerical ceiling and claim metadata for the first visual slice."""

  provider_id: str = 'plume.straight-analytical'
  provider_version: str = '0.1.0'
  num_expansion_lines: int = 2
  num_compression_lines: int = 1
  maximum_construction_passes: int = 1
  pressure_match_rtol: float = 1.0e-4
  permit_strong_shock_branch: bool = False
  permit_legacy_parabola_fallback: bool = False
  geometry_claim: GeometryClaim = GeometryClaim.ENGINEERING_APPROXIMATE
  radiation_claim: RadiationClaim = RadiationClaim.APPEARANCE_ONLY
  time_model: TimeModel = TimeModel.STEADY
  derivation: Derivation = Derivation.ADAPTED
  consistency: ConsistencyLevel = ConsistencyLevel.INDEPENDENT

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('analytical provider identity must not be empty')
    if isinstance(self.num_expansion_lines, bool) or self.num_expansion_lines < 2:
      raise ProviderConfigurationError('num_expansion_lines must be an integer >= 2')
    if isinstance(self.num_compression_lines, bool) or self.num_compression_lines < 1:
      raise ProviderConfigurationError('num_compression_lines must be an integer >= 1')
    if isinstance(self.maximum_construction_passes, bool) or self.maximum_construction_passes < 0:
      raise ProviderConfigurationError('maximum_construction_passes must be an integer >= 0')
    if not isfinite(self.pressure_match_rtol) or self.pressure_match_rtol <= 0.0:
      raise ProviderConfigurationError('pressure_match_rtol must be finite and positive')
  ####


@dataclass(frozen=True, slots=True)
class StraightAnalyticalOperatingState:
  """Explicit static exit and ambient states for one steady snapshot."""

  nozzle_exit: NozzleExitState
  ambient: AmbientState
  time_s: float = 0.0

  @property
  def exit_state(self) -> NozzleExitState:
    return self.nozzle_exit
  ####

  def __post_init__(self) -> None:
    if not isfinite(self.time_s):
      raise OperatingStateDomainError('time_s must be finite')
  ####


def _descriptor(configuration: StraightAnalyticalConfiguration) -> ProviderDescriptor:
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(VISUAL_SECTIONED_TUBE_CAPABILITY,),
    provider_definition_schema_id='plume.visual.straight-analytical-definition.v0',
    dynamic_state_schema_id='plume.visual.straight-analytical-operating-state.v0',
    configuration_schema_id='plume.visual.straight-analytical-configuration.v0',
    supported_morphologies=('straight', 'axisymmetric'),
    deterministic=True,
    notes=(
      'steady straight axisymmetric calorically-perfect inviscid near-field model',
      'visual sectioned-tube output only; no signature or ray-transfer capability',
    ),
  )
####


def _prescribed_configuration(
    configuration: StraightAnalyticalConfiguration,
    *,
    status: ApplicabilityStatus,
    reasons: tuple[str, ...],
    warnings: tuple[str, ...],
) -> PrescribedVisualConfiguration:
  return PrescribedVisualConfiguration(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    geometry_claim=configuration.geometry_claim,
    radiation_claim=configuration.radiation_claim,
    time_model=configuration.time_model,
    derivation=configuration.derivation,
    consistency=configuration.consistency,
    applicability_status=status,
    applicability_reasons=reasons,
    warnings=warnings,
  )
####


def _matched_definition(
    exit_state: NozzleExitState,
    extent_m: float,
    section_count: int,
    frame_id: str,
) -> PrescribedVisualDefinition:
  if not isfinite(extent_m) or extent_m <= 0.0:
    raise InvalidProductRequestError('matched visual output requires a finite positive maximum_axial_extent_m')
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


def _solution_digest_payload(solution: AnalyticalFirstCellSolution) -> dict[str, Any]:
  """Convert the structured solver result into canonical JSON data."""

  return {
    'regime': solution.regime.value,
    'status': solution.status.value,
    'termination_reason': solution.termination_reason.value,
    'pressure_residual': solution.pressure_residual,
    'details': {
      'solver_diagnostics_v1': solution.details.get('solver_diagnostics_v1', {}),
      'regime': solution.details.get('regime'),
      'termination': solution.details.get('termination'),
    },
    'zones': [
      {
        'zone_id': zone.zone_id,
        'cell_index': zone.cell_index,
        'vertices_xr_m': zone.vertices_xr_m.tolist(),
        'flow': {
          'mach': zone.flow.mach,
          'static_pressure': zone.flow.static_pressure,
          'static_temperature': zone.flow.static_temperature,
          'static_density': zone.flow.static_density,
        },
      }
      for zone in solution.zones
    ],
  }
####


class _StraightAnalyticalEvaluator:
  def __init__(
      self,
      definition: StraightAnalyticalDefinition,
      configuration: StraightAnalyticalConfiguration,
      solution: AnalyticalFirstCellSolution,
    ) -> None:
    self._definition = definition
    self._configuration = configuration
    self._solution = solution
  ####

  def evaluate(self, request: VisualSectionedTubeRequest, snapshot: SnapshotMetadata) -> VisualSectionedTubeResult:
    if request.output_frame_id != self._definition.plume_frame_id:
      raise ProductOutsideApplicabilityError(
        f'analytical visual provider supports output frame {self._definition.plume_frame_id!r}, '
        f'not {request.output_frame_id!r}'
      )
    if self._solution.status in {
        SolverStatus.INVALID_INPUT,
        SolverStatus.NUMERICAL_FAILURE,
        SolverStatus.OUTSIDE_MODEL_VALIDITY,
    }:
      diagnostics = self._solution.details.get('solver_diagnostics_v1', {})
      raise ProductOutsideApplicabilityError(
        'analytical first-cell solution is outside the visual provider applicability domain: '
        f'{diagnostics}'
      )

    if self._solution.regime.value == 'matched':
      extent_m = request.sampling.maximum_axial_extent_m
      if extent_m is None:
        raise InvalidProductRequestError(
          'matched analytical visual output requires sampling.maximum_axial_extent_m'
        )
      visual_definition = _matched_definition(
        self._solution.exit_state,
        extent_m,
        request.sampling.maximum_section_count,
        self._definition.plume_frame_id,
      )
      visual_configuration = _prescribed_configuration(
        self._configuration,
        status=ApplicabilityStatus.MARGINAL,
        reasons=(
          'matched flow has no finite shock-cell endpoint; requested axial domain defines the visual extent',
        ),
        warnings=(
          'matched-flow geometry is a constant-radius display tube over the requested axial domain',
        ),
      )
    else:
      if not self._solution.zones:
        raise ProductOutsideApplicabilityError(
          'analytical first-cell solution did not produce a finite closed zone'
        )
      from exhaust_plume.products.visual import visual_definition_from_zone_results
      visual_definition = visual_definition_from_zone_results(
        self._solution.zones,
        frame_id=self._definition.plume_frame_id,
        section_count=request.sampling.maximum_section_count,
        maximum_axial_extent_m=request.sampling.maximum_axial_extent_m,
      )
      visual_configuration = _prescribed_configuration(
        self._configuration,
        status=ApplicabilityStatus.MARGINAL,
        reasons=(
          'geometry is adapted from one bounded analytical shock-cell construction',
          'construction terminates at the configured first-cell limit; no physical endpoint is inferred',
        ),
        warnings=(
          'geometry is an engineering-approximate display envelope and is not a conservative plume boundary',
        ),
      )
    return _evaluate_prescribed_definition(
      visual_definition,
      visual_configuration,
      request,
      snapshot,
    )
  ####
####


class StraightAnalyticalPlumeProviderV0:
  """Common-lifecycle provider for the first analytical visual MVP."""

  def __init__(self, configuration: StraightAnalyticalConfiguration | None = None) -> None:
    self._configuration = configuration or StraightAnalyticalConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: StraightAnalyticalDefinition,
      configuration: StraightAnalyticalConfiguration | None = None,
  ) -> StraightAnalyticalSession:
    if not isinstance(definition, StraightAnalyticalDefinition):
      raise ProviderConfigurationError('definition must be StraightAnalyticalDefinition')
    selected_configuration = configuration or self._configuration
    if selected_configuration != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    return StraightAnalyticalSession(self._descriptor, definition, selected_configuration)
  ####
####


class StraightAnalyticalSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: StraightAnalyticalDefinition,
      configuration: StraightAnalyticalConfiguration,
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

  def _validate_operating_state(self, operating_state: StraightAnalyticalOperatingState) -> None:
    if not isinstance(operating_state, StraightAnalyticalOperatingState):
      raise OperatingStateDomainError('operating_state must be StraightAnalyticalOperatingState')
    if not isinstance(operating_state.nozzle_exit, NozzleExitState):
      raise OperatingStateDomainError('operating_state.nozzle_exit must be NozzleExitState')
    if not isinstance(operating_state.ambient, AmbientState):
      raise OperatingStateDomainError('operating_state.ambient must be AmbientState')
    radius_tolerance = max(1.0e-12, self._definition.nozzle_radius_m * 1.0e-10)
    if abs(operating_state.nozzle_exit.radius_m - self._definition.nozzle_radius_m) > radius_tolerance:
      raise OperatingStateDomainError('operating-state nozzle radius does not match the provider definition')
    if abs(operating_state.nozzle_exit.flow_angle_rad) > 1.0e-12:
      raise OperatingStateDomainError('straight axisymmetric provider requires zero exit flow angle')
  ####

  def snapshot(
      self,
      operating_state: StraightAnalyticalOperatingState,
      *,
      source_pose: Pose | None = None,
  ) -> ImmutableProductSnapshot:
    if self._closed:
      raise ProviderClosedError('straight analytical session is closed')
    self._validate_operating_state(operating_state)
    settings = ShockCellSolveConfig(
      exit=operating_state.nozzle_exit,
      ambient=operating_state.ambient,
      expansion_characteristics=self._configuration.num_expansion_lines,
      compression_characteristics=self._configuration.num_compression_lines,
      pressure_match_rtol=self._configuration.pressure_match_rtol,
      max_cells=self._configuration.maximum_construction_passes,
      permit_strong_shock_branch=self._configuration.permit_strong_shock_branch,
      permit_legacy_parabola_fallback=self._configuration.permit_legacy_parabola_fallback,
    )
    solution = solve_first_cell_from_exit_state(
      operating_state.nozzle_exit,
      operating_state.ambient,
      settings,
    )
    pose = source_pose or Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    )
    dynamic_digest = canonical_digest({'nozzle_exit': operating_state.nozzle_exit})
    ambient_digest = canonical_digest({'ambient': operating_state.ambient})
    provider_digest = canonical_digest({
      'definition': self._definition,
      'configuration': self._configuration,
      'solution': _solution_digest_payload(solution),
    })
    snapshot_id = canonical_digest({
      'session': self._metadata.session_id,
      'operating_state': operating_state,
      'source_pose': pose,
      'provider': provider_digest,
    })[:24]
    metadata = SnapshotMetadata(
      snapshot_id=snapshot_id,
      session_id=self._metadata.session_id,
      time_s=operating_state.time_s,
      source_pose=pose,
      dynamic_state_digest_sha256=dynamic_digest,
      ambient_state_digest_sha256=ambient_digest,
      provider_state_digest_sha256=provider_digest,
    )
    return ImmutableProductSnapshot(
      metadata=metadata,
      _evaluators={VISUAL_SECTIONED_TUBE_CAPABILITY: _StraightAnalyticalEvaluator(
        self._definition,
        self._configuration,
        solution,
      )},
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
    if not isfinite(time_s):
      raise ProviderConfigurationError('time_s must be finite')
    operating_state = dynamic_state.get('operating_state')
    if operating_state is None:
      nozzle_exit = dynamic_state.get('nozzle_exit')
      ambient = ambient_state.get('ambient')
      if not isinstance(nozzle_exit, NozzleExitState) or not isinstance(ambient, AmbientState):
        raise ProviderConfigurationError(
          "dynamic_state must contain 'nozzle_exit' and ambient_state must contain 'ambient'"
        )
      operating_state = StraightAnalyticalOperatingState(
        nozzle_exit=nozzle_exit,
        ambient=ambient,
        time_s=time_s,
      )
    if not isinstance(operating_state, StraightAnalyticalOperatingState):
      raise ProviderConfigurationError(
        "dynamic_state must contain a StraightAnalyticalOperatingState under 'operating_state'"
      )
    if abs(operating_state.time_s - time_s) > 1.0e-12:
      operating_state = replace(operating_state, time_s=time_s)
    return self.snapshot(operating_state, source_pose=source_pose)
  ####

  def close(self) -> None:
    self._closed = True
  ####


StraightAnalyticalProvider = StraightAnalyticalPlumeProviderV0
####
