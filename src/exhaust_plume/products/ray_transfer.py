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
  """Resolved source radiance and background transmittance.

  Downstream scene composition uses

      L_out = L_background * background_transmittance + source_radiance
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
      raise ValueError(f'Expected capability {OPTICAL_SPECTRAL_RAY_TRANSFER_V1}.')
    ####
    rows = len(self.rays)
    columns = len(self.spectral_axis.values)
    source = validateMatrix(
        self.source_radiance,
        rows=rows,
        columns=columns,
        name='source_radiance',
    )
    transmittance = validateMatrix(
        self.background_transmittance,
        rows=rows,
        columns=columns,
        name='background_transmittance',
    )
    if any(value < 0. or value > 1. for row in transmittance for value in row):
      raise ValueError('Background transmittance must lie in [0, 1].')
    ####
    object.__setattr__(self, 'source_radiance', source)
    object.__setattr__(self, 'background_transmittance', transmittance)
    if len(self.validity.valid) != rows:
      raise ValueError('Ray validity must contain one flag per ray.')
    ####
    return self
  ####
####
