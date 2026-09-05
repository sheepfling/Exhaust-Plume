"""Standalone no-network interactive view for deterministic FPA outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exhaust_plume.validation.fpa_visualization import (
  FpaDisplayLayer,
  FpaVisualizationInput,
  FpaVisualizationSpec,
  project_fpa_view,
)


FPA_INTERACTIVE_GALLERY_SCHEMA = 'plume.visualization.fpa-interactive@1'


def _json_script(payload: Any) -> str:
  return json.dumps(payload, allow_nan=False, ensure_ascii=True, separators=(',', ':')).replace('</', '<\\/')
####


def _layer_payload(
  inputs: FpaVisualizationInput,
  base_spec: FpaVisualizationSpec,
  layer: FpaDisplayLayer,
) -> dict[str, Any]:
  projection = project_fpa_view(
    inputs,
    base_spec.model_copy(update={
      'view_kind': f'fpa.interactive.{layer.value.replace("_", "-")}',
      'display_layer': layer,
    }),
  )
  return {
    'values': [list(row) for row in projection.layer_values],
    'validity_mask': [list(row) for row in projection.validity_mask],
  }
####


def write_interactive_fpa_gallery(
  inputs: FpaVisualizationInput,
  path: str | Path,
  *,
  spec: FpaVisualizationSpec | None = None,
) -> Path:
  """Write a self-contained FPA explorer with layer and pixel controls."""

  if not isinstance(inputs, FpaVisualizationInput):
    raise TypeError('inputs must be FpaVisualizationInput')
  ####
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  base_spec = spec or FpaVisualizationSpec.for_source(inputs.source, view_kind='fpa.interactive')
  base_spec.validate_for_source(inputs.source)
  layers = [
    FpaDisplayLayer.EXPECTED_ELECTRONS,
    FpaDisplayLayer.DARK_ELECTRONS,
    FpaDisplayLayer.NOISE_VARIANCE,
    FpaDisplayLayer.VALIDITY_MASK,
  ]
  if inputs.digitized is not None:
    layers.extend((FpaDisplayLayer.DIGITIZED_COUNTS, FpaDisplayLayer.SATURATED_MASK))
  ####
  payload: dict[str, Any] = {
    'schema': FPA_INTERACTIVE_GALLERY_SCHEMA,
    'product': 'focal-plane-array-downstream',
    'view_spec': base_spec.model_dump(mode='json'),
    'view_spec_digest_sha256': base_spec.digest_sha256(),
    'source': inputs.source.model_dump(mode='json'),
    'claim_ceiling': inputs.claim_ceiling,
    'validation_status': inputs.validation_status,
    'operator_ids': list(inputs.operator_ids),
    'width_px': inputs.image.width_px,
    'height_px': inputs.image.height_px,
    'wavelengths_m': list(inputs.image.wavelengths_m),
    'exposure_s': inputs.image.exposure_s,
    'source_semantics': inputs.image.source_semantics,
    'detector_response_id': inputs.image.detector_response_id,
    'atmospheric_path_operator_id': inputs.image.atmospheric_path_operator_id,
    'atmospheric_path_layer_digest': inputs.image.atmospheric_path_layer_digest,
    'atmospheric_path_layer_ids': list(inputs.image.atmospheric_path_layer_ids),
    'layers': {layer.value: _layer_payload(inputs, base_spec, layer) for layer in layers},
    'digitized_counts': None if inputs.digitized is None else [list(row) for row in inputs.digitized.counts],
    'saturated_mask': None if inputs.digitized is None else [list(row) for row in inputs.digitized.saturated_mask],
    'detector_response': None if inputs.detector_response is None else {
      'wavelengths_m': list(inputs.detector_response.wavelengths_m),
      'quantum_efficiency': list(inputs.detector_response.quantum_efficiency),
      'optical_throughput': list(inputs.detector_response.optical_throughput),
      'electron_response_per_joule': list(inputs.detector_response.electron_response_per_joule),
    },
  }
  layer_options = ''.join(
    f'<option value="{layer.value}">{layer.value}</option>' for layer in layers
  )
  html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>FPA downstream visualization</title>
<style>
:root {{ color-scheme: dark; --bg:#0e1116; --panel:#171c24; --text:#edf2f7; --muted:#aab7c4; --accent:#56c8ff; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:14px system-ui,sans-serif; }}
main {{ max-width:1180px; margin:0 auto; padding:22px; }}
.banner {{ border:1px solid #5b4830; background:#201a11; padding:12px 15px; border-radius:8px; color:#ffdca3; }}
.controls {{ display:flex; flex-wrap:wrap; gap:10px; align-items:end; padding:14px 0; }}
label {{ display:flex; flex-direction:column; gap:4px; color:var(--muted); }}
input,select,button {{ background:var(--panel); color:var(--text); border:1px solid #354252; border-radius:5px; padding:7px; }}
button {{ cursor:pointer; }}
.grid {{ display:grid; grid-template-columns:minmax(0,1fr) 310px; gap:16px; }}
.panel {{ background:var(--panel); border-radius:8px; padding:12px; }}
svg {{ width:100%; height:auto; min-height:430px; background:#10151c; border-radius:5px; }}
pre {{ white-space:pre-wrap; color:var(--muted); line-height:1.4; }}
.small {{ color:var(--muted); font-size:12px; }}
</style></head><body><main>
<h1>Focal-plane-array downstream view</h1>
<div class="banner">Deterministic expected detector output only — not a measured image, noise realization, detection result, or external validation claim.</div>
<div class="controls">
<label>Layer<select id="layer">{layer_options}</select></label>
<label>Row<input id="row" type="number" min="0" max="{inputs.image.height_px - 1}" value="0"></label>
<label>Column<input id="column" type="number" min="0" max="{inputs.image.width_px - 1}" value="0"></label>
<label>Wavelength index<input id="wavelength" type="number" min="0" max="{len(inputs.image.wavelengths_m) - 1}" value="0"></label>
<button id="export">Export current view spec</button>
</div>
<div class="grid"><section class="panel"><svg id="plot" viewBox="0 0 760 560" role="img" aria-label="FPA pixel grid"></svg><div class="small" id="caption"></div></section>
<aside class="panel"><h2>Selected pixel</h2><pre id="pixel"></pre><h2>Source</h2><pre id="source"></pre></aside></div>
<script>
const DATA = {_json_script(payload)};
const state = {{layer:Object.keys(DATA.layers)[0],row:0,column:0,wavelength:0}};
const svg = document.getElementById('plot');
const layerControl = document.getElementById('layer');
const rowControl = document.getElementById('row');
const columnControl = document.getElementById('column');
const wavelengthControl = document.getElementById('wavelength');
function esc(value) {{ return String(value).replace(/[&<>"']/g, char => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[char])); }}
function current() {{ return DATA.layers[state.layer]; }}
function color(value, min, max, valid) {{ if (!valid) return '#29313b'; const fraction = max===min ? 0.5 : (value-min)/(max-min); const hue = 215-215*Math.max(0,Math.min(1,fraction)); return 'hsl('+hue+' 85% 58%)'; }}
function draw() {{
  const matrix=current().values, mask=current().validity_mask, rows=DATA.height_px, cols=DATA.width_px;
  const values=matrix.flat().filter((value,index)=>mask.flat()[index]).map(Number), min=Math.min(...values), max=Math.max(...values);
  const left=70, top=46, width=620, height=420, cellW=width/cols, cellH=height/rows, parts=[];
  parts.push('<text x="'+left+'" y="24" fill="#edf2f7" font-size="16">'+esc(state.layer)+' | valid pixels masked</text>');
  for (let row=0; row<rows; row++) for (let column=0; column<cols; column++) {{
    const valid=Boolean(mask[row][column]), value=matrix[row][column];
    const selected=row===state.row && column===state.column;
    parts.push('<rect x="'+(left+column*cellW)+'" y="'+(top+row*cellH)+'" width="'+cellW+'" height="'+cellH+'" fill="'+color(value,min,max,valid)+'" stroke="'+(selected?'#56c8ff':'#0e1116')+'" stroke-width="'+(selected?'3':'1')+'"/>');
    parts.push('<text x="'+(left+column*cellW+cellW/2)+'" y="'+(top+row*cellH+cellH/2+4)+'" text-anchor="middle" fill="#fff" font-size="12">'+esc(valid?Number(value).toPrecision(5):'invalid')+'</text>');
  }}
  parts.push('<text x="'+(left+width/2)+'" y="'+(top+height+32)+'" text-anchor="middle" fill="#aab7c4">pixel column [index]</text>');
  parts.push('<text x="18" y="'+(top+height/2)+'" text-anchor="middle" transform="rotate(-90 18 '+(top+height/2)+')" fill="#aab7c4">pixel row [index]</text>');
  svg.innerHTML=parts.join('');
  const imageWavelength=DATA.wavelengths_m[state.wavelength];
  const digitized=DATA.digitized_counts===null?null:DATA.digitized_counts[state.row][state.column];
  const saturated=DATA.saturated_mask===null?null:DATA.saturated_mask[state.row][state.column];
  document.getElementById('pixel').textContent=JSON.stringify({{row_index:state.row,column_index:state.column,valid:mask[state.row][state.column],value:matrix[state.row][state.column],wavelength_m:imageWavelength,digitized_count:digitized,saturated:saturated}},null,2);
  document.getElementById('source').textContent=JSON.stringify({{content_sha256:DATA.source.content_sha256,provider_id:DATA.source.provider_id,snapshot_id:DATA.source.snapshot_id,frame_id:DATA.source.frame_id,operator_ids:DATA.operator_ids,source_semantics:DATA.source_semantics,claim_ceiling:DATA.claim_ceiling}},null,2);
  document.getElementById('caption').textContent='Exposure '+DATA.exposure_s+' s | detector '+DATA.detector_response_id+' | validation status '+DATA.validation_status;
}}
function update() {{ state.layer=layerControl.value; state.row=Math.max(0,Math.min(DATA.height_px-1,Number(rowControl.value)||0)); state.column=Math.max(0,Math.min(DATA.width_px-1,Number(columnControl.value)||0)); state.wavelength=Math.max(0,Math.min(DATA.wavelengths_m.length-1,Number(wavelengthControl.value)||0)); rowControl.value=state.row; columnControl.value=state.column; wavelengthControl.value=state.wavelength; draw(); }}
[layerControl,rowControl,columnControl,wavelengthControl].forEach(control=>control.addEventListener('input',update));
document.getElementById('export').addEventListener('click',()=>{{ const exported={{...DATA.view_spec,selection:{{row_index:state.row,column_index:state.column,wavelength_index:state.wavelength}},display_layer:state.layer,view_kind:'fpa.interactive.export'}}; const blob=new Blob([JSON.stringify(exported,null,2)+'\\n'],{{type:'application/json'}}); const link=document.createElement('a'); link.href=URL.createObjectURL(blob); link.download='fpa-visualization-spec.json'; link.click(); URL.revokeObjectURL(link.href); }});
update();
</script></main></body></html>'''
  output.write_text(html, encoding='utf-8')
  return output
####


__all__ = (
  'FPA_INTERACTIVE_GALLERY_SCHEMA',
  'write_interactive_fpa_gallery',
)
