"""Explicit study-validity envelopes and reproducible parameter sweeps."""

from exhaust_plume.validation.envelope import (
  DEFAULT_STUDY_VALIDITY_ENVELOPE,
  NozzleCaseAssessment,
  NozzleValidityCase,
  StudyValidityEnvelope,
  default_nozzle_geometries,
  default_pressure_sweep,
  default_validity_cases,
  evaluate_nozzle_case,
  evaluate_validity_matrix,
  write_validity_report_csv,
  write_validity_report_json,
)

__all__ = (
  'DEFAULT_STUDY_VALIDITY_ENVELOPE',
  'NozzleCaseAssessment',
  'NozzleValidityCase',
  'StudyValidityEnvelope',
  'default_nozzle_geometries',
  'default_pressure_sweep',
  'default_validity_cases',
  'evaluate_nozzle_case',
  'evaluate_validity_matrix',
  'write_validity_report_csv',
  'write_validity_report_json',
)
