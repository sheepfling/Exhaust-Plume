from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from exhaust_plume.contracts import ProductOutsideApplicabilityError, SpectralSignatureRequest, TimeModel
from exhaust_plume.products.signature import (
  evaluate_signature_table_asset,
  load_signature_table_asset,
  load_spectral_signature_request,
  render_signature_plots,
  write_signature_result_csv,
  write_signature_result_json,
  write_signature_table_asset,
)
from exhaust_plume.providers import SignatureTableConfiguration

ROOT = Path(__file__).resolve().parents[3]


def test_signature_mvp_loads_queries_and_exports(tmp_path: Path) -> None:
  asset_path = ROOT / 'fixtures/products/signature_asset_v1.json'
  definition = load_signature_table_asset(asset_path)
  request = load_spectral_signature_request(ROOT / 'fixtures/products/signature_request_v1.json')
  result = evaluate_signature_table_asset(definition, request)

  assert definition.operating_point_id == 'reference-atmosphere'
  assert definition.ambient_pressure_Pa == 101325.0
  assert definition.asset_sha256 is not None
  assert definition.asset_sha256 == hashlib.sha256(asset_path.read_bytes()).hexdigest()
  assert request.operating_point_id == definition.operating_point_id
  assert result.metadata.claims.radiation.value == 'tabulated'
  assert result.spectral_radiant_intensity == (
    (0.5, 1.5, 2.5),
    (1.0, 2.0, 3.0),
    (1.5, 2.5, 3.5),
  )
  assert result.metadata.provenance.asset_digests_sha256
  assert result.metadata.provenance.asset_digests_sha256 == (definition.asset_sha256,)
  assert result.metadata.provenance.metadata['extrapolation_policy'] == 'reject'
  assert write_signature_result_json(result, tmp_path / 'result.json').is_file()
  csv_path = write_signature_result_csv(definition, request, result, tmp_path / 'result.csv')
  assert csv_path.read_text(encoding='utf-8').count('\n') == 10
  round_trip = write_signature_table_asset(definition, tmp_path / 'asset.json')
  assert load_signature_table_asset(round_trip) == definition


def test_signature_mvp_renders_spectral_and_angular_views(tmp_path: Path) -> None:
  import matplotlib
  matplotlib.use('Agg')

  definition = load_signature_table_asset(ROOT / 'fixtures/products/signature_asset_v1.json')
  request = load_spectral_signature_request(ROOT / 'fixtures/products/signature_request_v1.json')
  result = evaluate_signature_table_asset(definition, request)
  paths = render_signature_plots(definition, request, result, tmp_path)

  assert tuple(path.name for path in paths) == (
    'signature_spectrum.png',
    'signature_angular.png',
    'signature_heatmap.png',
  )
  assert all(path.read_bytes().startswith(b'\x89PNG') for path in paths)


def test_signature_mvp_supports_time_slices_and_explicit_operating_points() -> None:
  definition = load_signature_table_asset(ROOT / 'fixtures/products/signature_time_asset_v1.json')
  request = SpectralSignatureRequest(
    direction_frame_id='source-local',
    operating_point_id='low-ambient-pressure',
    source_to_observer_directions=((0.0, 1.0, 0.0),),
    wavelengths_m=(1.5e-6,),
  )
  result = evaluate_signature_table_asset(
    definition,
    request,
    configuration=SignatureTableConfiguration(time_model=TimeModel.PRESCRIBED_TRANSIENT),
    time_s=0.5,
  )
  assert result.spectral_radiant_intensity[0][0] == pytest.approx(3.0)
  assert result.absolute_standard_uncertainty is not None
  assert result.absolute_standard_uncertainty[0][0] == pytest.approx(0.25)
  assert definition.ambient_pressure_Pa == 0.01
  assert result.metadata.provenance.metadata['interpolation_time'] == 'linear'

  with pytest.raises(ProductOutsideApplicabilityError, match='operating point'):
    evaluate_signature_table_asset(
      definition,
      request.model_copy(update={'operating_point_id': 'another-operating-point'}),
      configuration=SignatureTableConfiguration(time_model=TimeModel.PRESCRIBED_TRANSIENT),
      time_s=0.5,
    )
