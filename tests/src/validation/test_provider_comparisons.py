from __future__ import annotations

from typing import Any

from scripts.validate_provider_comparisons import (
  build_comparison_plan,
  build_unimplemented_boundaries,
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


def test_downstream_boundaries_do_not_advertise_unimplemented_products() -> None:
  boundaries = build_unimplemented_boundaries(_providers())

  assert [boundary['product_id'] for boundary in boundaries] == [
    'plume.optical.spectral-ray-transfer@1',
    'plume.image.spectral-radiance@1',
  ]
  assert all(boundary['provider_ids'] == [] for boundary in boundaries)
  assert all(boundary['claim_status'] == 'not_accepted' for boundary in boundaries)
