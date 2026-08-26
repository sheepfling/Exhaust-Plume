"""Lineage-aware diagnostics between compatible strict product results.

The reports in this module are comparison diagnostics, not validation claims.
They require explicit common frames and ordered domains, preserve validity
masks, and never infer ray intersections or a detector image.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from math import fsum, sqrt
from pathlib import Path
from typing import Any, Mapping, Sequence

from exhaust_plume.api import (
  PlumeFluxSectionResult,
  ProductResult,
  SectionedTubeResult,
  SpectralRadiantIntensityResult,
  SpectralRayTransferResult,
  VisualizationSpec,
)
from exhaust_plume.api.visualization import (
  extract_plume_flux_section_glyph,
  extract_sectioned_tube_line_data,
  extract_spectral_radiant_intensity_grid,
  extract_spectral_ray_transfer_data,
)
from exhaust_plume.products.workflow_gallery import _source_metadata

__all__ = (
  'COMPARISON_REPORT_SCHEMA',
  'ProductComparisonReport',
  'compare_product_results',
  'write_product_comparison_report',
)

COMPARISON_REPORT_SCHEMA = 'plume.visualization.comparison@1'


@dataclass(frozen=True, slots=True)
class ProductComparisonReport:
  """A reproducible, product-specific comparison diagnostic."""

  schema: str
  product: str
  status: str
  left_source: Mapping[str, Any]
  right_source: Mapping[str, Any]
  left_view_spec: VisualizationSpec
  right_view_spec: VisualizationSpec
  metrics: Mapping[str, Any]
  validity: Mapping[str, Any]
  guardrails: tuple[str, ...]
  reason: str | None = None

  def model_dump(self) -> dict[str, Any]:
    return {
      'schema': self.schema,
      'product': self.product,
      'status': self.status,
      'left_source': dict(self.left_source),
      'right_source': dict(self.right_source),
      'left_view_spec': self.left_view_spec.model_dump(mode='json'),
      'right_view_spec': self.right_view_spec.model_dump(mode='json'),
      'left_view_spec_digest_sha256': self.left_view_spec.digest_sha256(),
      'right_view_spec_digest_sha256': self.right_view_spec.digest_sha256(),
      'metrics': dict(self.metrics),
      'validity': dict(self.validity),
      'guardrails': list(self.guardrails),
      'reason': self.reason,
    }
  ####

  def canonical_json(self) -> str:
    return json.dumps(self.model_dump(), ensure_ascii=True, allow_nan=False, indent=2, sort_keys=True) + '\n'
  ####
####


def _product_kind(result: ProductResult) -> str:
  if isinstance(result, SectionedTubeResult):
    return 'sectioned-tube-visual'
  ####
  if isinstance(result, SpectralRadiantIntensityResult):
    return 'spectral-radiant-intensity'
  ####
  if isinstance(result, SpectralRayTransferResult):
    return 'spectral-ray-transfer'
  ####
  if isinstance(result, PlumeFluxSectionResult):
    return 'engineering-flux-section'
  ####
  raise TypeError('result must be one of the standard exhaust_plume.api product results')
####


def _default_spec(result: ProductResult, product: str, selection: Any = None) -> VisualizationSpec:
  prefix = {
    'sectioned-tube-visual': 'visual',
    'spectral-radiant-intensity': 'signature',
    'spectral-ray-transfer': 'ray-transfer',
    'engineering-flux-section': 'flux',
  }[product]
  return VisualizationSpec.for_result(
    result,
    view_kind=f'{prefix}.comparison',
    selection=selection,
  )
####


def _compatible_specs(
  left: ProductResult,
  right: ProductResult,
  product: str,
  left_spec: VisualizationSpec | None,
  right_spec: VisualizationSpec | None,
) -> tuple[VisualizationSpec, VisualizationSpec]:
  resolved_left = left_spec or _default_spec(left, product)
  resolved_right = right_spec or _default_spec(right, product, resolved_left.selection)
  resolved_left.validate_for_result(left)
  resolved_right.validate_for_result(right)
  if resolved_left.selection != resolved_right.selection:
    raise ValueError('comparison view selections must match')
  return resolved_left, resolved_right
####


def _metric(deltas: Sequence[float]) -> dict[str, Any]:
  values = tuple(float(value) for value in deltas)
  if not values:
    return {'sample_count': 0, 'rmse': None, 'max_abs_error': None}
  ####
  return {
    'sample_count': len(values),
    'rmse': sqrt(fsum(value * value for value in values) / len(values)),
    'max_abs_error': max(abs(value) for value in values),
  }
####


def _vector_metric(left: Sequence[float], right: Sequence[float]) -> dict[str, Any]:
  deltas = tuple(float(a) - float(b) for a, b in zip(left, right, strict=True))
  return {
    'component_delta': deltas,
    'l2_absolute_error': sqrt(fsum(value * value for value in deltas)),
  }
####


def _result_compatibility(left: ProductResult, right: ProductResult) -> str | None:
  if left.envelope.capability_id != right.envelope.capability_id:
    return 'capability IDs do not match'
  ####
  if left.envelope.schema_version != right.envelope.schema_version:
    return 'schema versions do not match'
  ####
  if left.envelope.frame.frame_id != right.envelope.frame.frame_id:
    return 'frame IDs do not match; an explicit frame transform is required'
  ####
  return None
####


def _blocked_report(
  left: ProductResult,
  right: ProductResult,
  product: str,
  left_spec: VisualizationSpec,
  right_spec: VisualizationSpec,
  reason: str,
) -> ProductComparisonReport:
  return ProductComparisonReport(
    schema=COMPARISON_REPORT_SCHEMA,
    product=product,
    status='blocked-incompatible-domain',
    left_source=_source_metadata(left),
    right_source=_source_metadata(right),
    left_view_spec=left_spec,
    right_view_spec=right_spec,
    metrics={},
    validity={},
    guardrails=(
      'comparison_is_a_diagnostic_and_not_validation_evidence',
      'no_extrapolation_or_implicit_frame_transform_is_performed',
    ),
    reason=reason,
  )
####


def _visual_report(
  left: SectionedTubeResult,
  right: SectionedTubeResult,
  left_spec: VisualizationSpec,
  right_spec: VisualizationSpec,
) -> ProductComparisonReport:
  left_data = extract_sectioned_tube_line_data(left)
  right_data = extract_sectioned_tube_line_data(right)
  if left_data.geometry.arc_length_m != right_data.geometry.arc_length_m:
    return _blocked_report(left, right, 'sectioned-tube-visual', left_spec, right_spec, 'section arc-length axes do not match exactly')
  ####
  centerline_deltas = tuple(
    sqrt(fsum((left_point[index] - right_point[index]) ** 2 for index in range(3)))
    for left_point, right_point in zip(left_data.geometry.centerline_m, right_data.geometry.centerline_m, strict=True)
  )
  axis_deltas = tuple(
    abs(left_axis - right_axis)
    for left_axis, right_axis in zip(left_data.geometry.semi_axis_1_m, right_data.geometry.semi_axis_1_m, strict=True)
  ) + tuple(
    abs(left_axis - right_axis)
    for left_axis, right_axis in zip(left_data.geometry.semi_axis_2_m, right_data.geometry.semi_axis_2_m, strict=True)
  )
  right_channels = {(channel.channel_id, channel.component_index): channel for channel in right_data.channels}
  channel_metrics: dict[str, Any] = {}
  for channel in left_data.channels:
    other = right_channels.get((channel.channel_id, channel.component_index))
    if other is None:
      continue
    ####
    deltas = tuple(
      left_value - right_value
      for left_value, right_value in zip(channel.values, other.values, strict=True)
      if left_value is not None and right_value is not None
    )
    channel_metrics[f'{channel.channel_id}:{channel.component_index}'] = _metric(deltas)
  ####
  return ProductComparisonReport(
    schema=COMPARISON_REPORT_SCHEMA,
    product='sectioned-tube-visual',
    status='computed-diagnostic',
    left_source=_source_metadata(left),
    right_source=_source_metadata(right),
    left_view_spec=left_spec,
    right_view_spec=right_spec,
    metrics={
      'centerline_position_m': _metric(centerline_deltas),
      'semi_axis_absolute_m': _metric(axis_deltas),
      'common_channel_metrics': channel_metrics,
    },
    validity={
      'section_count': len(centerline_deltas),
      'left_channel_count': len(left_data.channels),
      'right_channel_count': len(right_data.channels),
    },
    guardrails=(
      'shock_diamonds_regions_and_physical_endpoints_are_not_inferred',
      'comparison_is_a_diagnostic_and_not_validation_evidence',
    ),
  )
####


def _spectral_report(
  left: SpectralRadiantIntensityResult,
  right: SpectralRadiantIntensityResult,
  left_spec: VisualizationSpec,
  right_spec: VisualizationSpec,
) -> ProductComparisonReport:
  left_grid = extract_spectral_radiant_intensity_grid(left)
  right_grid = extract_spectral_radiant_intensity_grid(right)
  if left_grid.wavelengths_m != right_grid.wavelengths_m or left_grid.directions != right_grid.directions:
    return _blocked_report(left, right, 'spectral-radiant-intensity', left_spec, right_spec, 'wavelength and exact 3-D direction axes do not match')
  ####
  deltas: list[float] = []
  comparable = 0
  left_invalid = 0
  right_invalid = 0
  for left_row, right_row, left_mask, right_mask in zip(
    left_grid.radiant_intensity_W_sr_m,
    right_grid.radiant_intensity_W_sr_m,
    left_grid.validity_mask,
    right_grid.validity_mask,
    strict=True,
  ):
    for left_value, right_value, left_valid, right_valid in zip(left_row, right_row, left_mask, right_mask, strict=True):
      left_invalid += not left_valid
      right_invalid += not right_valid
      if left_valid and right_valid and left_value is not None and right_value is not None:
        deltas.append(left_value - right_value)
        comparable += 1
      ####
    ####
  ####
  return ProductComparisonReport(
    schema=COMPARISON_REPORT_SCHEMA,
    product='spectral-radiant-intensity',
    status='computed-diagnostic' if comparable else 'no-overlap-valid-samples',
    left_source=_source_metadata(left),
    right_source=_source_metadata(right),
    left_view_spec=left_spec,
    right_view_spec=right_spec,
    metrics={'absolute_radiant_intensity_delta_W_sr_m': _metric(deltas)},
    validity={
      'comparable_sample_count': comparable,
      'left_invalid_sample_count': left_invalid,
      'right_invalid_sample_count': right_invalid,
    },
    guardrails=(
      'exact_3d_direction_and_wavelength_axes_are_required',
      'comparison_is_a_diagnostic_and_not_validation_evidence',
      'no_geometry_or_focal_plane_quantity_is_derived',
    ),
  )
####


def _ray_report(
  left: SpectralRayTransferResult,
  right: SpectralRayTransferResult,
  left_spec: VisualizationSpec,
  right_spec: VisualizationSpec,
) -> ProductComparisonReport:
  left_data = extract_spectral_ray_transfer_data(left)
  right_data = extract_spectral_ray_transfer_data(right)
  if left_data.wavelengths_m != right_data.wavelengths_m or tuple(line.ray_id for line in left_data.lines) != tuple(line.ray_id for line in right_data.lines):
    return _blocked_report(left, right, 'spectral-ray-transfer', left_spec, right_spec, 'ray ID and wavelength axes do not match exactly')
  ####
  source_deltas: list[float] = []
  transmittance_deltas: list[float] = []
  invalid_count = 0
  geometry_errors: dict[str, Any] = {}
  for left_line, right_line in zip(left_data.lines, right_data.lines, strict=True):
    geometry_errors[left_line.ray_id] = {
      'origin_m': _vector_metric(left_line.origin_m, right_line.origin_m),
      'direction': _vector_metric(left_line.direction, right_line.direction),
    }
    for left_source, right_source, left_transmittance, right_transmittance, left_valid, right_valid in zip(
      left_line.source_radiance_W_m2_sr_m,
      right_line.source_radiance_W_m2_sr_m,
      left_line.background_transmittance,
      right_line.background_transmittance,
      left_line.validity_mask,
      right_line.validity_mask,
      strict=True,
    ):
      if left_valid and right_valid and left_source is not None and right_source is not None and left_transmittance is not None and right_transmittance is not None:
        source_deltas.append(left_source - right_source)
        transmittance_deltas.append(left_transmittance - right_transmittance)
      else:
        invalid_count += 1
      ####
    ####
  ####
  comparable = len(source_deltas)
  return ProductComparisonReport(
    schema=COMPARISON_REPORT_SCHEMA,
    product='spectral-ray-transfer',
    status='computed-diagnostic' if comparable else 'no-overlap-valid-samples',
    left_source=_source_metadata(left),
    right_source=_source_metadata(right),
    left_view_spec=left_spec,
    right_view_spec=right_spec,
    metrics={
      'source_radiance_delta_W_m2_sr_m': _metric(source_deltas),
      'background_transmittance_delta': _metric(transmittance_deltas),
      'ray_geometry': geometry_errors,
    },
    validity={'comparable_sample_count': comparable, 'noncomparable_sample_count': invalid_count},
    guardrails=(
      'source_radiance_and_background_transmittance_remain_separate',
      'hit_miss_intersections_and_optical_depth_are_not_inferred',
      'comparison_is_a_diagnostic_and_not_validation_evidence',
      'no_focal_plane_quantity_is_derived',
    ),
  )
####


def _flux_report(
  left: PlumeFluxSectionResult,
  right: PlumeFluxSectionResult,
  left_spec: VisualizationSpec,
  right_spec: VisualizationSpec,
) -> ProductComparisonReport:
  left_glyph = extract_plume_flux_section_glyph(left)
  right_glyph = extract_plume_flux_section_glyph(right)
  right_species = dict(right_glyph.species_mass_flows_kgps)
  common_species = tuple(
    (species_id, left_value - right_species[species_id])
    for species_id, left_value in left_glyph.species_mass_flows_kgps
    if species_id in right_species
  )
  scalar_deltas = {
    'area_m2': left_glyph.area_m2 - right_glyph.area_m2,
    'mass_flow_kgps': left_glyph.mass_flow_kgps - right_glyph.mass_flow_kgps,
    'total_energy_flow_W': left_glyph.total_energy_flow_W - right_glyph.total_energy_flow_W,
    'pressure_Pa': left_glyph.pressure_Pa - right_glyph.pressure_Pa,
    'ambient_pressure_Pa': left_glyph.ambient_pressure_Pa - right_glyph.ambient_pressure_Pa,
    'pressure_match_relative_residual': left_glyph.pressure_match_relative_residual - right_glyph.pressure_match_relative_residual,
  }
  return ProductComparisonReport(
    schema=COMPARISON_REPORT_SCHEMA,
    product='engineering-flux-section',
    status='computed-diagnostic',
    left_source=_source_metadata(left),
    right_source=_source_metadata(right),
    left_view_spec=left_spec,
    right_view_spec=right_spec,
    metrics={
      'normal': _vector_metric(left_glyph.normal, right_glyph.normal),
      'momentum_flux_N': _vector_metric(left_glyph.momentum_flux_N, right_glyph.momentum_flux_N),
      'scalar_deltas': scalar_deltas,
      'species_mass_flow_deltas_kgps': dict(common_species),
      'cross_section_second_moment_m2': {
        'delta_00': left_glyph.cross_section_second_moment_m2[0][0] - right_glyph.cross_section_second_moment_m2[0][0],
        'delta_01': left_glyph.cross_section_second_moment_m2[0][1] - right_glyph.cross_section_second_moment_m2[0][1],
        'delta_11': left_glyph.cross_section_second_moment_m2[1][1] - right_glyph.cross_section_second_moment_m2[1][1],
      },
    },
    validity={
      'left_species_count': len(left_glyph.species_mass_flows_kgps),
      'right_species_count': len(right_glyph.species_mass_flows_kgps),
      'common_species_count': len(common_species),
    },
    guardrails=(
      'ordered_section_and_time_trends_require_an_explicit_collection_contract',
      'comparison_is_a_diagnostic_and_not_validation_evidence',
      'no_geometry_radiance_or_focal_plane_quantity_is_derived',
    ),
  )
####


def compare_product_results(
  left: ProductResult,
  right: ProductResult,
  *,
  left_spec: VisualizationSpec | None = None,
  right_spec: VisualizationSpec | None = None,
) -> ProductComparisonReport:
  """Compare two same-capability results without extrapolation or fusion."""

  left_product = _product_kind(left)
  right_product = _product_kind(right)
  if left_product != right_product:
    raise TypeError('comparison requires two results from the same product family')
  ####
  resolved_left, resolved_right = _compatible_specs(left, right, left_product, left_spec, right_spec)
  compatibility_reason = _result_compatibility(left, right)
  if compatibility_reason is not None:
    return _blocked_report(left, right, left_product, resolved_left, resolved_right, compatibility_reason)
  ####
  if left_product == 'sectioned-tube-visual' and isinstance(left, SectionedTubeResult) and isinstance(right, SectionedTubeResult):
    return _visual_report(left, right, resolved_left, resolved_right)
  ####
  if left_product == 'spectral-radiant-intensity' and isinstance(left, SpectralRadiantIntensityResult) and isinstance(right, SpectralRadiantIntensityResult):
    return _spectral_report(left, right, resolved_left, resolved_right)
  ####
  if left_product == 'spectral-ray-transfer' and isinstance(left, SpectralRayTransferResult) and isinstance(right, SpectralRayTransferResult):
    return _ray_report(left, right, resolved_left, resolved_right)
  ####
  if isinstance(left, PlumeFluxSectionResult) and isinstance(right, PlumeFluxSectionResult):
    return _flux_report(left, right, resolved_left, resolved_right)
  ####
  raise TypeError('comparison result types do not match their product family')
####


def write_product_comparison_report(report: ProductComparisonReport, path: str | Path) -> Path:
  """Write a comparison report as deterministic JSON."""

  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(report.canonical_json(), encoding='utf-8')
  return output
####
