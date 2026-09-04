from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.validate_provider_comparisons import (
  PROVIDER_BOUND_EVIDENCE_SCHEMA,
  build_comparison_plan,
  build_unimplemented_boundaries,
  execute_visual_feature_probe,
  load_provider_bound_evidence,
  _provider_bound_evidence_source_label,
)
from exhaust_plume.validation.claims import (
  ComparisonEvidenceStatus,
  ProviderBoundComparisonEvidence,
)


def _observations() -> dict[str, Any]:
  return {
    'RP-HOTWAKE-001': {'mach_disk_relation': {'row_count': 606}},
    'RP-BSUV2-001': {'spectral_radiance': {'row_count': 13}},
    'RP-EMAP-RAD-001': {
      'uvvis_relative_spectrum': {'row_count': 758},
      'ftir_relative_envelopes': {'row_count': 708},
      'gardon_time_history': {'row_count': 922},
    },
    'RP-ALSI-001': {'thermal_comparison': {'row_count': 5}},
  }
####


def _providers() -> dict[str, Any]:
  return {
    'visual': {
      'provider_ids': ['plume.straight-analytical', 'plume.shock-cell-analytical'],
      'output_channels': ['core_radius_fraction', 'opacity_weight'],
    },
    'signature': {'provider_id': 'signature.table-lookup'},
    'optical': {
      'provider_ids': [],
      'output_fields': [
        'source_spectral_radiance',
        'background_transmittance',
        'optical_depth',
      ],
    },
    'focal_plane_array': {'provider_ids': []},
  }
####


def test_provider_comparisons_remain_blocked_without_required_observables() -> None:
  comparisons = build_comparison_plan(
    observations=_observations(),
    providers=_providers(),
    operator_crosswalk_status='pending',
  )

  assert [comparison['comparison_id'] for comparison in comparisons] == [
    'VIS-MVP-A-061',
    'SIG-MVP-A-043',
    'SIG-MVP-A-064',
    'SIG-MVP-A-066',
    'SIG-MVP-A-073',
    'RAY-MVP-A-044',
    'RAY-MVP-A-065',
    'RAY-MVP-A-067',
    'RAY-MVP-A-068',
    'RAY-MVP-A-074',
  ]
  assert all(comparison['comparison_status'] == 'blocked' for comparison in comparisons)
  assert all(comparison['claim_status'] == 'not_accepted' for comparison in comparisons)
  assert all(comparison['evidence_status'] == 'blocked' for comparison in comparisons)
  assert all(comparison['provider_bound_evidence'] is None for comparison in comparisons)
  assert len(comparisons) == 10
  assert {comparison['alignment_id'] for comparison in comparisons} == {
    'MVP-A-043',
    'MVP-A-044',
    'MVP-A-061',
    'MVP-A-064',
    'MVP-A-065',
    'MVP-A-066',
    'MVP-A-067',
    'MVP-A-068',
    'MVP-A-073',
    'MVP-A-074',
  }
  assert comparisons[0]['required_provider_outputs'] == [
    'mach_disk_position_m',
    'operating_pressure_or_branch_id',
  ]
  assert any('operator namespace' in blocker for blocker in comparisons[0]['blockers'])
####


def test_downstream_boundaries_do_not_advertise_unimplemented_products() -> None:
  boundaries = build_unimplemented_boundaries(_providers())

  assert [boundary['product_id'] for boundary in boundaries] == [
    'plume.optical.spectral-ray-transfer@1',
    'plume.optical.spectral-ray-transfer@1',
    'plume.image.spectral-radiance@1',
  ]
  assert boundaries[0]['provider_ids'] == []
  assert boundaries[1]['provider_ids'] == ['plume.curved-gray-ray-transfer']
  assert boundaries[2]['provider_ids'] == []
  assert all(boundary['claim_status'] == 'not_accepted' for boundary in boundaries)
####


def test_operator_execution_diagnostics_do_not_promote_a_blocked_comparison() -> None:
  comparisons = build_comparison_plan(
    observations=_observations(),
    providers=_providers(),
    operator_crosswalk_status='pending',
    operator_executions={
      'SIG-MVP-A-066': {
        'status': 'partial-overlap-diagnostic',
        'coverage_fraction': 0.16,
      },
    },
  )

  comparison = next(item for item in comparisons if item['comparison_id'] == 'SIG-MVP-A-066')
  assert comparison['operator_execution']['status'] == 'partial-overlap-diagnostic'
  assert comparison['comparison_status'] == 'blocked'
  assert comparison['claim_status'] == 'not_accepted'
####


def _accepted_spectral_evidence() -> ProviderBoundComparisonEvidence:
  return ProviderBoundComparisonEvidence(
    evidence_id='evidence-064',
    claim_id='SIG-MVP-A-064',
    provider_id='signature.table-lookup',
    provider_version='1.0.0',
    provider_snapshot_id='signature-snapshot-1',
    product_id='plume.signature.spectral-radiant-intensity@1',
    benchmark_id='RP-EMAP-RAD-001',
    external_operator_id='operator.spectrum.peak_normalize_after_sensor_sampling',
    internal_operator_ids=(
      'op.sensor.spectral-sampling',
      'op.sensor.peak-normalize-spectrum',
    ),
    measurement_space='relative-shape',
    coordinate_frame_id='observer-frame',
    metric_ids=(
      'metric.signature.relative_shape_rmse',
      'metric.signature.band_location_error',
    ),
    metric_results={
      'metric.signature.relative_shape_rmse': 0.01,
      'metric.signature.band_location_error': 1.0e-9,
    },
    metric_tolerances={
      'metric.signature.relative_shape_rmse': 0.05,
      'metric.signature.band_location_error': 2.0e-9,
    },
    coverage={'observed_samples': 100, 'coverage_fraction': 1.0},
    source_asset_ids=('emap-spectrum',),
    source_asset_sha256=('a' * 64,),
    provider_output_ids=('signature-output',),
    provider_output_sha256=('b' * 64,),
    operator_manifest_sha256='c' * 64,
    validation_case_ids=('emap-validation-1',),
    uncertainty={'relative_shape_rmse': 0.005},
    applicability_domain={'wavelength_m': [5.0e-7, 8.5e-7]},
    status=ComparisonEvidenceStatus.ACCEPTED,
  )
####


def test_provider_bound_evidence_can_promote_only_a_matching_comparison() -> None:
  comparisons = build_comparison_plan(
    observations=_observations(),
    providers=_providers(),
    operator_crosswalk_status='complete-scoped',
    provider_bound_evidence={'SIG-MVP-A-064': _accepted_spectral_evidence()},
  )

  accepted = next(item for item in comparisons if item['comparison_id'] == 'SIG-MVP-A-064')
  blocked = next(item for item in comparisons if item['comparison_id'] == 'SIG-MVP-A-066')
  assert accepted['comparison_status'] == 'accepted'
  assert accepted['claim_status'] == 'accepted'
  assert accepted['evidence_status'] == 'accepted'
  assert accepted['provider_bound_evidence']['evidence_id'] == 'evidence-064'
  assert blocked['comparison_status'] == 'blocked'
  assert blocked['claim_status'] == 'not_accepted'
####


def test_provider_bound_evidence_requires_a_complete_operator_crosswalk() -> None:
  with pytest.raises(ValueError, match='complete-scoped operator crosswalk'):
    build_comparison_plan(
      observations=_observations(),
      providers=_providers(),
      operator_crosswalk_status='pending',
      provider_bound_evidence={'SIG-MVP-A-064': _accepted_spectral_evidence()},
    )
  ####
####


def test_provider_bound_evidence_must_bind_to_a_compared_provider() -> None:
  evidence = _accepted_spectral_evidence().model_copy(
    update={'provider_id': 'unrelated.provider.v1'}
  )
  with pytest.raises(ValueError, match='must match a comparison provider'):
    build_comparison_plan(
      observations=_observations(),
      providers=_providers(),
      operator_crosswalk_status='complete-scoped',
      provider_bound_evidence={'SIG-MVP-A-064': evidence},
    )
  ####
####


def test_provider_bound_evidence_document_loads_by_claim_id(tmp_path) -> None:
  evidence = _accepted_spectral_evidence()
  path = tmp_path / 'provider-evidence.json'
  path.write_text(
    json.dumps({
      'schema_id': PROVIDER_BOUND_EVIDENCE_SCHEMA,
      'evidence': [evidence.model_dump(mode='json')],
    }),
    encoding='utf-8',
  )

  loaded = load_provider_bound_evidence(path)

  assert loaded == {'SIG-MVP-A-064': evidence}
####


def test_provider_bound_evidence_document_rejects_duplicate_claims(tmp_path) -> None:
  evidence = _accepted_spectral_evidence()
  path = tmp_path / 'provider-evidence.json'
  record = evidence.model_dump(mode='json')
  path.write_text(
    json.dumps({
      'schema_id': PROVIDER_BOUND_EVIDENCE_SCHEMA,
      'evidence': [record, record | {'evidence_id': 'evidence-064-copy'}],
    }),
    encoding='utf-8',
  )

  with pytest.raises(ValueError, match='duplicate claim_id'):
    load_provider_bound_evidence(path)
  ####
####


def test_provider_bound_evidence_document_rejects_unknown_top_level_fields(tmp_path) -> None:
  path = tmp_path / 'provider-evidence.json'
  path.write_text(
    json.dumps({
      'schema_id': PROVIDER_BOUND_EVIDENCE_SCHEMA,
      'evidence': [],
      'notes': 'not part of the schema',
    }),
    encoding='utf-8',
  )

  with pytest.raises(ValueError, match='only schema_id and evidence'):
    load_provider_bound_evidence(path)
  ####
####


def test_provider_bound_evidence_source_label_is_portable() -> None:
  assert _provider_bound_evidence_source_label(
    Path('/one/machine/provider-evidence.json')
  ) == 'provider-evidence.json'
  assert _provider_bound_evidence_source_label(
    Path('/another/machine/provider-evidence.json')
  ) == 'provider-evidence.json'
  assert _provider_bound_evidence_source_label(None) is None
####


def test_visual_feature_probe_reports_missing_feature_and_branch_contract() -> None:
  result = execute_visual_feature_probe(
    _observations(),
    _providers(),
  )

  assert result['status'] == 'blocked-missing-provider-feature'
  assert result['claim_status'] == 'not_accepted'
  assert result['comparison_method'] == 'branch-aware-no-extrapolation'
  assert result['observed_point_count'] == 606
  assert result['observed_branch_id_field_present'] is False
  assert result['missing_provider_outputs'] == [
    'mach_disk_position_m',
    'operating_pressure_or_branch_id',
  ]
####
