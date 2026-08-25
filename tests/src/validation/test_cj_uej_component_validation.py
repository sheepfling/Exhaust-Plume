from __future__ import annotations

from pytest import approx

from scripts.validate_cj_uej_component import (
  CJRunConfiguration,
  _case_from_metadata,
  _local_extrema,
  _score_samples,
  _strictly_contains,
  _typed_claim,
)


def _metadata() -> dict[str, object]:
  return {
    'case': {
      'exit_diameter_m': 0.038,
      'ideally_expanded_jet_mach': 1.15,
      'nozzle_pressure_ratio': 2.27,
    },
  }


def test_polygon_sampling_excludes_ambiguous_boundary_geometry() -> None:
  square = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))

  assert _strictly_contains((0.5, 0.5), square)
  assert not _strictly_contains((0.0, 0.5), square)
####


def test_score_samples_reports_coverage_and_digitization_weighted_error() -> None:
  result = _score_samples(
    [
      {'x_over_D': 0.1, 'observed': 1.0, 'predicted': 1.1, 'uncertainty': 0.1},
      {'x_over_D': 0.2, 'observed': 2.0, 'predicted': 1.8, 'uncertainty': 0.2},
    ],
    observed_count=4,
    skipped={'outside_support': 2},
    metadata={'profile_id': 'centerline'},
  )

  assert result['predicted_count'] == 2
  assert result['coverage_fraction'] == approx(0.5)
  assert result['metrics']['rmse'] == approx(0.1581138830)
  assert result['metrics']['digitization_uncertainty_weighted_rmse'] == approx(1.0)
  assert result['claim_status'] == 'not_accepted'
####


def test_local_extrema_preserves_feature_order() -> None:
  extrema = _local_extrema([
    {'x_over_D': 0.0, 'observed': 1.0},
    {'x_over_D': 0.5, 'observed': 0.5},
    {'x_over_D': 1.0, 'observed': 1.2},
    {'x_over_D': 1.5, 'observed': 0.8},
  ])

  assert [item['kind'] for item in extrema] == ['minimum', 'maximum']
  assert [item['x_over_D'] for item in extrema] == [0.5, 1.0]
####


def test_cj_adapter_keeps_source_npr_distinct_from_derived_exit_pressure() -> None:
  result, case = _case_from_metadata(_metadata(), CJRunConfiguration())

  assert len(result.cells) == 1
  assert case['source_nozzle_pressure_ratio_p0_over_pa'] == approx(2.27)
  assert case['derived_exit_pressure_ratio_pe_over_pa'] == approx(1.1992, rel=1.0e-4)
####


def test_typed_component_claim_is_proposed_not_accepted() -> None:
  claim = _typed_claim('archive-sha256', CJRunConfiguration())

  assert claim['claim_id'] == 'VAL-002-CJ-UEJ-LOCAL-FIELD-DIAGNOSTIC'
  assert claim['measurement_operator_id'] == 'op.field.profile-probe'
  assert claim['evidence_level'] == 3
  assert claim['status'] == 'proposed'
