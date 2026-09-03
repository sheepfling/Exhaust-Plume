from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from exhaust_plume.api import AxisScale
from exhaust_plume.api.v1 import ApplicabilityStatus, GeometryClaim, VisualSection
from exhaust_plume.products import (
  MODEL_GALLERY_MANIFEST_SCHEMA,
  ModelVisualizationClaims,
  ModelVisualizationGallerySpec,
  ModelVisualizationLane,
  ModelVisualChannel,
  ModelVisualField,
  ModelVisualPath,
  StandardizedModelVisualization,
  render_model_visualization_gallery,
)
from exhaust_plume.providers.prescribed_visual import PrescribedVisualDefinition


def _bundle() -> StandardizedModelVisualization:
  sections = tuple(
    VisualSection(
      arc_length_m=float(index),
      center_m=(float(index), 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=0.5 + 0.1 * index,
      radius_minor_m=0.4 + 0.1 * index,
    )
    for index in range(3)
  )
  channel = ModelVisualChannel(
    channel_id='mach',
    semantic='display Mach number',
    unit='1',
    values=(3.0, 2.5, 2.0),
  )
  return StandardizedModelVisualization(
    lane=ModelVisualizationLane.BASIC_SHOCK_CELL,
    model_id='gallery-test-model',
    model_version='1.0.0',
    source_status='converged',
    applicability_status=ApplicabilityStatus.INSIDE,
    applicability_reasons=(),
    claims=ModelVisualizationClaims(
      model_fidelity='ENGINEERING_APPROXIMATE',
      validation_level='UNIT_TESTED',
      geometry_claim=GeometryClaim.ENGINEERING_APPROXIMATE,
      production_claim_allowed=False,
      claim_notes=('gallery fixture only',),
    ),
    sectioned_tube=PrescribedVisualDefinition(
      frame_id='source-local',
      sections=sections,
      channels={'mach': channel.values},
    ),
    section_channels=(channel,),
    paths=(ModelVisualPath(
      path_id='shock-boundary',
      semantic='declared shock boundary',
      points_m=((0.0, 0.5, 0.0), (1.0, 0.7, 0.0), (2.0, 0.9, 0.0)),
    ),),
    fields=(ModelVisualField(
      field_id='cells',
      semantic='declared model cells',
      polygons_xr_m=(
        ((0.0, 0.0), (1.0, 0.0), (0.5, 0.6)),
        ((1.0, 0.0), (2.0, 0.0), (1.5, 0.8)),
      ),
      channels={'mach': (2.8, 2.2)},
      channel_units={'mach': '1'},
      channel_semantics={'mach': 'cell Mach number'},
    ),),
    diagnostics={'cell_count': 2, 'production_claim_allowed': False},
    warnings=('fixture warning',),
  )


def test_model_gallery_writes_bundle_bound_views_and_metadata(tmp_path: Path) -> None:
  os.environ['MPLCONFIGDIR'] = str(tmp_path / 'mplconfig')
  import matplotlib
  matplotlib.use('Agg')

  bundle = _bundle()
  spec = ModelVisualizationGallerySpec.for_bundle(
    bundle,
    view_kind='model.field-inspector',
    station_index=1,
    field_id='cells',
    field_channel_id='mach',
    path_ids=('shock-boundary',),
    x_scale=AxisScale.LINEAR,
  )
  manifest = render_model_visualization_gallery(bundle, tmp_path / 'gallery', spec=spec)
  payload = json.loads(manifest.manifest_path.read_text(encoding='utf-8'))

  assert manifest.schema == MODEL_GALLERY_MANIFEST_SCHEMA
  assert manifest.lane_id == 'shock-cell-basic-v1'
  assert payload['spec_digest_sha256'] == spec.digest_sha256()
  assert payload['source']['bundle_digest_sha256'] == bundle.digest_sha256()
  assert payload['source']['claims']['production_claim_allowed'] is False
  assert {artifact['view_id'] for artifact in payload['artifacts']} >= {
    'metadata.model-bundle',
    'metadata.model-gallery-spec',
    'model.overview',
    'model.projections',
    'model.channels',
    'model.fields',
  }
  assert all((tmp_path / 'gallery' / artifact['path']).exists() for artifact in payload['artifacts'])
  assert json.loads((tmp_path / 'gallery' / 'model_bundle.json').read_text(encoding='utf-8'))['lane_id'] == 'shock-cell-basic-v1'


def test_model_gallery_can_export_json_without_plot_dependency(tmp_path: Path) -> None:
  bundle = _bundle()
  manifest = render_model_visualization_gallery(bundle, tmp_path / 'json-only', render_plots=False)
  assert len(manifest.artifacts) == 2
  assert all((tmp_path / 'json-only' / artifact.path).exists() for artifact in manifest.artifacts)


@pytest.mark.parametrize('lane', ModelVisualizationLane)
def test_model_gallery_accepts_each_declared_model_lane(lane: ModelVisualizationLane, tmp_path: Path) -> None:
  bundle = replace(_bundle(), lane=lane)
  manifest = render_model_visualization_gallery(
    bundle,
    tmp_path / lane.value,
    render_plots=False,
  )
  assert manifest.lane_id == lane.value
  assert manifest.source['bundle_digest_sha256'] == bundle.digest_sha256()


def test_model_gallery_rejects_rebound_and_unknown_field_or_path(tmp_path: Path) -> None:
  bundle = _bundle()
  with pytest.raises(ValueError, match='different bundle'):
    render_model_visualization_gallery(
      bundle,
      tmp_path,
      spec=ModelVisualizationGallerySpec(
        bundle_digest_sha256='f' * 64,
      ),
      render_plots=False,
    )
  with pytest.raises(KeyError, match='unknown field_id'):
    render_model_visualization_gallery(
      bundle,
      tmp_path / 'bad-field',
      spec=ModelVisualizationGallerySpec.for_bundle(bundle, field_id='missing'),
      render_plots=False,
    )
  with pytest.raises(KeyError, match='unknown model visualization path'):
    render_model_visualization_gallery(
      bundle,
      tmp_path / 'bad-path',
      spec=ModelVisualizationGallerySpec.for_bundle(bundle, path_ids=('missing',)),
      render_plots=False,
    )
