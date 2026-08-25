"""Run fidelity-specific local acceptance checks for the current product lanes."""

from __future__ import annotations

import argparse
import json
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
from exhaust_plume.providers import (  # noqa: E402
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


def _run_fpa_boundary() -> dict[str, Any]:
  matrix = json.loads((REPO_ROOT / 'docs' / 'solver_fidelity_matrix_v1.json').read_text(encoding='utf-8'))
  lanes = {lane['lane_id']: lane for lane in matrix['lanes']}
  fpa = lanes['focal-plane-array-v1']
  optical = lanes['optical-transfer-v1']
  passed = (
    fpa['provider_ids'] == []
    and optical['provider_ids'] == []
    and fpa['focal_plane_array'] == 'downstream-adapter'
    and 'plume.optical.spectral-ray-transfer@1' in fpa['requires']
    and 'detector-response-contract' in fpa['requires']
  )
  return {
    'lane_id': 'focal-plane-array-v1',
    'status': 'boundary-valid-not-implemented' if passed else 'failed',
    'provider_advertised': False,
    'ray_provider_prerequisite_present': optical['provider_ids'] != [],
    'claim_ceiling': 'No FPA image, detector count, noise, or detection claim.',
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
  fpa = _run_check('focal-plane-array-v1', _run_fpa_boundary)
  local_passed = all(result['status'] in {'passed', 'boundary-valid-not-implemented'} for result in (visual, signature, fpa))
  report = {
    'report_id': 'exhaust-plume-product-lane-validation-v1',
    'local_status': 'passed' if local_passed else 'failed',
    'external_status': 'comparison-pending',
    'lanes': {
      'visual': visual,
      'signature': signature,
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
