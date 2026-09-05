"""Governance checks for reduced-order shock-train calibration splits.

This operator checks that a caller's calibration/validation role assignment
matches the available case identities.  It does not fit closure parameters,
compare pressure extrema to physical cell centers, or authorize a reduced-
order shock-cell, Signature, or FPA claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Sequence

from exhaust_plume.models.shock_train.contracts import (
  ShockTrainCalibrationValidationSplit,
)

__all__ = (
  'SHOCK_TRAIN_CALIBRATION_VALIDATION_SPLIT_AUDIT_OPERATOR_ID',
  'ShockTrainCalibrationValidationSplitAuditStatus',
  'ShockTrainCalibrationValidationSplitAudit',
  'audit_shock_train_calibration_validation_split',
)


SHOCK_TRAIN_CALIBRATION_VALIDATION_SPLIT_AUDIT_OPERATOR_ID = (
  'op.reduce.shock-train-calibration-validation-split'
)


class ShockTrainCalibrationValidationSplitAuditStatus(str, Enum):
  """Outcome of the reduced-order split governance audit."""

  VERIFIED = 'verified-disjoint-shock-train-split'
  INVALID_INPUT = 'invalid-input'
  DUPLICATE_CASE_IDS = 'duplicate-case-ids'
  UNKNOWN_CASE_IDS = 'unknown-case-ids'
  UNASSIGNED_CASES = 'unassigned-available-cases'
  MISSING_SPLIT = 'missing-calibration-or-validation-cases'
####


def _normalized_case_ids(
  name: str,
  values: Sequence[str],
) -> tuple[str, ...]:
  try:
    normalized = tuple(values)
  except TypeError as error:
    raise ValueError(f'{name} must be an iterable of case IDs') from error
  ####
  if any(not isinstance(value, str) or not value for value in normalized):
    raise ValueError(f'{name} must contain nonempty strings')
  ####
  return normalized
####


def _audit(
  status: ShockTrainCalibrationValidationSplitAuditStatus,
  message: str,
  *,
  available_case_ids: Sequence[str] = (),
  calibration_case_ids: Sequence[str] = (),
  validation_case_ids: Sequence[str] = (),
  unassigned_case_ids: Sequence[str] = (),
  duplicate_case_ids: Sequence[str] = (),
  unknown_case_ids: Sequence[str] = (),
  unassigned_available_case_ids: Sequence[str] = (),
) -> 'ShockTrainCalibrationValidationSplitAudit':
  return ShockTrainCalibrationValidationSplitAudit(
    status=status,
    available_case_ids=tuple(available_case_ids),
    calibration_case_ids=tuple(calibration_case_ids),
    validation_case_ids=tuple(validation_case_ids),
    unassigned_case_ids=tuple(unassigned_case_ids),
    duplicate_case_ids=tuple(duplicate_case_ids),
    unknown_case_ids=tuple(unknown_case_ids),
    unassigned_available_case_ids=tuple(unassigned_available_case_ids),
    claim_status='not_accepted',
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class ShockTrainCalibrationValidationSplitAudit:
  """Machine-readable role and case-coverage audit below the claim gate."""

  status: ShockTrainCalibrationValidationSplitAuditStatus
  available_case_ids: tuple[str, ...] = ()
  calibration_case_ids: tuple[str, ...] = ()
  validation_case_ids: tuple[str, ...] = ()
  unassigned_case_ids: tuple[str, ...] = ()
  duplicate_case_ids: tuple[str, ...] = ()
  unknown_case_ids: tuple[str, ...] = ()
  unassigned_available_case_ids: tuple[str, ...] = ()
  claim_status: str = 'not_accepted'
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      ShockTrainCalibrationValidationSplitAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'ShockTrainCalibrationValidationSplitAuditStatus'
      )
    ####
    for name in (
      'available_case_ids',
      'calibration_case_ids',
      'validation_case_ids',
      'unassigned_case_ids',
      'duplicate_case_ids',
      'unknown_case_ids',
      'unassigned_available_case_ids',
    ):
      values = _normalized_case_ids(name, getattr(self, name))
      if name != 'available_case_ids' and len(values) != len(set(values)):
        raise ValueError(f'{name} must not contain duplicate case IDs')
      ####
      object.__setattr__(self, name, values)
    ####
    claim_status = str(self.claim_status)
    if not claim_status:
      raise ValueError('claim_status must be nonempty')
    ####
    if claim_status != 'not_accepted':
      raise ValueError(
        'shock-train split audit cannot carry an accepted product claim'
      )
    ####
    object.__setattr__(self, 'claim_status', claim_status)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def verified(self) -> bool:
    return bool(
      self.status
      is ShockTrainCalibrationValidationSplitAuditStatus.VERIFIED
    )
  ####

  @property
  def accepted(self) -> bool:
    """Return false because split governance is not physical validation."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': SHOCK_TRAIN_CALIBRATION_VALIDATION_SPLIT_AUDIT_OPERATOR_ID,
      'status': self.status.value,
      'verified': self.verified,
      'accepted': self.accepted,
      'claim_status': self.claim_status,
      'available_case_count': len(self.available_case_ids),
      'calibration_case_count': len(self.calibration_case_ids),
      'validation_case_count': len(self.validation_case_ids),
      'unassigned_case_count': len(self.unassigned_case_ids),
      'available_case_ids': list(self.available_case_ids),
      'calibration_case_ids': list(self.calibration_case_ids),
      'validation_case_ids': list(self.validation_case_ids),
      'unassigned_case_ids': list(self.unassigned_case_ids),
      'duplicate_case_ids': list(self.duplicate_case_ids),
      'unknown_case_ids': list(self.unknown_case_ids),
      'unassigned_available_case_ids': list(
        self.unassigned_available_case_ids
      ),
      'message': self.message,
    }
  ####
####


def audit_shock_train_calibration_validation_split(
  split: ShockTrainCalibrationValidationSplit,
  available_case_ids: Sequence[str],
) -> ShockTrainCalibrationValidationSplitAudit:
  """Audit disjoint role assignments against a complete case inventory.

  A verified result means only that the case-role manifest is internally
  consistent and covers the supplied inventory.  It is not evidence that the
  model was calibrated, that a holdout comparison exists, or that any cell
  length is physically identified.
  """

  if not isinstance(split, ShockTrainCalibrationValidationSplit):
    return _audit(
      ShockTrainCalibrationValidationSplitAuditStatus.INVALID_INPUT,
      'split must be a ShockTrainCalibrationValidationSplit',
    )
  ####
  try:
    available = _normalized_case_ids('available_case_ids', available_case_ids)
  except ValueError as error:
    return _audit(
      ShockTrainCalibrationValidationSplitAuditStatus.INVALID_INPUT,
      str(error),
    )
  ####
  duplicate_case_ids = tuple(
    sorted({case_id for case_id in available if available.count(case_id) > 1})
  )
  if duplicate_case_ids:
    return _audit(
      ShockTrainCalibrationValidationSplitAuditStatus.DUPLICATE_CASE_IDS,
      'available case identities must be unique before split audit',
      available_case_ids=available,
      calibration_case_ids=split.calibration_case_ids,
      validation_case_ids=split.validation_case_ids,
      unassigned_case_ids=split.unassigned_case_ids,
      duplicate_case_ids=duplicate_case_ids,
    )
  ####
  available_set = set(available)
  assigned = set(split.calibration_case_ids) | set(split.validation_case_ids)
  declared = assigned | set(split.unassigned_case_ids)
  unknown_case_ids = tuple(sorted(declared - available_set))
  if unknown_case_ids:
    return _audit(
      ShockTrainCalibrationValidationSplitAuditStatus.UNKNOWN_CASE_IDS,
      'split references case identities absent from the available inventory',
      available_case_ids=available,
      calibration_case_ids=split.calibration_case_ids,
      validation_case_ids=split.validation_case_ids,
      unassigned_case_ids=split.unassigned_case_ids,
      unknown_case_ids=unknown_case_ids,
    )
  ####
  unassigned_available_case_ids = tuple(sorted(available_set - declared))
  if unassigned_available_case_ids:
    return _audit(
      ShockTrainCalibrationValidationSplitAuditStatus.UNASSIGNED_CASES,
      'available case identities must have an explicit calibration, validation, '
      'or unassigned role',
      available_case_ids=available,
      calibration_case_ids=split.calibration_case_ids,
      validation_case_ids=split.validation_case_ids,
      unassigned_case_ids=split.unassigned_case_ids,
      unassigned_available_case_ids=unassigned_available_case_ids,
    )
  ####
  if not split.accepted:
    return _audit(
      ShockTrainCalibrationValidationSplitAuditStatus.MISSING_SPLIT,
      'at least one calibration and one validation case are required; '
      'unassigned cases remain visible and cannot serve both roles',
      available_case_ids=available,
      calibration_case_ids=split.calibration_case_ids,
      validation_case_ids=split.validation_case_ids,
      unassigned_case_ids=split.unassigned_case_ids,
    )
  ####
  return _audit(
    ShockTrainCalibrationValidationSplitAuditStatus.VERIFIED,
    'case-role manifest is disjoint and covers the available inventory; '
    'calibration fitting and physical shock-cell acceptance remain separate',
    available_case_ids=available,
    calibration_case_ids=split.calibration_case_ids,
    validation_case_ids=split.validation_case_ids,
    unassigned_case_ids=split.unassigned_case_ids,
  )
####
