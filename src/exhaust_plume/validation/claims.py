"""Typed validation claims and measurement-operator alignment records."""

from __future__ import annotations

import csv
from enum import Enum, IntEnum
from math import isfinite
from pathlib import Path
import re
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ValidationModel(BaseModel):
  """Immutable, closed model for validation-governance records."""

  model_config = ConfigDict(extra='forbid', frozen=True)
####


_SHA256 = re.compile(r'^[0-9a-f]{64}$')


class EvidenceLevel(IntEnum):
  NONE_OR_NOT_ACQUIRED = 0
  UPSTREAM_CONTEXT = 1
  INDIRECT_FEATURE_OR_ENVELOPE = 2
  QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR = 3
  DIRECT_NATIVE_PRODUCT_OBSERVABLE = 4
####


class ClaimRole(str, Enum):
  CALIBRATION = 'calibration'
  VALIDATION = 'validation'
  CONTEXT = 'context'
####


class ClaimStatus(str, Enum):
  PENDING_DATA = 'pending_data'
  PROPOSED = 'proposed'
  ACCEPTED = 'accepted'
  REJECTED = 'rejected'
####


class OperatorStatus(str, Enum):
  REQUIRED = 'required'
  REQUIRED_CROSS_PRODUCT = 'required_cross_product'
  PENDING_DATA = 'pending_data_for_full_use'
####


class ComparisonEvidenceStatus(str, Enum):
  """Lifecycle state of a provider-bound comparison evidence package."""

  BLOCKED = 'blocked'
  DIAGNOSTIC = 'diagnostic'
  ACCEPTED = 'accepted'
####


class BenchmarkDefinition(ValidationModel):
  """Source-centric benchmark identity, kept separate from product data."""

  benchmark_id: str = Field(min_length=1)
  title: str = Field(min_length=1)
  source_record_ids: tuple[str, ...] = Field(min_length=1)
  applicability_domain: Mapping[str, Any] = Field(default_factory=dict)
  source_references: tuple[str, ...] = ()
  source_archive_verified: bool = False
####


class MeasurementOperatorSpec(ValidationModel):
  """Experiment-equivalent transformation from products to observables."""

  operator_id: str = Field(min_length=1)
  input_product_ids: tuple[str, ...] = Field(min_length=1)
  output_observable: str = Field(min_length=1)
  required_metadata: tuple[str, ...] = ()
  principal_benchmarks: tuple[str, ...] = ()
  status: OperatorStatus
####


class EvidenceLevelSpec(ValidationModel):
  """Claim language and meaning for one evidence level."""

  level: EvidenceLevel
  name: str = Field(min_length=1)
  definition: str = Field(min_length=1)
  allowed_claim_language: str = Field(min_length=1)
####


class ProviderBoundComparisonEvidence(ValidationModel):
  """Content-addressed evidence required to support an accepted claim.

  A numerical residual is not sufficient to promote a product claim.  This
  record binds the residual to the exact provider output, observation assets,
  measurement-operator implementation, and validation cases that produced
  it.  Calibration and validation case IDs are intentionally separate and
  must not overlap.
  """

  evidence_id: str = Field(min_length=1)
  claim_id: str = Field(min_length=1)
  provider_id: str = Field(min_length=1)
  provider_version: str = Field(min_length=1)
  provider_snapshot_id: str = Field(min_length=1)
  product_id: str = Field(min_length=1)
  benchmark_id: str = Field(min_length=1)
  external_operator_id: str = Field(min_length=1)
  internal_operator_ids: tuple[str, ...] = Field(min_length=1)
  measurement_space: str = Field(min_length=1)
  coordinate_frame_id: str = Field(min_length=1)
  metric_ids: tuple[str, ...] = Field(min_length=1)
  metric_results: Mapping[str, float] = Field(default_factory=dict)
  metric_tolerances: Mapping[str, float] = Field(default_factory=dict)
  coverage: Mapping[str, Any] = Field(default_factory=dict)
  source_asset_ids: tuple[str, ...] = Field(min_length=1)
  source_asset_sha256: tuple[str, ...] = Field(min_length=1)
  provider_output_ids: tuple[str, ...] = Field(min_length=1)
  provider_output_sha256: tuple[str, ...] = Field(min_length=1)
  operator_manifest_sha256: str
  calibration_case_ids: tuple[str, ...] = ()
  validation_case_ids: tuple[str, ...] = Field(min_length=1)
  uncertainty: Mapping[str, Any] = Field(default_factory=dict)
  applicability_domain: Mapping[str, Any] = Field(default_factory=dict)
  limitations: tuple[str, ...] = ()
  status: ComparisonEvidenceStatus = ComparisonEvidenceStatus.BLOCKED

  @field_validator(
    'internal_operator_ids',
    'metric_ids',
    'source_asset_ids',
    'provider_output_ids',
    'calibration_case_ids',
    'validation_case_ids',
  )
  @classmethod
  def validateIdentifiers(cls, values: tuple[str, ...]) -> tuple[str, ...]:
    if any(not value for value in values):
      raise ValueError('evidence identifier collections must not contain empty values')
    if len(values) != len(set(values)):
      raise ValueError('evidence identifier collections must not contain duplicates')
    ####
    return values
  ####

  @field_validator(
    'source_asset_sha256',
    'provider_output_sha256',
  )
  @classmethod
  def validateDigests(cls, values: tuple[str, ...]) -> tuple[str, ...]:
    invalid = tuple(value for value in values if not _SHA256.fullmatch(value))
    if invalid:
      raise ValueError(f'Invalid lowercase SHA-256 digest(s):{invalid!r}')
    ####
    if len(values) != len(set(values)):
      raise ValueError('evidence digest collections must not contain duplicates')
    ####
    return values
  ####

  @field_validator('operator_manifest_sha256')
  @classmethod
  def validateOperatorManifestDigest(cls, value: str) -> str:
    if not _SHA256.fullmatch(value):
      raise ValueError('operator_manifest_sha256 must be a lowercase SHA-256 digest')
    ####
    return value
  ####

  @model_validator(mode='after')
  def validateEvidence(self) -> ProviderBoundComparisonEvidence:
    overlap = set(self.calibration_case_ids) & set(self.validation_case_ids)
    if overlap:
      raise ValueError(
        'calibration_case_ids and validation_case_ids must be disjoint'
      )
    ####
    if self.status is ComparisonEvidenceStatus.ACCEPTED:
      if not self.uncertainty:
        raise ValueError('accepted comparison evidence requires uncertainty metadata')
      if not self.applicability_domain:
        raise ValueError('accepted comparison evidence requires an applicability domain')
      if not self.coverage:
        raise ValueError('accepted comparison evidence requires coverage metadata')
    missing_results = set(self.metric_ids) - set(self.metric_results)
    if missing_results:
      raise ValueError(
        'comparison evidence must report every declared metric result'
      )
    missing_tolerances = set(self.metric_ids) - set(self.metric_tolerances)
    if missing_tolerances:
      raise ValueError(
        'comparison evidence must declare a tolerance for every metric'
      )
    if any(
      not isfinite(float(value))
      for values in (self.metric_results.values(), self.metric_tolerances.values())
      for value in values
    ):
      raise ValueError('comparison evidence metric values and tolerances must be finite')
    if any(float(value) < 0.0 for value in self.metric_tolerances.values()):
      raise ValueError('comparison evidence metric tolerances must be nonnegative')
    if len(self.source_asset_ids) != len(self.source_asset_sha256):
      raise ValueError(
        'source_asset_ids and source_asset_sha256 must have matching lengths'
      )
    if len(self.provider_output_ids) != len(self.provider_output_sha256):
      raise ValueError(
        'provider_output_ids and provider_output_sha256 must have matching lengths'
      )
    if self.status is ComparisonEvidenceStatus.ACCEPTED:
      exceeded = tuple(
        metric_id
        for metric_id in self.metric_ids
        if abs(float(self.metric_results[metric_id]))
        > float(self.metric_tolerances[metric_id])
      )
      if exceeded:
        raise ValueError(
          'accepted comparison evidence has metrics outside declared tolerances'
        )
    ####
    return self
  ####
####


class ValidationClaim(ValidationModel):
  """One scoped, auditable claim about one product and benchmark."""

  claim_id: str = Field(min_length=1)
  benchmark_id: str = Field(min_length=1)
  product_id: str = Field(min_length=1)
  measurement_operator_id: str | None = None
  metric_id: str = Field(min_length=1)
  applicability_domain: Mapping[str, Any] = Field(default_factory=dict)
  evidence_level: EvidenceLevel
  claim_role: ClaimRole
  uncertainty: Mapping[str, Any] = Field(default_factory=dict)
  provenance: Mapping[str, str] = Field(default_factory=dict)
  limitations: tuple[str, ...] = ()
  comparison_evidence: ProviderBoundComparisonEvidence | None = None
  status: ClaimStatus = ClaimStatus.PROPOSED

  @model_validator(mode='after')
  def validate_evidence_requirements(self) -> ValidationClaim:
    quantitative = self.evidence_level >= EvidenceLevel.QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR
    if quantitative and self.measurement_operator_id is None:
      raise ValueError('quantitative claims require a measurement_operator_id')
    ####
    if quantitative and not self.uncertainty:
      raise ValueError('quantitative claims require uncertainty metadata')
    ####
    if quantitative and not self.provenance:
      raise ValueError('quantitative claims require provenance metadata')
    ####
    evidence = self.comparison_evidence
    if quantitative and self.status is ClaimStatus.ACCEPTED and evidence is None:
      raise ValueError(
        'accepted quantitative claims require provider-bound comparison evidence'
      )
    ####
    if evidence is not None:
      if evidence.claim_id != self.claim_id:
        raise ValueError('comparison evidence claim_id must match the validation claim')
      ####
      if evidence.benchmark_id != self.benchmark_id:
        raise ValueError('comparison evidence benchmark_id must match the validation claim')
      ####
      if evidence.product_id != self.product_id:
        raise ValueError('comparison evidence product_id must match the validation claim')
      ####
      if evidence.external_operator_id != self.measurement_operator_id:
        raise ValueError(
          'comparison evidence external_operator_id must match measurement_operator_id'
        )
      ####
      if self.metric_id not in evidence.metric_ids:
        raise ValueError('comparison evidence must include the validation claim metric_id')
      ####
      if self.status is ClaimStatus.ACCEPTED and evidence.status is not ComparisonEvidenceStatus.ACCEPTED:
        raise ValueError('an accepted validation claim requires accepted comparison evidence')
    ####
    if self.evidence_level is EvidenceLevel.NONE_OR_NOT_ACQUIRED and self.status is ClaimStatus.ACCEPTED:
      raise ValueError('unacquired evidence cannot be an accepted claim')
    ####
    return self
  ####
####


class ValidationRegistry(ValidationModel):
  """Alignment registry plus typed claims, with unique record identities."""

  product_ids: tuple[str, ...] = ()
  operators: tuple[MeasurementOperatorSpec, ...] = ()
  evidence_levels: tuple[EvidenceLevelSpec, ...] = ()
  benchmarks: tuple[BenchmarkDefinition, ...] = ()
  claims: tuple[ValidationClaim, ...] = ()
  source_archive_verified: bool = False

  @model_validator(mode='after')
  def validate_unique_ids(self) -> ValidationRegistry:
    for field_name, records in (
        ('operators', self.operators),
        ('evidence_levels', self.evidence_levels),
        ('benchmarks', self.benchmarks),
        ('claims', self.claims),
    ):
      identifiers = tuple(
        getattr(record, 'operator_id', None)
        or getattr(record, 'level', None)
        or getattr(record, 'benchmark_id', None)
        or getattr(record, 'claim_id', None)
        for record in records
      )
      if len(identifiers) != len(set(identifiers)):
        raise ValueError(f'{field_name} must have unique identifiers')
      ####
    ####
    if len(self.product_ids) != len(set(self.product_ids)):
      raise ValueError('product_ids must be unique')
    ####
    return self
  ####

  @classmethod
  def from_alignment_directory(cls, directory: Path) -> ValidationRegistry:
    """Load committed alignment metadata without loading external observations."""

    operator_path = directory / 'measurement_operator_registry.csv'
    evidence_path = directory / 'evidence_level_taxonomy.csv'
    catalog_path = directory / 'mvp_product_catalog.csv'
    return cls(
      product_ids=_load_product_ids(catalog_path),
      operators=_load_operators(operator_path),
      evidence_levels=_load_evidence_levels(evidence_path),
      source_archive_verified=False,
    )
  ####
####


def _split_field(value: str) -> tuple[str, ...]:
  return tuple(item.strip() for item in value.split(';') if item.strip())
####


def _load_product_ids(path: Path) -> tuple[str, ...]:
  with path.open(newline='', encoding='utf-8') as stream:
    return tuple(str(row['product_id']) for row in csv.DictReader(stream))
  ####
####


def _load_operators(path: Path) -> tuple[MeasurementOperatorSpec, ...]:
  with path.open(newline='', encoding='utf-8') as stream:
    return tuple(
      MeasurementOperatorSpec(
        operator_id=str(row['operator_id']),
        input_product_ids=_split_field(str(row['input_product_ids'])),
        output_observable=str(row['output_observable']),
        required_metadata=_split_field(str(row['required_metadata'])),
        principal_benchmarks=_split_field(str(row['principal_benchmarks'])),
        status=OperatorStatus(str(row['status'])),
      )
      for row in csv.DictReader(stream)
    )
  ####
####


def _load_evidence_levels(path: Path) -> tuple[EvidenceLevelSpec, ...]:
  with path.open(newline='', encoding='utf-8') as stream:
    return tuple(
      EvidenceLevelSpec(
        level=EvidenceLevel(int(row['level'])),
        name=str(row['name']),
        definition=str(row['definition']),
        allowed_claim_language=str(row['allowed_claim_language']),
      )
      for row in csv.DictReader(stream)
    )
  ####
####


__all__ = (
  'BenchmarkDefinition',
  'ClaimRole',
  'ClaimStatus',
  'ComparisonEvidenceStatus',
  'EvidenceLevel',
  'EvidenceLevelSpec',
  'MeasurementOperatorSpec',
  'OperatorStatus',
  'ProviderBoundComparisonEvidence',
  'ValidationClaim',
  'ValidationRegistry',
)
