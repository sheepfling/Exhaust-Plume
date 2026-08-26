"""Standalone linked galleries for strict standard product results.

This module writes a self-contained HTML evaluation page.  The page uses only
embedded contract data and inline SVG, so it can be opened from a file without
network access.  It is intentionally an evaluation utility: it does not
create a provider, infer missing geometry/ray paths, or manufacture an FPA.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from exhaust_plume.api import (
  PlumeFluxSectionResult,
  ProductResult,
  SectionedTubeResult,
  SpectralRadiantIntensityResult,
  SpectralRayTransferResult,
  VisualizationSpec,
  WavelengthDisplayUnit,
  project_plume_flux_view,
  project_sectioned_tube_view,
  project_spectral_radiant_intensity_view,
  project_spectral_ray_transfer_view,
)
from exhaust_plume.products.workflow_gallery import _source_metadata

__all__ = (
  'INTERACTIVE_GALLERY_SCHEMA',
  'write_interactive_product_gallery',
)

INTERACTIVE_GALLERY_SCHEMA = 'plume.visualization.interactive-gallery@1'


def _resolve_spec(
  result: ProductResult,
  spec: VisualizationSpec | None,
  *,
  default_view_kind: str,
  product_prefix: str,
) -> VisualizationSpec:
  resolved = spec or VisualizationSpec.for_result(result, view_kind=default_view_kind)
  resolved.validate_for_result(result)
  if not resolved.view_kind.startswith(f'{product_prefix}.'):
    raise ValueError(
      f'view spec {resolved.view_kind!r} is not valid for the {product_prefix} product'
    )
  ####
  if resolved.wavelength_display_unit is None and product_prefix in {'signature', 'ray-transfer'}:
    resolved = resolved.model_copy(update={'wavelength_display_unit': WavelengthDisplayUnit.UM})
  ####
  return resolved
####


def _common_payload(result: ProductResult, spec: VisualizationSpec, product: str) -> dict[str, Any]:
  return {
    'schema': INTERACTIVE_GALLERY_SCHEMA,
    'product': product,
    'source': _source_metadata(result),
    'view_spec': spec.model_dump(mode='json'),
    'view_spec_digest_sha256': spec.digest_sha256(),
  }
####


def _visual_payload(result: SectionedTubeResult, spec: VisualizationSpec) -> dict[str, Any]:
  projection = project_sectioned_tube_view(result, spec)
  geometry = projection.data.geometry
  return {
    **_common_payload(result, spec, 'visual'),
    'geometry': {
      'arc_length_m': list(geometry.arc_length_m),
      'centerline_m': [list(point) for point in geometry.centerline_m],
      'tangent': [list(point) for point in geometry.tangent],
      'normal_1': [list(point) for point in geometry.normal_1],
      'normal_2': [list(point) for point in geometry.normal_2],
      'semi_axis_1_m': list(geometry.semi_axis_1_m),
      'semi_axis_2_m': list(geometry.semi_axis_2_m),
    },
    'channels': [
      {
        'channel_id': channel.channel_id,
        'semantic': channel.semantic,
        'unit': channel.unit,
        'component_index': channel.component_index,
        'values': list(channel.values),
      }
      for channel in projection.data.channels
    ],
    'initial_selection': {
      'station_index': projection.station_index,
      'channel_key': (
        None
        if projection.selected_channel is None
        else f'{projection.selected_channel.channel_id}:{projection.selected_channel.component_index}'
      ),
    },
  }
####


def _signature_payload(result: SpectralRadiantIntensityResult, spec: VisualizationSpec) -> dict[str, Any]:
  projection = project_spectral_radiant_intensity_view(result, spec)
  grid = projection.grid
  return {
    **_common_payload(result, spec, 'signature'),
    'directions': [list(direction) for direction in grid.directions],
    'wavelengths_m': list(grid.wavelengths_m),
    'values': [list(row) for row in grid.radiant_intensity_W_sr_m],
    'validity_mask': [list(row) for row in grid.validity_mask],
    'initial_selection': {
      'direction_index': projection.direction_index,
      'wavelength_index': projection.wavelength_index,
    },
  }
####


def _ray_payload(result: SpectralRayTransferResult, spec: VisualizationSpec) -> dict[str, Any]:
  projection = project_spectral_ray_transfer_view(result, spec)
  data = projection.data
  return {
    **_common_payload(result, spec, 'ray-transfer'),
    'wavelengths_m': list(data.wavelengths_m),
    'rays': [
      {
        'ray_id': line.ray_id,
        'origin_m': list(line.origin_m),
        'direction': list(line.direction),
        'source_radiance': list(line.source_radiance_W_m2_sr_m),
        'background_transmittance': list(line.background_transmittance),
        'validity_mask': list(line.validity_mask),
        'item_status': line.item_status.value,
      }
      for line in data.lines
    ],
    'initial_selection': {
      'ray_id': projection.selected_line.ray_id,
      'wavelength_index': projection.wavelength_index,
    },
  }
####


def _flux_payload(result: PlumeFluxSectionResult, spec: VisualizationSpec) -> dict[str, Any]:
  projection = project_plume_flux_view(result, spec)
  glyph = projection.glyph
  return {
    **_common_payload(result, spec, 'flux'),
    'translation_m': list(glyph.section_translation_m),
    'normal': list(glyph.normal),
    'momentum_flux_N': list(glyph.momentum_flux_N),
    'area_m2': glyph.area_m2,
    'mass_flow_kgps': glyph.mass_flow_kgps,
    'total_energy_flow_W': glyph.total_energy_flow_W,
    'pressure_Pa': glyph.pressure_Pa,
    'ambient_pressure_Pa': glyph.ambient_pressure_Pa,
    'pressure_match_relative_residual': glyph.pressure_match_relative_residual,
    'species': [
      {'species_id': species_id, 'mass_flow_kgps': value}
      for species_id, value in glyph.species_mass_flows_kgps
    ],
    'second_moment_m2': [list(row) for row in glyph.cross_section_second_moment_m2],
    'initial_selection': {'species_index': projection.species_index},
  }
####


def _page_shell(payload: Mapping[str, Any]) -> str:
  data_literal = json.dumps(payload, allow_nan=False, ensure_ascii=True, separators=(',', ':')).replace('</', '<\\/')
  title = f"Exhaust-plume linked gallery — {payload['product']}"
  return (
    '<!doctype html>\n'
    '<html lang="en"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1">'
    f'<title>{title}</title>'
    '<style>'
    ':root{color-scheme:light dark;--fg:#17202a;--muted:#59636e;--bg:#f7f8fa;--line:#b8c0c8;--accent:#c9273f;--blue:#3f73a8;}'
    '@media(prefers-color-scheme:dark){:root{--fg:#edf2f7;--muted:#aeb9c4;--bg:#171a1f;--line:#53606d;--accent:#ff7585;--blue:#82b7e8;}}'
    'body{margin:0;padding:22px;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif;}'
    'main{max-width:1240px;margin:auto;}h1{font-size:22px;margin:0 0 4px;}h2{font-size:16px;margin:16px 0 6px;}'
    'code,pre,select,button{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;}code{color:var(--muted);}'
    '.toolbar{display:flex;gap:14px;flex-wrap:wrap;align-items:end;margin:16px 0 8px;padding:10px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line);}'
    'label{display:flex;flex-direction:column;gap:4px;color:var(--muted);}select,button{padding:5px 7px;border:1px solid var(--line);background:transparent;color:var(--fg);}'
    'button{cursor:pointer;}button:hover{border-color:var(--accent);}.selection{white-space:pre-wrap;color:var(--muted);min-height:34px;}'
    'svg{display:block;width:100%;height:auto;border:1px solid var(--line);background:transparent;}'
    '.meta{margin-top:14px;border-top:1px solid var(--line);padding-top:8px;}summary{cursor:pointer;color:var(--muted);}pre{white-space:pre-wrap;overflow:auto;max-height:340px;}'
    '</style></head><body><main>'
    f'<h1>{title}</h1><code id="identity"></code>'
    '<div id="controls" class="toolbar"></div><div id="selection" class="selection"></div>'
    '<svg id="plot" viewBox="0 0 1200 720" role="img" aria-label="linked exhaust-plume product views"></svg>'
    '<details class="meta"><summary>source, validity, fidelity, and provenance</summary><pre id="metadata"></pre></details>'
    '<script>const DATA='
    + data_literal
    + r''';
const SVG_NS='http://www.w3.org/2000/svg';
const svg=document.getElementById('plot');
const controls=document.getElementById('controls');
const selectionBox=document.getElementById('selection');
document.getElementById('identity').textContent=DATA.source.capability_id+' | '+DATA.source.fidelity.model_fidelity+' | '+DATA.source.fidelity.validation_level+' | frame='+DATA.source.frame.frame_id+' | content='+DATA.source.content_sha256;
document.getElementById('metadata').textContent=JSON.stringify({source:DATA.source,view_spec:DATA.view_spec,view_spec_digest_sha256:DATA.view_spec_digest_sha256},null,2);
const state=JSON.parse(JSON.stringify(DATA.initial_selection));
const esc=value=>String(value).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const finite=value=>value!==null&&Number.isFinite(value);
const colors=['#c9273f','#3f73a8','#54a24b','#f58518','#9467bd','#17becf'];
function addControl(label,id,options,selected,onChange){
  const wrap=document.createElement('label'); wrap.textContent=label;
  const select=document.createElement('select'); select.id=id;
  for(const option of options){const node=document.createElement('option');node.value=option.value;node.textContent=option.label;select.appendChild(node);}
  select.value=String(selected); select.addEventListener('change',()=>{onChange(select.value);draw();}); wrap.appendChild(select); controls.appendChild(wrap);
}
function addButton(label,onClick){const button=document.createElement('button');button.type='button';button.textContent=label;button.addEventListener('click',onClick);controls.appendChild(button);}
function currentSelection(){return JSON.parse(JSON.stringify(state));}
function installControls(){
  if(DATA.product==='visual'){
    addControl('station','station',DATA.geometry.arc_length_m.map((value,index)=>({value:index,label:index+' — s='+value+' m'})),state.station_index,value=>{state.station_index=Number(value);});
    const channelOptions=[{value:'none',label:'all declared channels'}].concat(DATA.channels.map(channel=>({value:channel.channel_id+':'+channel.component_index,label:channel.channel_id+'['+channel.component_index+'] — '+channel.semantic})));
    addControl('channel','channel',channelOptions,state.channel_key??'none',value=>{state.channel_key=value==='none'?null:value;});
  }
  if(DATA.product==='signature'){
    addControl('direction','direction',DATA.directions.map((value,index)=>({value:index,label:index+' — ('+value.map(item=>item.toFixed(3)).join(', ')+')'})),state.direction_index,value=>{state.direction_index=Number(value);});
    addControl('wavelength','wavelength',DATA.wavelengths_m.map((value,index)=>({value:index,label:index+' — '+(value*1e6).toPrecision(5)+' μm'})),state.wavelength_index,value=>{state.wavelength_index=Number(value);});
  }
  if(DATA.product==='ray-transfer'){
    addControl('ray','ray',DATA.rays.map((value,index)=>({value:index,label:value.ray_id+' — '+value.item_status})),DATA.rays.findIndex(value=>value.ray_id===state.ray_id),value=>{state.ray_id=DATA.rays[Number(value)].ray_id;});
    addControl('wavelength','wavelength',DATA.wavelengths_m.map((value,index)=>({value:index,label:index+' — '+(value*1e6).toPrecision(5)+' μm'})),state.wavelength_index,value=>{state.wavelength_index=Number(value);});
  }
  if(DATA.product==='flux'){
    const options=[{value:'none',label:'no species selection'}].concat(DATA.species.map((value,index)=>({value:index,label:index+' — '+value.species_id})));
    addControl('species','species',options,state.species_index??'none',value=>{state.species_index=value==='none'?null:Number(value);});
  }
  addButton('Export current view spec',()=>{
    const exportPayload={schema:'plume.visualization.spec-export@1',view_spec:{...DATA.view_spec,selection:currentSelection()},view_spec_digest_sha256:DATA.view_spec_digest_sha256,source:{capability_id:DATA.source.capability_id,schema_version:DATA.source.schema_version,snapshot_id:DATA.source.snapshot_id,content_sha256:DATA.source.content_sha256,frame_id:DATA.source.frame.frame_id}};
    const blob=new Blob([JSON.stringify(exportPayload,null,2)+'\n'],{type:'application/json'});const link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='visualization_spec.json';link.click();URL.revokeObjectURL(link.href);
  });
}
function range(values){const valid=values.filter(finite);if(!valid.length)return [0,1];let lo=Math.min(...valid),hi=Math.max(...valid);if(lo===hi){const pad=Math.max(Math.abs(lo)*.1,1);lo-=pad;hi+=pad;}return [lo,hi];}
function sx(value,lo,hi,x,w){return x+(value-lo)/(hi-lo)*w;}
function sy(value,lo,hi,y,h){return y+h-(value-lo)/(hi-lo)*h;}
function text(parts,x,y,value,size=12,anchor='start',fill='var(--fg)'){parts.push('<text x="'+x+'" y="'+y+'" font-size="'+size+'" text-anchor="'+anchor+'" fill="'+fill+'">'+esc(value)+'</text>');}
function frame(parts,x,y,w,h,title,xlabel,ylabel){parts.push('<rect x="'+x+'" y="'+y+'" width="'+w+'" height="'+h+'" fill="none" stroke="var(--line)"/>');text(parts,x+5,y+16,title,13);text(parts,x+w/2,y+h+22,xlabel,11,'middle','var(--muted)');text(parts,x-8,y+h/2,ylabel,11,'middle','var(--muted)');}
function pathFor(points,xf,yf){let d='',open=false;for(const point of points){if(point[1]===null||!finite(point[1])){open=false;continue;}const command=open?'L':'M';d+=command+xf(point[0])+','+yf(point[1])+' ';open=true;}return d;}
function lineChart(parts,x,y,w,h,title,xs,series,xlabel,ylabel,selectedIndex=-1){const pad={l:48,r:12,t:28,b:30},px=x+pad.l,py=y+pad.t,pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;const xr=range(xs),all=series.flatMap(item=>item.values),yr=range(all);frame(parts,x,y,w,h,title,xlabel,ylabel);for(let i=0;i<=4;i++){const gx=px+pw*i/4,gy=py+ph*i/4;parts.push('<path d="M'+gx+' '+py+'V'+(py+ph)+' M'+px+' '+gy+'H'+(px+pw)+'" stroke="var(--line)" opacity=".35"/>');text(parts,gx,py+ph+15,(xr[0]+(xr[1]-xr[0])*i/4).toPrecision(4),9,'middle','var(--muted)');text(parts,px-6,gy+3,(yr[1]-(yr[1]-yr[0])*i/4).toPrecision(4),9,'end','var(--muted)');}series.forEach((item,index)=>{const points=xs.map((value,column)=>[value,item.values[column]]);const d=pathFor(points,value=>sx(value,xr[0],xr[1],px,pw),value=>sy(value,yr[0],yr[1],py,ph));if(d)parts.push('<path d="'+d+'" fill="none" stroke="'+colors[index%colors.length]+'" stroke-width="'+(index===selectedIndex?2.8:1.4)+'"/>');const valid=points.filter(point=>point[1]!==null);for(const point of valid)parts.push('<circle cx="'+sx(point[0],xr[0],xr[1],px,pw)+'" cy="'+sy(point[1],yr[0],yr[1],py,ph)+'" r="'+(index===selectedIndex?4:2.5)+'" fill="'+colors[index%colors.length]+'"/>');text(parts,px+8+index*105,py+12,item.label,9,'start',colors[index%colors.length]);});}
function scatterChart(parts,x,y,w,h,title,points,xlabel,ylabel,selectedIndex=-1){const pad={l:45,r:12,t:28,b:30},px=x+pad.l,py=y+pad.t,pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;const xr=range(points.map(item=>item[0])),yr=range(points.map(item=>item[1]));frame(parts,x,y,w,h,title,xlabel,ylabel);for(let index=0;index<points.length;index++){const point=points[index];parts.push('<circle cx="'+sx(point[0],xr[0],xr[1],px,pw)+'" cy="'+sy(point[1],yr[0],yr[1],py,ph)+'" r="'+(index===selectedIndex?7:4)+'" fill="'+(index===selectedIndex?'var(--accent)':'var(--blue)')+'"/>');text(parts,sx(point[0],xr[0],xr[1],px,pw)+6,sy(point[1],yr[0],yr[1],py,ph)-5,String(index),9);}}
function barChart(parts,x,y,w,h,title,labels,values,ylabel,selectedIndex=null){const pad={l:48,r:12,t:30,b:45},px=x+pad.l,py=y+pad.t,pw=w-pad.l-pad.r,ph=h-pad.t-pad.b;const yr=range(values);frame(parts,x,y,w,h,title,'',''+ylabel);const step=pw/Math.max(values.length,1);values.forEach((value,index)=>{const top=sy(value,yr[0],yr[1],py,ph);const bottom=sy(0,yr[0],yr[1],py,ph);const height=Math.max(1,bottom-top);parts.push('<rect x="'+(px+step*index+step*.14)+'" y="'+top+'" width="'+step*.72+'" height="'+height+'" fill="'+(index===selectedIndex?'var(--accent)':'var(--blue)')+'"/>');text(parts,px+step*(index+.5),py+ph+16,labels[index],10,'middle');text(parts,px+step*(index+.5),top-5,Number(value).toPrecision(4),9,'middle');});}
function drawVisual(){const g=DATA.geometry,parts=[];svg.setAttribute('viewBox','0 0 1200 720');const projections=[[0,1,'XY'],[0,2,'XZ'],[1,2,'YZ']];projections.forEach((item,index)=>{const points=g.centerline_m.map(point=>[point[item[0]],point[item[1]]]);const station=[points[state.station_index]];scatterChart(parts,20+index*395,20,370,260,item[2]+' projection',points,item[0]===0?'x [m]':'y [m]',item[1]===1?'y [m]':'z [m]',state.station_index);});const channelKey=state.channel_key;const selectedChannels=channelKey?DATA.channels.filter(channel=>channel.channel_id+':'+channel.component_index===channelKey):DATA.channels;lineChart(parts,20,315,760,370,'axial declared feature channels',g.arc_length_m,selectedChannels.map(channel=>({label:channel.channel_id+'['+channel.component_index+']',values:channel.values})), 'arc length [m]','value',channelKey?0:-1);const station=state.station_index,semi1=g.semi_axis_1_m[station],semi2=g.semi_axis_2_m[station],cross=[];for(let i=0;i<=96;i++){const t=2*Math.PI*i/96;cross.push([semi1*Math.cos(t),semi2*Math.sin(t)]);}scatterChart(parts,810,315,370,370,'station '+station+' cross-section',cross,'local normal_1 [m]','local normal_2 [m]',-1);text(parts,825,695,'center='+g.centerline_m[station].map(value=>value.toFixed(3)).join(', ')+' m | tangent='+g.tangent[station].map(value=>value.toFixed(3)).join(', '),9,'start','var(--muted)');svg.innerHTML=parts.join('');}
function drawSignature(){const parts=[],xs=DATA.wavelengths_m.map(value=>value*1e6),series=DATA.values.map((values,index)=>({label:'dir '+index,values:values}));svg.setAttribute('viewBox','0 0 1200 720');lineChart(parts,20,20,740,670,'spectral radiant intensity by direction',xs,series,'wavelength [μm]','Jλ [W sr⁻¹ m⁻¹]',state.direction_index);const points=DATA.directions.map((direction,index)=>[direction[0],direction[1]]);scatterChart(parts,785,20,395,670,'direction x/y projection at λ '+xs[state.wavelength_index].toPrecision(5)+' μm',points,'direction x [1]','direction y [1]',state.direction_index);points.forEach((point,index)=>text(parts,sx(point[0],...range(points.map(item=>item[0])),830,330)+6,sy(point[1],...range(points.map(item=>item[1])),48,580)-5,'z='+DATA.directions[index][2].toFixed(3),9));svg.innerHTML=parts.join('');}
function drawRay(){const parts=[],rayIndex=DATA.rays.findIndex(ray=>ray.ray_id===state.ray_id),xs=DATA.wavelengths_m.map(value=>value*1e6),rays=DATA.rays;svg.setAttribute('viewBox','0 0 1200 720');const bundlePoints=[];rays.forEach(ray=>{const end=ray.origin_m.map((value,index)=>value+DATA.view_spec.ray_display_length_m*ray.direction[index]);bundlePoints.push([ray.origin_m[0],ray.origin_m[1]], [end[0],end[1]]);});scatterChart(parts,20,20,440,670,'ray origins and display directions (XY)',bundlePoints,'x [m]','y [m]',rayIndex*2);rays.forEach((ray,index)=>{const end=ray.origin_m.map((value,component)=>value+DATA.view_spec.ray_display_length_m*ray.direction[component]);parts.push('<path d="M'+(70+end[0]*220)+' '+(650-end[1]*220)+'L'+(70+ray.origin_m[0]*220)+' '+(650-ray.origin_m[1]*220)+'" stroke="'+(index===rayIndex?'var(--accent)':'var(--blue)')+'"/>');});lineChart(parts,485,20,695,320,'source radiance',xs,rays.map(ray=>({label:ray.ray_id,values:ray.source_radiance})), 'wavelength [μm]','source radiance',rayIndex);lineChart(parts,485,370,695,320,'background transmittance',xs,rays.map(ray=>({label:ray.ray_id,values:ray.background_transmittance})), 'wavelength [μm]','transmittance',rayIndex);svg.innerHTML=parts.join('');}
function drawFlux(){const parts=[];svg.setAttribute('viewBox','0 0 1200 720');barChart(parts,20,20,370,300,'section normal components',['x','y','z'],DATA.normal,'component [1]',null);barChart(parts,410,20,370,300,'momentum-flux components',['x','y','z'],DATA.momentum_flux_N,'N',null);barChart(parts,800,20,380,300,'species mass flow',DATA.species.map(value=>value.species_id),DATA.species.map(value=>value.mass_flow_kgps), 'kg/s',state.species_index);const labels=['area [m²]','mass [kg/s]','energy [W]','pressure [Pa]','ambient [Pa]','residual [1]'];const values=[DATA.area_m2,DATA.mass_flow_kgps,DATA.total_energy_flow_W,DATA.pressure_Pa,DATA.ambient_pressure_Pa,DATA.pressure_match_relative_residual];barChart(parts,20,350,760,330,'declared engineering scalars',labels,values,'value',null);text(parts,820,410,'section translation [m]: '+DATA.translation_m.map(value=>value.toFixed(4)).join(', '),12);text(parts,820,440,'selected species: '+(state.species_index===null?'none':DATA.species[state.species_index].species_id),12);text(parts,820,480,'second moment [m²]:',12);text(parts,820,505,JSON.stringify(DATA.second_moment_m2),11,'start','var(--muted)');svg.innerHTML=parts.join('');}
function draw(){if(DATA.product==='visual')drawVisual();if(DATA.product==='signature')drawSignature();if(DATA.product==='ray-transfer')drawRay();if(DATA.product==='flux')drawFlux();selectionBox.textContent='Current linked selection:\n'+JSON.stringify(currentSelection(),null,2);}
installControls();draw();
</script></main></body></html>'''
  )
####


def write_interactive_product_gallery(
  result: ProductResult,
  path: str | Path,
  *,
  spec: VisualizationSpec | None = None,
) -> Path:
  """Write one standalone linked HTML gallery for a strict product result."""

  if isinstance(result, SectionedTubeResult):
    resolved = _resolve_spec(result, spec, default_view_kind='visual.interactive', product_prefix='visual')
    payload = _visual_payload(result, resolved)
  elif isinstance(result, SpectralRadiantIntensityResult):
    resolved = _resolve_spec(result, spec, default_view_kind='signature.interactive', product_prefix='signature')
    payload = _signature_payload(result, resolved)
  elif isinstance(result, SpectralRayTransferResult):
    resolved = _resolve_spec(result, spec, default_view_kind='ray-transfer.interactive', product_prefix='ray-transfer')
    payload = _ray_payload(result, resolved)
  elif isinstance(result, PlumeFluxSectionResult):
    resolved = _resolve_spec(result, spec, default_view_kind='flux.interactive', product_prefix='flux')
    payload = _flux_payload(result, resolved)
  else:
    raise TypeError('result must be one of the standard exhaust_plume.api product results')
  ####
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(_page_shell(payload), encoding='utf-8')
  return output
####
