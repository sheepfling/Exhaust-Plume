"""Validated signature and ray-transfer query/result contracts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from exhaust_plume.contracts.capability import CapabilityId
from exhaust_plume.contracts.errors import AngularDomainError, ContractViolationError, SpatialDomainError, SpectralDomainError

FloatArray = NDArray[np.float64]


def _readonly_float_array(value: NDArray[np.floating] | NDArray[np.integer] | list[float] | tuple[float, ...]) -> FloatArray:
  array = np.array(value, dtype=np.float64, copy=True)
  array.flags.writeable = False
  return array
####


def _validate_wavelengths(value: FloatArray) -> None:
  if value.ndim != 1 or value.size == 0:
    raise SpectralDomainError('wavelength_m must be a non-empty one-dimensional array')
  ####
  if not np.isfinite(value).all() or (value <= 0).any():
    raise SpectralDomainError('wavelength_m must contain finite positive values')
  ####
  if value.size > 1 and not np.all(np.diff(value) > 0):
    raise SpectralDomainError('wavelength_m must be strictly increasing')
  ####
####


def _validate_unit_directions(value: FloatArray, field_name: str) -> None:
  if value.ndim != 2 or value.shape[1] != 3 or value.shape[0] == 0:
    raise AngularDomainError(f'{field_name} must have shape (n, 3) with n > 0')
  ####
  if not np.isfinite(value).all():
    raise AngularDomainError(f'{field_name} must contain finite values')
  ####
  norms = np.linalg.norm(value, axis=1)
  if not np.allclose(norms, 1.0, rtol=0.0, atol=1.0e-7):
    raise AngularDomainError(f'{field_name} must contain unit vectors')
  ####
####


@dataclass(frozen=True, slots=True)
class DirectionalSpectralIntensityQuery:
  """Request for intrinsic unresolved source intensity."""

  wavelength_m: FloatArray
  source_to_observer_direction_plume: FloatArray

  def __post_init__(self) -> None:
    wavelengths = _readonly_float_array(self.wavelength_m)
    directions = _readonly_float_array(self.source_to_observer_direction_plume)
    _validate_wavelengths(wavelengths)
    _validate_unit_directions(directions, 'source_to_observer_direction_plume')
    object.__setattr__(self, 'wavelength_m', wavelengths)
    object.__setattr__(self, 'source_to_observer_direction_plume', directions)
  ####
####


@dataclass(frozen=True, slots=True)
class DirectionalSpectralIntensityResult:
  """Intrinsic intensity in W/(sr m), ordered as (view, wavelength)."""

  wavelength_m: FloatArray
  source_to_observer_direction_plume: FloatArray
  spectral_radiant_intensity_w_sr_m: FloatArray
  quality_flags: tuple[str, ...]
  provenance_id: str
  capability_id: CapabilityId = CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY
  major_version: int = 1

  def __post_init__(self) -> None:
    wavelengths = _readonly_float_array(self.wavelength_m)
    directions = _readonly_float_array(self.source_to_observer_direction_plume)
    intensity = _readonly_float_array(self.spectral_radiant_intensity_w_sr_m)
    _validate_wavelengths(wavelengths)
    _validate_unit_directions(directions, 'source_to_observer_direction_plume')
    if intensity.shape != (directions.shape[0], wavelengths.shape[0]):
      raise ContractViolationError('spectral intensity must have shape (n_view, n_lambda)')
    ####
    if not np.isfinite(intensity).all() or (intensity < 0).any():
      raise ContractViolationError('spectral intensity must be finite and nonnegative')
    ####
    if not self.provenance_id:
      raise ContractViolationError('provenance_id must not be empty')
    ####
    object.__setattr__(self, 'wavelength_m', wavelengths)
    object.__setattr__(self, 'source_to_observer_direction_plume', directions)
    object.__setattr__(self, 'spectral_radiant_intensity_w_sr_m', intensity)
    object.__setattr__(self, 'quality_flags', tuple(self.quality_flags))
  ####
####


@dataclass(frozen=True, slots=True)
class SpectralRayTransferQuery:
  """Request for source radiance and background transmittance along rays."""

  observer_origin_plume_m: FloatArray
  observer_to_scene_direction_plume: FloatArray
  maximum_distance_m: FloatArray
  wavelength_m: FloatArray

  def __post_init__(self) -> None:
    origins = _readonly_float_array(self.observer_origin_plume_m)
    directions = _readonly_float_array(self.observer_to_scene_direction_plume)
    distances = _readonly_float_array(self.maximum_distance_m)
    wavelengths = _readonly_float_array(self.wavelength_m)
    if origins.ndim != 2 or origins.shape[1] != 3 or origins.shape[0] == 0 or not np.isfinite(origins).all():
      raise SpatialDomainError('observer_origin_plume_m must have finite shape (n_ray, 3)')
    ####
    _validate_unit_directions(directions, 'observer_to_scene_direction_plume')
    if directions.shape[0] != origins.shape[0]:
      raise ContractViolationError('ray origins and directions must have matching lengths')
    ####
    if distances.ndim != 1 or distances.shape[0] != origins.shape[0] or not np.isfinite(distances).all() or (distances <= 0).any():
      raise SpatialDomainError('maximum_distance_m must be finite, positive, and match n_ray')
    ####
    _validate_wavelengths(wavelengths)
    object.__setattr__(self, 'observer_origin_plume_m', origins)
    object.__setattr__(self, 'observer_to_scene_direction_plume', directions)
    object.__setattr__(self, 'maximum_distance_m', distances)
    object.__setattr__(self, 'wavelength_m', wavelengths)
  ####
####


@dataclass(frozen=True, slots=True)
class SpectralRayTransferResult:
  """Resolved source radiance and background transmittance."""

  source_spectral_radiance_w_sr_m: FloatArray
  background_transmittance: FloatArray
  provenance_id: str
  capability_id: CapabilityId = CapabilityId.SPECTRAL_RAY_TRANSFER
  major_version: int = 1

  def __post_init__(self) -> None:
    source = _readonly_float_array(self.source_spectral_radiance_w_sr_m)
    transmittance = _readonly_float_array(self.background_transmittance)
    if source.ndim != 2 or transmittance.shape != source.shape:
      raise ContractViolationError('ray-transfer arrays must have matching shape (n_ray, n_lambda)')
    ####
    if not np.isfinite(source).all() or (source < 0).any():
      raise ContractViolationError('source spectral radiance must be finite and nonnegative')
    ####
    if not np.isfinite(transmittance).all() or (transmittance < 0).any() or (transmittance > 1).any():
      raise ContractViolationError('background transmittance must be finite and in [0, 1]')
    ####
    if not self.provenance_id:
      raise ContractViolationError('provenance_id must not be empty')
    ####
    object.__setattr__(self, 'source_spectral_radiance_w_sr_m', source)
    object.__setattr__(self, 'background_transmittance', transmittance)
  ####
####
