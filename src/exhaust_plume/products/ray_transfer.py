"""Resolved spectral ray-transfer product."""

from __future__ import annotations

from math import isclose, sqrt
from typing import Literal

from pydantic import Field, field_validator, model_validator

from exhaust_plume.products._base import (
    BatchValidity,
    ContractModel,
    DirectionConvention,
    Matrix,
    OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
    ProductMetadata,
    SpectralAxis,
    Vector3,
    normalizeVector3,
    validateMatrix,
)


class RayDefinition(ContractModel):
  """One ray origin and propagation direction in the product frame."""

  origin_m: Vector3
  direction_unit: Vector3

  @field_validator('origin_m', mode='before')
  @classmethod
  def normalizeOrigin(cls, value: object) -> Vector3:
    return normalizeVector3(value, name='origin_m')
  ####

  @field_validator('direction_unit', mode='before')
  @classmethod
  def normalizeDirection(cls, value: object) -> Vector3:
    return normalizeVector3(value, name='direction_unit')
  ####

  @model_validator(mode='after')
  def validateDirection(self) -> RayDefinition:
    magnitude = sqrt(sum(component * component for component in self.direction_unit))
    if not isclose(magnitude, 1., rel_tol=1.e-7, abs_tol=1.e-9):
      raise ValueError(f'Ray direction is not unit length:{magnitude}')
    ####
    return self
  ####
####


class SpectralRayTransferProduct(ContractModel):
  """Resolved plume source radiance and background transmittance.

  Downstream composition uses

      L_out = L_background * background_transmittance + source_radiance

  for each ray and spectral coordinate.
  """

  metadata: ProductMetadata
  spectral_axis: SpectralAxis
  rays: tuple[RayDefinition, ...] = Field(min_length=1)
  direction_convention: Literal[DirectionConvention.RAY_PROPAGATION] = (
      DirectionConvention.RAY_PROPAGATION
  )
  source_radiance: Matrix
  source_radiance_unit: str = Field(min_length=1)
  background_transmittance: Matrix
  validity: BatchValidity

  @model_validator(mode='after')
  def validateProduct(self) -> SpectralRayTransferProduct:
    if self.metadata.capability != OPTICAL_SPECTRAL_RAY_TRANSFER_V1:
      raise ValueError(
          f'Expected capability {OPTICAL_SPECTRAL_RAY_TRANSFER_V1}. '
          f'Got:{self.metadata.capability}'
      )
    ####
    shape = (len(self.rays), len(self.spectral_axis.values))
    object.__setattr__(
        self,
        'source_radiance',
        validateMatrix(
            self.source_radiance,
            rows=shape[0],
            columns=shape[1],
            name='source_radiance',
        ),
    )
    transmittance = validateMatrix(
        self.background_transmittance,
        rows=shape[0],
        columns=shape[1],
        name='background_transmittance',
    )
    if any(value < 0. or value > 1. for row in transmittance for value in row):
      raise ValueError('Background transmittance must lie in [0, 1].')
    ####
    object.__setattr__(self, 'background_transmittance', transmittance)
    if len(self.validity.valid) != len(self.rays):
      raise ValueError('Ray validity must contain one flag per ray.')
    ####
    return self
  ####
####
