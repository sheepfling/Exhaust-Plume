"""Separate path-aware gray transfer provider for curved sectioned supports."""

from __future__ import annotations

from exhaust_plume.contracts.errors import ProviderConfigurationError
from exhaust_plume.providers.gray_ray_transfer import (
  GrayRayTransferConfiguration,
  GrayRayTransferDefinition,
  GrayRayTransferSession,
  _descriptor,
)

__all__ = ('CurvedGrayRayTransferProvider',)


class CurvedGrayRayTransferProvider:
  """Expose homogeneous gray transfer for explicitly curved support geometry.

  This is a separate experimental provider.  It does not claim curved-flow
  physics, chemistry, atmosphere, detector, or external validation.
  """

  def __init__(self, configuration: GrayRayTransferConfiguration | None = None) -> None:
    selected = configuration or GrayRayTransferConfiguration(provider_id='plume.curved-gray-ray-transfer')
    if selected.provider_id != 'plume.curved-gray-ray-transfer':
      raise ProviderConfigurationError('curved provider requires its dedicated provider identity')
    ####
    self._configuration = selected
    base = _descriptor(selected)
    self._descriptor = base.model_copy(update={
      'supported_morphologies': ('curved-sectioned',),
      'notes': (
        'piecewise capsule path transfer through a curved sectioned support',
        'homogeneous gray source-function transfer only',
        'curved geometry is a conservative segment-maximum support approximation',
        'no chemistry, atmosphere, detector, FPA, or external-validation claim',
        'fidelity profile: curved-optical-transfer-v1',
      ),
    })
  ####

  @property
  def descriptor(self):
    return self._descriptor
  ####

  def create_session(self, *, definition: GrayRayTransferDefinition, configuration=None) -> GrayRayTransferSession:
    if not isinstance(definition, GrayRayTransferDefinition):
      raise ProviderConfigurationError('definition must be GrayRayTransferDefinition')
    ####
    if definition.support.is_straight:
      raise ProviderConfigurationError('curved provider requires a non-straight support')
    ####
    if not definition.allow_curved_support:
      raise ProviderConfigurationError('curved definition must explicitly allow curved support')
    ####
    selected = configuration or self._configuration
    if selected != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return GrayRayTransferSession(self._descriptor, definition, selected)
  ####
####
