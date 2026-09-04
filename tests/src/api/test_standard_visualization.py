from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

import pytest

from exhaust_plume.api import (
  ENGINEERING_FLUX_SECTION_V1,
  OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
  SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
  Applicability,
  FidelityClaim,
  FrameRef,
  ItemStatus,
  ModelFidelity,
  PlumeFluxSection,
  PlumeFluxSectionGlyph,
  PlumeFluxSectionResult,
  Pose3,
  ProductResult,
  ProductVisualizationData,
  Provenance,
  ResultEnvelope,
  ResultStatus,
  SectionedTubeLineData,
  SectionedTubeResult,
  SpectralRadiantIntensityGrid,
  SpectralRadiantIntensityPayload,
  SpectralRadiantIntensityResult,
  SpectralRayTransferData,
  SpectralRayTransferLine,
  SpectralRayTransferPayload,
  SpectralRayTransferResult,
  ValidationLevel,
  extract_plume_flux_section_glyph,
  extract_product_visualization_data,
  extract_spectral_radiant_intensity_grid,
  extract_spectral_radiant_intensity_lines,
  extract_spectral_ray_transfer_data,
  extract_spectral_ray_transfer_lines,
)

ROOT = Path(__file__).resolve().parents[3]


def _frame() -> FrameRef:
  return FrameRef(
    frame_id='aircraft-body',
    parent_frame_id=None,
    pose_parent_from_frame=Pose3(
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
  )
####


def _envelope(capability_id: str) -> ResultEnvelope:
  return ResultEnvelope(
    capability_id=capability_id,
    schema_version='1.0.0',
    provider_id=uuid4(),
    session_id=uuid4(),
    snapshot_id=uuid4(),
    content_sha256='1' * 64,
    requested_time_s=0.0,
    actual_time_s=0.0,
    frame=_frame(),
    status=ResultStatus.OK,
    fidelity=FidelityClaim(
      model_fidelity=ModelFidelity.PRESCRIBED,
      validation_level=ValidationLevel.VERIFIED,
    ),
    applicability=Applicability(supported=True),
    provenance=Provenance(
      model_id='visualization-test',
      model_version='1.0.0',
      code_revision='test',
      configuration_sha256='2' * 64,
    ),
  )
####


def _signature_result() -> SpectralRadiantIntensityResult:
  payload = SpectralRadiantIntensityPayload(
    directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    wavelengths_m=(3.0e-6, 5.0e-6),
    radiant_intensity_W_sr_m=((1.0, None), (0.5, 0.25)),
    validity_mask=((True, False), (True, True)),
    uncertainty={'source': 'synthetic'},
  )
  return SpectralRadiantIntensityResult(
    envelope=_envelope(SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1),
    payload=payload,
  )
####


def _ray_transfer_result() -> SpectralRayTransferResult:
  payload = SpectralRayTransferPayload(
    ray_ids=('ray-1', 'ray-2'),
    origins_m=((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    wavelengths_m=(3.0e-6, 5.0e-6),
    source_radiance_W_m2_sr_m=((1.0, None), (0.0, 2.0)),
    background_transmittance=((0.8, None), (1.0, 0.5)),
    validity_mask=((True, False), (True, True)),
    item_status=(ItemStatus.OK, ItemStatus.OK),
  )
  return SpectralRayTransferResult(
    envelope=_envelope(OPTICAL_SPECTRAL_RAY_TRANSFER_V1),
    payload=payload,
  )
####


def _flux_result() -> PlumeFluxSectionResult:
  payload = PlumeFluxSection(
    time_s=4.0,
    frame=_frame(),
    section_pose=Pose3(
      translation_m=(1.0, 2.0, 3.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    normal=(1.0, 0.0, 0.0),
    area_m2=0.2,
    mass_flow_kgps=1.5,
    momentum_flux_N=(60.0, 2.0, 3.0),
    total_energy_flow_W=8.0e5,
    species_mass_flows_kgps=(
      {'species_id': 'exhaust', 'mass_flow_kgps': 1.5},
      {'species_id': 'air', 'mass_flow_kgps': 0.2},
    ),
    pressure_Pa=101325.0,
    ambient_pressure_Pa=101325.0,
    pressure_match_relative_residual=0.0,
    cross_section_second_moment_m2=((0.01, 0.0), (0.0, 0.02)),
    provenance=Provenance(
      model_id='visualization-test',
      model_version='1.0.0',
      code_revision='test',
      configuration_sha256='3' * 64,
    ),
    applicability=Applicability(supported=True),
  )
  return PlumeFluxSectionResult(
    envelope=_envelope(ENGINEERING_FLUX_SECTION_V1),
    payload=payload,
  )
####


def _visual_result() -> SectionedTubeResult:
  fixture_path = ROOT / 'tests' / 'fixtures' / 'sectioned_tube_washed_v1.json'
  return SectionedTubeResult.model_validate_json(fixture_path.read_text(encoding='utf-8'))
####


def test_signature_visualization_preserves_wavelength_grid_and_validity() -> None:
  result = _signature_result()

  grid = extract_spectral_radiant_intensity_grid(result)
  lines = extract_spectral_radiant_intensity_lines(result, direction_index=0)

  assert isinstance(grid, SpectralRadiantIntensityGrid)
  assert grid.frame_id == 'aircraft-body'
  assert grid.wavelengths_m == (3.0e-6, 5.0e-6)
  assert grid.radiant_intensity_W_sr_m[0] == (1.0, None)
  assert grid.validity_mask[0] == (True, False)
  assert len(lines) == 1
  assert lines[0].direction == (1.0, 0.0, 0.0)
  assert lines[0].values_W_sr_m == (1.0, None)
  assert lines[0].validity_mask == (True, False)
####


def test_ray_transfer_visualization_keeps_ray_geometry_and_separate_fields() -> None:
  result = _ray_transfer_result()

  data = extract_spectral_ray_transfer_data(result, ray_id='ray-2')
  line = extract_spectral_ray_transfer_lines(result, ray_id='ray-1')[0]

  assert isinstance(data, SpectralRayTransferData)
  assert data.frame_id == 'aircraft-body'
  assert data.wavelengths_m == (3.0e-6, 5.0e-6)
  assert len(data.lines) == 1
  assert data.lines[0].ray_id == 'ray-2'
  assert isinstance(line, SpectralRayTransferLine)
  assert line.origin_m == (0.0, 0.0, 0.0)
  assert line.direction == (1.0, 0.0, 0.0)
  assert line.source_radiance_W_m2_sr_m == (1.0, None)
  assert line.background_transmittance == (0.8, None)
  assert line.validity_mask == (True, False)
  assert line.item_status is ItemStatus.OK
####


def test_flux_visualization_preserves_vector_scalar_and_species_glyph_data() -> None:
  result = _flux_result()

  glyph = extract_plume_flux_section_glyph(result)

  assert isinstance(glyph, PlumeFluxSectionGlyph)
  assert glyph.frame_id == 'aircraft-body'
  assert glyph.section_frame_id == 'aircraft-body'
  assert glyph.section_translation_m == (1.0, 2.0, 3.0)
  assert glyph.normal == (1.0, 0.0, 0.0)
  assert glyph.momentum_flux_N == (60.0, 2.0, 3.0)
  assert glyph.species_mass_flows_kgps == (('exhaust', 1.5), ('air', 0.2))
  assert glyph.cross_section_second_moment_m2 == ((0.01, 0.0), (0.0, 0.02))
####


@pytest.mark.parametrize(
  ('result_factory', 'expected_type'),
  (
    (_visual_result, SectionedTubeLineData),
    (_signature_result, SpectralRadiantIntensityGrid),
    (_ray_transfer_result, SpectralRayTransferData),
    (_flux_result, PlumeFluxSectionGlyph),
  ),
)
def test_product_visualization_dispatcher_keeps_product_specific_types(
  result_factory: Callable[[], ProductResult],
  expected_type: type[ProductVisualizationData],
) -> None:
  data = extract_product_visualization_data(result_factory())
  assert isinstance(data, expected_type)
####


def test_product_visualization_rejects_failed_results_and_unknown_rays() -> None:
  result = _signature_result()
  failed = SpectralRadiantIntensityResult(
    envelope=result.envelope.model_copy(update={'status': ResultStatus.FAILED}),
    payload=result.payload,
  )

  with pytest.raises(ValueError, match='FAILED'):
    extract_product_visualization_data(failed)
  ####
  with pytest.raises(KeyError, match='unknown ray_id'):
    extract_spectral_ray_transfer_lines(_ray_transfer_result(), ray_id='missing')
  ####
  with pytest.raises(IndexError, match='direction_index'):
    extract_spectral_radiant_intensity_lines(result, direction_index=10)
  ####
####
