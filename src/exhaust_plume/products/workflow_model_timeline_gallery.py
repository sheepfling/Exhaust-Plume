"""Offline, exact-sample gallery for a mission Visualization timeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exhaust_plume.products.mission_timeline import MissionVisualizationTimeline
from exhaust_plume.products.workflow_model_gallery import (
  ModelVisualizationGallerySpec,
  _mesh,
  render_model_visualization_gallery,
)

__all__ = (
  'MODEL_VISUALIZATION_TIMELINE_GALLERY_SCHEMA',
  'write_interactive_model_visualization_timeline_gallery',
)

MODEL_VISUALIZATION_TIMELINE_GALLERY_SCHEMA = (
  'plume.visualization.model-mission-timeline-gallery@1'
)


def _timeline_spatial_bounds(
  timeline: MissionVisualizationTimeline,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
  points: list[tuple[float, float, float]] = []
  for sample in timeline.samples:
    bundle = sample.visualization
    vertices, _faces, _face_sections = _mesh(bundle, 24)
    points.extend(vertices)
    points.extend(
      tuple(float(value) for value in section.center_m)
      for section in bundle.sectioned_tube.sections
    )
    points.extend(
      tuple(float(value) for value in point)
      for path in bundle.paths
      for point in path.points_m
    )
    points.extend(
      (float(x), float(radius), 0.0)
      for field in bundle.fields
      for polygon in field.polygons_xr_m
      for x, radius in polygon
    )
  ####
  lower = tuple(min(point[axis] for point in points) for axis in range(3))
  upper = tuple(max(point[axis] for point in points) for axis in range(3))
  span = max(upper[axis] - lower[axis] for axis in range(3))
  margin = max(span * 0.02, 1.0e-6)
  return tuple(
    (lower[axis] - margin, upper[axis] + margin)
    for axis in range(3)
  )  # type: ignore[return-value]
####


def _timeline_geometry_x_axis_id(
  timeline: MissionVisualizationTimeline,
) -> str:
  if all(sample.state.geopotential_altitude_m is not None for sample in timeline.samples):
    return 'geopotential_altitude_m'
  return 'time_s'
####


def _sectioned_tube_display_geometry_metrics(
  bundle: Any,
) -> dict[str, float]:
  sections = bundle.sectioned_tube.sections
  arc_lengths_m = tuple(float(section.arc_length_m) for section in sections)
  return {
    'sectioned_tube_arc_extent_m': max(arc_lengths_m) - min(arc_lengths_m),
    'maximum_section_semiaxis_m': max(
      max(float(section.radius_major_m), float(section.radius_minor_m))
      for section in sections
    ),
  }
####


def _sample_payload(
  timeline: MissionVisualizationTimeline,
  sample_index: int,
  output: Path,
  *,
  render_plots: bool,
  spatial_bounds_m: tuple[
    tuple[float, float],
    tuple[float, float],
    tuple[float, float],
  ],
) -> dict[str, Any]:
  sample = timeline.samples[sample_index]
  sample_directory = Path('samples') / f'{sample_index:04d}'
  bundle = sample.visualization
  geometry_metrics = _sectioned_tube_display_geometry_metrics(bundle)
  gallery_spec = ModelVisualizationGallerySpec.for_bundle(
    bundle,
    view_kind='model.mission-timeline-sample',
    spatial_bounds_m=spatial_bounds_m,
  )
  gallery = render_model_visualization_gallery(
    bundle,
    output / sample_directory,
    spec=gallery_spec,
    render_plots=render_plots,
  )
  metadata = sample.visual_product.metadata
  state = sample.state
  pose = state.source_pose
  views = tuple(
    {
      'view_id': artifact.view_id,
      'path': (sample_directory / artifact.path).as_posix(),
      'mime_type': artifact.mime_type,
    }
    for artifact in gallery.artifacts
    if artifact.mime_type.startswith('image/')
  )
  return {
    'sample_index': sample_index,
    'time_s': state.time_s,
    'result_id': metadata.result_id,
    'snapshot_id': metadata.snapshot.snapshot_id,
    'model_lane_id': bundle.lane_id,
    'model_id': bundle.model_id,
    'model_version': bundle.model_version,
    'bundle_digest_sha256': bundle.digest_sha256(),
    'gallery_spec_digest_sha256': gallery.spec.digest_sha256(),
    'visualization_frame_id': bundle.frame_id,
    'output_frame_id': metadata.output_frame_id,
    'source_pose': {
      'frame_id': pose.frame_id,
      'translation_m': list(pose.translation_m),
      'rotation_xyzw': list(pose.rotation_xyzw),
    },
    'geopotential_altitude_m': state.geopotential_altitude_m,
    **geometry_metrics,
    'throttle_fraction': state.throttle_fraction,
    'remaining_propellant_mass_kg': state.remaining_propellant_mass_kg,
    'operating_point_id': state.operating_point_id,
    'continuous_state': dict(state.continuous_state),
    'dynamic_state': dict(state.dynamic_state),
    'ambient_state': dict(state.ambient_state),
    'claims': bundle.claims.model_dump(),
    'gallery_manifest_path': (
      sample_directory / gallery.manifest_path.name
    ).as_posix(),
    'views': list(views),
  }


def _page(payload: dict[str, Any]) -> str:
  serialized = json.dumps(
    payload,
    sort_keys=True,
    ensure_ascii=True,
    allow_nan=False,
    separators=(',', ':'),
  )
  serialized = (
    serialized.replace('&', '\\u0026')
    .replace('<', '\\u003c')
    .replace('>', '\\u003e')
  )
  return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Plume mission Visualization timeline</title>
<style>
:root{{color-scheme:light dark;--fg:#17202a;--muted:#59636e;--bg:#f7f8fa;--line:#b8c0c8;--panel:#fff}}
@media(prefers-color-scheme:dark){{:root{{--fg:#edf2f7;--muted:#aeb9c4;--bg:#171a1f;--line:#53606d;--panel:#20252b}}}}
*{{box-sizing:border-box}}body{{margin:0;padding:22px;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif}}
main{{max-width:1400px;margin:auto}}h1{{font-size:22px;margin:0 0 6px}}h2{{font-size:16px;margin:4px 0 10px}}
.muted{{color:var(--muted)}}.toolbar{{display:flex;align-items:center;gap:14px;flex-wrap:wrap;margin:18px 0;padding:12px 0;border-block:1px solid var(--line)}}
label{{display:flex;align-items:center;gap:10px;min-width:min(520px,100%);flex:1}}input[type=range]{{flex:1;min-width:120px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px}}.panel{{min-width:0;border:1px solid var(--line);border-radius:8px;background:var(--panel);padding:12px}}
.view img{{display:block;width:100%;height:auto}}.view a,.meta a{{color:inherit}}.meta{{margin-top:16px}}pre{{white-space:pre-wrap;overflow:auto;max-height:300px}}
.geometry-chart{{display:block;width:100%;height:auto;max-height:520px}}.geometry-chart text{{fill:var(--fg);font:12px system-ui,sans-serif}}.geometry-chart .axis{{stroke:var(--line);stroke-width:1}}.geometry-chart .sample-marker{{fill:#3978b8;stroke:var(--panel);stroke-width:1.5}}.geometry-chart .sample-marker.is-selected{{fill:#e87522;stroke:var(--fg);stroke-width:3}}
table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}}
@media(max-width:650px){{body{{padding:14px}}label{{min-width:100%}}}}
</style></head><body><main>
<h1>Plume mission Visualization timeline</h1>
<div id="identity" class="muted"></div>
<p class="muted">The selector moves between evaluated mission samples only. Geometry and field channels are shown from that exact sample; no visual values are interpolated. Spatial views use one shared extent across the timeline. Source pose and operating state remain attached as metadata. Geometry is rendered in its declared Visualization output frame; this page does not apply the source pose a second time. Fidelity and claim limits are unchanged.</p>
<div class="toolbar"><label for="sample-index">Exact sample <input id="sample-index" type="range" min="0" max="0" step="1" value="0"><output id="sample-time"></output></label></div>
<section class="panel"><h2>Selected mission state</h2><pre id="selected-state"></pre></section>
<section class="grid" id="views" aria-live="polite"></section>
<section class="panel meta"><h2>Retained plume display geometry by mission sample</h2><p class="muted">Points show exact evaluated samples with no interpolation. The axial extent and maximum section semiaxis describe retained sectioned-tube display geometry; they are not validated physical plume boundaries. Geometry remains in its declared Visualization frame.</p><svg id="geometry-chart" class="geometry-chart" viewBox="0 0 960 480" role="img" aria-labelledby="geometry-chart-title geometry-chart-description"></svg><div id="geometry-selection" class="muted" aria-live="polite"></div></section>
<section class="panel meta"><h2>Source trajectory samples</h2><div id="trajectory-frame" class="muted"></div><div id="trajectory"></div></section>
<section class="panel meta"><h2>Timeline manifest</h2><a href="mission_visualization_timeline_manifest.json">Open exact lineage and view manifest</a></section>
<script id="timeline-data" type="application/json">{serialized}</script>
<script>
const data=JSON.parse(document.getElementById('timeline-data').textContent);
const slider=document.getElementById('sample-index');
const timeOutput=document.getElementById('sample-time');
const stateOutput=document.getElementById('selected-state');
const viewRoot=document.getElementById('views');
const geometryChart=document.getElementById('geometry-chart');
const geometrySelection=document.getElementById('geometry-selection');
const entries=data.samples;
slider.max=String(entries.length-1);
document.getElementById('identity').textContent=`${{data.model_lane_id}} · ${{data.model_id}} ${{data.model_version}} · Visualization frame ${{data.visualization_frame_id}} · output frame ${{data.output_frame_id}} · source-pose frame ${{entries[0].source_pose.frame_id}}`;
const svgNamespace='http://www.w3.org/2000/svg';
function svgNode(name,attributes,text){{
  const node=document.createElementNS(svgNamespace,name);
  for(const [key,value] of Object.entries(attributes)) node.setAttribute(key,String(value));
  if(text!==undefined) node.textContent=text;
  return node;
}}
function numericDomain(values){{
  let low=Math.min(...values),high=Math.max(...values);
  if(low===high){{const padding=Math.max(Math.abs(low)*0.05,1e-6);low-=padding;high+=padding;}}
  return [low,high];
}}
function formatValue(value){{return Number(Number(value).toPrecision(4)).toString();}}
function drawGeometryChart(){{
  const metrics=data.trajectory_geometry_metrics;
  const xValues=entries.map(item=>item[metrics.x_axis_id]);
  const xDomain=numericDomain(xValues);
  geometryChart.append(
    svgNode('title',{{id:'geometry-chart-title'}},'Retained plume display geometry at exact mission samples'),
    svgNode('desc',{{id:'geometry-chart-description'}},`Two point plots against ${{metrics.x_axis_label}}. Points are exact evaluated samples with no connecting interpolation.`)
  );
  const left=118,right=925,plotHeight=122;
  metrics.series.forEach((series,index)=>{{
    const top=22+index*222,plotTop=top+34,plotBottom=plotTop+plotHeight;
    const yValues=entries.map(item=>item[series.metric_id]);
    const yDomain=numericDomain(yValues);
    geometryChart.append(svgNode('text',{{x:left,y:top+14,'font-weight':'600'}},`${{series.label}} [${{series.unit}}]`));
    geometryChart.append(
      svgNode('line',{{x1:left,y1:plotTop,x2:left,y2:plotBottom,class:'axis'}}),
      svgNode('line',{{x1:left,y1:plotBottom,x2:right,y2:plotBottom,class:'axis'}}),
      svgNode('text',{{x:left-8,y:plotTop+4,'text-anchor':'end'}},formatValue(yDomain[1])),
      svgNode('text',{{x:left-8,y:plotBottom,'text-anchor':'end'}},formatValue(yDomain[0])),
      svgNode('text',{{x:left,y:plotBottom+14,'text-anchor':'start'}},formatValue(xDomain[0])),
      svgNode('text',{{x:right,y:plotBottom+14,'text-anchor':'end'}},formatValue(xDomain[1])),
      svgNode('text',{{x:(left+right)/2,y:plotBottom+32,'text-anchor':'middle'}},metrics.x_axis_label)
    );
    entries.forEach((item,sampleIndex)=>{{
      const x=left+(xValues[sampleIndex]-xDomain[0])/(xDomain[1]-xDomain[0])*(right-left);
      const y=plotBottom-(yValues[sampleIndex]-yDomain[0])/(yDomain[1]-yDomain[0])*plotHeight;
      const marker=svgNode('circle',{{cx:x,cy:y,r:7,class:'sample-marker','data-mission-sample-index':sampleIndex,'data-metric-id':series.metric_id,tabindex:0,role:'button','aria-label':`Select sample ${{sampleIndex}}, ${{metrics.x_axis_label}} ${{formatValue(xValues[sampleIndex])}}, ${{series.label}} ${{formatValue(yValues[sampleIndex])}} ${{series.unit}}`}});
      marker.append(svgNode('title',{{}},`Sample ${{sampleIndex}}: ${{metrics.x_axis_label}} ${{formatValue(xValues[sampleIndex])}}; ${{series.label}} ${{formatValue(yValues[sampleIndex])}} ${{series.unit}}`));
      marker.addEventListener('click',()=>{{slider.value=String(sampleIndex);selectSample(sampleIndex);}});
      marker.addEventListener('keydown',event=>{{if(event.key==='Enter'||event.key===' '){{event.preventDefault();slider.value=String(sampleIndex);selectSample(sampleIndex);}}}});
      geometryChart.append(marker);
    }});
  }});
}}
drawGeometryChart();
function selectSample(index){{
  const item=entries[index];
  if(!item) return;
  timeOutput.value=`t = ${{item.time_s}} s`;
  stateOutput.textContent=JSON.stringify({{
    result_id:item.result_id,
    snapshot_id:item.snapshot_id,
    exact_time_s:item.time_s,
    source_pose:item.source_pose,
    geopotential_altitude_m:item.geopotential_altitude_m,
    throttle_fraction:item.throttle_fraction,
    remaining_propellant_mass_kg:item.remaining_propellant_mass_kg,
    operating_point_id:item.operating_point_id,
    continuous_state:item.continuous_state,
    dynamic_state:item.dynamic_state,
    ambient_state:item.ambient_state,
    claims:item.claims,
    sectioned_tube_arc_extent_m:item.sectioned_tube_arc_extent_m,
    maximum_section_semiaxis_m:item.maximum_section_semiaxis_m,
    bundle_digest_sha256:item.bundle_digest_sha256
  }},null,2);
  geometrySelection.textContent=`Selected sample ${{index}}: sectioned-tube axial extent ${{formatValue(item.sectioned_tube_arc_extent_m)}} m; maximum section semiaxis ${{formatValue(item.maximum_section_semiaxis_m)}} m.`;
  for(const marker of geometryChart.querySelectorAll('[data-mission-sample-index]')){{
    marker.classList.toggle('is-selected',Number(marker.getAttribute('data-mission-sample-index'))===index);
  }}
  viewRoot.replaceChildren();
  for(const view of item.views){{
    const card=document.createElement('article');
    card.className='panel view';
    const heading=document.createElement('h2');
    heading.textContent=view.view_id;
    const link=document.createElement('a');
    link.href=view.path;
    link.textContent='Open image';
    const image=document.createElement('img');
    image.src=view.path;
    image.alt=`${{view.view_id}} at mission time ${{item.time_s}} seconds`;
    image.loading='lazy';
    card.append(heading,image,link);
    viewRoot.append(card);
  }}
}}
document.getElementById('trajectory-frame').textContent=`Source position coordinates use ${{entries[0].source_pose.frame_id}}.`;
const trajectory=document.getElementById('trajectory');
const table=document.createElement('table');
const head=document.createElement('thead');
const headingRow=document.createElement('tr');
for(const label of ['Exact time [s]','Altitude [m]','Source position [m]','Throttle [1]','Snapshot ID']){{
  const cell=document.createElement('th');
  cell.textContent=label;
  headingRow.append(cell);
}}
head.append(headingRow);
const body=document.createElement('tbody');
for(const item of entries){{
  const row=document.createElement('tr');
  const values=[item.time_s,item.geopotential_altitude_m ?? 'not supplied',item.source_pose.translation_m.map(value=>value.toPrecision(7)).join(', '),item.throttle_fraction ?? 'not supplied',item.snapshot_id];
  for(const value of values){{
    const cell=document.createElement('td');
    cell.textContent=String(value);
    row.append(cell);
  }}
  body.append(row);
}}
table.append(head,body);
trajectory.replaceChildren(table);
slider.addEventListener('input',()=>selectSample(Number(slider.value)));
selectSample(0);
</script></main></body></html>'''


def write_interactive_model_visualization_timeline_gallery(
  timeline: MissionVisualizationTimeline,
  output_dir: str | Path,
  *,
  render_plots: bool = True,
) -> Path:
  """Write exact-time model galleries and a standalone timeline selector.

  The timeline contract guarantees one lane, model identity, output frame, and
  channel schema. This writer renders each retained sample independently and
  lets the reader select among those exact products; it does not interpolate
  geometry, fields, source pose, or physical values for display.
  """

  if not isinstance(timeline, MissionVisualizationTimeline):
    raise TypeError('timeline must be a MissionVisualizationTimeline')
  if not isinstance(render_plots, bool):
    raise TypeError('render_plots must be bool')
  ####
  output = Path(output_dir)
  output.mkdir(parents=True, exist_ok=True)
  spatial_bounds_m = _timeline_spatial_bounds(timeline)
  samples = tuple(
    _sample_payload(
      timeline,
      index,
      output,
      render_plots=render_plots,
      spatial_bounds_m=spatial_bounds_m,
    )
    for index in range(len(timeline.samples))
  )
  first_bundle = timeline.samples[0].visualization
  geometry_x_axis_id = _timeline_geometry_x_axis_id(timeline)
  geometry_x_axis_label = (
    'Geopotential altitude [m]'
    if geometry_x_axis_id == 'geopotential_altitude_m'
    else 'Mission time [s]'
  )
  payload: dict[str, Any] = {
    'schema': MODEL_VISUALIZATION_TIMELINE_GALLERY_SCHEMA,
    'mission_timeline_schema': 'plume.mission-timeline@1',
    'product': 'mission-visualization-timeline',
    'model_lane_id': timeline.lane_id,
    'model_id': first_bundle.model_id,
    'model_version': first_bundle.model_version,
    'visualization_frame_id': first_bundle.frame_id,
    'output_frame_id': timeline.output_frame_id,
    'sample_count': len(samples),
    'times_s': list(timeline.times_s),
    'source_positions_m': [list(position) for position in timeline.source_positions_m],
    'shared_spatial_bounds_m': [list(axis_bounds) for axis_bounds in spatial_bounds_m],
    'trajectory_geometry_metrics': {
      'x_axis_id': geometry_x_axis_id,
      'x_axis_label': geometry_x_axis_label,
      'samples_are_exact_evaluated_states': True,
      'interpolation': 'none',
      'interpretation': 'retained sectioned-tube display geometry; not a validated physical plume boundary',
      'series': [
        {
          'metric_id': 'sectioned_tube_arc_extent_m',
          'label': 'Retained sectioned-tube arc-length extent',
          'unit': 'm',
        },
        {
          'metric_id': 'maximum_section_semiaxis_m',
          'label': 'Maximum retained section semiaxis',
          'unit': 'm',
        },
      ],
    },
    'samples': list(samples),
    'guardrails': [
      'selection_is_limited_to_exact_evaluated_mission_samples',
      'visual_geometry_and_channels_are_not_interpolated_between_samples',
      'trajectory_geometry_metrics_use_exact_retained_sectioned_tube_samples',
      'trajectory_geometry_chart_has_no_interpolated_or_connected_samples',
      'sectioned_tube_metrics_are_display_geometry_not_validated_physical_boundaries',
      'source_pose_is_retained_as_metadata_and_not_applied_a_second_time',
      'each_sample_keeps_its_model_bundle_and_gallery_spec_digest',
      'rendering_does_not_raise_model_fidelity_or_claim_ceilings',
      'gallery_is_evaluation_output_not_physical_or_provider_validation',
    ],
  }
  manifest_path = output / 'mission_visualization_timeline_manifest.json'
  manifest_path.write_text(
    json.dumps(
      payload,
      sort_keys=True,
      indent=2,
      ensure_ascii=True,
      allow_nan=False,
    )
    + '\n',
    encoding='utf-8',
  )
  page_path = output / 'index.html'
  page_path.write_text(_page(payload), encoding='utf-8')
  return page_path
