"""Intrinsic unresolved spectral radiant-intensity product."""

from __future__ import annotations

from math import isclose, sqrt
from typing import Literal

from pydantic import Field, field_validator, model_validator

from exhaust_plume.products._base import (
    BatchValidity,
    ContractModel,
    DirectionConvention,
    Matrix,
    ProductMetadata,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    SpectralAxis,
    Vector3,
    normalizeVector3,
    validateMatrix,
)


class SpectralRadiantIntensityProduct(ContractModel):
  """Source-intrinsic unresolved spectral radiant intensity.

  Range loss, external atmosphere, optics, and detector response are excluded.
  """

  metadata: ProductMetadata
  spectral_axis: SpectralAxis
  directions_unit: tuple[Vector3, ...] = Field(min_length=1)
  direction_convention: Literal[DirectionConvention.SOURCE_TO_OBSERVER] = (
      DirectionConvention.SOURCE_TO_OBSERVER
  )
  radiant_intensity: Matrix
  value_unit: str = Field(min_length=1)
  validity: BatchValidity
  includes_range_loss: Literal[False] = False
  includes_external_atmosphere: Literal[False] = False
  includes_optics: Literal[False] = False
  includes_detector_response: Literal[False] = False

  @field_validator('directions_unit', mode='before')
  @classmethod
  def normalizeDirections(cls, value: object) -> tuple[Vector3, ...]:
    try:
      return tuple(normalizeVector3(item, name='direction') for item in value)  # type: ignore[arg-type]
    except TypeError as exc:
      raise ValueError('Expected a direction sequence.') from exc
    ####
  ####

  @model_validator(mode='after')
  def validateProduct(self) -> SpectralRadiantIntensityProduct:
    if self.metadata.capability != SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1:
      raise ValueError(f'Expected capability {SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1}.')
    ####
    for index, direction in enumerate(self.directions_unit):
      magnitude = sqrt(sum(component * component for component in direction))
      if not isclose(magnitude, 1., rel_tol=1.e-7, abs_tol=1.e-9):
        raise ValueError(f'Direction {index} is not unit length:{magnitude}')
      ####
    ####
    matrix = validateMatrix(
        self.radiant_intensity,
        rows=len(self.directions_unit),
        columns=len(self.spectral_axis.values),
        name='radiant_intensity',
    )
    object.__setattr__(self, 'radiant_intensity', matrix)
    if len(self.validity.valid) != len(self.directions_unit):
      raise ValueError('Signature validity must contain one flag per direction.')
    ####
    return self
  ####
####
