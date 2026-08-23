"""Product-facing MVP workflows for visual geometry and spectral lookup."""

from exhaust_plume.products.signature import (
  evaluate_signature_table_asset,
  load_signature_table_asset,
  load_spectral_signature_request,
  render_signature_plots,
  write_signature_result_csv,
  write_signature_result_json,
  write_signature_table_asset,
)
from exhaust_plume.products.visual import (
  VisualMesh,
  build_sectioned_tube_mesh,
  evaluate_nozzle_geometry_visual,
  evaluate_shock_cell_visual,
  evaluate_visual_definition,
  load_straight_visual_definition,
  render_visual_preview,
  visual_definition_from_shock_cells,
  visual_definition_from_zone_results,
  write_visual_mesh_json,
  write_visual_obj,
  write_visual_result_json,
  write_straight_visual_asset,
)

__all__ = (
  'VisualMesh',
  'build_sectioned_tube_mesh',
  'evaluate_nozzle_geometry_visual',
  'evaluate_signature_table_asset',
  'evaluate_shock_cell_visual',
  'evaluate_visual_definition',
  'load_signature_table_asset',
  'load_spectral_signature_request',
  'load_straight_visual_definition',
  'render_signature_plots',
  'render_visual_preview',
  'visual_definition_from_shock_cells',
  'visual_definition_from_zone_results',
  'write_signature_result_csv',
  'write_signature_result_json',
  'write_signature_table_asset',
  'write_straight_visual_asset',
  'write_visual_mesh_json',
  'write_visual_obj',
  'write_visual_result_json',
)
