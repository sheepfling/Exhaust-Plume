"""Generate the additive downstream FPA detector-frame schema and example."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from exhaust_plume.contracts.fpa_detector_v1 import (
  FPA_DIGITIZATION_OPERATOR_ID,
  FPA_PIXEL_DETECTOR_OPERATOR_ID,
  FPA_POINT_SPREAD_OPERATOR_ID,
  FpaCameraOpticsContract,
  FpaDetectorFrameResult,
  FpaDetectorResponseContract,
  FpaDetectorSourceReference,
  FpaDigitizationPolicyContract,
  FpaPointSpreadFunctionContract,
  fpa_measurement_operator_digest,
)
from exhaust_plume.contracts.common_v1 import canonical_digest


def detector_frame_fixture() -> FpaDetectorFrameResult:
  """Return a deterministic contract example, not validation evidence."""

  psf_payload = {
    'model_id': 'fixture-delta-psf-v1',
    'kernel_weights': ((1.0,),),
    'spectral_scope': 'achromatic',
    'edge_policy': 'mask-incomplete-support',
  }
  digitization_policy = FpaDigitizationPolicyContract(
    policy_id='fixture-adc',
    electrons_per_count=1.0,
    offset_counts=0.0,
    bit_depth=12,
    rounding_mode='nearest_even',
    saturation_mode='clip',
    invalid_count=0,
  )
  detector = FpaDetectorResponseContract(
    response_id='fixture-detector',
    wavelengths_m=(1.0e-6, 2.0e-6),
    quantum_efficiency=(0.5, 0.6),
    optical_throughput=(0.8, 0.9),
    dark_current_e_per_s=2.0,
    read_noise_std_e=2.0,
  )
  return FpaDetectorFrameResult(
    source=FpaDetectorSourceReference(
      capability_id='plume.optical.spectral-ray-transfer@1',
      schema_version='1.0.0',
      provider_id='fixture-provider',
      session_id='fixture-session',
      snapshot_id='fixture-snapshot',
      source_time_s=5.0,
      content_sha256='a' * 64,
      frame_id='fixture-ray-frame',
      source_status='inside',
      source_fidelity={'radiation': 'engineering-approximate'},
      source_applicability={'supported': True, 'status': 'inside'},
      source_provenance={'fixture': 'synthetic-contract-example'},
      operator_chain=(FPA_PIXEL_DETECTOR_OPERATOR_ID,),
    ),
    source_times_s=(5.0,),
    digitization_operator_id=FPA_DIGITIZATION_OPERATOR_ID,
    operator_input_sha256='b' * 64,
    digitization_input_sha256=canonical_digest({
      'operator_id': FPA_DIGITIZATION_OPERATOR_ID,
      'pixel_operator_input_sha256': 'b' * 64,
      'expected_electrons_e': ((16.0,),),
      'validity_mask': ((True,),),
      'digitization_policy': digitization_policy,
    }),
    pixel_geometry_sha256='c' * 64,
    measurement_operator_sha256=fpa_measurement_operator_digest(
      pixel_operator_id=FPA_PIXEL_DETECTOR_OPERATOR_ID,
      temporal_operator_id=None,
      pixel_geometry_sha256='c' * 64,
      wavelengths_m=(1.0e-6, 2.0e-6),
      exposure_s=3.0,
      detector_response=detector,
    ),
    point_spread_operator_id=FPA_POINT_SPREAD_OPERATOR_ID,
    width_px=1,
    height_px=1,
    exposure_s=3.0,
    wavelengths_m=(1.0e-6, 2.0e-6),
    expected_electrons_e=((16.0,),),
    dark_electrons_e=((6.0,),),
    noise_variance_e2=((20.0,),),
    validity_mask=((True,),),
    detector=detector,
    camera_optics_id='fixture-camera',
    camera_mapping_model_id='fixture-mapping-v1',
    camera_optics=FpaCameraOpticsContract(
      camera_id='fixture-camera',
      focal_length_m=0.05,
      pixel_pitch_m=(5.0e-6, 5.0e-6),
      principal_point_px=(0.5, 0.5),
      aperture_area_m2=1.0e-4,
      mapping_model_id='fixture-mapping-v1',
      point_spread_function=FpaPointSpreadFunctionContract(
        **psf_payload,
        digest_sha256=canonical_digest(psf_payload),
      ),
    ),
    digitization_policy=digitization_policy,
    digitized_counts=((16,),),
    digitized_validity_mask=((True,),),
    saturated_mask=((False,),),
    source_semantics='source-only',
  )
####


def generate_assets(
    schema_path: str | Path,
    fixture_path: str | Path,
    manifest_path: str | Path,
) -> tuple[Path, Path, Path]:
  schema_output = Path(schema_path)
  fixture_output = Path(fixture_path)
  manifest_output = Path(manifest_path)
  schema_output.parent.mkdir(parents=True, exist_ok=True)
  fixture_output.parent.mkdir(parents=True, exist_ok=True)
  manifest_output.parent.mkdir(parents=True, exist_ok=True)
  schema_bytes = (
    json.dumps(FpaDetectorFrameResult.model_json_schema(), indent=2, sort_keys=True) + '\n'
  ).encode('utf-8')
  fixture_bytes = (
    json.dumps(detector_frame_fixture().model_dump(mode='json'), indent=2, sort_keys=True) + '\n'
  ).encode('utf-8')
  schema_output.write_bytes(schema_bytes)
  fixture_output.write_bytes(fixture_bytes)
  manifest = {
    'contract_id': 'plume.fpa.detector-frame@1',
    'fixture': {
      'file': fixture_output.name,
      'sha256': hashlib.sha256(fixture_bytes).hexdigest(),
      'synthetic': True,
    },
    'generator': 'scripts/generate_fpa_detector_contract_assets.py',
    'manifest_version': 'exhaust-plume-fpa-detector-frame-assets-v1',
    'schema': {
      'dialect': 'https://json-schema.org/draft/2020-12/schema',
      'file': schema_output.name,
      'sha256': hashlib.sha256(schema_bytes).hexdigest(),
    },
  }
  manifest_output.write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + '\n',
    encoding='utf-8',
  )
  return schema_output, fixture_output, manifest_output
####


def main() -> None:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--schema', default='schemas/fpa_detector_frame_v1.schema.json')
  parser.add_argument('--fixture', default='fixtures/contracts/fpa_detector_frame_v1.json')
  parser.add_argument('--manifest', default='schemas/fpa_detector_contract_manifest_v1.json')
  arguments = parser.parse_args()
  for path in generate_assets(arguments.schema, arguments.fixture, arguments.manifest):
    print(path)
  ####
####


if __name__ == '__main__':
  main()
####
