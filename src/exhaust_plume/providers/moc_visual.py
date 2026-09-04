"""Lifecycle provider for the planar-MOC research visualization lane."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from exhaust_plume.api.v1 import (
  ImmutableProductSnapshot,
  Pose,
  ProviderClosedError,
  ProviderConfigurationError,
  ProviderDescriptor,
  SessionMetadata,
  SnapshotMetadata,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  canonical_digest,
)
from exhaust_plume.products.model_visualization import (
  ModelVisualizationLane,
  evaluate_standardized_model_visualization,
  standardize_model_visualization,
)

__all__ = ('MocVisualDefinition', 'MocVisualProvider', 'MocVisualSession')


@dataclass(frozen=True, slots=True)
class MocVisualDefinition:
  frame_id: str
  result: object

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ProviderConfigurationError('MOC visual frame_id must not be empty')
    ####
    try:
      standardize_model_visualization(self.result, lane=ModelVisualizationLane.PLANAR_MOC, frame_id=self.frame_id)
    except (TypeError, ValueError) as error:
      raise ProviderConfigurationError('MOC visual result is not a retained planar-MOC result') from error
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class MocVisualConfiguration:
  provider_id: str = 'plume.visual.planar-moc'
  provider_version: str = '1.0.0'
####


def _descriptor(configuration: MocVisualConfiguration) -> ProviderDescriptor:
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(VISUAL_SECTIONED_TUBE_CAPABILITY,),
    provider_definition_schema_id='plume.visual.planar-moc-definition.v1',
    dynamic_state_schema_id='plume.visual.planar-moc-dynamic-state.v1',
    configuration_schema_id='plume.visual.planar-moc-configuration.v1',
    supported_morphologies=('planar-moc-research-envelope',),
    deterministic=True,
    notes=(
      '2-D planar characteristic field visualization and display envelope only',
      'research-only illustrative geometry; no axisymmetric flow claim',
      'no Signature, ray-transfer, detector, or FPA capability',
    ),
  )
####


class _Evaluator:
  def __init__(self, definition: MocVisualDefinition, configuration: MocVisualConfiguration) -> None:
    self.definition = definition
    self.configuration = configuration
  ####

  def evaluate(self, request: VisualSectionedTubeRequest, snapshot: SnapshotMetadata) -> VisualSectionedTubeResult:
    visualization = standardize_model_visualization(
      self.definition.result,
      lane=ModelVisualizationLane.PLANAR_MOC,
      frame_id=self.definition.frame_id,
      section_count=request.sampling.maximum_section_count,
    )
    if request.output_frame_id != self.definition.frame_id:
      raise ProviderConfigurationError(f'MOC visual provider supports output frame {self.definition.frame_id!r}, not {request.output_frame_id!r}')
    ####
    return evaluate_standardized_model_visualization(
      visualization,
      request,
      snapshot,
      provider_id=self.configuration.provider_id,
      provider_version=self.configuration.provider_version,
    )
  ####
####


class MocVisualProvider:
  def __init__(self, configuration: MocVisualConfiguration | None = None) -> None:
    self.configuration = configuration or MocVisualConfiguration()
    self._descriptor = _descriptor(self.configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(self, *, definition: MocVisualDefinition, configuration: MocVisualConfiguration | None = None) -> 'MocVisualSession':
    if not isinstance(definition, MocVisualDefinition):
      raise ProviderConfigurationError('definition must be MocVisualDefinition')
    ####
    selected = configuration or self.configuration
    if selected != self.configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return MocVisualSession(self._descriptor, definition, selected)
  ####
####


class MocVisualSession:
  def __init__(self, descriptor: ProviderDescriptor, definition: MocVisualDefinition, configuration: MocVisualConfiguration) -> None:
    self._descriptor = descriptor
    self._definition = definition
    self._configuration = configuration
    self._closed = False
    digest = canonical_digest(configuration)
    self._metadata = SessionMetadata(
      session_id=canonical_digest({'provider': descriptor.provider_id, 'definition': canonical_digest(definition), 'configuration': digest})[:24],
      provider_id=descriptor.provider_id,
      provider_version=descriptor.provider_version,
      configuration_digest_sha256=digest,
    )
  ####

  @property
  def metadata(self) -> SessionMetadata:
    return self._metadata
  ####

  def create_snapshot(self, *, time_s: float, source_pose: Pose, dynamic_state: Mapping[str, Any], ambient_state: Mapping[str, Any]) -> ImmutableProductSnapshot:
    if self._closed:
      raise ProviderClosedError('MOC visual session is closed')
    ####
    if not isfinite(float(time_s)):
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
    state_digest = canonical_digest(self._definition)
    snapshot = SnapshotMetadata(
      snapshot_id=canonical_digest({'session': self._metadata.session_id, 'time_s': time_s, 'pose': source_pose, 'dynamic': dynamic_digest, 'ambient': ambient_digest})[:24],
      session_id=self._metadata.session_id,
      time_s=float(time_s),
      source_pose=source_pose,
      dynamic_state_digest_sha256=dynamic_digest,
      ambient_state_digest_sha256=ambient_digest,
      provider_state_digest_sha256=state_digest,
    )
    return ImmutableProductSnapshot(metadata=snapshot, _evaluators={VISUAL_SECTIONED_TUBE_CAPABILITY: _Evaluator(self._definition, self._configuration)})
  ####

  def close(self) -> None:
    self._closed = True
  ####
####
