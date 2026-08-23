"""Structured public errors for plume-provider and product operations."""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import UUID


class PlumeErrorCode(str, Enum):
  CAPABILITY_NOT_SUPPORTED = 'CAPABILITY_NOT_SUPPORTED'
  SCHEMA_VERSION_NOT_SUPPORTED = 'SCHEMA_VERSION_NOT_SUPPORTED'
  INVALID_REQUEST = 'INVALID_REQUEST'
  INVALID_FRAME = 'INVALID_FRAME'
  INVALID_UNITS = 'INVALID_UNITS'
  TIME_OUT_OF_RANGE = 'TIME_OUT_OF_RANGE'
  EXTRAPOLATION_FORBIDDEN = 'EXTRAPOLATION_FORBIDDEN'
  OUT_OF_DOMAIN = 'OUT_OF_DOMAIN'
  APPLICABILITY_VIOLATION = 'APPLICABILITY_VIOLATION'
  NONPHYSICAL_STATE = 'NONPHYSICAL_STATE'
  NUMERICAL_FAILURE = 'NUMERICAL_FAILURE'
  RESOURCE_LIMIT = 'RESOURCE_LIMIT'
  INTERNAL_ERROR = 'INTERNAL_ERROR'
####


class PlumeApiError(RuntimeError):
  """Exception carrying a stable public error code and structured context."""

  def __init__(
      self,
      code: PlumeErrorCode,
      message: str,
      *,
      details: dict[str, Any] | None = None,
      provider_id: UUID | None = None,
      session_id: UUID | None = None,
      snapshot_id: UUID | None = None,
  ) -> None:
    super().__init__(message)
    self.code = code
    self.message = message
    self.details = {} if details is None else dict(details)
    self.provider_id = provider_id
    self.session_id = session_id
    self.snapshot_id = snapshot_id
  ####

  def as_dict(self) -> dict[str, Any]:
    return {
        'code': self.code.value,
        'message': self.message,
        'details': self.details,
        'provider_id': None if self.provider_id is None else str(self.provider_id),
        'session_id': None if self.session_id is None else str(self.session_id),
        'snapshot_id': None if self.snapshot_id is None else str(self.snapshot_id),
    }
  ####
####
