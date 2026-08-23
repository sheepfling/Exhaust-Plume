"""User-facing MVP workflows for lookup-backed spectral signatures."""

from __future__ import annotations

import csv
from dataclasses import asdict, replace
import hashlib
import json
from math import isfinite
from pathlib import Path
from typing import Any

from exhaust_plume.contracts import Pose, SpectralSignatureRequest, SpectralSignatureResult
from exhaust_plume.contracts.errors import ProviderConfigurationError
from exhaust_plume.contracts.specs_v1 import SPECTRAL_RADIANT_INTENSITY_V1
from exhaust_plume.providers.signature_table import (
  SignatureTableConfiguration,
  SignatureTableDefinition,
  SignatureTableProvider,
)

__all__ = (
  'evaluate_signature_table_asset',
  'load_signature_table_asset',
  'load_spectral_signature_request',
  'render_signature_plots',
  'write_signature_result_csv',
  'write_signature_result_json',
  'write_signature_table_asset',
)

_SIGNATURE_ASSET_SCHEMA = 'plume.signature.table-asset@1'
_SIGNATURE_REQUEST_SCHEMA = 'plume.signature.request@1'


def _load_json(path: str | Path) -> dict[str, Any]:
  payload = json.loads(Path(path).read_text(encoding='utf-8'))
  if not isinstance(payload, dict):
    raise ValueError(f'{path} must contain a JSON object')
  return payload
####


def load_signature_table_asset(path: str | Path) -> SignatureTableDefinition:
  """Load a raw provider definition or the wrapped v1 signature asset."""

  asset_path = Path(path)
  raw_bytes = asset_path.read_bytes()
  payload = json.loads(raw_bytes.decode('utf-8'))
  if not isinstance(payload, dict):
    raise ValueError(f'{path} must contain a JSON object')
  if 'definition' in payload:
    schema = payload.get('asset_schema')
    if schema is not None and schema != _SIGNATURE_ASSET_SCHEMA:
      raise ValueError(f'unsupported signature asset schema: {schema}')
    payload = payload['definition']
  elif 'asset_schema' in payload:
    schema = payload.pop('asset_schema')
    if schema != _SIGNATURE_ASSET_SCHEMA:
      raise ValueError(f'unsupported signature asset schema: {schema}')
  if not isinstance(payload, dict):
    raise ValueError('signature table definition must be a JSON object')
  definition_payload = dict(payload)
  definition_payload.pop('asset_sha256', None)
  definition = SignatureTableDefinition(**definition_payload)
  return replace(definition, asset_sha256=hashlib.sha256(raw_bytes).hexdigest())
####


def write_signature_table_asset(definition: SignatureTableDefinition, path: str | Path) -> Path:
  """Write a canonical wrapped v1 signature asset."""

  if not isinstance(definition, SignatureTableDefinition):
    raise ProviderConfigurationError('definition must be SignatureTableDefinition')
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  definition_payload = asdict(definition)
  definition_payload.pop('asset_sha256', None)
  payload = {
    'asset_schema': _SIGNATURE_ASSET_SCHEMA,
    'definition': definition_payload,
  }
  output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
  return output
####


def load_spectral_signature_request(path: str | Path) -> SpectralSignatureRequest:
  """Load a raw request or the wrapped v1 request asset."""

  payload = _load_json(path)
  if 'request' in payload:
    schema = payload.get('request_schema')
    if schema is not None and schema != _SIGNATURE_REQUEST_SCHEMA:
      raise ValueError(f'unsupported signature request schema: {schema}')
    payload = payload['request']
  elif 'request_schema' in payload:
    schema = payload.pop('request_schema')
    if schema != _SIGNATURE_REQUEST_SCHEMA:
      raise ValueError(f'unsupported signature request schema: {schema}')
  if not isinstance(payload, dict):
    raise ValueError('signature request must be a JSON object')
  return SpectralSignatureRequest(**payload)
####


def evaluate_signature_table_asset(
    definition: SignatureTableDefinition,
    request: SpectralSignatureRequest,
    *,
    configuration: SignatureTableConfiguration | None = None,
    time_s: float = 0.0,
) -> SpectralSignatureResult:
  """Evaluate one lookup asset through the public lifecycle."""

  if not isinstance(definition, SignatureTableDefinition):
    raise ProviderConfigurationError('definition must be SignatureTableDefinition')
  if not isinstance(request, SpectralSignatureRequest):
    raise ProviderConfigurationError('request must be SpectralSignatureRequest')
  provider = SignatureTableProvider(configuration)
  session = provider.create_session(definition=definition)
  snapshot = session.create_snapshot(
    time_s=time_s,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  try:
    return snapshot.evaluate(SPECTRAL_RADIANT_INTENSITY_V1, request)
  finally:
    session.close()
####


def write_signature_result_json(result: SpectralSignatureResult, path: str | Path) -> Path:
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(result.model_dump_json(indent=2), encoding='utf-8')
  return output
####


def _direction_cosines(definition: SignatureTableDefinition, request: SpectralSignatureRequest) -> tuple[float, ...]:
  return tuple(
    sum(direction[axis] * definition.axis_direction[axis] for axis in range(3))
    for direction in request.source_to_observer_directions
  )
####


def write_signature_result_csv(
    definition: SignatureTableDefinition,
    request: SpectralSignatureRequest,
    result: SpectralSignatureResult,
    path: str | Path,
) -> Path:
  """Write one long-form row per direction/wavelength sample."""

  if len(result.spectral_radiant_intensity) != len(request.source_to_observer_directions):
    raise ValueError('signature result and request direction counts do not match')
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  direction_cosines = _direction_cosines(definition, request)
  with output.open('w', encoding='utf-8', newline='') as stream:
    writer = csv.writer(stream)
    writer.writerow((
      'direction_index',
      'direction_x',
      'direction_y',
      'direction_z',
      'direction_cosine',
      'wavelength_m',
      'spectral_radiant_intensity_w_sr_m',
      'valid',
      'status_code',
      'absolute_standard_uncertainty_w_sr_m',
    ))
    for direction_index, direction in enumerate(request.source_to_observer_directions):
      uncertainty_row = (
        result.absolute_standard_uncertainty[direction_index]
        if result.absolute_standard_uncertainty is not None
        else (None,) * len(request.wavelengths_m)
      )
      for wavelength_index, wavelength in enumerate(request.wavelengths_m):
        writer.writerow((
          direction_index,
          *direction,
          direction_cosines[direction_index],
          wavelength,
          result.spectral_radiant_intensity[direction_index][wavelength_index],
          result.validity_mask[direction_index][wavelength_index],
          result.direction_status[direction_index].code.value,
          uncertainty_row[wavelength_index],
        ))
  return output
####


def _matplotlib():
  try:
    from matplotlib import pyplot as plt
  except ImportError as error:
    raise RuntimeError('signature plots require the optional plot dependency: pip install .[plot]') from error
  return plt
####


def render_signature_plots(
    definition: SignatureTableDefinition,
    request: SpectralSignatureRequest,
    result: SpectralSignatureResult,
    output_dir: str | Path,
) -> tuple[Path, Path, Path]:
  """Render spectrum, angular-cut, and wavelength-angle heatmap PNGs."""

  plt = _matplotlib()
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  wavelengths_um = tuple(wavelength * 1.0e6 for wavelength in request.wavelengths_m)
  direction_cosines = _direction_cosines(definition, request)
  valid_values = [
    [value if result.validity_mask[row_index][column_index] else float('nan') for column_index, value in enumerate(row)]
    for row_index, row in enumerate(result.spectral_radiant_intensity)
  ]

  spectrum_figure, spectrum_axes = plt.subplots(figsize=(8.0, 5.0))
  for row_index, (values, direction_cosine) in enumerate(zip(valid_values, direction_cosines, strict=True)):
    spectrum_axes.plot(wavelengths_um, values, marker='o', label=f'direction {row_index} (μ={direction_cosine:.3f})')
    if result.absolute_standard_uncertainty is not None:
      uncertainty = result.absolute_standard_uncertainty[row_index]
      lower = tuple(value - error if isfinite(value) else float('nan') for value, error in zip(values, uncertainty, strict=True))
      upper = tuple(value + error if isfinite(value) else float('nan') for value, error in zip(values, uncertainty, strict=True))
      spectrum_axes.fill_between(wavelengths_um, lower, upper, alpha=0.12)
  spectrum_axes.set_title('Spectral radiant intensity')
  spectrum_axes.set_xlabel('Wavelength [μm]')
  spectrum_axes.set_ylabel('Jλ [W sr⁻¹ m⁻¹]')
  spectrum_axes.grid(True, alpha=0.25)
  spectrum_axes.legend()
  spectrum_figure.tight_layout()
  spectrum_path = output / 'signature_spectrum.png'
  spectrum_figure.savefig(spectrum_path, dpi=140)
  plt.close(spectrum_figure)

  angular_figure, angular_axes = plt.subplots(figsize=(8.0, 5.0))
  sorted_indices = tuple(sorted(range(len(direction_cosines)), key=direction_cosines.__getitem__))
  if len(request.wavelengths_m) <= 4:
    angular_wavelength_indices = tuple(range(len(request.wavelengths_m)))
  else:
    angular_wavelength_indices = tuple(dict.fromkeys((0, len(request.wavelengths_m) // 2, len(request.wavelengths_m) - 1)))
  for wavelength_index in angular_wavelength_indices:
    angular_axes.plot(
      tuple(direction_cosines[index] for index in sorted_indices),
      tuple(valid_values[index][wavelength_index] for index in sorted_indices),
      marker='o',
      label=f'{wavelengths_um[wavelength_index]:g} μm',
    )
  angular_axes.set_title('Angular signature lookup')
  angular_axes.set_xlabel('Direction cosine to source axis [1]')
  angular_axes.set_ylabel('Jλ [W sr⁻¹ m⁻¹]')
  angular_axes.grid(True, alpha=0.25)
  angular_axes.legend()
  angular_figure.tight_layout()
  angular_path = output / 'signature_angular.png'
  angular_figure.savefig(angular_path, dpi=140)
  plt.close(angular_figure)

  heatmap_figure, heatmap_axes = plt.subplots(figsize=(8.0, 5.0))
  sorted_cosines = tuple(direction_cosines[index] for index in sorted_indices)
  matrix = tuple(tuple(valid_values[index]) for index in sorted_indices)
  image = heatmap_axes.pcolormesh(wavelengths_um, sorted_cosines, matrix, shading='auto')
  heatmap_figure.colorbar(image, ax=heatmap_axes, label='Jλ [W sr⁻¹ m⁻¹]')
  heatmap_axes.set_title('Spectral/angular lookup')
  heatmap_axes.set_xlabel('Wavelength [μm]')
  heatmap_axes.set_ylabel('Direction cosine to source axis [1]')
  heatmap_figure.tight_layout()
  heatmap_path = output / 'signature_heatmap.png'
  heatmap_figure.savefig(heatmap_path, dpi=140)
  plt.close(heatmap_figure)
  return spectrum_path, angular_path, heatmap_path
####
