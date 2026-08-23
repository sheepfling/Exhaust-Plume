"""Typed failures shared by provider and consumer contracts."""

from __future__ import annotations


class ProviderError(Exception):
  """Base class for provider contract failures."""

  ####


class UnsupportedCapabilityError(ProviderError):
  """Raised when a snapshot does not advertise a requested capability."""

  ####


class CapabilityVersionMismatchError(ProviderError):
  """Raised when a requested capability major version is unsupported."""

  ####


class ProviderConfigurationError(ProviderError):
  """Raised when provider definition or configuration is invalid."""

  ####


class OperatingStateDomainError(ProviderError):
  """Raised when an operating state is outside provider applicability."""

  ####


class SpectralDomainError(ProviderError, ValueError):
  """Raised for invalid wavelength grids or spectral domains."""

  ####


class AngularDomainError(ProviderError, ValueError):
  """Raised for invalid source/view direction vectors."""

  ####


class TemporalDomainError(ProviderError):
  """Raised when a requested time is outside provider applicability."""

  ####


class SpatialDomainError(ProviderError):
  """Raised when a spatial query is outside provider applicability."""

  ####


class ContractViolationError(ProviderError, ValueError):
  """Raised when a provider returns an internally inconsistent contract."""

  ####


class SnapshotInvalidatedError(ProviderError):
  """Raised when a retained snapshot can no longer serve capabilities."""

  ####


class ProviderClosedError(ProviderError):
  """Raised when a session is used after it has been closed."""

  ####


class PublicContractError(ProviderError):
  """Base class for failures at the versioned consumer contract boundary."""

  ####


class InvalidProductRequestError(PublicContractError, ValueError):
  """Raised when a product request is not valid for its contract."""

  ####


class UnsupportedProductCapabilityError(PublicContractError):
  """Raised when a snapshot does not advertise a versioned product capability."""

  ####


class UnsupportedProductVersionError(PublicContractError):
  """Raised when a product major version is not supported."""

  ####


class ProductOutsideApplicabilityError(PublicContractError):
  """Raised when a valid request is outside the provider's declared domain."""

  ####


class ProductSnapshotExpiredError(PublicContractError):
  """Raised when an immutable snapshot is no longer retained."""

  ####
