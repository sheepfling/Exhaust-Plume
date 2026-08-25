"""Compatibility contracts for the pre-v1 plume product workflows.

These models are retained for existing workflows and adapters. They are not
the public v1 wire authority and must not replace provider-private solver
states or receive new product fields.
"""

from __future__ import annotations

from enum import Enum
from math import isfinite
import re
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Vector3: TypeAlias = tuple[float, float, float]
Matrix: TypeAlias = tuple[tuple[float, ...], ...]

_CAPABILITY_NAME = re.compile(r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')


class ContractModel(BaseModel):
  """Frozen contract base that rejects unknown fields."""

  model_config = ConfigDict(extra='forbid', frozen=True, validate_default=True)
####


class CapabilityId(ContractModel):
  """Capability identity with an explicit incompatible major version."""

  name: str
  major: Annotated[int, Field(ge=1)]

  @field_validator('name')
  @classmethod
  def validateName(cls, value: str) -> str:
    if not _CAPABILITY_NAME.fullmatch(value):
      raise ValueError(f'Invalid capability name:{value!r}')
    ####
    return value
  ####

  @classmethod
  def parse(cls, value: str) -> CapabilityId:
    name, separator, major_text = value.rpartition('@')
    if not separator or not major_text.isdigit():
      raise ValueError(f'Expected `<name>@<major>`. Got:{value!r}')
    ####
    return cls(name=name, major=int(major_text))
  ####

  def __str__(self) -> str:
    return f'{self.name}@{self.major}'
  ####
####


VISUAL_SECTIONED_TUBE_V1 = CapabilityId(name='plume.visual.sectioned-tube', major=1)
SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1 = CapabilityId(
    name='plume.signature.spectral-radiant-intensity', major=1,
)
OPTICAL_SPECTRAL_RAY_TRANSFER_V1 = CapabilityId(
    name='plume.optical.spectral-ray-transfer', major=1,
)
SPATIAL_CONSERVATIVE_SUPPORT_V1 = CapabilityId(
    name='plume.spatial.conservative-support', major=1,
)
ENGINEERING_FLUX_SECTION_V1 = CapabilityId(
    name='plume.engineering.flux-section', major=1,
)


class CoordinateFrame(ContractModel):
  """Named right-handed coordinate frame and axis convention."""

  frame_id: str = Field(min_length=1)
  axis_convention: str = Field(min_length=1)
  handedness: Literal['right-handed'] = 'right-handed'
####


class DirectionConvention(str, Enum):
  SOURCE_TO_OBSERVER = 'source-to-observer'
  RAY_PROPAGATION = 'ray-propagation'
####


class SpectralCoordinateKind(str, Enum):
  WAVELENGTH = 'wavelength'
  WAVENUMBER = 'wavenumber'
####


class SpectralAxis(ContractModel):
  """Strictly increasing positive spectral coordinates."""

  kind: SpectralCoordinateKind
  values: tuple[float, ...] = Field(min_length=1)
  coordinate_unit: Literal['m', '1/m']

  @field_validator('values', mode='before')
  @classmethod
  def normalizeValues(cls, value: object) -> tuple[float, ...]:
    try:
      return tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
      raise ValueError('Expected a finite spectral coordinate sequence.') from exc
    ####
  ####

  @model_validator(mode='after')
  def validateAxis(self) -> SpectralAxis:
    if any(not isfinite(value) or value <= 0. for value in self.values):
      raise ValueError('Spectral coordinates must be finite and positive.')
    ####
    if any(right <= left for left, right in zip(self.values, self.values[1:])):
      raise ValueError('Spectral coordinates must be strictly increasing.')
    ####
    expected_unit = 'm' if self.kind is SpectralCoordinateKind.WAVELENGTH else '1/m'
    if self.coordinate_unit != expected_unit:
      raise ValueError(
          f'{self.kind.value!r} requires coordinate unit {expected_unit!r}. '
          f'Got:{self.coordinate_unit!r}'
      )
    ####
    return self
  ####
####


class ProductReference(ContractModel):
  product_id: str = Field(min_length=1)
  capability: CapabilityId
####


class Provenance(ContractModel):
  provider_id: str = Field(min_length=1)
  provider_version: str = Field(min_length=1)
  model_name: str = Field(min_length=1)
  model_revision: str = Field(min_length=1)
  asset_sha256: tuple[str, ...] = ()
  calibration_id: str | None = None

  @field_validator('asset_sha256')
  @classmethod
  def validateDigests(cls, values: tuple[str, ...]) -> tuple[str, ...]:
    invalid = tuple(value for value in values if not _SHA256.fullmatch(value))
    if invalid:
      raise ValueError(f'Invalid lowercase SHA-256 digest(s):{invalid!r}')
    ####
    return values
  ####
####


class Fidelity(ContractModel):
  """Independent fidelity axes, deliberately not one opaque score."""

  morphology: str = Field(min_length=1)
  flow: str = Field(min_length=1)
  radiation: str = Field(min_length=1)
  time: str = Field(min_length=1)
  validation: str = Field(min_length=1)
####


class Applicability(ContractModel):
  minimum_time_s: float | None = None
  maximum_time_s: float | None = None
  allows_extrapolation: bool = False
  notes: tuple[str, ...] = ()

  @model_validator(mode='after')
  def validateRange(self) -> Applicability:
    for name, value in (
        ('minimum_time_s', self.minimum_time_s),
        ('maximum_time_s', self.maximum_time_s),
    ):
      if value is not None and not isfinite(value):
        raise ValueError(f'Expected `{name}` to be finite when present.')
      ####
    ####
    if (
        self.minimum_time_s is not None
        and self.maximum_time_s is not None
        and self.maximum_time_s < self.minimum_time_s
    ):
      raise ValueError('Expected maximum_time_s >= minimum_time_s.')
    ####
    return self
  ####
####


class ProductMetadata(ContractModel):
  product_id: str = Field(min_length=1)
  capability: CapabilityId
  snapshot_id: str = Field(min_length=1)
  time_s: float
  frame: CoordinateFrame
  provenance: Provenance
  fidelity: Fidelity
  applicability: Applicability = Field(default_factory=Applicability)
  derived_from: tuple[ProductReference, ...] = ()
  claims: tuple[str, ...] = ()

  @field_validator('time_s')
  @classmethod
  def validateTime(cls, value: float) -> float:
    if not isfinite(value):
      raise ValueError('Expected time_s to be finite.')
    ####
    return value
  ####
####


class CompletionStatus(str, Enum):
  COMPLETE = 'complete'
  PARTIAL = 'partial'
####


class BatchValidity(ContractModel):
  status: CompletionStatus
  valid: tuple[bool, ...] = Field(min_length=1)
  diagnostics: tuple[str, ...] = ()

  @model_validator(mode='after')
  def validateStatus(self) -> BatchValidity:
    if self.status is CompletionStatus.COMPLETE and not all(self.valid):
      raise ValueError('A complete batch cannot contain invalid entries.')
    ####
    if self.status is CompletionStatus.PARTIAL and all(self.valid):
      raise ValueError('A partial batch must identify at least one invalid entry.')
    ####
    return self
  ####
####


class Aabb3(ContractModel):
  minimum_m: Vector3
  maximum_m: Vector3

  @field_validator('minimum_m', 'maximum_m', mode='before')
  @classmethod
  def normalizeVector(cls, value: object) -> Vector3:
    return normalizeVector3(value, name='bound')
  ####

  @model_validator(mode='after')
  def validateBounds(self) -> Aabb3:
    if any(maximum < minimum for minimum, maximum in zip(self.minimum_m, self.maximum_m)):
      raise ValueError('Expected every maximum bound to be >= its minimum bound.')
    ####
    return self
  ####
####


def normalizeVector3(value: object, *, name: str) -> Vector3:
  try:
    vector = tuple(float(item) for item in value)  # type: ignore[arg-type]
  except (TypeError, ValueError) as exc:
    raise ValueError(f'Expected `{name}` to be a finite three-vector.') from exc
  ####
  if len(vector) != 3 or any(not isfinite(item) for item in vector):
    raise ValueError(f'Expected `{name}` to be a finite three-vector. Got:{vector!r}')
  ####
  return vector  # type: ignore[return-value]
####


def validateMatrix(
    values: object,
    *,
    rows: int,
    columns: int,
    name: str,
) -> Matrix:
  try:
    matrix = tuple(tuple(float(item) for item in row) for row in values)  # type: ignore[arg-type]
  except (TypeError, ValueError) as exc:
    raise ValueError(f'Expected `{name}` to be a finite matrix.') from exc
  ####
  if len(matrix) != rows or any(len(row) != columns for row in matrix):
    raise ValueError(f'Expected `{name}` shape ({rows}, {columns}).')
  ####
  if any(not isfinite(item) for row in matrix for item in row):
    raise ValueError(f'Expected `{name}` to contain only finite values.')
  ####
  return matrix
####
