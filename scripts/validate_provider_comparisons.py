"""Record provider-specific validation comparability for the recovered corpus."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any, Mapping
from zipfile import ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / 'src') not in sys.path:
  sys.path.insert(0, str(REPO_ROOT / 'src'))

try:
  from scripts.validate_external_corpus_alignment import (
    _read_csv,
    _read_json,
    preflight_corpus,
  )
  from scripts.validate_product_lanes import (
    _run_fpa_boundary,
    _run_optical_lane,
    _run_signature_lane,
    _run_visual_lane,
  )
  from exhaust_plume.validation.spectral_comparisons import compare_peak_normalized_spectral_shape
  from exhaust_plume.validation.visual_comparisons import MACH_DISK_FEATURE_OPERATOR_ID
except ModuleNotFoundError:  # pragma: no cover - direct script execution
  from validate_external_corpus_alignment import _read_csv, _read_json, preflight_corpus
  from validate_product_lanes import _run_fpa_boundary, _run_optical_lane, _run_signature_lane, _run_visual_lane
  from exhaust_plume.validation.spectral_comparisons import compare_peak_normalized_spectral_shape
  from exhaust_plume.validation.visual_comparisons import MACH_DISK_FEATURE_OPERATOR_ID


VISUAL_PRODUCT = 'plume.visual.sectioned-tube@1'
SIGNATURE_PRODUCT = 'plume.signature.spectral-radiant-intensity@1'
RAY_PRODUCT = 'plume.optical.spectral-ray-transfer@1'


def _summarize_csv(
    archive: ZipFile,
    relative_path: str,
    *,
    categorical_fields: tuple[str, ...] = (),
) -> dict[str, Any]:
  rows = _read_csv(archive, relative_path)
  columns = tuple(sorted(rows[0])) if rows else ()
  return {
    'relative_path': relative_path,
    'row_count': len(rows),
    'columns': list(columns),
    'categorical_values': {
      field: sorted({row.get(field, '') for row in rows})
      for field in categorical_fields
    },
    'uncertainty_fields': [field for field in columns if 'uncertainty' in field],
  }


def _summarize_metadata(metadata: Mapping[str, Any]) -> dict[str, Any]:
  source = metadata.get('source')
  source_summary = dict(source) if isinstance(source, dict) else {}
  for key in ('source_id', 'source_url', 'source_pdf_sha256'):
    if key in metadata:
      source_summary[key] = metadata[key]
  return {
    'benchmark_id': metadata.get('benchmark_id'),
    'source': source_summary,
    'evidence_limits': list(metadata.get('evidence_limits', ())),
    'validation_role': metadata.get('validation_role'),
  }


def summarize_corpus_observations(archive: ZipFile) -> dict[str, Any]:
  """Summarize available observation shapes without copying raw observations."""

  return {
    'CJ-UEJ-001': {
      'metadata': _summarize_metadata(_read_json(archive, 'data/cj_uej_001_metadata.json')),
      'profiles': _summarize_csv(
        archive,
        'data/cj_uej_001_profiles.csv',
        categorical_fields=('observable', 'measurement_kind', 'profile_id'),
      ),
      'mach_estimates': _summarize_csv(
        archive,
        'data/cj_uej_001_mach_estimates.csv',
        categorical_fields=('method', 'measurement_kind', 'profile_id'),
      ),
    },
    'RP-HOTWAKE-001': {
      'metadata': _summarize_metadata(_read_json(archive, 'data/rp_hotwake_001_metadata.json')),
      'mach_disk_relation': _summarize_csv(
        archive,
        'data/rp_hotwake_001_mach_disk_pressure_relation.csv',
        categorical_fields=('temporal_order_available', 'measurement_kind', 'run_id'),
      ),
      'frequency_features': _summarize_csv(
        archive,
        'data/rp_hotwake_001_frequency_features.csv',
        categorical_fields=('diagnostic', 'mode_name', 'symmetry'),
      ),
    },
    'RP-BSUV2-001': {
      'metadata': _summarize_metadata(_read_json(archive, 'data/rp_bsuv2_001_metadata.json')),
      'spectral_radiance': _summarize_csv(
        archive,
        'data/rp_bsuv2_001_uv_spectral_radiance.csv',
        categorical_fields=('measurement_kind', 'evidence_layer', 'quality_flag'),
      ),
    },
    'RP-EMAP-RAD-001': {
      'metadata': _summarize_metadata(_read_json(archive, 'data/rp_emap_rad_001_metadata.json')),
      'uvvis_relative_spectrum': _summarize_csv(
        archive,
        'data/rp_emap_rad_001_uvvis_relative_spectrum.csv',
        categorical_fields=('measurement_kind', 'evidence_layer'),
      ),
      'ftir_relative_envelopes': _summarize_csv(
        archive,
        'data/rp_emap_rad_001_ftir_relative_envelopes.csv',
        categorical_fields=('measurement_kind', 'evidence_layer'),
      ),
      'gardon_time_history': _summarize_csv(
        archive,
        'data/rp_emap_rad_001_gardon_time_history.csv',
        categorical_fields=('measurement_kind', 'evidence_layer'),
      ),
    },
    'RP-ALSI-001': {
      'metadata': _summarize_metadata(_read_json(archive, 'data/rp_alsi_001_metadata.json')),
      'thermal_comparison': _summarize_csv(
        archive,
        'data/rp_alsi_001_thermal_comparison.csv',
        categorical_fields=('measurement_kind', 'evidence_layer'),
      ),
    },
  }


def _local_provider_inventory() -> dict[str, Any]:
  visual = _run_visual_lane()
  signature = _run_signature_lane()
  optical = _run_optical_lane()
  fpa = _run_fpa_boundary()
  visual_channels = sorted({
    channel
    for provider in visual['provider_reports']
    for channel in provider['output_channels']
  })
  return {
    'visual': {
      'lane_id': visual['lane_id'],
      'provider_ids': visual['provider_ids'],
      'output_channels': visual_channels,
      'status': visual['status'],
      'claim_ceiling': visual['claim_ceiling'],
    },
    'signature': {
      'lane_id': signature['lane_id'],
      'provider_id': signature['provider_id'],
      'output_units': signature['output_units'],
      'output_shape': signature['output_shape'],
      'status': signature['status'],
      'asset_source': signature['asset_source'],
      'claim_ceiling': signature['claim_ceiling'],
      'measurement_space_operator_ids': signature['measurement_space_operators']['operator_ids'],
      'measurement_space_operator_status': signature['measurement_space_operators']['status'],
      'wavelength_domain_m': [
        min(signature['wavelengths_m']),
        max(signature['wavelengths_m']),
      ],
      'measurement_probe': signature['measurement_probe'],
    },
    'optical': {
      'provider_ids': [optical['provider_id']],
      'status': optical['status'],
      'claim_ceiling': optical['claim_ceiling'],
      'analytic_transfer_passed': optical['analytic_slab_and_chord_passed'],
      'output_fields': [
        'source_spectral_radiance',
        'background_transmittance',
        'optical_depth',
      ],
      'wavelength_domain_m': [
        min(optical['wavelengths_m']),
        max(optical['wavelengths_m']),
      ],
      'measurement_probe': optical['measurement_probe'],
    },
    'focal_plane_array': {
      'provider_ids': [],
      'status': fpa['status'],
      'claim_ceiling': fpa['claim_ceiling'],
    },
  }


def _read_spectral_curve(
    archive: ZipFile,
    relative_path: str,
    *,
    wavelength_field: str,
    wavelength_scale: float,
    value_field: str,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
  rows = _read_csv(archive, relative_path)
  wavelengths = tuple(float(row[wavelength_field]) * wavelength_scale for row in rows)
  values = tuple(float(row[value_field]) for row in rows)
  return wavelengths, values


def _not_executed(reason: str) -> dict[str, Any]:
  return {
    'status': 'not-executed',
    'reason': reason,
  }


def execute_visual_feature_probe(
    observations: Mapping[str, Any],
    providers: Mapping[str, Any],
) -> dict[str, Any]:
  """Record whether the visual Mach-disk feature contract can execute."""

  observed = observations['RP-HOTWAKE-001']['mach_disk_relation']
  available_outputs = list(providers['visual']['output_channels'])
  required_outputs = ['mach_disk_position_m', 'operating_pressure_or_branch_id']
  missing_outputs = [output for output in required_outputs if output not in available_outputs]
  observed_columns = list(observed.get('columns', []))
  return {
    'operator_id': MACH_DISK_FEATURE_OPERATOR_ID,
    'status': 'blocked-missing-provider-feature' if missing_outputs else 'not-executed-provider-sample-not-bound',
    'claim_status': 'not_accepted',
    'comparison_method': 'branch-aware-no-extrapolation',
    'available_provider_outputs': available_outputs,
    'required_provider_outputs': required_outputs,
    'missing_provider_outputs': missing_outputs,
    'observed_point_count': observed.get('row_count', 0),
    'observed_columns': observed_columns,
    'observed_branch_id_field_present': 'branch_id' in observed_columns,
    'reason': (
      'current visual providers do not emit a Mach-disk feature and operating-branch channel'
      if missing_outputs else
      'provider inventory has the feature names but no bound pressure/feature sample arrays'
    ),
  }


def execute_spectral_shape_probes(path: Path, providers: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
  """Run domain/shape diagnostics against recovered spectral curves.

  These probes use the current synthetic provider fixtures only to expose
  coverage and metric behavior.  They never change a comparison's blocked or
  claim-status fields and therefore cannot promote a scenario-mismatched
  fixture into external validation.
  """

  with ZipFile(path) as archive:
    bsuv2 = _read_spectral_curve(
      archive,
      'data/rp_bsuv2_001_uv_spectral_radiance.csv',
      wavelength_field='wavelength_um',
      wavelength_scale=1.0e-6,
      value_field='spectral_radiance_w_m2_sr_m',
    )
    uvvis = _read_spectral_curve(
      archive,
      'data/rp_emap_rad_001_uvvis_relative_spectrum.csv',
      wavelength_field='wavelength_nm',
      wavelength_scale=1.0e-9,
      value_field='relative_intensity_recommended',
    )
    ftir = _read_spectral_curve(
      archive,
      'data/rp_emap_rad_001_ftir_relative_envelopes.csv',
      wavelength_field='wavelength_nm',
      wavelength_scale=1.0e-9,
      value_field='relative_intensity_recommended',
    )
  signature_probe = providers['signature']['measurement_probe']
  optical_probe = providers['optical']['measurement_probe']
  optical_model = {
    'wavelengths_m': optical_probe['wavelengths_m'],
    'values': optical_probe['source_spectral_radiance_w_m2_sr_m'],
  }

  def run(model: Mapping[str, Any], observed: tuple[tuple[float, ...], tuple[float, ...]]) -> dict[str, Any]:
    result = compare_peak_normalized_spectral_shape(
      model['wavelengths_m'],
      model['values'],
      observed[0],
      observed[1],
    )
    return asdict(result)

  return {
    'VIS-MVP-A-061': _not_executed(
      'visual Mach-disk feature extraction is not a spectral-shape comparison',
    ),
    'SIG-MVP-A-043': run(
      {
        'wavelengths_m': signature_probe['wavelengths_m'],
        'values': signature_probe['spectral_radiant_intensity_w_sr_m'],
      },
      bsuv2,
    ),
    'SIG-MVP-A-064': run(
      {
        'wavelengths_m': signature_probe['wavelengths_m'],
        'values': signature_probe['spectral_radiant_intensity_w_sr_m'],
      },
      uvvis,
    ),
    'SIG-MVP-A-066': run(
      {
        'wavelengths_m': signature_probe['wavelengths_m'],
        'values': signature_probe['spectral_radiant_intensity_w_sr_m'],
      },
      ftir,
    ),
    'SIG-MVP-A-073': _not_executed(
      'ALSI corpus record is a band-integrated thermal table without a spectral curve',
    ),
    'RAY-MVP-A-044': run(optical_model, bsuv2),
    'RAY-MVP-A-065': run(optical_model, uvvis),
    'RAY-MVP-A-067': run(optical_model, ftir),
    'RAY-MVP-A-068': _not_executed(
      'Gardon corpus record is a time history without a spectral curve',
    ),
    'RAY-MVP-A-074': _not_executed(
      'ALSI corpus record is a band-integrated thermal table without a spectral curve',
    ),
  }


def _comparison(
    *,
    comparison_id: str,
    product_id: str,
    provider_ids: list[str],
    benchmark_id: str,
    alignment_id: str,
    measurement_operator_id: str,
    metric_ids: list[str],
    observed_data: Mapping[str, Any],
    available_provider_outputs: list[str],
    required_provider_outputs: list[str],
    blockers: list[str],
) -> dict[str, Any]:
  return {
    'comparison_id': comparison_id,
    'product_id': product_id,
    'provider_ids': provider_ids,
    'benchmark_id': benchmark_id,
    'alignment_id': alignment_id,
    'measurement_operator_id': measurement_operator_id,
    'metric_ids': metric_ids,
    'observed_data': dict(observed_data),
    'available_provider_outputs': available_provider_outputs,
    'required_provider_outputs': required_provider_outputs,
    'comparison_status': 'blocked',
    'claim_status': 'not_accepted',
    'blockers': blockers,
  }


def build_comparison_plan(
    *,
    observations: Mapping[str, Any],
    providers: Mapping[str, Any],
    operator_crosswalk_status: str,
    operator_executions: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
  """Build explicit comparison blockers without guessing operator aliases."""

  crosswalk_blocker = (
    'external measurement-operator namespace is not reconciled with the committed registry'
    if operator_crosswalk_status not in {'reconciled', 'complete-scoped'}
    else None
  )
  visual_ids = list(providers['visual']['provider_ids'])
  visual_outputs = list(providers['visual']['output_channels'])
  signature_id = providers['signature']['provider_id']
  signature_outputs = ['spectral_radiant_intensity']
  ray_ids = list(providers['optical']['provider_ids'])
  ray_outputs = list(providers['optical']['output_fields'])
  visual_blockers = [
    'current visual providers emit display channels only; no mach_disk_position observable is produced',
    'the bounded construction endpoint is not a physical Mach-disk endpoint',
    'the external relation is an unordered hysteretic point cloud and requires branch-aware operator semantics',
  ]
  if crosswalk_blocker is not None:
    visual_blockers.append(crosswalk_blocker)
  comparisons = [
    _comparison(
      comparison_id='VIS-MVP-A-061',
      product_id=VISUAL_PRODUCT,
      provider_ids=visual_ids,
      benchmark_id='RP-HOTWAKE-001',
      alignment_id='MVP-A-061',
      measurement_operator_id='operator.extract.sectioned_tube_mach_disk_position',
      metric_ids=['metric.geometry.mach_disk_position_rmse'],
      observed_data=observations['RP-HOTWAKE-001']['mach_disk_relation'],
      available_provider_outputs=visual_outputs,
      required_provider_outputs=['mach_disk_position_m', 'operating_pressure_or_branch_id'],
      blockers=visual_blockers,
    ),
    _comparison(
      comparison_id='SIG-MVP-A-043',
      product_id=SIGNATURE_PRODUCT,
      provider_ids=[signature_id],
      benchmark_id='RP-BSUV2-001',
      alignment_id='MVP-A-043',
      measurement_operator_id='operator.sensor.bsuv2_los_fov',
      metric_ids=['metric.signature.log_spectral_rmse'],
      observed_data=observations['RP-BSUV2-001']['spectral_radiance'],
      available_provider_outputs=signature_outputs,
      required_provider_outputs=['bsuv2_los_fov_sensor_space_radiance'],
      blockers=[
        'the provider asset is a synthetic table fixture, not the BSUV2 operating point',
        'generic LOS/FOV and path-transfer operators are implemented, but the signature-table provider is not bound to the BSUV2 observer, source, or detector scenario',
        'the corpus contains 13 digitized sensor-space markers, not intrinsic J_lambda truth',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
    _comparison(
      comparison_id='SIG-MVP-A-064',
      product_id=SIGNATURE_PRODUCT,
      provider_ids=[signature_id],
      benchmark_id='RP-EMAP-RAD-001',
      alignment_id='MVP-A-064',
      measurement_operator_id='operator.spectrum.peak_normalize_after_sensor_sampling',
      metric_ids=['metric.signature.relative_shape_rmse', 'metric.signature.band_location_error'],
      observed_data=observations['RP-EMAP-RAD-001']['uvvis_relative_spectrum'],
      available_provider_outputs=signature_outputs,
      required_provider_outputs=['sensor_sampled_peak_normalized_spectral_shape'],
      blockers=[
        'the provider has no corpus-backed EMAP source asset or operating point',
        'the local spectral sampling and peak-normalization operators do not provide a corpus-backed EMAP source asset or operating point',
        'normalized spectral shape cannot validate the provider absolute-radiance claim',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
    _comparison(
      comparison_id='SIG-MVP-A-066',
      product_id=SIGNATURE_PRODUCT,
      provider_ids=[signature_id],
      benchmark_id='RP-EMAP-RAD-001',
      alignment_id='MVP-A-066',
      measurement_operator_id='operator.spectrum.peak_normalize_after_sensor_sampling',
      metric_ids=['metric.signature.relative_shape_rmse', 'metric.signature.band_location_error'],
      observed_data=observations['RP-EMAP-RAD-001']['ftir_relative_envelopes'],
      available_provider_outputs=signature_outputs,
      required_provider_outputs=['sensor_sampled_peak_normalized_spectral_shape'],
      blockers=[
        'the provider has no corpus-backed EMAP FTIR source asset or operating point',
        'the local spectral sampling and peak-normalization operators do not provide the FTIR measurement volume or relative-calibration provenance',
        'the FTIR product is a raster envelope and cannot validate absolute intrinsic J_lambda',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
    _comparison(
      comparison_id='SIG-MVP-A-073',
      product_id=SIGNATURE_PRODUCT,
      provider_ids=[signature_id],
      benchmark_id='RP-ALSI-001',
      alignment_id='MVP-A-073',
      measurement_operator_id='operator.sensor.alsi_thermal_band',
      metric_ids=['metric.signature.band_power_relative_error', 'metric.signature.composition_trend'],
      observed_data=observations['RP-ALSI-001']['thermal_comparison'],
      available_provider_outputs=signature_outputs,
      required_provider_outputs=['band_integrated_radiance', 'formulation_sweep'],
      blockers=[
        'the signature contract emits wavelength-resolved intensity, not the ALSI band-integrated observable',
        'generic bandpass integration is implemented, but no ALSI detector-response asset or formulation-sweep provider input is available',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
    _comparison(
      comparison_id='RAY-MVP-A-044',
      product_id=RAY_PRODUCT,
      provider_ids=ray_ids,
      benchmark_id='RP-BSUV2-001',
      alignment_id='MVP-A-044',
      measurement_operator_id='operator.sensor.bsuv2_los_fov',
      metric_ids=['metric.ray.sensor_space_log_rmse'],
      observed_data=observations['RP-BSUV2-001']['spectral_radiance'],
      available_provider_outputs=ray_outputs,
      required_provider_outputs=['bsuv2_los_fov_sensor_space_radiance'],
      blockers=[
        'generic LOS/FOV and path-transfer operators are implemented, but the gray provider has no BSUV2 plume field, observer, or calibrated detector scenario',
        'the external observable combines source, path, and sensor effects; the current provider only supplies homogeneous support transfer',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
    _comparison(
      comparison_id='RAY-MVP-A-065',
      product_id=RAY_PRODUCT,
      provider_ids=ray_ids,
      benchmark_id='RP-EMAP-RAD-001',
      alignment_id='MVP-A-065',
      measurement_operator_id='operator.spectrum.peak_normalize_after_los_transfer',
      metric_ids=['metric.ray.relative_spectral_shape_rmse'],
      observed_data=observations['RP-EMAP-RAD-001']['uvvis_relative_spectrum'],
      available_provider_outputs=ray_outputs,
      required_provider_outputs=['line_of_sight_peak_normalized_spectral_shape'],
      blockers=[
        'the provider has no EMAP field or path-extinction scenario; generic LOS/FOV, path-transfer, spectral sampling, and peak-normalization helpers cannot create the missing provider-bound field',
        'the corpus records a normalized source-plus-path shape, not independent source radiance and transmittance',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
    _comparison(
      comparison_id='RAY-MVP-A-067',
      product_id=RAY_PRODUCT,
      provider_ids=ray_ids,
      benchmark_id='RP-EMAP-RAD-001',
      alignment_id='MVP-A-067',
      measurement_operator_id='operator.spectrum.peak_normalize_after_los_transfer',
      metric_ids=['metric.ray.relative_spectral_shape_rmse'],
      observed_data=observations['RP-EMAP-RAD-001']['ftir_relative_envelopes'],
      available_provider_outputs=ray_outputs,
      required_provider_outputs=['line_of_sight_peak_normalized_spectral_shape'],
      blockers=[
        'the gray provider has no EMAP field, path-extinction scenario, or FTIR measurement-volume model; generic LOS/FOV and path-transfer helpers cannot create those provider-bound inputs',
        'the FTIR product is a raster envelope and does not separately identify source radiance and transmittance',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
    _comparison(
      comparison_id='RAY-MVP-A-068',
      product_id=RAY_PRODUCT,
      provider_ids=ray_ids,
      benchmark_id='RP-EMAP-RAD-001',
      alignment_id='MVP-A-068',
      measurement_operator_id='operator.surface.gardon_band_integral',
      metric_ids=['metric.ray.surface_flux_log_rmse'],
      observed_data=observations['RP-EMAP-RAD-001']['gardon_time_history'],
      available_provider_outputs=ray_outputs,
      required_provider_outputs=['surface_detector_band_integrated_flux_time_history'],
      blockers=[
        'the gray provider has no time-dependent source state, surface pose, detector response, or conjugate thermal model',
        'generic bandpass integration is available, but no time-dependent surface pose, Gardon response, or surface-flux provider is implemented',
        'the corpus trace is a digitized published display and is not a per-ray source-radiance truth set',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
    _comparison(
      comparison_id='RAY-MVP-A-074',
      product_id=RAY_PRODUCT,
      provider_ids=ray_ids,
      benchmark_id='RP-ALSI-001',
      alignment_id='MVP-A-074',
      measurement_operator_id='operator.image.integrate_alsi_band_and_area',
      metric_ids=['metric.ray.band_radiance_relative_error'],
      observed_data=observations['RP-ALSI-001']['thermal_comparison'],
      available_provider_outputs=ray_outputs,
      required_provider_outputs=['alsi_band_integrated_radiance_and_projected_power'],
      blockers=[
        'generic bandpass integration is available, but no ALSI detector response, image integration, or projected-area scenario operator is implemented',
        'the thermal corpus is band-integrated and is not a per-ray source-spectrum truth set',
        *([crosswalk_blocker] if crosswalk_blocker is not None else []),
      ],
    ),
  ]
  if operator_executions is not None:
    for comparison in comparisons:
      execution = operator_executions.get(comparison['comparison_id'])
      if execution is not None:
        comparison['operator_execution'] = dict(execution)
  ####
  return comparisons


def build_unimplemented_boundaries(providers: Mapping[str, Any]) -> list[dict[str, Any]]:
  """Keep downstream product boundaries explicit in the same validation record."""

  return [
    {
      'product_id': RAY_PRODUCT,
      'provider_ids': list(providers['optical']['provider_ids']),
      'status': 'external-validation-pending' if providers['optical']['provider_ids'] else 'blocked_no_provider',
      'claim_status': 'not_accepted',
      'required_prerequisites': [
        'source radiance and transmittance separation',
        'sensor-space comparison operators',
      ],
    },
    {
      'product_id': 'plume.image.spectral-radiance@1',
      'provider_ids': list(providers['focal_plane_array']['provider_ids']),
      'status': 'blocked_upstream_ray_and_external_detector',
      'claim_status': 'not_accepted',
      'required_prerequisites': [
        RAY_PRODUCT,
        'camera and optics model',
        'op.sensor.fpa-pixel-detector expected-electron adapter',
        'external detector calibration, digitization, and detection policy',
      ],
    },
  ]


def build_provider_comparison_preflight(path: Path) -> dict[str, Any]:
  """Validate the archive, probe current providers, and record blocked gates."""

  corpus_report = preflight_corpus(path)
  archive_summary = {
    key: value for key, value in corpus_report.get('archive', {}).items()
    if key != 'path'
  }
  report: dict[str, Any] = {
    'report_id': 'exhaust-plume-provider-comparison-preflight-v1',
    'archive': archive_summary,
    'corpus_status': corpus_report['status'],
    'operator_reconciliation': corpus_report.get('operator_reconciliation', {}),
    'release_ready': False,
  }
  if corpus_report['status'] != 'preflight-valid-pending-release-gates':
    report.update({
      'status': 'blocked-invalid-corpus',
      'errors': corpus_report.get('errors', []),
      'comparisons': [],
      'release_blockers': ['recovered corpus did not pass the structural preflight'],
    })
    return report

  with ZipFile(path) as archive:
    observations = summarize_corpus_observations(archive)
  providers = _local_provider_inventory()
  operator_status = corpus_report['operator_reconciliation'].get(
    'semantic_crosswalk_status',
    corpus_report['operator_reconciliation']['crosswalk_status'],
  )
  operator_executions = execute_spectral_shape_probes(path, providers)
  visual_feature_execution = execute_visual_feature_probe(observations, providers)
  operator_executions['VIS-MVP-A-061'] = visual_feature_execution
  comparisons = build_comparison_plan(
    observations=observations,
    providers=providers,
    operator_crosswalk_status=operator_status,
    operator_executions=operator_executions,
  )
  report.update({
    'status': 'comparisons-recorded-pending-implementation',
    'providers': providers,
    'corpus_observations': observations,
    'operator_executions': operator_executions,
    'visual_feature_operator': visual_feature_execution,
    'comparisons': comparisons,
    'unimplemented_product_boundaries': build_unimplemented_boundaries(providers),
    'release_blockers': [
      *(['external operator semantic crosswalk is incomplete'] if operator_status != 'complete-scoped' else []),
      'all current provider-specific external comparisons remain blocked by missing provider-bound measurement-space outputs, physical scenario assets, or accepted product-specific measurement-operator mappings',
      'separately named MVP alignment archive is not yet verified',
    ],
  })
  return report


def main(argv: list[str] | None = None) -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--corpus', required=True, type=Path)
  parser.add_argument('--output', type=Path)
  args = parser.parse_args(argv)
  report = build_provider_comparison_preflight(args.corpus)
  serialized = json.dumps(report, indent=2, sort_keys=True) + '\n'
  if args.output is not None:
    args.output.write_text(serialized, encoding='utf-8')
  print(serialized, end='')
  return 0 if report['status'] == 'comparisons-recorded-pending-implementation' else 1


if __name__ == '__main__':
  raise SystemExit(main())
