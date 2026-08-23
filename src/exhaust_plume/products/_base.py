"""Common immutable contracts for plume products.

These contracts are an API-review witness. They intentionally do not replace
provider-private solver states or claim that the v1 capability schemas are
frozen.
"""

from __future__ import annotations

from enum import Enum
from math import isfinite
from numbers import Real
import re
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

Vector3: TypeAlias = tuple[float, float, float]
Matrix: TypeAlias = tuple[tuple[float, ...], ...]

_CAPABILITY_NAME = re.compile(r'^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$')
_SHA256 = re.compile(r'^[0-9a-f]{64}$')


def normalizeFiniteFloat(value: object, *, name: str) -> float:
  """Accept a real numeric value without string or boolean coercion."""
  if isinstance(value, bool) or not isinstance(value, Real):
    raise ValueError(f'Expected `{name}` to be a real numeric value. Got:{value!r}')
  ####
  result = float(value)
  if not isfinite(result):
    raise ValueError(f'Expected `{name}` to be finite. Got:{value!r}')
  ####
  return result
####


def normalizeFiniteSequence(value: object, *, name: str) -> tuple[float, ...]:
  """Normalize a numeric sequence without scalar-string coercion."""
  if isinstance(value, (str, bytes)):
    raise ValueError(f'Expected `{name}` to be a numeric sequence.')
  ####
  try:
    return tuple(normalizeFiniteFloat(item, name=name) for item in value)  # type: ignore[arg-type]
  except TypeError as exc:
    raise ValueError(f'Expected `{name}` to be a numeric sequence.') from exc
  ####
####


class ContractModel(BaseModel):
  """Frozen, extra-forbidding base for transport-safe product contracts."""

  model_config = ConfigDict(
      extra='forbid',
      frozen=True,
      validate_default=True,
  )
####


class CapabilityId(ContractModel):
  """Semantic capability identity with an explicit incompatible major version."""

  name: str
  major: Annotated[int, Field(ge=1, strict=True)]

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
      raise ValueError(f'Expected capability in `<name>@<major>` form. Got:{value!r}')
    ####
    return cls(name=name, major=int(major_text))
  ####

  def __str__(self) -> str:
    return f'{self.name}@{self.major}'
  ####
####


VISUAL_SECTIONED_TUBE_V1 = CapabilityId(name='plume.visual.sectioned-tube', major=1)
SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1 = CapabilityId(
    name='plume.signature.spectral-radiant-intensity',
    major=1,
)
OPTICAL_SPECTRAL_RAY_TRANSFER_V1 = CapabilityId(
    name='plume.optical.spectral-ray-transfer',
    major=1,
)
SPATIAL_CONSERVATIVE_SUPPORT_V1 = CapabilityId(
    name='plume.spatial.conservative-support',
    major=1,
)
ENGINEERING_FLUX_SECTION_V1 = CapabilityId(
    name='plume.engineering.flux-section',
    major=1,
)


class CoordinateFrame(ContractModel):
  """Named right-handed coordinate frame and axis convention."""

  frame_id: str = Field(min_length=1)
  axis_convention: str = Field(min_length=1)
  handedness: Literal['right-handed'] = 'right-handed'
####


class DirectionConvention(str, Enum):
  """Physical meaning of a normalized direction vector."""

  SOURCE_TO_OBSERVER = 'source-to-observer'
  RAY_PROPAGATION = 'ray-propagation'
####


class SpectralCoordinateKind(str, Enum):
  """Coordinate used by a spectral density."""

  WAVELENGTH = 'wavelength'
  WAVENUMBER = 'wavenumber'
####


class SpectralAxis(ContractModel):
  """Strictly increasing spectral coordinates with an explicit density basis."""

  kind: SpectralCoordinateKind
  values: tuple[float, ...] = Field(min_length=1)
  coordinate_unit: Literal['m', '1/m']

  @field_validator('values', mode='before')
  @classmethod
  def normalizeValues(cls, value: object) -> tuple[float, ...]:
    return normalizeFiniteSequence(value, name='spectral coordinate')
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
          f'Spectral kind {self.kind.value!r} requires coordinate unit {expected_unit!r}. '
          f'Got:{self.coordinate_unit!r}'
      )
    ####
    return self
  ####
####


class ProductReference(ContractModel):
  """Stable lineage reference to another product."""

  product_id: str = Field(min_length=1)
  capability: CapabilityId
####


class Provenance(ContractModel):
  """Provider, model, asset, and calibration provenance."""

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
  """Independent fidelity axes; deliberately not collapsed into one score."""

  morphology: str = Field(min_length=1)
  flow: str = Field(min_length=1)
  radiation: str = Field(min_length=1)
  time: str = Field(min_length=1)
  validation: str = Field(min_length=1)
####


class Applicability(ContractModel):
  """Declared product domain and extrapolation behavior."""

  minimum_time_s: float | None = None
  maximum_time_s: float | None = None
  allows_extrapolation: bool = False
  notes: tuple[str, ...] = ()

  @field_validator('minimum_time_s', 'maximum_time_s', mode='before')
  @classmethod
  def normalizeOptionalTime(cls, value: object) -> float | None:
    if value is None:
      return None
    ####
    return normalizeFiniteFloat(value, name='applicability time')
  ####

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
  """Metadata shared by every public plume product."""

  product_id: str = Field(min_length=1)
  capability: CapabilityId
  snapshot_id: str = Field(min_length=1)
  time_s: float
  frame: CoordinateFrame
  provenance: Provenance
  fidelity: Fidelity
  applicability: Applicability = Applicability()
  derived_from: tuple[ProductReference, ...] = ()
  claims: tuple[str, ...] = ()

  @field_validator('time_s', mode='before')
  @classmethod
  def validateTime(cls, value: object) -> float:
    return normalizeFiniteFloat(value, name='time_s')
  ####
####


class CompletionStatus(str, Enum):
  """Whether a batched result is complete or explicitly partial."""

  COMPLETE = 'complete'
  PARTIAL = 'partial'
####


class BatchValidity(ContractModel):
  """Validity and diagnostics for batched product values."""

  status: CompletionStatus
  valid: tuple[StrictBool, ...] = Field(min_length=1)
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
  """Axis-aligned bounds in the product coordinate frame."""

  minimum_m: Vector3
  maximum_m: Vector3

  @field_validator('minimum_m', 'maximum_m', mode='before')
  @classmethod
  def normalizeVector(cls, value: object) -> Vector3:
    vector = normalizeFiniteSequence(value, name='bounds vector')
    if len(vector) != 3:
      raise ValueError(f'Expected three vector components. Got:{len(vector)}')
    ####
    return vector  # type: ignore[return-value]
  ####

  @model_validator(mode='after')
  def validateBounds(self) -> Aabb3:
    if any(not isfinite(value) for value in (*self.minimum_m, *self.maximum_m)):
      raise ValueError('Bounds must be finite.')
    ####
    if any(maximum < minimum for minimum, maximum in zip(self.minimum_m, self.maximum_m)):
      raise ValueError('Expected every maximum bound to be >= its minimum bound.')
    ####
    return self
  ####
####


def normalizeVector3(value: object, *, name: str) -> Vector3:
  """Normalize one finite three-vector for use in field validators."""
  vector = normalizeFiniteSequence(value, name=name)
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
  """Normalize one finite rectangular matrix with an exact shape."""
  if isinstance(values, (str, bytes)):
    raise ValueError(f'Expected `{name}` to be a finite matrix.')
  ####
  try:
    matrix = tuple(normalizeFiniteSequence(row, name=name) for row in values)  # type: ignore[arg-type]
  except TypeError as exc:
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
