"""Straight, deterministic visual-product provider built from explicit parameters."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi, tan

from exhaust_plume.api.v1 import (
  GeometryClaim,
  ProviderConfigurationError,
  ProviderDescriptor,
  RadiationClaim,
  TimeModel,
  VisualSection,
)
from exhaust_plume.providers.prescribed_visual import (
  PrescribedVisualConfiguration,
  PrescribedVisualDefinition,
  PrescribedVisualProvider,
  PrescribedVisualSession,
)

__all__ = (
  'StraightVisualConfiguration',
  'StraightVisualDefinition',
  'StraightVisualProvider',
)


@dataclass(frozen=True, slots=True)
class StraightVisualDefinition:
  """Provider-specific straight centerline and radius parameters."""

  frame_id: str
  length_m: float
  initial_radius_major_m: float
  initial_radius_minor_m: float
  divergence_angle_rad: float = 0.0
  base_section_count: int = 32

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ProviderConfigurationError('straight visual frame_id must not be empty')
    ####
    for field_name, value in (
      ('length_m', self.length_m),
      ('initial_radius_major_m', self.initial_radius_major_m),
      ('initial_radius_minor_m', self.initial_radius_minor_m),
      ('divergence_angle_rad', self.divergence_angle_rad),
    ):
      if not isfinite(value):
        raise ProviderConfigurationError(f'{field_name} must be finite')
      ####
    ####
    if self.length_m <= 0.0:
      raise ProviderConfigurationError('length_m must be positive')
    ####
    if self.initial_radius_major_m <= 0.0 or self.initial_radius_minor_m <= 0.0:
      raise ProviderConfigurationError('initial radii must be positive')
    ####
    if not (-pi / 4.0 < self.divergence_angle_rad < pi / 4.0):
      raise ProviderConfigurationError('divergence_angle_rad must be between -pi/4 and pi/4')
    ####
    if isinstance(self.base_section_count, bool) or self.base_section_count < 2:
      raise ProviderConfigurationError('base_section_count must be an integer >= 2')
    ####
    final_scale = 1.0 + self.length_m * tan(self.divergence_angle_rad) / min(
      self.initial_radius_major_m,
      self.initial_radius_minor_m,
    )
    if final_scale <= 0.0:
      raise ProviderConfigurationError('divergence causes a non-positive terminal radius')
    ####
  ####

  def to_prescribed_definition(self) -> PrescribedVisualDefinition:
    arc_lengths = tuple(
      self.length_m * index / (self.base_section_count - 1)
      for index in range(self.base_section_count)
    )
    radii = tuple(
      self.initial_radius_major_m + arc_length * tan(self.divergence_angle_rad)
      for arc_length in arc_lengths
    )
    minor_radii = tuple(
      self.initial_radius_minor_m + arc_length * tan(self.divergence_angle_rad)
      for arc_length in arc_lengths
    )
    maximum_radius = max((*radii, *minor_radii))
    sections = tuple(
      VisualSection(
        arc_length_m=arc_length,
        center_m=(arc_length, 0.0, 0.0),
        section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
        radius_major_m=radius,
        radius_minor_m=minor_radius,
      )
      for arc_length, radius, minor_radius in zip(arc_lengths, radii, minor_radii, strict=True)
    )
    return PrescribedVisualDefinition(
      frame_id=self.frame_id,
      sections=sections,
      channels={
        'core_radius_fraction': tuple(radius / maximum_radius for radius in radii),
        'opacity_weight': tuple(1.0 for _ in radii),
      },
    )
  ####
####


@dataclass(frozen=True, slots=True)
class StraightVisualConfiguration:
  provider_id: str = 'visual.straight-parametric'
  provider_version: str = '1.0.0'
  geometry_claim: GeometryClaim = GeometryClaim.ILLUSTRATIVE
  radiation_claim: RadiationClaim = RadiationClaim.APPEARANCE_ONLY
  time_model: TimeModel = TimeModel.STEADY

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('straight visual provider identity must not be empty')
    ####
  ####
####


class StraightVisualProvider:
  """Expose a straight parametric visual product through the common lifecycle."""

  def __init__(self, configuration: StraightVisualConfiguration | None = None) -> None:
    self._configuration = configuration or StraightVisualConfiguration()
    self._delegate = PrescribedVisualProvider(PrescribedVisualConfiguration(
      provider_id=self._configuration.provider_id,
      provider_version=self._configuration.provider_version,
      geometry_claim=self._configuration.geometry_claim,
      radiation_claim=self._configuration.radiation_claim,
      time_model=self._configuration.time_model,
    ))
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._delegate.descriptor
  ####

  def create_session(
      self,
      *,
      definition: StraightVisualDefinition,
      configuration: StraightVisualConfiguration | None = None,
  ) -> PrescribedVisualSession:
    if not isinstance(definition, StraightVisualDefinition):
      raise ProviderConfigurationError('definition must be StraightVisualDefinition')
    ####
    selected_configuration = configuration or self._configuration
    if selected_configuration != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return self._delegate.create_session(
      definition=definition.to_prescribed_definition(),
      configuration=PrescribedVisualConfiguration(
        provider_id=selected_configuration.provider_id,
        provider_version=selected_configuration.provider_version,
        geometry_claim=selected_configuration.geometry_claim,
        radiation_claim=selected_configuration.radiation_claim,
        time_model=selected_configuration.time_model,
      ),
    )
  ####
####
