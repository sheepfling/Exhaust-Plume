"""Non-promoting external comparisons for the downstream FPA lane.

The focal-plane array is a deterministic downstream operator, not a fifth
plume provider.  This module defines the evidence boundary for a future
measured detector frame: the owner must declare the exact measurement space,
pixel grid, units, source lineage, split role, and uncertainty.  Comparisons
are shape-exact and pixel-index exact; they do not resample, fit, interpolate,
or manufacture missing detector data.  A passing comparison remains external
evidence and never authorizes an FPA production claim by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import fsum, isfinite, sqrt
from typing import Any, Mapping, Sequence, TypeAlias

from exhaust_plume.contracts.common_v1 import canonical_digest
from exhaust_plume.validation.fpa_operators import (
  FPA_DIGITIZATION_OPERATOR_ID,
  FPA_PIXEL_DETECTOR_OPERATOR_ID,
  FpaDigitizedExpectation,
  FpaPixelImage,
)
from exhaust_plume.validation.fpa_visualization import (
  FpaSourceAdmissionDecision,
  FpaSourceReference,
  evaluate_fpa_source_admission,
)


__all__ = (
  'FPA_EXTERNAL_COMPARISON_OPERATOR_ID',
  'FPA_EXTERNAL_PROMOTION_REVIEW_OPERATOR_ID',
  'FPA_EXTERNAL_EVIDENCE_ATTESTATIONS',
  'FpaExternalValidationRole',
  'FpaExternalEvidenceOrigin',
  'FpaExternalEvidenceAttestation',
  'FpaExternalMeasurementSpace',
  'FpaExternalComparisonStatus',
  'FpaExternalSplitAuditStatus',
  'FpaExternalPromotionReviewStatus',
  'FpaExternalModelCase',
  'FpaExternalDataset',
  'FpaExternalPromotionPolicy',
  'FpaExternalPixelComparison',
  'FpaExternalComparison',
  'FpaExternalSplitAudit',
  'FpaExternalPromotionReview',
  'audit_fpa_external_validation_splits',
  'compare_fpa_to_external',
  'review_fpa_external_promotion',
  'verify_fpa_external_evidence_attestation',
)


FPA_EXTERNAL_COMPARISON_OPERATOR_ID = 'op.sensor.fpa-external-comparison'
FPA_EXTERNAL_PROMOTION_REVIEW_OPERATOR_ID = (
  'op.sensor.fpa-external-promotion-review'
)
FPA_RAY_TRANSFER_CAPABILITY_ID = 'plume.optical.spectral-ray-transfer@1'
FPA_PIXEL_INDEXING = 'row-major-zero-based'

FloatMatrix: TypeAlias = tuple[tuple[float, ...], ...]


class FpaExternalValidationRole(str, Enum):
  """Role of one owner-supplied detector case."""

  CALIBRATION = 'calibration'
  VALIDATION = 'validation'
####


class FpaExternalEvidenceOrigin(str, Enum):
  """Declared origin class for detector observations."""

  SYNTHETIC_FIXTURE = 'synthetic-fixture'
  MEASURED_EXTERNAL = 'measured-external'
####


class FpaExternalMeasurementSpace(str, Enum):
  """Detector quantity represented by an owner-supplied frame."""

  EXPECTED_ELECTRONS = 'expected_electrons'
  DIGITIZED_COUNTS = 'digitized_counts'
####


class FpaExternalComparisonStatus(str, Enum):
  """Outcome of one exact external pixel comparison."""

  FULL_DOMAIN_COMPUTED = 'full-domain-computed'
  BLOCKED_MODEL = 'blocked-model-measurement'
  BLOCKED_SOURCE_LINEAGE = 'blocked-source-lineage'
  BLOCKED_OPERATOR_IDENTITY = 'blocked-measurement-operator-identity'
  BLOCKED_PIXEL_GRID = 'blocked-pixel-grid'
####


class FpaExternalSplitAuditStatus(str, Enum):
  """Outcome of the calibration/validation split audit."""

  VERIFIED = 'split-verified'
  INVALID_INPUT = 'invalid-input'
  MISSING_SPLIT = 'blocked-missing-split'
  DUPLICATE_DATASET = 'blocked-duplicate-dataset'
  CASE_OVERLAP = 'blocked-case-overlap'
####


class FpaExternalPromotionReviewStatus(str, Enum):
  """Outcome of an explicit external-evidence review."""

  EXTERNAL_EVIDENCE_VERIFIED = 'external-evidence-verified'
  INVALID_INPUT = 'invalid-input'
  BLOCKED_MISSING_DATA = 'blocked-missing-external-data'
  BLOCKED_SPLIT_AUDIT = 'blocked-external-split-audit'
  BLOCKED_MODEL = 'blocked-model-measurement'
  BLOCKED_MEASUREMENT_SPACE = 'blocked-measurement-space'
  BLOCKED_COVERAGE = 'blocked-external-coverage'
  BLOCKED_SOURCE_LINEAGE = 'blocked-source-lineage'
  BLOCKED_OPERATOR_IDENTITY = 'blocked-measurement-operator-identity'
  BLOCKED_PIXEL_GRID = 'blocked-pixel-grid'
  BLOCKED_TOLERANCE = 'blocked-tolerance-configuration'
  BLOCKED_RESIDUAL = 'blocked-external-residual'
  BLOCKED_EVIDENCE_ORIGIN = 'blocked-non-measured-evidence'
  BLOCKED_EVIDENCE_ATTESTATION = 'blocked-unattested-evidence'
  BLOCKED_SOURCE_ADMISSION = 'blocked-source-admission'
####


def _text(name: str, value: str) -> str:
  if not isinstance(value, str) or not value.strip():
    raise ValueError(f'{name} must be a non-empty string')
  ####
  return value.strip()
####


def _positive_dimension(value: int, name: str) -> int:
  if isinstance(value, bool) or not isinstance(value, int) or value < 1:
    raise ValueError(f'{name} must be a positive integer')
  ####
  return value
####


def _matrix(
  values: Sequence[Sequence[float]],
  *,
  width_px: int,
  height_px: int,
  field_name: str,
  minimum: float = 0.0,
) -> FloatMatrix:
  try:
    raw_matrix = tuple(tuple(row) for row in values)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{field_name} must contain numeric values') from error
  ####
  if any(isinstance(value, bool) for row in raw_matrix for value in row):
    raise ValueError(f'{field_name} must contain numeric values, not booleans')
  ####
  try:
    matrix = tuple(tuple(float(value) for value in row) for row in raw_matrix)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{field_name} must contain numeric values') from error
  ####
  if len(matrix) != height_px or any(len(row) != width_px for row in matrix):
    raise ValueError(f'{field_name} must have shape ({height_px}, {width_px})')
  ####
  if any(
      not isfinite(value) or value < minimum
      for row in matrix
      for value in row
  ):
    raise ValueError(
      f'{field_name} must contain finite values >= {minimum:g}'
    )
  ####
  return matrix
####


def _optional_matrix(
  values: Sequence[Sequence[float]] | None,
  *,
  width_px: int,
  height_px: int,
  field_name: str,
) -> FloatMatrix | None:
  if values is None:
    return None
  ####
  return _matrix(
    values,
    width_px=width_px,
    height_px=height_px,
    field_name=field_name,
  )
####


def _hash_or_none(name: str, value: str | None) -> str | None:
  if value is None:
    return None
  ####
  if not isinstance(value, str) or len(value) != 64 or any(
      character not in '0123456789abcdef' for character in value
  ):
    raise ValueError(f'{name} must be a lowercase SHA-256 digest when supplied')
  ####
  return value
####


@dataclass(frozen=True, slots=True)
class FpaExternalEvidenceAttestation:
  """Reviewed binding from one measured dataset to its source package."""

  dataset_id: str
  case_id: str
  evidence_record_id: str
  evidence_package_sha256: str
  dataset_content_sha256: str

  def __post_init__(self) -> None:
    for name in ('dataset_id', 'case_id', 'evidence_record_id'):
      object.__setattr__(self, name, _text(name, getattr(self, name)))
    ####
    for name in ('evidence_package_sha256', 'dataset_content_sha256'):
      digest = _hash_or_none(name, getattr(self, name))
      if digest is None:
        raise ValueError(f'{name} is required')
      ####
    ####
  ####
####


# The registry is intentionally empty until a measured archive and its
# provenance, rights, coordinate/frame semantics, and dataset digests have
# been independently reviewed. A dataset cannot attest itself by declaration.
FPA_EXTERNAL_EVIDENCE_ATTESTATIONS: tuple[FpaExternalEvidenceAttestation, ...] = ()


@dataclass(frozen=True, slots=True)
class FpaExternalModelCase:
  """Typed deterministic FPA output and the upstream source identity."""

  image: FpaPixelImage
  source: FpaSourceReference
  digitized: FpaDigitizedExpectation | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.image, FpaPixelImage):
      raise TypeError('image must be an FpaPixelImage')
    ####
    if not isinstance(self.source, FpaSourceReference):
      raise TypeError('source must be an FpaSourceReference')
    ####
    if self.source.capability_id != FPA_RAY_TRANSFER_CAPABILITY_ID:
      raise ValueError(
        'source must identify the spectral ray-transfer capability'
      )
    ####
    self.source.validate_for_fpa()
    if self.image.source_binding is None:
      raise ValueError('external comparison requires an image bound to its exact ray source')
    ####
    if self.image.source_binding != self.source.ray_source_binding:
      raise ValueError('image source binding must match the FPA source reference')
    ####
    if self.image.operator_id != FPA_PIXEL_DETECTOR_OPERATOR_ID:
      raise ValueError(
        'image must be produced by the FPA pixel detector operator'
      )
    ####
    if self.digitized is not None:
      if not isinstance(self.digitized, FpaDigitizedExpectation):
        raise TypeError('digitized must be an FpaDigitizedExpectation or None')
      ####
      if (
          self.digitized.operator_id != FPA_DIGITIZATION_OPERATOR_ID
          or self.digitized.source_operator_id != self.image.operator_id
          or self.digitized.width_px != self.image.width_px
          or self.digitized.height_px != self.image.height_px
          or self.digitized.validity_mask != self.image.validity_mask
          or self.digitized.camera_optics_id != self.image.camera_optics_id
          or self.digitized.camera_mapping_model_id != self.image.camera_mapping_model_id
      ):
        raise ValueError(
          'digitized output must preserve image shape, mask, and operator lineage'
        )
      ####
    ####
  ####


@dataclass(frozen=True, slots=True)
class FpaExternalDataset:
  """One owner-supplied, exact-grid detector measurement.

  When supplied, uncertainty is a per-pixel standard uncertainty. A weighted
  residual is available only when every pixel has a strictly positive value.
  """

  dataset_id: str
  case_id: str
  split: FpaExternalValidationRole
  measurement_space: FpaExternalMeasurementSpace
  width_px: int
  height_px: int
  values: Sequence[Sequence[float]]
  pixel_grid_id: str
  source_snapshot_id: str
  source_frame_id: str
  source_content_sha256: str | None
  measurement_operator_sha256: str
  source: str
  provenance: str
  uncertainty: Sequence[Sequence[float]] | None = None
  digitization_policy_sha256: str | None = None
  evidence_origin: FpaExternalEvidenceOrigin = (
    FpaExternalEvidenceOrigin.SYNTHETIC_FIXTURE
  )
  evidence_record_id: str | None = None
  evidence_package_sha256: str | None = None
  units: str = 'electrons'
  source_capability_id: str = FPA_RAY_TRANSFER_CAPABILITY_ID
  pixel_indexing: str = FPA_PIXEL_INDEXING

  def __post_init__(self) -> None:
    for name in (
      'dataset_id',
      'case_id',
      'pixel_grid_id',
      'source_snapshot_id',
      'source_frame_id',
      'source',
      'provenance',
    ):
      object.__setattr__(self, name, _text(name, getattr(self, name)))
    ####
    if not isinstance(self.split, FpaExternalValidationRole):
      raise TypeError('split must be an FpaExternalValidationRole')
    ####
    if not isinstance(self.measurement_space, FpaExternalMeasurementSpace):
      raise TypeError(
        'measurement_space must be an FpaExternalMeasurementSpace'
      )
    ####
    if not isinstance(self.evidence_origin, FpaExternalEvidenceOrigin):
      raise TypeError('evidence_origin must be an FpaExternalEvidenceOrigin')
    ####
    if self.evidence_record_id is not None:
      object.__setattr__(
        self,
        'evidence_record_id',
        _text('evidence_record_id', self.evidence_record_id),
      )
    ####
    object.__setattr__(
      self,
      'evidence_package_sha256',
      _hash_or_none('evidence_package_sha256', self.evidence_package_sha256),
    )
    if self.evidence_origin is FpaExternalEvidenceOrigin.MEASURED_EXTERNAL and (
        self.evidence_record_id is None or self.evidence_package_sha256 is None
    ):
      raise ValueError(
        'measured external data requires an evidence record ID and package SHA-256'
      )
    ####
    width = _positive_dimension(self.width_px, 'width_px')
    height = _positive_dimension(self.height_px, 'height_px')
    ####
    expected_units = (
      'electrons'
      if self.measurement_space is FpaExternalMeasurementSpace.EXPECTED_ELECTRONS
      else 'count'
    )
    if self.units != expected_units:
      raise ValueError(
        f'units must be {expected_units!r} for {self.measurement_space.value}'
      )
    ####
    if self.source_capability_id != FPA_RAY_TRANSFER_CAPABILITY_ID:
      raise ValueError(
        'source_capability_id must identify the spectral ray-transfer capability'
      )
    ####
    if self.pixel_indexing != FPA_PIXEL_INDEXING:
      raise ValueError(
        f'pixel_indexing must be {FPA_PIXEL_INDEXING!r}; no coordinate conversion is performed'
      )
    ####
    object.__setattr__(
      self,
      'source_content_sha256',
      _hash_or_none('source_content_sha256', self.source_content_sha256),
    )
    operator_digest = _hash_or_none(
      'measurement_operator_sha256',
      self.measurement_operator_sha256,
    )
    if operator_digest is None:
      raise ValueError('measurement_operator_sha256 is required')
    object.__setattr__(self, 'measurement_operator_sha256', operator_digest)
    digitization_digest = _hash_or_none(
      'digitization_policy_sha256',
      self.digitization_policy_sha256,
    )
    if (
        self.measurement_space is FpaExternalMeasurementSpace.DIGITIZED_COUNTS
        and digitization_digest is None
    ):
      raise ValueError('digitized-count evidence requires a digitization policy digest')
    if (
        self.measurement_space is FpaExternalMeasurementSpace.EXPECTED_ELECTRONS
        and digitization_digest is not None
    ):
      raise ValueError('expected-electron evidence cannot declare a digitization policy')
    object.__setattr__(self, 'digitization_policy_sha256', digitization_digest)
    object.__setattr__(
      self,
      'width_px',
      width,
    )
    object.__setattr__(self, 'height_px', height)
    object.__setattr__(
      self,
      'values',
      _matrix(
        self.values,
        width_px=width,
        height_px=height,
        field_name='values',
      ),
    )
    object.__setattr__(
      self,
      'uncertainty',
      _optional_matrix(
        self.uncertainty,
        width_px=width,
        height_px=height,
        field_name='uncertainty',
      ),
    )
  ####

  def as_report(self) -> dict[str, Any]:
    flat_values = tuple(value for row in self.values for value in row)
    return {
      'dataset_id': self.dataset_id,
      'case_id': self.case_id,
      'split': self.split.value,
      'evidence_origin': self.evidence_origin.value,
      'evidence_record_id': self.evidence_record_id,
      'evidence_package_sha256': self.evidence_package_sha256,
      'dataset_content_sha256': self.evidence_content_sha256,
      'measurement_space': self.measurement_space.value,
      'units': self.units,
      'shape': {'height_px': self.height_px, 'width_px': self.width_px},
      'pixel_grid_id': self.pixel_grid_id,
      'pixel_indexing': self.pixel_indexing,
      'measurement_operator_sha256': self.measurement_operator_sha256,
      'digitization_policy_sha256': self.digitization_policy_sha256,
      'source_capability_id': self.source_capability_id,
      'source_snapshot_id': self.source_snapshot_id,
      'source_frame_id': self.source_frame_id,
      'source_content_sha256': self.source_content_sha256,
      'source': self.source,
      'provenance': self.provenance,
      'uncertainty_supplied': self.uncertainty is not None,
      'value_min': min(flat_values),
      'value_max': max(flat_values),
    }
  ####

  @property
  def evidence_content_sha256(self) -> str:
    """Digest the exact measured values and lineage used for acceptance."""

    return canonical_digest({
      'dataset_id': self.dataset_id,
      'case_id': self.case_id,
      'split': self.split.value,
      'measurement_space': self.measurement_space.value,
      'width_px': self.width_px,
      'height_px': self.height_px,
      'values': self.values,
      'uncertainty': self.uncertainty,
      'units': self.units,
      'pixel_grid_id': self.pixel_grid_id,
      'pixel_indexing': self.pixel_indexing,
      'measurement_operator_sha256': self.measurement_operator_sha256,
      'digitization_policy_sha256': self.digitization_policy_sha256,
      'source_capability_id': self.source_capability_id,
      'source_snapshot_id': self.source_snapshot_id,
      'source_frame_id': self.source_frame_id,
      'source_content_sha256': self.source_content_sha256,
      'source': self.source,
      'provenance': self.provenance,
      'evidence_origin': self.evidence_origin.value,
      'evidence_record_id': self.evidence_record_id,
      'evidence_package_sha256': self.evidence_package_sha256,
    })
  ####
####


def verify_fpa_external_evidence_attestation(
  dataset: FpaExternalDataset,
) -> bool:
  """Check measured data against the source-controlled evidence registry."""

  if not isinstance(dataset, FpaExternalDataset):
    raise TypeError('dataset must be an FpaExternalDataset')
  ####
  if (
      dataset.evidence_origin is not FpaExternalEvidenceOrigin.MEASURED_EXTERNAL
      or dataset.evidence_record_id is None
      or dataset.evidence_package_sha256 is None
  ):
    return False
  ####
  return any(
    attestation.dataset_id == dataset.dataset_id
    and attestation.case_id == dataset.case_id
    and attestation.evidence_record_id == dataset.evidence_record_id
    and attestation.evidence_package_sha256 == dataset.evidence_package_sha256
    and attestation.dataset_content_sha256 == dataset.evidence_content_sha256
    for attestation in FPA_EXTERNAL_EVIDENCE_ATTESTATIONS
  )
####


@dataclass(frozen=True, slots=True)
class FpaExternalPromotionPolicy:
  """Owner-declared residual rules; no tolerance is inferred."""

  required_measurement_space: FpaExternalMeasurementSpace = (
    FpaExternalMeasurementSpace.EXPECTED_ELECTRONS
  )
  maximum_rmse: float | None = None
  minimum_valid_pixel_fraction: float = 1.0
  maximum_uncertainty_weighted_rmse: float | None = None

  def __post_init__(self) -> None:
    if not isinstance(
        self.required_measurement_space,
        FpaExternalMeasurementSpace,
    ):
      raise TypeError(
        'required_measurement_space must be an FpaExternalMeasurementSpace'
      )
    ####
    for name in ('maximum_rmse', 'maximum_uncertainty_weighted_rmse'):
      value = getattr(self, name)
      if value is not None:
        if isinstance(value, bool):
          raise ValueError(f'{name} must be numeric, not boolean')
        ####
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, normalized)
      ####
    ####
    if isinstance(self.minimum_valid_pixel_fraction, bool):
      raise ValueError('minimum_valid_pixel_fraction must be numeric, not boolean')
    ####
    fraction = float(self.minimum_valid_pixel_fraction)
    if not isfinite(fraction) or not 0.0 < fraction <= 1.0:
      raise ValueError('minimum_valid_pixel_fraction must be in (0, 1]')
    ####
    object.__setattr__(self, 'minimum_valid_pixel_fraction', fraction)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'required_measurement_space': self.required_measurement_space.value,
      'maximum_rmse': self.maximum_rmse,
      'minimum_valid_pixel_fraction': self.minimum_valid_pixel_fraction,
      'maximum_uncertainty_weighted_rmse': self.maximum_uncertainty_weighted_rmse,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class FpaExternalPixelComparison:
  """Exact-grid residuals for one detector quantity."""

  measurement_space: FpaExternalMeasurementSpace
  residuals: FloatMatrix
  valid_pixel_count: int
  pixel_count: int
  rmse: float
  max_abs_residual: float
  uncertainty_weighted_rmse: float | None

  @property
  def valid_pixel_fraction(self) -> float:
    return self.valid_pixel_count / self.pixel_count if self.pixel_count else 0.0
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'measurement_space': self.measurement_space.value,
      'residuals': [list(row) for row in self.residuals],
      'valid_pixel_count': self.valid_pixel_count,
      'pixel_count': self.pixel_count,
      'valid_pixel_fraction': self.valid_pixel_fraction,
      'rmse': self.rmse,
      'max_abs_residual': self.max_abs_residual,
      'uncertainty_weighted_rmse': self.uncertainty_weighted_rmse,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class FpaExternalComparison:
  """Non-accepting exact-grid comparison between one model case and dataset."""

  status: FpaExternalComparisonStatus
  operator_id: str
  dataset_id: str
  case_id: str
  split: FpaExternalValidationRole
  measurement_space: FpaExternalMeasurementSpace
  model_width_px: int
  model_height_px: int
  observed_width_px: int
  observed_height_px: int
  model_pixel_grid_id: str | None
  observed_pixel_grid_id: str
  pixel_comparison: FpaExternalPixelComparison | None
  claim_status: str
  reason: str
  model_measurement_operator_sha256: str | None = None
  observed_measurement_operator_sha256: str | None = None
  model_digitization_policy_sha256: str | None = None
  observed_digitization_policy_sha256: str | None = None

  @property
  def computed(self) -> bool:
    return self.pixel_comparison is not None
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'dataset_id': self.dataset_id,
      'case_id': self.case_id,
      'split': self.split.value,
      'measurement_space': self.measurement_space.value,
      'model_shape': {
        'height_px': self.model_height_px,
        'width_px': self.model_width_px,
      },
      'observed_shape': {
        'height_px': self.observed_height_px,
        'width_px': self.observed_width_px,
      },
      'model_pixel_grid_id': self.model_pixel_grid_id,
      'observed_pixel_grid_id': self.observed_pixel_grid_id,
      'model_measurement_operator_sha256': self.model_measurement_operator_sha256,
      'observed_measurement_operator_sha256': self.observed_measurement_operator_sha256,
      'model_digitization_policy_sha256': self.model_digitization_policy_sha256,
      'observed_digitization_policy_sha256': self.observed_digitization_policy_sha256,
      'pixel_comparison': (
        None if self.pixel_comparison is None
        else self.pixel_comparison.as_report()
      ),
      'claim_status': self.claim_status,
      'reason': self.reason,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class FpaExternalSplitAudit:
  """Audit proving calibration and validation cases are disjoint."""

  status: FpaExternalSplitAuditStatus
  dataset_count: int
  calibration_case_ids: tuple[str, ...]
  validation_case_ids: tuple[str, ...]
  duplicate_dataset_ids: tuple[str, ...]
  overlapping_case_ids: tuple[str, ...]
  claim_status: str
  message: str

  @property
  def verified(self) -> bool:
    return self.status is FpaExternalSplitAuditStatus.VERIFIED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'dataset_count': self.dataset_count,
      'calibration_case_ids': list(self.calibration_case_ids),
      'validation_case_ids': list(self.validation_case_ids),
      'duplicate_dataset_ids': list(self.duplicate_dataset_ids),
      'overlapping_case_ids': list(self.overlapping_case_ids),
      'verified': self.verified,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class FpaExternalPromotionReview:
  """External-evidence review that never authorizes an FPA production claim."""

  status: FpaExternalPromotionReviewStatus
  operator_id: str
  model_case_count: int
  dataset_count: int
  policy: FpaExternalPromotionPolicy
  split_audit: FpaExternalSplitAudit
  comparisons: tuple[FpaExternalComparison, ...] = ()
  source_admission_decisions: tuple[
    tuple[str, FpaSourceAdmissionDecision], ...
  ] = ()
  failed_dataset_ids: tuple[str, ...] = ()
  residual_failures: tuple[str, ...] = ()
  external_validation_verified: bool = False
  production_claim_allowed: bool = False
  claim_status: str = 'not_accepted'
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is FpaExternalPromotionReviewStatus.EXTERNAL_EVIDENCE_VERIFIED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'model_case_count': self.model_case_count,
      'dataset_count': self.dataset_count,
      'policy': self.policy.as_report(),
      'split_audit': self.split_audit.as_report(),
      'comparisons': [comparison.as_report() for comparison in self.comparisons],
      'source_admission_decisions': [
        {'case_id': case_id, **decision.as_report()}
        for case_id, decision in self.source_admission_decisions
      ],
      'failed_dataset_ids': list(self.failed_dataset_ids),
      'residual_failures': list(self.residual_failures),
      'external_validation_verified': self.external_validation_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####
####


def _split_result(
  status: FpaExternalSplitAuditStatus,
  message: str,
  datasets: Sequence[FpaExternalDataset] = (),
  *,
  duplicate_dataset_ids: Sequence[str] = (),
  overlapping_case_ids: Sequence[str] = (),
) -> FpaExternalSplitAudit:
  items = tuple(datasets)
  return FpaExternalSplitAudit(
    status=status,
    dataset_count=len(items),
    calibration_case_ids=tuple(
      dataset.case_id
      for dataset in items
      if dataset.split is FpaExternalValidationRole.CALIBRATION
    ),
    validation_case_ids=tuple(
      dataset.case_id
      for dataset in items
      if dataset.split is FpaExternalValidationRole.VALIDATION
    ),
    duplicate_dataset_ids=tuple(duplicate_dataset_ids),
    overlapping_case_ids=tuple(overlapping_case_ids),
    claim_status='not_accepted',
    message=message,
  )
####


def audit_fpa_external_validation_splits(
  datasets: Sequence[FpaExternalDataset],
) -> FpaExternalSplitAudit:
  """Require disjoint calibration and validation detector cases."""

  try:
    items = tuple(datasets)
  except TypeError:
    return _split_result(
      FpaExternalSplitAuditStatus.INVALID_INPUT,
      'datasets must be an iterable of FpaExternalDataset values',
    )
  ####
  if any(not isinstance(dataset, FpaExternalDataset) for dataset in items):
    return _split_result(
      FpaExternalSplitAuditStatus.INVALID_INPUT,
      'datasets must contain FpaExternalDataset values',
    )
  ####
  dataset_ids = tuple(dataset.dataset_id for dataset in items)
  duplicate_dataset_ids = tuple(sorted({
    dataset_id for dataset_id in dataset_ids if dataset_ids.count(dataset_id) > 1
  }))
  if duplicate_dataset_ids:
    return _split_result(
      FpaExternalSplitAuditStatus.DUPLICATE_DATASET,
      'dataset identities must be unique before the split can be audited',
      items,
      duplicate_dataset_ids=duplicate_dataset_ids,
    )
  ####
  calibration_ids = {
    dataset.case_id
    for dataset in items
    if dataset.split is FpaExternalValidationRole.CALIBRATION
  }
  validation_ids = {
    dataset.case_id
    for dataset in items
    if dataset.split is FpaExternalValidationRole.VALIDATION
  }
  if not calibration_ids or not validation_ids:
    return _split_result(
      FpaExternalSplitAuditStatus.MISSING_SPLIT,
      'at least one calibration dataset and one validation dataset are required',
      items,
    )
  ####
  overlapping_case_ids = tuple(sorted(calibration_ids & validation_ids))
  if overlapping_case_ids:
    return _split_result(
      FpaExternalSplitAuditStatus.CASE_OVERLAP,
      'case identities must not appear in both calibration and validation splits',
      items,
      overlapping_case_ids=overlapping_case_ids,
    )
  ####
  return _split_result(
    FpaExternalSplitAuditStatus.VERIFIED,
    'calibration and validation detector case identities are disjoint; '
    'operator comparison and product acceptance remain separate gates',
    items,
  )
####


def _model_values(
  model: FpaExternalModelCase,
  measurement_space: FpaExternalMeasurementSpace,
) -> FloatMatrix | None:
  if measurement_space is FpaExternalMeasurementSpace.EXPECTED_ELECTRONS:
    return model.image.expected_electrons
  ####
  if model.digitized is None:
    return None
  ####
  return tuple(
    tuple(float(value) for value in row)
    for row in model.digitized.counts
  )
####


def _empty_comparison(
  model: FpaExternalModelCase,
  dataset: FpaExternalDataset,
  *,
  status: FpaExternalComparisonStatus,
  reason: str,
) -> FpaExternalComparison:
  return FpaExternalComparison(
    status=status,
    operator_id=FPA_EXTERNAL_COMPARISON_OPERATOR_ID,
    dataset_id=dataset.dataset_id,
    case_id=dataset.case_id,
    split=dataset.split,
    measurement_space=dataset.measurement_space,
    model_width_px=model.image.width_px,
    model_height_px=model.image.height_px,
    observed_width_px=dataset.width_px,
    observed_height_px=dataset.height_px,
    model_pixel_grid_id=model.image.camera_mapping_model_id,
    observed_pixel_grid_id=dataset.pixel_grid_id,
    pixel_comparison=None,
    claim_status='not_accepted',
    reason=reason,
    model_measurement_operator_sha256=model.image.measurement_operator_sha256,
    observed_measurement_operator_sha256=dataset.measurement_operator_sha256,
    model_digitization_policy_sha256=(
      None
      if model.digitized is None
      else model.digitized.digitization_policy_sha256
    ),
    observed_digitization_policy_sha256=dataset.digitization_policy_sha256,
  )
####


def compare_fpa_to_external(
  model: FpaExternalModelCase,
  dataset: FpaExternalDataset,
) -> FpaExternalComparison:
  """Compare one deterministic FPA result to one exact external frame.

  The comparison requires exact source snapshot/frame/content identity and an
  exact camera mapping identifier.  It intentionally has no interpolation,
  resampling, fitting, or missing-pixel path.
  """

  if not isinstance(model, FpaExternalModelCase):
    raise TypeError('model must be an FpaExternalModelCase')
  ####
  if not isinstance(dataset, FpaExternalDataset):
    raise TypeError('dataset must be an FpaExternalDataset')
  ####
  model_values = _model_values(model, dataset.measurement_space)
  if model_values is None:
    return _empty_comparison(
      model,
      dataset,
      status=FpaExternalComparisonStatus.BLOCKED_MODEL,
      reason=(
        'digitized-count comparison requires a typed deterministic ADC output; '
        'no counts are inferred from expected electrons'
      ),
    )
  ####
  if (
      dataset.source_capability_id != model.source.capability_id
      or dataset.source_snapshot_id != model.source.snapshot_id
      or dataset.source_frame_id != model.source.frame_id
      or dataset.source_content_sha256 != model.source.content_sha256
  ):
    return _empty_comparison(
      model,
      dataset,
      status=FpaExternalComparisonStatus.BLOCKED_SOURCE_LINEAGE,
      reason=(
        'external data must bind to the exact ray-transfer capability, snapshot, '
        'frame, and source-result SHA-256; no lineage is inferred'
      ),
    )
  ####
  model_digitization_digest = (
    None
    if model.digitized is None
    else model.digitized.digitization_policy_sha256
  )
  if (
      model.image.measurement_operator_sha256 is None
      or dataset.measurement_operator_sha256
      != model.image.measurement_operator_sha256
      or (
        dataset.measurement_space is FpaExternalMeasurementSpace.DIGITIZED_COUNTS
        and (
          model_digitization_digest is None
          or dataset.digitization_policy_sha256 != model_digitization_digest
        )
      )
      or (
        dataset.measurement_space is FpaExternalMeasurementSpace.EXPECTED_ELECTRONS
        and dataset.digitization_policy_sha256 is not None
      )
  ):
    return _empty_comparison(
      model,
      dataset,
      status=FpaExternalComparisonStatus.BLOCKED_OPERATOR_IDENTITY,
      reason=(
        'external data must bind the exact camera, pixel geometry, detector, '
        'wavelength, exposure, and applicable digitization operator digests'
      ),
    )
  ####
  if (
      dataset.width_px != model.image.width_px
      or dataset.height_px != model.image.height_px
      or model.image.camera_mapping_model_id is None
      or dataset.pixel_grid_id != model.image.camera_mapping_model_id
      or dataset.pixel_indexing != FPA_PIXEL_INDEXING
  ):
    return _empty_comparison(
      model,
      dataset,
      status=FpaExternalComparisonStatus.BLOCKED_PIXEL_GRID,
      reason=(
        'external data must use the exact model image shape and declared '
        'row-major pixel mapping; no grid conversion is performed'
      ),
    )
  ####
  if not all(valid for row in model.image.validity_mask for valid in row):
    return _empty_comparison(
      model,
      dataset,
      status=FpaExternalComparisonStatus.BLOCKED_MODEL,
      reason=(
        'the model image contains invalid pixels; partial detector frames are '
        'not treated as full-domain validation evidence'
      ),
    )
  ####
  if model.digitized is not None and not all(
      valid for row in model.digitized.validity_mask for valid in row
  ):
    return _empty_comparison(
      model,
      dataset,
      status=FpaExternalComparisonStatus.BLOCKED_MODEL,
      reason=(
        'the deterministic digitized image contains invalid pixels; partial '
        'detector frames are not treated as full-domain evidence'
      ),
    )
  ####
  residual_rows = tuple(
    tuple(
      model_value - observed_value
      for model_value, observed_value in zip(model_row, observed_row, strict=True)
    )
    for model_row, observed_row in zip(model_values, dataset.values, strict=True)
  )
  residuals = tuple(value for row in residual_rows for value in row)
  uncertainty_values = (
    tuple(value for row in dataset.uncertainty for value in row)
    if dataset.uncertainty is not None
    else ()
  )
  weighted = (
    tuple(
      residual / uncertainty
      for residual, uncertainty in zip(
        residuals,
        uncertainty_values,
        strict=True,
      )
    )
    if uncertainty_values and all(value > 0.0 for value in uncertainty_values)
    else ()
  )
  pixel_comparison = FpaExternalPixelComparison(
    measurement_space=dataset.measurement_space,
    residuals=residual_rows,
    valid_pixel_count=len(residuals),
    pixel_count=len(residuals),
    rmse=sqrt(fsum(value * value for value in residuals) / len(residuals)),
    max_abs_residual=max(abs(value) for value in residuals),
    uncertainty_weighted_rmse=(
      sqrt(fsum(value * value for value in weighted) / len(weighted))
      if weighted else None
    ),
  )
  return FpaExternalComparison(
    status=FpaExternalComparisonStatus.FULL_DOMAIN_COMPUTED,
    operator_id=FPA_EXTERNAL_COMPARISON_OPERATOR_ID,
    dataset_id=dataset.dataset_id,
    case_id=dataset.case_id,
    split=dataset.split,
    measurement_space=dataset.measurement_space,
    model_width_px=model.image.width_px,
    model_height_px=model.image.height_px,
    observed_width_px=dataset.width_px,
    observed_height_px=dataset.height_px,
    model_pixel_grid_id=model.image.camera_mapping_model_id,
    observed_pixel_grid_id=dataset.pixel_grid_id,
    pixel_comparison=pixel_comparison,
    claim_status='not_accepted',
    reason=(
      'exact pixel values were compared in the declared measurement space; '
      'residuals remain external evidence and do not authorize an FPA claim'
    ),
    model_measurement_operator_sha256=model.image.measurement_operator_sha256,
    observed_measurement_operator_sha256=dataset.measurement_operator_sha256,
    model_digitization_policy_sha256=model_digitization_digest,
    observed_digitization_policy_sha256=dataset.digitization_policy_sha256,
  )
####


def _review_base(
  status: FpaExternalPromotionReviewStatus,
  message: str,
  *,
  policy: FpaExternalPromotionPolicy,
  split_audit: FpaExternalSplitAudit,
  model_case_count: int,
  dataset_count: int,
  comparisons: Sequence[FpaExternalComparison] = (),
  source_admission_decisions: Sequence[
    tuple[str, FpaSourceAdmissionDecision]
  ] = (),
  failed_dataset_ids: Sequence[str] = (),
  residual_failures: Sequence[str] = (),
  external_validation_verified: bool = False,
) -> FpaExternalPromotionReview:
  return FpaExternalPromotionReview(
    status=status,
    operator_id=FPA_EXTERNAL_PROMOTION_REVIEW_OPERATOR_ID,
    model_case_count=model_case_count,
    dataset_count=dataset_count,
    policy=policy,
    split_audit=split_audit,
    comparisons=tuple(comparisons),
    source_admission_decisions=tuple(source_admission_decisions),
    failed_dataset_ids=tuple(failed_dataset_ids),
    residual_failures=tuple(residual_failures),
    external_validation_verified=external_validation_verified,
    message=message,
  )
####


def review_fpa_external_promotion(
  models_by_case: Mapping[str, FpaExternalModelCase],
  datasets: Sequence[FpaExternalDataset],
  policy: FpaExternalPromotionPolicy | None = None,
) -> FpaExternalPromotionReview:
  """Review disjoint external FPA evidence without enabling production claims."""

  if policy is None:
    policy = FpaExternalPromotionPolicy()
  ####
  if not isinstance(policy, FpaExternalPromotionPolicy):
    raise TypeError('policy must be an FpaExternalPromotionPolicy or None')
  ####
  if not isinstance(models_by_case, Mapping):
    raise TypeError('models_by_case must map case IDs to FpaExternalModelCase values')
  ####
  try:
    items = tuple(datasets)
  except TypeError:
    items = ()
    input_valid = False
  else:
    input_valid = all(
      isinstance(dataset, FpaExternalDataset) for dataset in items
    )
  ####
  split_audit = audit_fpa_external_validation_splits(items)
  if not input_valid:
    return _review_base(
      FpaExternalPromotionReviewStatus.INVALID_INPUT,
      'datasets must contain FpaExternalDataset values',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
    )
  ####
  if not items:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_MISSING_DATA,
      'no owner-supplied FPA detector observations were supplied',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=0,
    )
  ####
  if not split_audit.verified:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_SPLIT_AUDIT,
      'both disjoint calibration and validation detector datasets are required',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
    )
  ####
  missing_model_cases = tuple(
    dataset.dataset_id
    for dataset in items
    if dataset.case_id not in models_by_case
    or not isinstance(models_by_case[dataset.case_id], FpaExternalModelCase)
  )
  if missing_model_cases:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_MODEL,
      'every external case must have a typed deterministic FPA model case',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      failed_dataset_ids=missing_model_cases,
    )
  ####
  source_admission_decisions = tuple(
    (
      case_id,
      evaluate_fpa_source_admission(models_by_case[case_id].source),
    )
    for case_id in dict.fromkeys(dataset.case_id for dataset in items)
  )
  comparisons = tuple(
    compare_fpa_to_external(models_by_case[dataset.case_id], dataset)
    for dataset in items
  )
  failed_model = tuple(
    comparison.dataset_id
    for comparison in comparisons
    if comparison.status is FpaExternalComparisonStatus.BLOCKED_MODEL
  )
  if failed_model:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_MODEL,
      'every calibration and validation case must provide a complete valid '
      'deterministic FPA image in the requested measurement space',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=failed_model,
    )
  ####
  wrong_space = tuple(
    comparison.dataset_id
    for comparison in comparisons
    if comparison.measurement_space is not policy.required_measurement_space
  )
  if wrong_space:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_MEASUREMENT_SPACE,
      'every dataset must use the policy-declared detector measurement space; '
      'no conversion between electrons and counts is performed',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=wrong_space,
    )
  ####
  failed_lineage = tuple(
    comparison.dataset_id
    for comparison in comparisons
    if comparison.status is FpaExternalComparisonStatus.BLOCKED_SOURCE_LINEAGE
  )
  if failed_lineage:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_SOURCE_LINEAGE,
      'every external frame must bind to the exact ray-transfer source lineage',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=failed_lineage,
    )
  ####
  failed_operator_identity = tuple(
    comparison.dataset_id
    for comparison in comparisons
    if comparison.status is FpaExternalComparisonStatus.BLOCKED_OPERATOR_IDENTITY
  )
  if failed_operator_identity:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_OPERATOR_IDENTITY,
      'every external frame must bind the exact camera, detector, exposure, '
      'and applicable digitization operator configuration',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=failed_operator_identity,
    )
  ####
  failed_grid = tuple(
    comparison.dataset_id
    for comparison in comparisons
    if comparison.status is FpaExternalComparisonStatus.BLOCKED_PIXEL_GRID
  )
  if failed_grid:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_PIXEL_GRID,
      'every external frame must use the exact declared model pixel grid',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=failed_grid,
    )
  ####
  failed_coverage = tuple(
    comparison.dataset_id
    for comparison in comparisons
    if comparison.status is not FpaExternalComparisonStatus.FULL_DOMAIN_COMPUTED
  )
  if failed_coverage:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_COVERAGE,
      'calibration and validation datasets require exact full-domain pixel coverage',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=failed_coverage,
    )
  ####
  if policy.maximum_rmse is None:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_TOLERANCE,
      'the review owner must declare a maximum RMSE for the required measurement space',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
    )
  ####
  residual_failures: list[str] = []
  for comparison in comparisons:
    assert comparison.pixel_comparison is not None
    metrics = comparison.pixel_comparison
    if metrics.valid_pixel_fraction < policy.minimum_valid_pixel_fraction:
      residual_failures.append(comparison.dataset_id)
      continue
    ####
    if metrics.rmse > policy.maximum_rmse:
      residual_failures.append(comparison.dataset_id)
      continue
    ####
    weighted_tolerance = policy.maximum_uncertainty_weighted_rmse
    if weighted_tolerance is not None:
      weighted_rmse = metrics.uncertainty_weighted_rmse
      if weighted_rmse is None or weighted_rmse > weighted_tolerance:
        residual_failures.append(comparison.dataset_id)
    ####
  ####
  if residual_failures:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_RESIDUAL,
      'one or more exact-grid detector residuals exceed the explicit policy '
      'or lack complete positive uncertainty for the requested weighted check; '
      'no calibration, denoising, or image correction was applied',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      residual_failures=residual_failures,
    )
  ####
  non_measured = tuple(
    dataset.dataset_id
    for dataset in items
    if dataset.evidence_origin is not FpaExternalEvidenceOrigin.MEASURED_EXTERNAL
  )
  if non_measured:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_EVIDENCE_ORIGIN,
      'synthetic or contract-only fixtures may support diagnostics but cannot '
      'be counted as measured external detector evidence',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=non_measured,
    )
  ####
  unattested = tuple(
    dataset.dataset_id
    for dataset in items
    if not verify_fpa_external_evidence_attestation(dataset)
  )
  if unattested:
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_EVIDENCE_ATTESTATION,
      'measured detector data must match a reviewed source-package and exact '
      'dataset-content attestation',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=unattested,
    )
  ####
  blocked_source_cases = tuple(
    case_id
    for case_id, decision in source_admission_decisions
    if not decision.admitted
  )
  if blocked_source_cases:
    blocked_datasets = tuple(
      dataset.dataset_id
      for dataset in items
      if dataset.case_id in blocked_source_cases
    )
    return _review_base(
      FpaExternalPromotionReviewStatus.BLOCKED_SOURCE_ADMISSION,
      'every FPA source must match an accepted provider, fidelity, and '
      'applicability-domain admission rule',
      policy=policy,
      split_audit=split_audit,
      model_case_count=len(models_by_case),
      dataset_count=len(items),
      comparisons=comparisons,
      source_admission_decisions=source_admission_decisions,
      failed_dataset_ids=blocked_datasets,
    )
  ####
  return _review_base(
    FpaExternalPromotionReviewStatus.EXTERNAL_EVIDENCE_VERIFIED,
    'exact-grid calibration and holdout comparisons satisfy the declared policy; '
    'the FPA remains a downstream deterministic lane and production claims remain gated',
    policy=policy,
    split_audit=split_audit,
    model_case_count=len(models_by_case),
    dataset_count=len(items),
    comparisons=comparisons,
    source_admission_decisions=source_admission_decisions,
    external_validation_verified=True,
  )
####
