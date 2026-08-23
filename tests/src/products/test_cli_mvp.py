from __future__ import annotations

from pathlib import Path

from exhaust_plume.products.signature_cli import main as signature_main
from exhaust_plume.products.visual_cli import main as visual_main
from exhaust_plume.validation.cli import main as validity_main

ROOT = Path(__file__).resolve().parents[3]


def test_visual_cli_writes_file_driven_outputs(tmp_path: Path) -> None:
  output_dir = tmp_path / 'visual'
  assert visual_main([
    '--config', str(ROOT / 'fixtures/products/visual_asset_v1.json'),
    '--output-dir', str(output_dir),
    '--channel', 'core_radius_fraction',
    '--no-preview',
  ]) == 0
  assert (output_dir / 'visual_result.json').is_file()
  assert (output_dir / 'visual_mesh.json').is_file()
  assert (output_dir / 'visual_mesh.obj').is_file()
####


def test_signature_cli_writes_file_driven_outputs(tmp_path: Path) -> None:
  output_dir = tmp_path / 'signature'
  assert signature_main([
    '--asset', str(ROOT / 'fixtures/products/signature_asset_v1.json'),
    '--request', str(ROOT / 'fixtures/products/signature_request_v1.json'),
    '--output-dir', str(output_dir),
    '--no-plots',
  ]) == 0
  assert (output_dir / 'signature_result.json').is_file()
  assert (output_dir / 'signature_result.csv').is_file()
####


def test_signature_cli_accepts_prescribed_time_slices(tmp_path: Path) -> None:
  output_dir = tmp_path / 'signature-time'
  assert signature_main([
    '--asset', str(ROOT / 'fixtures/products/signature_time_asset_v1.json'),
    '--request', str(ROOT / 'fixtures/products/signature_time_request_v1.json'),
    '--output-dir', str(output_dir),
    '--time-s', '0.5',
    '--time-model', 'prescribed_transient',
    '--no-plots',
  ]) == 0
  assert (output_dir / 'signature_result.json').is_file()
  assert (output_dir / 'signature_result.csv').is_file()
####


def test_validity_cli_writes_pressure_matrix_outputs(tmp_path: Path) -> None:
  output_dir = tmp_path / 'validity'
  assert validity_main(['--output-dir', str(output_dir)]) == 0
  assert (output_dir / 'validity_report.json').is_file()
  assert (output_dir / 'validity_report.csv').is_file()
####
