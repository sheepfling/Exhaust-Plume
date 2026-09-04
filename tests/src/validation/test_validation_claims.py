from __future__ import annotations

from pathlib import Path

import pytest

from exhaust_plume.validation.claims import (
  ClaimRole,
  ClaimStatus,
  ComparisonEvidenceStatus,
  EvidenceLevel,
  ProviderBoundComparisonEvidence,
  ValidationClaim,
  ValidationRegistry,
)

ROOT = Path(__file__).resolve().parents[3]
ALIGNMENT = ROOT / 'docs' / 'coding_agent_handoff' / 'resync_v0.1.0a1' / 'alignment'


def test_alignment_registry_loads_committed_semantics_without_external_data() -> None:
  registry = ValidationRegistry.from_alignment_directory(ALIGNMENT)
  assert len(registry.product_ids) == 8
  assert len(registry.operators) == 21
  assert len(registry.evidence_levels) == 5
  assert registry.source_archive_verified is False
  assert any(operator.operator_id == 'op.visual.feature-extractor' for operator in registry.operators)
  assert any(operator.operator_id == 'op.sensor.fpa-pixel-detector' for operator in registry.operators)
####


def test_quantitative_claim_requires_operator_uncertainty_and_provenance() -> None:
  with pytest.raises(ValueError, match='measurement_operator_id'):
    ValidationClaim(
      claim_id='claim-1',
      benchmark_id='CJ-UEJ-001',
      product_id='plume.visual.sectioned-tube@1',
      metric_id='shock-spacing',
      evidence_level=EvidenceLevel.QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR,
      claim_role=ClaimRole.VALIDATION,
    )
  ####
  with pytest.raises(ValueError, match='uncertainty metadata'):
    ValidationClaim(
      claim_id='claim-2',
      benchmark_id='CJ-UEJ-001',
      product_id='plume.visual.sectioned-tube@1',
      measurement_operator_id='op.visual.feature-extractor',
      metric_id='shock-spacing',
      evidence_level=EvidenceLevel.QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR,
      claim_role=ClaimRole.VALIDATION,
      provenance={'source': 'fixture'},
    )
  ####
####


def test_pending_unacquired_claim_is_not_accepted() -> None:
  with pytest.raises(ValueError, match='unacquired evidence'):
    ValidationClaim(
      claim_id='claim-3',
      benchmark_id='RP-IMP-001',
      product_id='plume.signature.spectral-radiant-intensity@1',
      metric_id='intrinsic-spectrum',
      evidence_level=EvidenceLevel.NONE_OR_NOT_ACQUIRED,
      claim_role=ClaimRole.VALIDATION,
      status=ClaimStatus.ACCEPTED,
    )
  ####


def _accepted_comparison_evidence(**overrides: object) -> ProviderBoundComparisonEvidence:
  values: dict[str, object] = {
    'evidence_id': 'evidence-1',
    'claim_id': 'claim-accepted',
    'provider_id': 'plume.provider.v1',
    'provider_version': '1.2.3',
    'provider_snapshot_id': 'snapshot-1',
    'product_id': 'plume.visual.sectioned-tube@1',
    'benchmark_id': 'CJ-UEJ-001',
    'external_operator_id': 'operator.extract.sectioned_tube_mach_disk_position',
    'internal_operator_ids': ('op.visual.feature-extractor',),
    'measurement_space': 'physical-geometry',
    'coordinate_frame_id': 'nozzle-exit-frame',
    'metric_ids': ('shock-spacing',),
    'metric_results': {'shock-spacing': 0.1},
    'metric_tolerances': {'shock-spacing': 0.5},
    'coverage': {'matched_points': 10, 'observed_points': 10},
    'source_asset_ids': ('source-1',),
    'source_asset_sha256': ('a' * 64,),
    'provider_output_ids': ('output-1',),
    'provider_output_sha256': ('b' * 64,),
    'operator_manifest_sha256': 'c' * 64,
    'calibration_case_ids': ('calibration-1',),
    'validation_case_ids': ('validation-1',),
    'uncertainty': {'position_rmse_m': 0.1},
    'applicability_domain': {'mach': [1.5, 3.0]},
    'status': ComparisonEvidenceStatus.ACCEPTED,
  }
  values.update(overrides)
  return ProviderBoundComparisonEvidence(**values)


def test_accepted_quantitative_claim_requires_and_matches_bound_evidence() -> None:
  claim = ValidationClaim(
    claim_id='claim-accepted',
    benchmark_id='CJ-UEJ-001',
    product_id='plume.visual.sectioned-tube@1',
    measurement_operator_id='operator.extract.sectioned_tube_mach_disk_position',
    metric_id='shock-spacing',
    evidence_level=EvidenceLevel.QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR,
    claim_role=ClaimRole.VALIDATION,
    uncertainty={'position_rmse_m': 0.1},
    provenance={'source': 'provider-output'},
    comparison_evidence=_accepted_comparison_evidence(),
    status=ClaimStatus.ACCEPTED,
  )

  assert claim.comparison_evidence is not None
  assert claim.comparison_evidence.validation_case_ids == ('validation-1',)
####


def test_accepted_quantitative_claim_without_bound_evidence_is_rejected() -> None:
  with pytest.raises(ValueError, match='provider-bound comparison evidence'):
    ValidationClaim(
      claim_id='claim-accepted',
      benchmark_id='CJ-UEJ-001',
      product_id='plume.visual.sectioned-tube@1',
      measurement_operator_id='operator.extract.sectioned_tube_mach_disk_position',
      metric_id='shock-spacing',
      evidence_level=EvidenceLevel.QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR,
      claim_role=ClaimRole.VALIDATION,
      uncertainty={'position_rmse_m': 0.1},
      provenance={'source': 'provider-output'},
      status=ClaimStatus.ACCEPTED,
    )
  ####


def test_bound_evidence_rejects_calibration_validation_overlap() -> None:
  with pytest.raises(ValueError, match='must be disjoint'):
    _accepted_comparison_evidence(
      calibration_case_ids=('shared-case',),
      validation_case_ids=('shared-case',),
    )
  ####


def test_bound_evidence_must_match_claim_identity() -> None:
  with pytest.raises(ValueError, match='claim_id must match'):
    ValidationClaim(
      claim_id='claim-accepted',
      benchmark_id='CJ-UEJ-001',
      product_id='plume.visual.sectioned-tube@1',
      measurement_operator_id='operator.extract.sectioned_tube_mach_disk_position',
      metric_id='shock-spacing',
      evidence_level=EvidenceLevel.QUANTITATIVE_AFTER_MEASUREMENT_OPERATOR,
      claim_role=ClaimRole.VALIDATION,
      uncertainty={'position_rmse_m': 0.1},
      provenance={'source': 'provider-output'},
      comparison_evidence=_accepted_comparison_evidence(claim_id='other-claim'),
      status=ClaimStatus.ACCEPTED,
    )
  ####


def test_bound_evidence_requires_one_digest_per_named_asset_and_output() -> None:
  with pytest.raises(ValueError, match='source_asset_ids and source_asset_sha256'):
    _accepted_comparison_evidence(source_asset_ids=('source-1', 'source-2'))
  ####

  with pytest.raises(ValueError, match='provider_output_ids and provider_output_sha256'):
    _accepted_comparison_evidence(provider_output_ids=('output-1', 'output-2'))
  ####


def test_accepted_bound_evidence_requires_metrics_within_tolerance() -> None:
  with pytest.raises(ValueError, match='outside declared tolerances'):
    _accepted_comparison_evidence(
      metric_results={'shock-spacing': 0.6},
      metric_tolerances={'shock-spacing': 0.5},
    )
  ####
