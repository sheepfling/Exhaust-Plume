from __future__ import annotations

from pathlib import Path

import pytest

from exhaust_plume.validation.claims import (
  ClaimRole,
  ClaimStatus,
  EvidenceLevel,
  ValidationClaim,
  ValidationRegistry,
)

ROOT = Path(__file__).resolve().parents[3]
ALIGNMENT = ROOT / 'docs' / 'coding_agent_handoff' / 'resync_v0.1.0a1' / 'alignment'


def test_alignment_registry_loads_committed_semantics_without_external_data() -> None:
  registry = ValidationRegistry.from_alignment_directory(ALIGNMENT)
  assert len(registry.product_ids) == 8
  assert len(registry.operators) == 19
  assert len(registry.evidence_levels) == 5
  assert registry.source_archive_verified is False
  assert any(operator.operator_id == 'op.visual.feature-extractor' for operator in registry.operators)
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
