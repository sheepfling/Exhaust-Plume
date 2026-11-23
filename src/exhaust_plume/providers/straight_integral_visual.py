"""Canonical visual provider for retained straight-integral plume results."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from exhaust_plume.api.v1 import (
  ENGINEERING_FLUX_SECTION_CAPABILITY,
  ImmutableProductSnapshot,
  MODEL_LANE_VISUALIZATION_CAPABILITY,
  ModelLaneVisualizationRequest,
  ModelLaneVisualizationResult,
  Pose,
  ProviderClosedError,
  ProviderConfigurationError,
  ProviderDescriptor,
  SessionMetadata,
  SnapshotMetadata,
  SPATIAL_LOCAL_FIELD_CAPABILITY,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  canonical_digest,
)
from exhaust_plume.models.integral.straight import IntegralStraightResult
from exhaust_plume.products.model_visualization import (
  ModelVisualizationLane,
  evaluate_model_lane_visualization,
  evaluate_standardized_model_visualization,
  standardize_model_visualization,
)
from exhaust_plume.providers.model_lane_local_field import ModelLaneLocalFieldEvaluator
from exhaust_plume.providers.straight_integral_engineering_flux import (
  StraightIntegralEngineeringFluxEvaluator,
)

STRAIGHT_INTEGRAL_CENTERLINE_REFERENCE_ID = 'straight-integral-native-centerline'

__all__ = (
  'StraightIntegralVisualConfiguration',
  'StraightIntegralVisualDefinition',
  'StraightIntegralVisualProvider',
  'StraightIntegralVisualSession',
  'STRAIGHT_INTEGRAL_CENTERLINE_REFERENCE_ID',
)


@dataclass(frozen=True, slots=True)
class StraightIntegralVisualDefinition:
  """An already-solved straight-integral result and its local frame."""

  frame_id: str
  result: IntegralStraightResult
  centerline_reference_id: str = STRAIGHT_INTEGRAL_CENTERLINE_REFERENCE_ID

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ProviderConfigurationError('straight-integral visual frame_id must not be empty')
    if not isinstance(self.centerline_reference_id, str) or not self.centerline_reference_id.strip():
      raise ProviderConfigurationError('straight-integral centerline_reference_id must not be empty')
    ####
    if not isinstance(self.result, IntegralStraightResult):
      raise ProviderConfigurationError('straight-integral visual result must be IntegralStraightResult')
    ####
    if len(self.result.states) < 2:
      raise ProviderConfigurationError('straight-integral visual result requires at least two states')
    ####
    x_values = tuple(state.x_m for state in self.result.states)
    if any(next_x <= x for x, next_x in zip(x_values, x_values[1:])):
      raise ProviderConfigurationError('straight-integral state x coordinates must strictly increase')
    ####
  ####

  @property
  def digest(self) -> str:
    return canonical_digest({
      'frame_id': self.frame_id,
      'centerline_reference_id': self.centerline_reference_id,
      'states': tuple({
        'x_m': state.x_m,
        'mass_flow_rate_kg_s': state.mass_flow_rate_kg_s,
        'momentum_flux_N': state.momentum_flux_N,
        'total_enthalpy_flux_W': state.total_enthalpy_flux_W,
        'velocity_mps': state.velocity_mps,
        'temperature_K': state.temperature_K,
        'pressure_Pa': state.pressure_Pa,
        'density_kgpm3': state.density_kgpm3,
        'radius_m': state.radius_m,
        'species_mass_fractions': state.species_mass_fractions,
      } for state in self.result.states),
      'termination_reason': self.result.termination_reason.value,
      'termination_x_m': self.result.termination_x_m,
      'termination_is_physical': self.result.termination_is_physical,
      'conservation_residuals': dict(self.result.conservation_residuals),
    })
  ####
####


@dataclass(frozen=True, slots=True)
class StraightIntegralVisualConfiguration:
  """Provider identity for this steady, source-bound integral adapter."""

  provider_id: str = 'plume.visual.straight-integral'
  provider_version: str = '1.0.0'
  code_revision: str | None = None

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('straight-integral visual provider identity must not be empty')
    if self.code_revision is not None and (
        not isinstance(self.code_revision, str) or not self.code_revision.strip()
    ):
      raise ProviderConfigurationError('code_revision must be non-empty when configured')
    ####
  ####
####


def _descriptor(configuration: StraightIntegralVisualConfiguration) -> ProviderDescriptor:
  supported_capabilities = (
    VISUAL_SECTIONED_TUBE_CAPABILITY,
    MODEL_LANE_VISUALIZATION_CAPABILITY,
    SPATIAL_LOCAL_FIELD_CAPABILITY,
  )
  notes = [
    'adapts the retained IntegralStraightResult without substituting parametric geometry',
    'steady visualization only; no Signature, ray-transfer, or detector capability',
    'spatial-domain endpoints remain requested-domain limits unless solver termination is physical',
  ]
  if configuration.code_revision is not None:
    supported_capabilities += (ENGINEERING_FLUX_SECTION_CAPABILITY,)
    notes.append(
      'engineering-flux sections are engineering-approximate, steady, pressure-matched, and not measurement-validated'
    )
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=supported_capabilities,
    provider_definition_schema_id='plume.visual.straight-integral-definition.v1',
    dynamic_state_schema_id='plume.visual.straight-integral-dynamic-state.v1',
    configuration_schema_id='plume.visual.straight-integral-configuration.v1',
    supported_morphologies=('straight-integral-top-hat',),
    deterministic=True,
    notes=tuple(notes),
  )
####


class _StraightIntegralVisualEvaluator:
  def __init__(
      self,
      definition: StraightIntegralVisualDefinition,
      configuration: StraightIntegralVisualConfiguration,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
  ####

  def evaluate(
      self,
      request: VisualSectionedTubeRequest,
      snapshot: SnapshotMetadata,
  ) -> VisualSectionedTubeResult:
    if request.output_frame_id != self._definition.frame_id:
      raise ProviderConfigurationError(
        f'straight-integral visual provider supports output frame {self._definition.frame_id!r}, '
        f'not {request.output_frame_id!r}'
      )
    ####
    visualization = standardize_model_visualization(
      self._definition.result,
      lane=ModelVisualizationLane.STRAIGHT_INTEGRAL,
      frame_id=self._definition.frame_id,
      section_count=request.sampling.maximum_section_count,
      maximum_axial_extent_m=request.sampling.maximum_axial_extent_m,
    )
    return evaluate_standardized_model_visualization(
      visualization,
      request,
      snapshot,
      provider_id=self._configuration.provider_id,
      provider_version=self._configuration.provider_version,
    )
  ####
####


class _StraightIntegralModelLaneEvaluator:
  def __init__(
      self,
      definition: StraightIntegralVisualDefinition,
      configuration: StraightIntegralVisualConfiguration,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
  ####

  def evaluate(
      self,
      request: ModelLaneVisualizationRequest,
      snapshot: SnapshotMetadata,
  ) -> ModelLaneVisualizationResult:
    return evaluate_model_lane_visualization(
      self._definition.result,
      ModelVisualizationLane.STRAIGHT_INTEGRAL,
      request,
      snapshot,
      frame_id=self._definition.frame_id,
      provider_id=self._configuration.provider_id,
      provider_version=self._configuration.provider_version,
    )
  ####
####


class StraightIntegralVisualProvider:
  """Expose solved straight-integral states through canonical visual APIs."""

  def __init__(self, configuration: StraightIntegralVisualConfiguration | None = None) -> None:
    self._configuration = configuration or StraightIntegralVisualConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: StraightIntegralVisualDefinition,
      configuration: StraightIntegralVisualConfiguration | None = None,
  ) -> 'StraightIntegralVisualSession':
    if not isinstance(definition, StraightIntegralVisualDefinition):
      raise ProviderConfigurationError('definition must be StraightIntegralVisualDefinition')
    ####
    selected = configuration or self._configuration
    if selected != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return StraightIntegralVisualSession(self._descriptor, definition, selected)
  ####
####


class StraightIntegralVisualSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: StraightIntegralVisualDefinition,
      configuration: StraightIntegralVisualConfiguration,
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
        'definition': definition.digest,
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

  def create_snapshot(
      self,
      *,
      time_s: float,
      source_pose: Pose,
      dynamic_state: Mapping[str, Any],
      ambient_state: Mapping[str, Any],
  ) -> ImmutableProductSnapshot:
    if self._closed:
      raise ProviderClosedError('straight-integral visual session is closed')
    ####
    if not isfinite(time_s):
      raise ProviderConfigurationError('time_s must be finite')
    ####
    if not isinstance(source_pose, Pose):
      raise ProviderConfigurationError('source_pose must be Pose')
    ####
    if not isinstance(dynamic_state, Mapping) or not isinstance(ambient_state, Mapping):
      raise ProviderConfigurationError('dynamic_state and ambient_state must be mappings')
    ####
    dynamic_digest = canonical_digest(dynamic_state)
    ambient_digest = canonical_digest(ambient_state)
    provider_digest = canonical_digest({
      'definition': self._definition.digest,
      'configuration': self._configuration,
    })
    metadata = SnapshotMetadata(
      snapshot_id=canonical_digest({
        'session': self._metadata.session_id,
        'time_s': time_s,
        'source_pose': source_pose,
        'dynamic': dynamic_digest,
        'ambient': ambient_digest,
        'provider': provider_digest,
      })[:24],
      session_id=self._metadata.session_id,
      time_s=time_s,
      source_pose=source_pose,
      dynamic_state_digest_sha256=dynamic_digest,
      ambient_state_digest_sha256=ambient_digest,
      provider_state_digest_sha256=provider_digest,
    )
    model_lane_evaluator = _StraightIntegralModelLaneEvaluator(
      self._definition,
      self._configuration,
    )
    configuration_digest = canonical_digest(self._configuration)
    evaluators = {
      VISUAL_SECTIONED_TUBE_CAPABILITY: _StraightIntegralVisualEvaluator(
        self._definition,
        self._configuration,
      ),
      MODEL_LANE_VISUALIZATION_CAPABILITY: model_lane_evaluator,
      SPATIAL_LOCAL_FIELD_CAPABILITY: ModelLaneLocalFieldEvaluator(
        model_lane_evaluator,
      ),
    }
    if self._configuration.code_revision is not None:
      evaluators[ENGINEERING_FLUX_SECTION_CAPABILITY] = StraightIntegralEngineeringFluxEvaluator(
        result=self._definition.result,
        frame_id=self._definition.frame_id,
        centerline_reference_id=self._definition.centerline_reference_id,
        provider_id=self._configuration.provider_id,
        provider_version=self._configuration.provider_version,
        code_revision=self._configuration.code_revision,
        configuration_digest_sha256=configuration_digest,
        result_definition_digest_sha256=self._definition.digest,
      )
    return ImmutableProductSnapshot(
      metadata=metadata,
      _evaluators=evaluators,
    )
  ####

  def close(self) -> None:
    self._closed = True
  ####
####
