"""Run fidelity-specific local acceptance checks for the current product lanes."""

from __future__ import annotations

import argparse
import json
from math import cos, exp, isclose, pi, sin
from pathlib import Path
import sys
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))

from exhaust_plume import (  # noqa: E402
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  Pose,
  SPECTRAL_RADIANT_INTENSITY_V1,
  SPECTRAL_RAY_TRANSFER_V1,
  SpectralRayTransferRequest,
  VISUAL_SECTIONED_TUBE_V1,
  VisualSampling,
  VisualSectionedTubeRequest,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.contracts import (  # noqa: E402
  SpectralSignatureRequest,
  run_visual_provider_conformance,
)
from exhaust_plume.geometry import SectionedTubeSupport, intersect_sectioned_tube  # noqa: E402
from exhaust_plume.radiation import FarFieldRayIntegration, far_field_from_rays  # noqa: E402
from exhaust_plume.providers import (  # noqa: E402
  GrayRayTransferDefinition,
  GrayRayTransferProvider,
  LookupInterpolationPolicy,
  SignatureTableDefinition,
  SignatureTableProvider,
  ShockCellVisualDefinition,
  ShockCellVisualOperatingState,
  ShockCellVisualProvider,
  StraightAnalyticalDefinition,
  StraightAnalyticalOperatingState,
  StraightAnalyticalProvider,
)
try:
  from scripts.validate_external_corpus_alignment import preflight_corpus  # noqa: E402
except ModuleNotFoundError:  # pragma: no cover - direct script execution
  from validate_external_corpus_alignment import preflight_corpus  # noqa: E402


def _fixture() -> dict[str, Any]:
  return json.loads(
    (REPO_ROOT / 'tests' / 'fixtures' / 'physics' / 'first_mvp_regression_v1.json').read_text(
      encoding='utf-8',
    )
  )


def _analytical_components(exit_to_ambient_pressure_ratio: float) -> tuple[Any, Any]:
  values = _fixture()['gas']
  gas = CaloricallyPerfectGas.dry_air(gamma=float(values['gamma']))
  factor = 1.0 + (gas.gamma - 1.0) * float(values['mach'])**2 / 2.0
  total_pressure = (
    float(values['ambient_pressure_Pa'])
    * exit_to_ambient_pressure_ratio
    * factor**(gas.gamma / (gas.gamma - 1.0))
  )
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=float(values['mach']),
      total_pressure_Pa=total_pressure,
      total_temperature_K=float(values['total_temperature_K']),
      exit_radius_m=float(values['exit_radius_m']),
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(
      pressure_Pa=float(values['ambient_pressure_Pa']),
      temperature_K=float(values['ambient_temperature_K']),
    ),
    gas,
  )
  return exit_state, ambient


def _analytical_state(exit_to_ambient_pressure_ratio: float) -> StraightAnalyticalOperatingState:
  exit_state, ambient = _analytical_components(exit_to_ambient_pressure_ratio)
  return StraightAnalyticalOperatingState(nozzle_exit=exit_state, ambient=ambient)


def _shock_cell_state(exit_to_ambient_pressure_ratio: float) -> ShockCellVisualOperatingState:
  exit_state, ambient = _analytical_components(exit_to_ambient_pressure_ratio)
  return ShockCellVisualOperatingState(nozzle_exit=exit_state, ambient=ambient)


def _visual_request(frame_id: str) -> VisualSectionedTubeRequest:
  return VisualSectionedTubeRequest(
    output_frame_id=frame_id,
    sampling=VisualSampling(
      maximum_section_count=16,
      maximum_axial_extent_m=8.0,
    ),
    requested_channels=('core_radius_fraction', 'opacity_weight'),
  )


def _run_visual_lane() -> dict[str, Any]:
  pose = Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  provider_specs = (
    (
      StraightAnalyticalProvider(),
      StraightAnalyticalDefinition(nozzle_radius_m=1.0),
      _analytical_state,
      'source-local',
    ),
    (
      ShockCellVisualProvider(),
      ShockCellVisualDefinition(nozzle_radius_m=1.0),
      _shock_cell_state,
      'straight-axisymmetric-xr',
    ),
  )
  provider_reports: list[dict[str, Any]] = []
  case_summaries: list[dict[str, Any]] = []
  for provider, definition, state_factory, frame_id in provider_specs:
    request = _visual_request(frame_id)
    for ratio in (1.0, 1.2, 0.85):
      state = state_factory(ratio)
      session = provider.create_session(definition=definition)
      snapshot = session.create_snapshot(
        time_s=0.0,
        source_pose=pose,
        dynamic_state={'operating_state': state},
        ambient_state={},
      )
      result = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, request)
      case_summaries.append({
        'exit_to_ambient_pressure_ratio': ratio,
        'section_count': len(result.sections),
        'output_channels': sorted(result.channels),
        'applicability': result.metadata.applicability.status.value,
        'provider_id': result.metadata.provenance.provider_id,
        'radiation_claim': result.metadata.claims.radiation.value,
      })

    conformance = run_visual_provider_conformance(
      provider.descriptor,
      lambda provider=provider, definition=definition, state_factory=state_factory, pose=pose: provider.create_session(
        definition=definition,
      ).create_snapshot(
        time_s=0.0,
        source_pose=pose,
        dynamic_state={'operating_state': state_factory(1.2)},
        ambient_state={},
      ),
      request,
    )
    provider_reports.append({
      'provider_id': provider.descriptor.provider_id,
      'contract_conformance': conformance.passed,
      'deterministic_serialization': conformance.deterministic_serialization,
      'output_channels': case_summaries[-1]['output_channels'],
    })
  all_conformant = all(report['contract_conformance'] for report in provider_reports)
  all_deterministic = all(report['deterministic_serialization'] for report in provider_reports)
  return {
    'lane_id': 'shock-cell-basic-v1',
    'product_id': VISUAL_SECTIONED_TUBE_V1.capability.wire_id,
    'provider_ids': [report['provider_id'] for report in provider_reports],
    'status': 'passed' if all_conformant and all_deterministic else 'failed',
    'contract_conformance': all_conformant,
    'deterministic_serialization': all_deterministic,
    'provider_reports': provider_reports,
    'cases': case_summaries,
    'external_comparison': {
      'status': 'pending',
      'reason': 'The current visual contract exposes geometry/display channels, while the recovered CJ gate requires explicit pressure/velocity/Mach feature operators.'
    },
    'claim_ceiling': 'Engineering-approximate straight visual geometry and named display features only.',
  }


def _signature_definition() -> SignatureTableDefinition:
  return SignatureTableDefinition(
    frame_id='source-local',
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    direction_cosine_nodes=(-0.5, 0.0, 0.5),
    spectral_radiant_intensity_w_sr_m=(
      (0.5, 1.5, 2.5),
      (1.0, 2.0, 3.0),
      (1.5, 2.5, 3.5),
    ),
    absolute_standard_uncertainty_w_sr_m=(
      (0.05, 0.05, 0.05),
      (0.1, 0.1, 0.1),
      (0.15, 0.15, 0.15),
    ),
    wavelength_interpolation=LookupInterpolationPolicy.LINEAR,
    angular_interpolation=LookupInterpolationPolicy.LINEAR,
  )


def _run_signature_lane() -> dict[str, Any]:
  provider = SignatureTableProvider()
  definition = _signature_definition()
  snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  result = snapshot.evaluate(
    SPECTRAL_RADIANT_INTENSITY_V1,
    SpectralSignatureRequest(
      direction_frame_id='source-local',
      source_to_observer_directions=((0.5, 3**0.5 / 2.0, 0.0),),
      wavelengths_m=(1.5e-6, 2.5e-6),
    ),
  )
  expected = ((2.0, 3.0),)
  contract_passed = result.spectral_radiant_intensity == expected and all(result.validity_mask[0])
  return {
    'lane_id': 'signature-table-mvp-v1',
    'product_id': SPECTRAL_RADIANT_INTENSITY_V1.capability.wire_id,
    'provider_id': provider.descriptor.provider_id,
    'status': 'passed' if contract_passed else 'failed',
    'contract_interpolation_passed': contract_passed,
    'output_shape': [len(result.spectral_radiant_intensity), len(result.spectral_radiant_intensity[0])],
    'output_units': 'W sr^-1 m^-1',
    'validity_mask': result.validity_mask,
    'radiation_claim': result.metadata.claims.radiation.value,
    'asset_source': 'repository synthetic contract fixture',
    'external_comparison': {
      'status': 'pending',
      'reason': 'Recovered spectral observations are sensor-space or relative-shape products and require explicit LOS/band operators before comparison to intrinsic J_lambda.'
    },
    'claim_ceiling': 'Versioned table and interpolation behavior only; no intrinsic physical validation claim.',
  }


def _gray_definition() -> GrayRayTransferDefinition:
  return GrayRayTransferDefinition(
    frame_id='sensor',
    support=SectionedTubeSupport(
      frame_id='sensor',
      centers_m=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
      radii_m=(1.0, 1.0),
    ),
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
    source_function_w_sr_m=(2.0, 4.0, 8.0),
    absorption_coefficient_per_m=(0.5, 1.0, 2.0),
  )


def _run_optical_lane() -> dict[str, Any]:
  provider = GrayRayTransferProvider()
  definition = _gray_definition()
  pose = Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0), (-2.0, 2.0, 0.0)),
    ray_directions=((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    ray_t_min_m=(0.0, 0.0),
    ray_t_max_m=(10.0, 10.0),
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
  )
  first_snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=pose,
    dynamic_state={},
    ambient_state={},
  )
  second_snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=pose,
    dynamic_state={},
    ambient_state={},
  )
  first = first_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  second = second_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  expected_transmittance = tuple(exp(-2.0 * coefficient) for coefficient in definition.absorption_coefficient_per_m)
  expected_source = tuple(
    source * (1.0 - transmission)
    for source, transmission in zip(definition.source_function_w_sr_m, expected_transmittance)
  )
  def curved_support(section_count: int) -> SectionedTubeSupport:
    centers = tuple(
      (
        5.0 * cos(index * pi / (2.0 * (section_count - 1))),
        5.0 * sin(index * pi / (2.0 * (section_count - 1))),
        0.0,
      )
      for index in range(section_count)
    )
    return SectionedTubeSupport(
      frame_id='sensor',
      centers_m=centers,
      radii_m=(0.4,) * section_count,
    )

  spatial_refinement_lengths = []
  for section_count in (3, 5, 9, 17):
    intervals = intersect_sectioned_tube(
      (-1.0, 2.5, 0.0),
      (1.0, 0.0, 0.0),
      curved_support(section_count),
      t_max_m=12.0,
    )
    spatial_refinement_lengths.append(sum(interval.t_exit_m - interval.t_enter_m for interval in intervals))
  straight_refinement_lengths = []
  for section_count in (2, 3, 5, 9):
    straight_support = SectionedTubeSupport(
      frame_id='sensor',
      centers_m=tuple((2.0 * index / (section_count - 1), 0.0, 0.0) for index in range(section_count)),
      radii_m=(1.0,) * section_count,
    )
    straight_intervals = intersect_sectioned_tube(
      (-2.0, 0.0, 0.0),
      (1.0, 0.0, 0.0),
      straight_support,
      t_max_m=10.0,
    )
    straight_refinement_lengths.append(sum(interval.t_exit_m - interval.t_enter_m for interval in straight_intervals))
  spatial_refinement_passed = all(isclose(length, 4.0, rel_tol=0.0, abs_tol=1.0e-12) for length in straight_refinement_lengths)
  coarse_request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0),),
    ray_directions=((1.0, 0.0, 0.0),),
    ray_t_min_m=(0.0,),
    ray_t_max_m=(10.0,),
    wavelengths_m=(1.0e-6, 3.0e-6),
  )
  fine_request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0),),
    ray_directions=((1.0, 0.0, 0.0),),
    ray_t_min_m=(0.0,),
    ray_t_max_m=(10.0,),
    wavelengths_m=(1.0e-6, 2.0e-6, 3.0e-6),
  )
  coarse = first_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, coarse_request)
  fine = first_snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, fine_request)
  spectral_endpoint_error = max(
    abs(coarse.source_spectral_radiance[0][index] - fine.source_spectral_radiance[0][2 * index])
    for index in (0, 1)
  )
  spectral_refinement_passed = spectral_endpoint_error <= 1.0e-12
  analytic_passed = (
    all(isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12) for actual, expected in zip(first.source_spectral_radiance[0], expected_source))
    and all(isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12) for actual, expected in zip(first.background_transmittance[0], expected_transmittance))
    and first.optical_depth is not None
    and all(isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-12) for actual, expected in zip(first.optical_depth[0], (1.0, 2.0, 4.0)))
    and first.hit_mask == (True, False)
  )
  return {
    'lane_id': 'optical-transfer-v1',
    'product_id': SPECTRAL_RAY_TRANSFER_V1.capability.wire_id,
    'provider_id': provider.descriptor.provider_id,
    'status': 'passed' if analytic_passed else 'failed',
    'analytic_slab_and_chord_passed': analytic_passed,
    'deterministic_serialization': first.model_dump(mode='json') == second.model_dump(mode='json'),
    'spatial_refinement': {
      'straight_section_counts': [2, 3, 5, 9],
      'straight_exact_chord_lengths_m': straight_refinement_lengths,
      'passed': spatial_refinement_passed,
      'curved_section_counts': [3, 5, 9, 17],
      'curved_capsule_path_lengths_m': spatial_refinement_lengths,
      'curved_status': 'nonmonotonic-observed-not-promoted',
      'note': 'the provider gate uses the exact straight cylinder; curved-support refinement is recorded as geometry-only evidence and is not advertised as converged',
    },
    'spectral_refinement': {
      'coarse_wavelength_count': 2,
      'fine_wavelength_count': 3,
      'endpoint_max_abs_delta': spectral_endpoint_error,
      'passed': spectral_refinement_passed,
      'note': 'linear property interpolation consistency, not chemistry or source-model validation',
    },
    'hit_mask': first.hit_mask,
    'intersection_intervals_m': first.plume_intersection_t_m,
    'radiation_claim': first.metadata.claims.radiation.value,
    'external_comparison': {
      'status': 'pending',
      'reason': 'The gray provider is analytically validated but the recovered external gates require sensor-space LOS, band, or path operators that are not yet implemented.',
    },
    'claim_ceiling': 'Homogeneous gray transfer through a straight constant-radius support only; no chemistry, atmosphere, detector, or FPA claim.',
  }


def _run_fpa_boundary() -> dict[str, Any]:
  matrix = json.loads((REPO_ROOT / 'docs' / 'solver_fidelity_matrix_v1.json').read_text(encoding='utf-8'))
  lanes = {lane['lane_id']: lane for lane in matrix['lanes']}
  fpa = lanes['focal-plane-array-v1']
  optical = lanes['optical-transfer-v1']
  passed = (
    fpa['provider_ids'] == []
    and optical['provider_ids'] == ['plume.gray-ray-transfer']
    and fpa['focal_plane_array'] == 'downstream-adapter'
    and 'plume.optical.spectral-ray-transfer@1' in fpa['requires']
    and 'detector-response-contract' in fpa['requires']
  )
  return {
    'lane_id': 'focal-plane-array-v1',
    'status': 'boundary-valid-not-implemented' if passed else 'failed',
    'provider_advertised': False,
    'ray_provider_prerequisite_present': optical['provider_ids'] != [],
    'ray_signature_adapter_present': True,
    'claim_ceiling': 'No FPA image, detector count, noise, or detection claim.',
  }


def _run_cross_product_consistency() -> dict[str, Any]:
  """Validate the bounded ray-to-signature operator with synthetic rays."""

  provider = GrayRayTransferProvider()
  definition = _gray_definition()
  pose = Pose(
    frame_id='world',
    translation_m=(0.0, 0.0, 0.0),
    rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
  )
  request = SpectralRayTransferRequest(
    ray_frame_id='sensor',
    ray_origins_m=((-2.0, 0.0, 0.0), (-2.0, 0.0, 0.0), (-2.0, 2.0, 0.0)),
    ray_directions=((1.0, 0.0, 0.0),) * 3,
    ray_t_min_m=(0.0, 0.0, 0.0),
    ray_t_max_m=(10.0, 10.0, 10.0),
    wavelengths_m=(1.5e-6, 2.5e-6),
  )
  snapshot = provider.create_session(definition=definition).create_snapshot(
    time_s=0.0,
    source_pose=pose,
    dynamic_state={},
    ambient_state={},
  )
  ray_result = snapshot.evaluate(SPECTRAL_RAY_TRANSFER_V1, request)
  integration = FarFieldRayIntegration(
    direction_frame_id='sensor',
    source_to_observer_directions=((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    ray_direction_indices=(0, 0, 1),
    ray_projected_area_weights_m2=(0.25, 0.75, 1.0),
  )
  first = far_field_from_rays(request, ray_result, integration)
  second = far_field_from_rays(request, ray_result, integration)
  expected = ray_result.source_spectral_radiance[0]
  integration_error = max(
    abs(actual - target)
    for actual, target in zip(first.spectral_radiant_intensity[0], expected, strict=True)
  )
  passed = (
    integration_error <= 1.0e-12
    and first.spectral_radiant_intensity[1] == (0.0, 0.0)
    and first.validity_mask == ((True, True), (True, True))
    and first.metadata.provenance.parent_result_ids == (ray_result.metadata.result_id,)
    and first.metadata.provenance.metadata['wavelength_grid_digest_sha256']
    and first.model_dump(mode='json') == second.model_dump(mode='json')
  )
  return {
    'lane_id': 'ray-to-signature-consistency-v1',
    'status': 'passed' if passed else 'failed',
    'adapter_id': 'plume.adapter.far-field-from-rays',
    'registry_operator_id': 'op.ray.projected-area-signature',
    'corpus_cross_product_rule_id': 'MVP-X-001',
    'external_adapter_id': 'adapter.far_field_from_rays@1',
    'operator_mapping_status': 'semantic-match-reviewed-for-synthetic-rule-only',
    'ray_provider_id': provider.descriptor.provider_id,
    'product_id': 'plume.signature.spectral-radiant-intensity@1',
    'orthographic_area_integration_passed': integration_error <= 1.0e-12,
    'miss_group_zero_passed': first.spectral_radiant_intensity[1] == (0.0, 0.0),
    'wavelength_grid_identity_preserved': bool(first.metadata.provenance.metadata['wavelength_grid_digest_sha256']),
    'snapshot_lineage_preserved': first.metadata.provenance.parent_result_ids == (ray_result.metadata.result_id,),
    'deterministic_serialization': first.model_dump(mode='json') == second.model_dump(mode='json'),
    'radiation_claim': first.metadata.claims.radiation.value,
    'claim_derivation': first.metadata.claims.derivation.value,
    'external_comparison': {
      'status': 'synthetic-only',
      'reason': 'The adapter operator is verified against a homogeneous gray ray fixture; recovered sensor-space comparisons remain blocked by missing operators and the unresolved external namespace crosswalk.',
    },
    'claim_ceiling': 'Synthetic orthographic ray-to-signature consistency only; no experimental signature, atmosphere, detector, image, or FPA claim.',
  }


def _external_summary(path: Path | None) -> dict[str, Any]:
  if path is None:
    return {'status': 'not-provided'}
  report = preflight_corpus(path)
  return {
    'status': report['status'],
    'archive': report['archive'],
    'content_counts': report.get('content_counts', {}),
    'gate_statuses': report.get('alignment', {}).get('validation_gate_statuses', {}),
    'operator_crosswalk_status': report.get('operator_reconciliation', {}).get('crosswalk_status'),
    'release_blockers': report.get('release_blockers', []),
  }


def _run_check(name: str, function: Callable[[], dict[str, Any]]) -> dict[str, Any]:
  try:
    return function()
  except Exception as error:  # pragma: no cover - failure report path
    return {
      'lane_id': name,
      'status': 'failed',
      'error_type': type(error).__name__,
      'error': str(error),
    }


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', type=Path)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  visual = _run_check('shock-cell-basic-v1', _run_visual_lane)
  signature = _run_check('signature-table-mvp-v1', _run_signature_lane)
  optical = _run_check('optical-transfer-v1', _run_optical_lane)
  cross_product = _run_check('ray-to-signature-consistency-v1', _run_cross_product_consistency)
  fpa = _run_check('focal-plane-array-v1', _run_fpa_boundary)
  local_passed = all(result['status'] in {'passed', 'boundary-valid-not-implemented'} for result in (visual, signature, optical, cross_product, fpa))
  report = {
    'report_id': 'exhaust-plume-product-lane-validation-v1',
    'local_status': 'passed' if local_passed else 'failed',
    'external_status': 'comparison-pending',
    'lanes': {
      'visual': visual,
      'signature': signature,
      'optical': optical,
      'cross_product': cross_product,
      'focal_plane_array': fpa,
    },
    'external_corpus': _external_summary(args.corpus),
    'release_ready': False,
  }
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if args.output is not None:
    args.output.write_text(serialized, encoding='utf-8')
  print(serialized, end='')
  return 0 if local_passed else 1


if __name__ == '__main__':
  raise SystemExit(main())
