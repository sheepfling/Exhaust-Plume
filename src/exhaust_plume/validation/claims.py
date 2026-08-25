"""Typed validation claims and measurement-operator alignment records."""

from __future__ import annotations

import csv
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ValidationModel(BaseModel):
  """Immutable, closed model for validation-governance records."""

  model_config = ConfigDict(extra='forbid', frozen=True)
####


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
  'EvidenceLevel',
  'EvidenceLevelSpec',
  'MeasurementOperatorSpec',
  'OperatorStatus',
  'ValidationClaim',
  'ValidationRegistry',
)
