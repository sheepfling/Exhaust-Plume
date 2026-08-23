"""Deterministic provider for the neutral sectioned-tube contract.

This provider exists to exercise lifecycle, validation, and interchange. It
does not claim to reconstruct a physical plume or to provide radiometry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from types import MappingProxyType
from typing import Any, Mapping

from exhaust_plume.contracts import (
  ApplicabilityReport,
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ImmutableProductSnapshot,
  InvalidProductRequestError,
  Pose,
  ProductClaims,
  ProductOutsideApplicabilityError,
  ProviderDescriptor,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SessionMetadata,
  SnapshotMetadata,
  TimeModel,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualSection,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  VisualTubeSummary,
  VisualBounds,
  Vector3,
  canonical_digest,
)
from exhaust_plume.contracts.errors import ProviderClosedError, ProviderConfigurationError

__all__ = (
  'PrescribedVisualConfiguration',
  'PrescribedVisualDefinition',
  'PrescribedVisualProvider',
  'PrescribedVisualSession',
)
####


@dataclass(frozen=True, slots=True)
class PrescribedVisualDefinition:
  """Explicit renderer-neutral sections and optional feature channels."""

  frame_id: str
  sections: tuple[VisualSection, ...]
  channels: Mapping[str, tuple[float, ...]] = field(default_factory=dict)

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ProviderConfigurationError('visual definition frame_id must not be empty')
    if len(self.sections) < 2:
      raise ProviderConfigurationError('visual definition requires at least two sections')
    arc_lengths = [section.arc_length_m for section in self.sections]
    if any(next_value <= value for value, next_value in zip(arc_lengths, arc_lengths[1:])):
      raise ProviderConfigurationError('visual definition section arc lengths must be strictly increasing')
    normalized_channels: dict[str, tuple[float, ...]] = {}
    for channel_name, values in self.channels.items():
      if not channel_name or any(
          not (character.islower() or character.isdigit() or character in {'_', '-'})
          for character in channel_name
      ):
        raise ProviderConfigurationError(f'invalid visual channel name: {channel_name}')
      if len(values) != len(self.sections):
        raise ProviderConfigurationError(f'visual channel {channel_name!r} length must equal section count')
      if not all(isfinite(value) for value in values):
        raise ProviderConfigurationError(f'visual channel {channel_name!r} must be finite')
      normalized_channels[channel_name] = tuple(float(value) for value in values)
    object.__setattr__(self, 'sections', tuple(self.sections))
    object.__setattr__(self, 'channels', MappingProxyType(normalized_channels))
  ####
####


@dataclass(frozen=True, slots=True)
class PrescribedVisualConfiguration:
  provider_id: str = 'prescribed.visual'
  provider_version: str = '1.0.0'
  geometry_claim: GeometryClaim = GeometryClaim.ILLUSTRATIVE
  radiation_claim: RadiationClaim = RadiationClaim.APPEARANCE_ONLY
  time_model: TimeModel = TimeModel.STEADY
  derivation: Derivation = Derivation.NATIVE
  consistency: ConsistencyLevel = ConsistencyLevel.CO_GENERATED
  applicability_status: ApplicabilityStatus = ApplicabilityStatus.INSIDE
  applicability_reasons: tuple[str, ...] = ()
  warnings: tuple[str, ...] = ()

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('visual provider identity must not be empty')
  ####
####


def _descriptor(configuration: PrescribedVisualConfiguration) -> ProviderDescriptor:
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(VISUAL_SECTIONED_TUBE_CAPABILITY,),
    provider_definition_schema_id='plume.visual.prescribed-definition.v1',
    dynamic_state_schema_id='plume.visual.prescribed-dynamic-state.v1',
    configuration_schema_id='plume.visual.prescribed-configuration.v1',
    supported_morphologies=('prescribed',),
    deterministic=True,
    notes=('explicit sections and appearance channels only',),
  )
####


class PrescribedVisualProvider:
  """Provider that demonstrates one consumer product without physics coupling."""

  def __init__(self, configuration: PrescribedVisualConfiguration | None = None) -> None:
    self._configuration = configuration or PrescribedVisualConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: PrescribedVisualDefinition,
      configuration: PrescribedVisualConfiguration | None = None,
  ) -> 'PrescribedVisualSession':
    if not isinstance(definition, PrescribedVisualDefinition):
      raise ProviderConfigurationError('definition must be PrescribedVisualDefinition')
    selected_configuration = configuration or self._configuration
    if selected_configuration != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    return PrescribedVisualSession(self._descriptor, definition, selected_configuration)
  ####
####


class _PrescribedVisualEvaluator:
  def __init__(self, definition: PrescribedVisualDefinition, configuration: PrescribedVisualConfiguration) -> None:
    self._definition = definition
    self._configuration = configuration
  ####

  def evaluate(self, request: VisualSectionedTubeRequest, snapshot: SnapshotMetadata) -> VisualSectionedTubeResult:
    return _evaluate_prescribed_definition(
      self._definition,
      self._configuration,
      request,
      snapshot,
    )
  ####
####


def _evaluate_prescribed_definition(
    definition: PrescribedVisualDefinition,
    configuration: PrescribedVisualConfiguration,
    request: VisualSectionedTubeRequest,
    snapshot: SnapshotMetadata,
) -> VisualSectionedTubeResult:
  """Evaluate any explicit section definition through the v1 result contract.

  Analytical providers use this private adapter after constructing their own
  geometry.  Keeping sampling, channels, bounds, metadata, and provenance in
  one path prevents provider-specific result drift.
  """

  if request.output_frame_id != definition.frame_id:
    raise ProductOutsideApplicabilityError(
      f'prescribed visual provider supports output frame {definition.frame_id!r}, '
      f'not {request.output_frame_id!r}'
    )
  unsupported = tuple(channel for channel in request.requested_channels if channel not in definition.channels)
  if unsupported:
    raise InvalidProductRequestError(f'unsupported visual channels: {unsupported}')
  sections = _sample_sections(definition.sections, request.sampling.maximum_section_count)
  selected_indices = _sample_indices(len(definition.sections), len(sections))
  channels = {
    channel_name: tuple(definition.channels[channel_name][index] for index in selected_indices)
    for channel_name in request.requested_channels
  }
  maximum_radius = max(max(section.radius_major_m, section.radius_minor_m) for section in sections)
  bounds = _visual_bounds(sections) if request.include_visual_bounds else None
  request_digest = canonical_digest(request)
  lineage_id = canonical_digest({
    'definition_frame_id': definition.frame_id,
    'sections': [section.model_dump(mode='json') for section in definition.sections],
    'channels': definition.channels,
  })
  metadata = ResultMetadata(
    capability=VISUAL_SECTIONED_TUBE_CAPABILITY,
    result_id=canonical_digest({'snapshot': snapshot.snapshot_id, 'request': request_digest})[:24],
    request_digest_sha256=request_digest,
    snapshot=snapshot,
    output_frame_id=request.output_frame_id,
    claims=ProductClaims(
      geometry=configuration.geometry_claim,
      radiation=configuration.radiation_claim,
      time_model=configuration.time_model,
      derivation=configuration.derivation,
      consistency=configuration.consistency,
    ),
    applicability=ApplicabilityReport(
      status=configuration.applicability_status,
      reasons=configuration.applicability_reasons,
    ),
    provenance=ResultProvenance(
      model_lineage_id=lineage_id,
      provider_id=configuration.provider_id,
      provider_version=configuration.provider_version,
      configuration_digest_sha256=canonical_digest(configuration),
    ),
    warnings=configuration.warnings,
  )
  return VisualSectionedTubeResult(
    metadata=metadata,
    sections=sections,
    channels=channels,
    visual_bounds=bounds,
    summary=VisualTubeSummary(
      length_m=sections[-1].arc_length_m,
      maximum_radius_m=maximum_radius,
    ),
  )


def _sample_indices(total_count: int, selected_count: int) -> tuple[int, ...]:
  if selected_count >= total_count:
    return tuple(range(total_count))
  indices = tuple(round(index * (total_count - 1) / (selected_count - 1)) for index in range(selected_count))
  return tuple(int(index) for index in indices)
####


def _sample_sections(sections: tuple[VisualSection, ...], maximum_count: int) -> tuple[VisualSection, ...]:
  selected_indices = _sample_indices(len(sections), min(len(sections), maximum_count))
  return tuple(sections[index] for index in selected_indices)
####


def _visual_bounds(sections: tuple[VisualSection, ...]) -> VisualBounds:
  radius = max(max(section.radius_major_m, section.radius_minor_m) for section in sections)
  minimum: Vector3 = (
    min(section.center_m[0] - radius for section in sections),
    min(section.center_m[1] - radius for section in sections),
    min(section.center_m[2] - radius for section in sections),
  )
  maximum: Vector3 = (
    max(section.center_m[0] + radius for section in sections),
    max(section.center_m[1] + radius for section in sections),
    max(section.center_m[2] + radius for section in sections),
  )
  return VisualBounds(minimum_m=minimum, maximum_m=maximum)
####


class PrescribedVisualSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: PrescribedVisualDefinition,
      configuration: PrescribedVisualConfiguration,
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
        'definition': definition.frame_id,
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
      raise ProviderClosedError('prescribed visual session is closed')
    if not isfinite(time_s):
      raise ProviderConfigurationError('time_s must be finite')
    dynamic_digest = canonical_digest(dynamic_state)
    ambient_digest = canonical_digest(ambient_state)
    provider_digest = canonical_digest({
      'definition': self._definition,
      'configuration': self._configuration,
    })
    snapshot_id = canonical_digest({
      'session': self._metadata.session_id,
      'time_s': time_s,
      'dynamic': dynamic_digest,
      'ambient': ambient_digest,
      'provider': provider_digest,
      'source_pose': source_pose,
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
      _evaluators={VISUAL_SECTIONED_TUBE_CAPABILITY: _PrescribedVisualEvaluator(self._definition, self._configuration)},
    )
  ####

  def close(self) -> None:
    self._closed = True
  ####
