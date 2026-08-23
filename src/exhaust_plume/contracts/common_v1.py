"""Transport-neutral v1 contracts shared by all public plume products.

The legacy contract classes in this package remain available for compatibility.
This module is the project-neutral, versioned boundary for new consumers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from enum import Enum
from math import isfinite, sqrt
from typing import Any, Mapping, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Vector3: TypeAlias = tuple[float, float, float]
QuaternionXyzw: TypeAlias = tuple[float, float, float, float]
MatrixFloat: TypeAlias = tuple[tuple[float, ...], ...]
MatrixBool: TypeAlias = tuple[tuple[bool, ...], ...]
####


class ApiModel(BaseModel):
  """Immutable, closed DTO base used at the public interface boundary."""

  model_config = ConfigDict(extra='forbid', frozen=True)
  ####
####


class CapabilityIdentity(ApiModel):
  """A stable dotted capability name and positive major version."""

  name: str = Field(pattern=r'^[a-z][a-z0-9]*(?:\.[a-z][a-z0-9-]*)+$')
  major: int = Field(ge=1)

  @property
  def wire_id(self) -> str:
    return f'{self.name}@{self.major}'
  ####

  def __hash__(self) -> int:
    return hash((self.name, self.major))
  ####

  @classmethod
  def parse(cls, value: str) -> 'CapabilityIdentity':
    name, separator, major_text = value.rpartition('@')
    if not separator or not name or not major_text:
      raise ValueError('capability ID must contain a name and @<major>')
    try:
      major = int(major_text)
    except ValueError as error:
      raise ValueError('capability major version must be an integer') from error
    return cls(name=name, major=major)
  ####
####


class GeometryClaim(str, Enum):
  NOT_APPLICABLE = 'not_applicable'
  ILLUSTRATIVE = 'illustrative'
  PHYSICS_INFORMED = 'physics_informed'
  ENGINEERING_APPROXIMATE = 'engineering_approximate'
  CONSERVATIVE = 'conservative'
  VALIDATED = 'validated'
  ####


class RadiationClaim(str, Enum):
  NOT_APPLICABLE = 'not_applicable'
  APPEARANCE_ONLY = 'appearance_only'
  GRAY_APPROXIMATE = 'gray_approximate'
  SPECTRAL_ENGINEERING = 'spectral_engineering'
  TABULATED = 'tabulated'
  VALIDATED = 'validated'
  ####


class TimeModel(str, Enum):
  STEADY = 'steady'
  QUASI_STEADY = 'quasi_steady'
  PRESCRIBED_TRANSIENT = 'prescribed_transient'
  SOLVED_TRANSIENT = 'solved_transient'
  ####


class Derivation(str, Enum):
  NATIVE = 'native'
  ADAPTED = 'adapted'
  TABULATED = 'tabulated'
  SURROGATE = 'surrogate'
  ####


class ConsistencyLevel(str, Enum):
  INDEPENDENT = 'independent'
  CALIBRATED = 'calibrated'
  CO_GENERATED = 'co_generated'
  ####


class ApplicabilityStatus(str, Enum):
  INSIDE = 'inside'
  MARGINAL = 'marginal'
  OUTSIDE = 'outside'
  ####


class ErrorCode(str, Enum):
  UNSUPPORTED_CAPABILITY = 'unsupported_capability'
  UNSUPPORTED_MAJOR_VERSION = 'unsupported_major_version'
  INVALID_REQUEST = 'invalid_request'
  OUTSIDE_APPLICABILITY = 'outside_applicability'
  INVALID_PROVIDER_STATE = 'invalid_provider_state'
  SNAPSHOT_EXPIRED = 'snapshot_expired'
  RESOURCE_EXHAUSTED = 'resource_exhausted'
  BACKEND_FAILURE = 'backend_failure'
  CANCELLED = 'cancelled'
  ####


class SampleStatusCode(str, Enum):
  OK = 'ok'
  OUTSIDE_APPLICABILITY = 'outside_applicability'
  INVALID_SAMPLE = 'invalid_sample'
  BACKEND_FAILURE = 'backend_failure'
  ####


class SampleStatus(ApiModel):
  """Status for one direction or ray when partial evaluation is enabled."""

  code: SampleStatusCode
  message: str | None = None
  retryable: bool = False
  ####
####


class Pose(ApiModel):
  """Right-handed SI pose with quaternion components ordered ``x,y,z,w``."""

  frame_id: str = Field(min_length=1)
  translation_m: Vector3 = Field(min_length=3, max_length=3)
  rotation_xyzw: QuaternionXyzw = Field(min_length=4, max_length=4)

  @field_validator('translation_m')
  @classmethod
  def validate_translation(cls, value: Vector3) -> Vector3:
    if not all(isfinite(component) for component in value):
      raise ValueError('translation_m must contain finite values')
    return value
  ####

  @field_validator('rotation_xyzw')
  @classmethod
  def validate_rotation(cls, value: QuaternionXyzw) -> QuaternionXyzw:
    if not all(isfinite(component) for component in value):
      raise ValueError('rotation_xyzw must contain finite values')
    norm = sqrt(sum(component * component for component in value))
    if abs(norm - 1.0) > 1.0e-6:
      raise ValueError('rotation_xyzw must be unit length')
    return value
  ####
####


class ProductClaims(ApiModel):
  """Independent claim axes; no scalar fidelity label is implied."""

  geometry: GeometryClaim
  radiation: RadiationClaim
  time_model: TimeModel
  derivation: Derivation
  consistency: ConsistencyLevel
  ####
####


class ApplicabilityReport(ApiModel):
  status: ApplicabilityStatus
  reasons: tuple[str, ...] = ()
  ####
####


class ResultProvenance(ApiModel):
  """Lineage and asset identity attached to one public result."""

  model_lineage_id: str = Field(min_length=1)
  provider_id: str = Field(min_length=1)
  provider_version: str = Field(min_length=1)
  configuration_digest_sha256: str = Field(min_length=1)
  asset_digests_sha256: tuple[str, ...] = ()
  parent_result_ids: tuple[str, ...] = ()
  metadata: Mapping[str, str] = Field(default_factory=dict)

  @field_validator('metadata')
  @classmethod
  def copy_metadata(cls, value: Mapping[str, str]) -> Mapping[str, str]:
    return dict(value)
  ####
####


class ProviderDescriptor(ApiModel):
  """Provider discovery metadata independent of implementation details."""

  provider_id: str = Field(min_length=1)
  provider_version: str = Field(min_length=1)
  supported_capabilities: tuple[CapabilityIdentity, ...] = Field(min_length=1)
  provider_definition_schema_id: str = Field(min_length=1)
  dynamic_state_schema_id: str = Field(min_length=1)
  configuration_schema_id: str | None = None
  supported_morphologies: tuple[str, ...] = ()
  deterministic: bool = True
  maximum_batch_size: int | None = Field(default=None, ge=1)
  notes: tuple[str, ...] = ()

  @model_validator(mode='after')
  def validate_unique_capabilities(self) -> 'ProviderDescriptor':
    wire_ids = [capability.wire_id for capability in self.supported_capabilities]
    if len(wire_ids) != len(set(wire_ids)):
      raise ValueError('supported capabilities must be unique')
    return self
  ####
####


class SessionMetadata(ApiModel):
  session_id: str = Field(min_length=1)
  provider_id: str = Field(min_length=1)
  provider_version: str = Field(min_length=1)
  configuration_digest_sha256: str = Field(min_length=1)
  ####
####


class SnapshotMetadata(ApiModel):
  snapshot_id: str = Field(min_length=1)
  session_id: str = Field(min_length=1)
  time_s: float
  source_pose: Pose
  dynamic_state_digest_sha256: str = Field(min_length=1)
  ambient_state_digest_sha256: str = Field(min_length=1)
  provider_state_digest_sha256: str = Field(min_length=1)
  expires_at_utc: str | None = None

  @field_validator('time_s')
  @classmethod
  def validate_time(cls, value: float) -> float:
    if not isfinite(value):
      raise ValueError('time_s must be finite')
    return value
  ####
####


class ResultMetadata(ApiModel):
  capability: CapabilityIdentity
  result_id: str = Field(min_length=1)
  request_digest_sha256: str = Field(min_length=1)
  snapshot: SnapshotMetadata
  output_frame_id: str = Field(min_length=1)
  claims: ProductClaims
  applicability: ApplicabilityReport
  provenance: ResultProvenance
  warnings: tuple[str, ...] = ()
  ####
####


class ApiError(ApiModel):
  """Serializable typed error payload for in-process and adapter use."""

  code: ErrorCode
  message: str = Field(min_length=1)
  field_path: str | None = None
  details: Mapping[str, Any] = Field(default_factory=dict)
  retryable: bool = False
  provider_id: str | None = None
  snapshot_id: str | None = None

  @field_validator('details')
  @classmethod
  def copy_details(cls, value: Mapping[str, Any]) -> Mapping[str, Any]:
    return dict(value)
  ####
####


def canonical_digest(value: Any) -> str:
  """Return a deterministic SHA-256 digest for JSON-compatible contract data."""

  value = _jsonable(value)
  payload = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
  return hashlib.sha256(payload.encode('utf-8')).hexdigest()
####


def _jsonable(value: Any) -> Any:
  if isinstance(value, BaseModel):
    return _jsonable(value.model_dump(mode='python'))
  if isinstance(value, Enum):
    return value.value
  if is_dataclass(value):
    return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
  if isinstance(value, Mapping):
    return {str(key): _jsonable(item) for key, item in value.items()}
  if isinstance(value, (tuple, list)):
    return [_jsonable(item) for item in value]
  return value
####


def validate_rectangular_matrix(matrix: tuple[tuple[Any, ...], ...], field_name: str) -> tuple[int, int]:
  """Validate a non-empty rectangular matrix and return its dimensions."""

  if not matrix or not matrix[0]:
    raise ValueError(f'{field_name} must be a non-empty matrix')
  width = len(matrix[0])
  if any(len(row) != width for row in matrix):
    raise ValueError(f'{field_name} must be rectangular')
  return len(matrix), width
####


__all__ = (
  'ApiError',
  'ApiModel',
  'ApplicabilityReport',
  'ApplicabilityStatus',
  'CapabilityIdentity',
  'ConsistencyLevel',
  'Derivation',
  'ErrorCode',
  'GeometryClaim',
  'MatrixBool',
  'MatrixFloat',
  'Pose',
  'ProductClaims',
  'ProviderDescriptor',
  'QuaternionXyzw',
  'RadiationClaim',
  'ResultMetadata',
  'ResultProvenance',
  'SampleStatus',
  'SampleStatusCode',
  'SessionMetadata',
  'SnapshotMetadata',
  'TimeModel',
  'Vector3',
  'canonical_digest',
  'validate_rectangular_matrix',
)
####
