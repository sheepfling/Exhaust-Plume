"""Standalone exact-sample Signature timeline explorer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from exhaust_plume.products.signature_timeline import (
  SignatureAngularBinning,
  SignatureTimeline,
)

__all__ = (
  'SIGNATURE_TIMELINE_INTERACTIVE_SCHEMA',
  'write_interactive_signature_timeline_gallery',
)

SIGNATURE_TIMELINE_INTERACTIVE_SCHEMA = (
  'plume.signature.angular-timeline-interactive@1'
)
_ANGULAR_COORDINATE_CONVENTION = {
  'azimuth': 'atan2(y, x), in [-180, 180) degrees',
  'elevation': 'atan2(z, hypot(x, y)), in [-90, 90] degrees',
  'positive_azimuth': '+X toward +Y',
  'positive_elevation': 'XY plane toward +Z',
  'pole_azimuth_display_deg': 0,
}


def _payload(
  timeline: SignatureTimeline,
  binning: SignatureAngularBinning,
) -> dict[str, Any]:
  return {
    'schema': SIGNATURE_TIMELINE_INTERACTIVE_SCHEMA,
    'product': 'signature-spectral-radiant-intensity-timeline',
    'quantity': 'spectral_radiant_intensity',
    'units': 'W sr^-1 m^-1',
    'direction_frame_id': timeline.direction_frame_id,
    'position_frame_id': timeline.position_frame_id,
    'angular_coordinate_convention': dict(_ANGULAR_COORDINATE_CONVENTION),
    'directions': [list(direction) for direction in timeline.directions],
    'wavelengths_m': list(timeline.wavelengths_m),
    'binning': {
      'azimuth_bin_count': binning.azimuth_bin_count,
      'elevation_bin_count': binning.elevation_bin_count,
    },
    'samples': [
      {
        'time_s': sample.time_s,
        'result_id': sample.result.metadata.result_id,
        'snapshot_id': sample.result.metadata.snapshot.snapshot_id,
        'provider_id': sample.result.metadata.provenance.provider_id,
        'model_lineage_id': sample.result.metadata.provenance.model_lineage_id,
        'source_position_m': list(
          sample.result.metadata.snapshot.source_pose.translation_m
        ),
        'values_W_sr_m': [
          list(row) for row in sample.result.spectral_radiant_intensity
        ],
        'validity_mask': [list(row) for row in sample.result.validity_mask],
        'direction_status': [
          status.code.value for status in sample.result.direction_status
        ],
        'absolute_standard_uncertainty_W_sr_m': (
          None
          if sample.result.absolute_standard_uncertainty is None
          else [
            list(row)
            for row in sample.result.absolute_standard_uncertainty
          ]
        ),
      }
      for sample in timeline.samples
    ],
    'guardrails': [
      'exact_timeline_samples_only_no_temporal_interpolation',
      'direction_traces_are_exact_sample_points_without_interpolation',
      'invalid_signature_samples_are_never_aggregated_as_zero',
      'angular_bins_are_display_aggregates_in_the_declared_direction_frame',
      'quantity_is_source_spectral_radiant_intensity_not_radiance',
      'atmosphere_ray_transfer_optics_and_detector_operators_are_not_applied',
      'source_result_and_snapshot_ids_are_retained_per_sample',
      'this_gallery_is_not_external_validation_evidence',
    ],
  }


_PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Signature timeline explorer</title>
<style>
:root{color-scheme:light dark;--fg:#17202a;--muted:#59636e;--bg:#f7f8fa;--line:#b8c0c8;--accent:#c9273f;--invalid:#8b9097}
@media(prefers-color-scheme:dark){:root{--fg:#edf2f7;--muted:#aeb9c4;--bg:#171a1f;--line:#53606d;--accent:#ff7585;--invalid:#7e8791}}
*{box-sizing:border-box}body{margin:0;padding:22px;background:var(--bg);color:var(--fg);font:14px system-ui,sans-serif}main{max-width:1320px;margin:auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:18px 0 7px}.muted,small{color:var(--muted)}
.toolbar{display:flex;gap:14px;flex-wrap:wrap;align-items:end;margin:16px 0;padding:10px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
label{display:flex;flex-direction:column;gap:4px;color:var(--muted)}select,button{padding:6px 8px;border:1px solid var(--line);background:transparent;color:var(--fg);font:12px ui-monospace,monospace}button{cursor:pointer}
.grid{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(320px,1fr);gap:16px}.panel{min-width:0;border:1px solid var(--line);padding:12px;border-radius:8px}
canvas{display:block;width:100%;height:auto}.status{min-height:46px;white-space:pre-wrap;color:var(--muted)}.meta{margin-top:16px;border-top:1px solid var(--line);padding-top:10px}pre{white-space:pre-wrap;overflow:auto;max-height:280px}
.scale{display:grid;grid-template-columns:auto minmax(80px,1fr) auto;align-items:center;gap:8px;margin:8px 4px;color:var(--muted);font:11px ui-monospace,monospace}.gradient{height:12px;border:1px solid var(--line);background:linear-gradient(90deg,#1e1450,#622070,#be3756,#f58236,#fcdd5f)}
@media(max-width:850px){.grid{grid-template-columns:1fr}body{padding:14px}}
</style></head><body><main>
<h1>Signature timeline explorer</h1>
<div id="identity" class="muted"></div>
<p class="muted">Source spectral radiant intensity Jλ [W sr⁻¹ m⁻¹]. In the declared direction frame, azimuth is atan2(y,x), positive from +X toward +Y; elevation is atan2(z,hypot(x,y)), positive from the XY plane toward +Z. Pole azimuth is set to 0° for display. Each angular bin shows the arithmetic mean of its valid sampled directions, without solid-angle weighting; it is not an angular integral. Hatching marks invalid samples. Atmosphere, ray transfer, optics, and detector response are not applied. This view is not validation evidence.</p>
<div class="toolbar">
  <label>Exact sample time<select id="time"></select></label>
  <label>Wavelength<select id="wavelength"></select></label>
  <label>Exact direction trace<select id="direction"></select></label>
  <button id="export" type="button">Export view spec</button>
</div>
<div class="grid">
  <section class="panel"><h2>Angular space</h2>
    <canvas id="heatmap" width="960" height="450" aria-label="Exact-time angular Signature heatmap"></canvas>
    <div class="scale" aria-label="Shared intensity color scale"><span id="scale-min"></span><div class="gradient" role="img" aria-label="low to high spectral radiant intensity"></div><span id="scale-max"></span></div>
    <small class="muted">Solid color is the valid direction-sample mean; it is not solid-angle weighted. Diagonal hatching marks invalid samples; blank cells have no sampled direction.</small>
    <div id="heatmap-status" class="status"></div>
    <div id="tooltip" class="status" role="status"></div>
  </section>
  <section class="panel"><h2>Exact direction across samples</h2>
    <canvas id="trace" width="720" height="500" aria-label="Sampled Signature intensity at one exact direction"></canvas>
    <div id="trace-status" class="status"></div>
  </section>
  <section class="panel"><h2>Exact source positions (X-Z projection)</h2>
    <canvas id="trajectory" width="720" height="360" aria-label="Exact source position samples projected into X-Z"></canvas>
    <div id="trajectory-status" class="status"></div>
  </section>
</div>
<section class="panel meta"><h2>Source pose at selected time</h2><div id="pose" class="status"></div></section>
<details class="meta"><summary>Source lineage and view contract</summary><pre id="metadata"></pre></details>
<script id="timeline-data" type="application/json">__TIMELINE_DATA__</script>
<script>
const DATA=JSON.parse(document.getElementById('timeline-data').textContent);
const timeSelect=document.getElementById('time');
const wavelengthSelect=document.getElementById('wavelength');
const directionSelect=document.getElementById('direction');
const heat=document.getElementById('heatmap'), trace=document.getElementById('trace'), trajectory=document.getElementById('trajectory');
const ctx=heat.getContext('2d'), traceCtx=trace.getContext('2d'), trajectoryCtx=trajectory.getContext('2d');
const A=DATA.binning.azimuth_bin_count,E=DATA.binning.elevation_bin_count;
const fmt=value=>Number(value).toPrecision(5);
const STYLE=getComputedStyle(document.documentElement);
const FG=STYLE.getPropertyValue('--fg').trim()||'#17202a', MUTED=STYLE.getPropertyValue('--muted').trim()||'#59636e', ACCENT=STYLE.getPropertyValue('--accent').trim()||'#c9273f';
const sampleIndex=()=>Number(timeSelect.value), wavelengthIndex=()=>Number(wavelengthSelect.value), directionIndex=()=>Number(directionSelect.value);
function populate(){
  DATA.samples.forEach((sample,index)=>{const option=document.createElement('option');option.value=index;option.textContent='t='+sample.time_s+' s';timeSelect.appendChild(option);});
  DATA.wavelengths_m.forEach((value,index)=>{const option=document.createElement('option');option.value=index;option.textContent=fmt(value*1e6)+' μm';wavelengthSelect.appendChild(option);});
  DATA.directions.forEach((value,index)=>{const option=document.createElement('option');option.value=index;option.textContent=index+' — ('+value.map(fmt).join(', ')+')';directionSelect.appendChild(option);});
}
function angularBin(direction){
  let az=Math.atan2(direction[1],direction[0])*180/Math.PI;if(az>=180)az=-180;
  const horizontal=Math.hypot(direction[0],direction[1]);if(horizontal===0)az=0;
  const el=Math.atan2(direction[2],horizontal)*180/Math.PI;
  return [Math.min(A-1,Math.floor((az+180)/360*A)),Math.min(E-1,Math.floor((el+90)/180*E))];
}
const memberships=DATA.directions.map(angularBin);
const allValidValues=wave=>DATA.samples.flatMap(sample=>sample.values_W_sr_m.map((row,d)=>sample.validity_mask[d][wave]?row[wave]:null)).filter(value=>value!==null&&Number.isFinite(value));
function color(value,lo,hi){const stops=[[30,20,80],[98,32,112],[190,55,86],[245,130,54],[252,220,95]];const t=hi===lo?0.5:Math.max(0,Math.min(1,(value-lo)/(hi-lo)))*(stops.length-1);const i=Math.min(stops.length-2,Math.floor(t)),f=t-i;const rgb=stops[i].map((component,k)=>Math.round(component+(stops[i+1][k]-component)*f));return 'rgb('+rgb.join(',')+')';}
function drawHeatmap(){
  const si=sampleIndex(),wi=wavelengthIndex(),sample=DATA.samples[si],loValues=allValidValues(wi);
  let lo=loValues.length?Math.min(...loValues):0,hi=loValues.length?Math.max(...loValues):1;if(hi===lo)hi=lo+1;
  ctx.clearRect(0,0,heat.width,heat.height);const left=62,top=25,right=20,bottom=52,pw=heat.width-left-right,ph=heat.height-top-bottom,cw=pw/A,ch=ph/E;
  const cells=Array.from({length:A*E},()=>({sampled:[],valid:[],invalid:[],sum:0}));
  DATA.directions.forEach((direction,d)=>{const [ai,ei]=memberships[d],cell=cells[ei*A+ai];cell.sampled.push(d);if(sample.validity_mask[d][wi]){cell.valid.push(d);cell.sum+=sample.values_W_sr_m[d][wi];}else cell.invalid.push(d);});
  ctx.strokeStyle='#89919a';ctx.lineWidth=0.5;
  for(let ei=0;ei<E;ei++)for(let ai=0;ai<A;ai++){
    const cell=cells[ei*A+ai],x=left+ai*cw,y=top+ph-(ei+1)*ch;
    if(cell.valid.length){ctx.fillStyle=color(cell.sum/cell.valid.length,lo,hi);ctx.fillRect(x,y,cw,ch);}
    if(cell.invalid.length){
      if(!cell.valid.length){ctx.fillStyle='rgba(130,135,145,.35)';ctx.fillRect(x,y,cw,ch);}
      ctx.save();ctx.beginPath();ctx.rect(x,y,cw,ch);ctx.clip();ctx.strokeStyle='rgba(30,35,40,.65)';ctx.lineWidth=1;
      for(let offset=-ch;offset<cw;offset+=7){ctx.beginPath();ctx.moveTo(x+offset,y+ch);ctx.lineTo(x+offset+ch,y);ctx.stroke();}
      ctx.restore();
    }
    ctx.strokeStyle='#89919a';ctx.strokeRect(x,y,cw,ch);
  }
  ctx.fillStyle=FG;ctx.font='12px system-ui';ctx.textAlign='center';ctx.fillText('azimuth [deg; +X→+Y] — '+DATA.direction_frame_id,left+pw/2,heat.height-12);ctx.save();ctx.translate(16,top+ph/2);ctx.rotate(-Math.PI/2);ctx.fillText('elevation [deg; XY→+Z]',0,0);ctx.restore();ctx.textAlign='right';
  for(let i=0;i<=4;i++){ctx.fillText(String(-180+360*i/4),left+pw*i/4,top+ph+18);ctx.textAlign='left';ctx.fillText(String(-90+180*i/4),left-8,top+ph-ph*i/4+4);ctx.textAlign='right';}
  document.getElementById('scale-min').textContent=fmt(lo)+' W sr⁻¹ m⁻¹';
  document.getElementById('scale-max').textContent=fmt(hi)+' W sr⁻¹ m⁻¹';
  const selectedDirection=directionIndex(),[sai,sei]=memberships[selectedDirection],sx=left+(sai+.5)*cw,sy=top+ph-(sei+.5)*ch;ctx.strokeStyle='white';ctx.lineWidth=2;ctx.beginPath();ctx.arc(sx,sy,Math.max(4,Math.min(cw,ch)*.28),0,2*Math.PI);ctx.stroke();
  document.getElementById('heatmap-status').textContent='Exact sample t='+sample.time_s+' s | λ='+fmt(DATA.wavelengths_m[wi]*1e6)+' μm | valid directions='+sample.validity_mask.reduce((n,row,d)=>n+(row[wi]?1:0),0)+' | invalid directions='+sample.validity_mask.reduce((n,row,d)=>n+(!row[wi]?1:0),0)+' | color range is shared across exact times at this wavelength: ['+fmt(lo)+', '+fmt(hi)+'] W sr⁻¹ m⁻¹.';
  heat._cells=cells;heat._plot={left,top,pw,ph,cw,ch};
}
function drawTrace(){
  const wi=wavelengthIndex(),di=directionIndex();
  const values=DATA.samples.map(sample=>sample.validity_mask[di][wi]?sample.values_W_sr_m[di][wi]:null);
  const uncertainties=DATA.samples.map((sample,index)=>{
    const matrix=sample.absolute_standard_uncertainty_W_sr_m;
    return values[index]===null||!matrix?null:matrix[di][wi];
  });
  const validIndices=values.map((value,index)=>value===null?-1:index).filter(index=>index>=0&&Number.isFinite(values[index]));
  traceCtx.clearRect(0,0,trace.width,trace.height);
  const l=76,t=30,r=22,b=112,pw=trace.width-l-r,ph=trace.height-t-b;
  traceCtx.strokeStyle='#89919a';traceCtx.strokeRect(l,t,pw,ph);
  if(!validIndices.length){document.getElementById('trace-status').textContent='No valid exact samples for this direction and wavelength.';return;}
  const times=DATA.samples.map(sample=>sample.time_s),xmin=Math.min(...times),xmax=Math.max(...times),xpad=xmin===xmax?1:0;
  const bounds=validIndices.flatMap(index=>{const value=values[index],uncertainty=uncertainties[index]??0;return[value-uncertainty,value+uncertainty];});
  let ymin=Math.min(...bounds),ymax=Math.max(...bounds);
  if(ymin===ymax){const pad=Math.max(Math.abs(ymin)*.1,1e-12);ymin-=pad;ymax+=pad;}
  const x=index=>l+(times[index]-(xmin-xpad))/(xmax-xmin+2*xpad)*pw;
  const y=value=>t+ph-(value-ymin)/(ymax-ymin)*ph,selected=sampleIndex();
  traceCtx.font='10px system-ui';traceCtx.textAlign='right';
  for(let tick=0;tick<=4;tick++){
    const value=ymin+(ymax-ymin)*tick/4,py=y(value);
    traceCtx.strokeStyle='rgba(130,140,150,.32)';traceCtx.beginPath();
    traceCtx.moveTo(l,py);traceCtx.lineTo(l+pw,py);traceCtx.stroke();
    traceCtx.fillStyle=MUTED;traceCtx.fillText(fmt(value),l-8,py+3);
  }
  const tickIndices=[...new Set([0,Math.floor((times.length-1)/4),Math.floor((times.length-1)/2),Math.floor(3*(times.length-1)/4),times.length-1])];
  traceCtx.textAlign='center';
  tickIndices.forEach(index=>{
    const px=x(index);traceCtx.strokeStyle='rgba(130,140,150,.35)';traceCtx.beginPath();
    traceCtx.moveTo(px,t);traceCtx.lineTo(px,t+ph);traceCtx.stroke();
    traceCtx.fillStyle=MUTED;traceCtx.fillText(fmt(times[index]),px,t+ph+17);
  });
  traceCtx.fillStyle=FG;traceCtx.font='12px system-ui';
  traceCtx.fillText('exact sample time [s] — points only, no interpolation',l+pw/2,trace.height-47);
  traceCtx.save();traceCtx.translate(16,t+ph/2);traceCtx.rotate(-Math.PI/2);
  traceCtx.fillText('Jλ [W sr⁻¹ m⁻¹]',0,0);traceCtx.restore();
  traceCtx.font='10px system-ui';traceCtx.textAlign='left';traceCtx.fillStyle=MUTED;
  traceCtx.fillText('× = invalid; bars = declared standard uncertainty where available',l,trace.height-15);
  times.forEach((time,index)=>{
    const px=x(index);
    if(values[index]===null){
      traceCtx.strokeStyle='#8b9097';traceCtx.beginPath();
      traceCtx.moveTo(px-4,t+ph+7);traceCtx.lineTo(px+4,t+ph+15);
      traceCtx.moveTo(px+4,t+ph+7);traceCtx.lineTo(px-4,t+ph+15);traceCtx.stroke();
      return;
    }
    const uncertainty=uncertainties[index];
    if(uncertainty!==null){
      traceCtx.strokeStyle='#3478a8';traceCtx.beginPath();
      traceCtx.moveTo(px,y(values[index]-uncertainty));traceCtx.lineTo(px,y(values[index]+uncertainty));
      traceCtx.moveTo(px-4,y(values[index]-uncertainty));traceCtx.lineTo(px+4,y(values[index]-uncertainty));
      traceCtx.moveTo(px-4,y(values[index]+uncertainty));traceCtx.lineTo(px+4,y(values[index]+uncertainty));traceCtx.stroke();
    }
    traceCtx.fillStyle=index===selected?ACCENT:'#3478a8';traceCtx.beginPath();
    traceCtx.arc(px,y(values[index]),index===selected?6:4,0,2*Math.PI);traceCtx.fill();
  });
  document.getElementById('trace-status').textContent='Direction '+di+' = ('+DATA.directions[di].map(fmt).join(', ')+') in '+DATA.direction_frame_id+'; valid exact samples='+validIndices.length+'/'+values.length+'.';
}
function drawTrajectory(){
  const positions=DATA.samples.map(sample=>sample.source_position_m);
  const xs=positions.map(position=>position[0]),zs=positions.map(position=>position[2]);
  const xmin=Math.min(...xs),xmax=Math.max(...xs),zmin=Math.min(...zs),zmax=Math.max(...zs);
  const xpad=xmin===xmax?Math.max(Math.abs(xmin)*.1,1e-3):0,zpad=zmin===zmax?Math.max(Math.abs(zmin)*.1,1e-3):0;
  const xlo=xmin-xpad,xhi=xmax+xpad,zlo=zmin-zpad,zhi=zmax+zpad,l=76,t=34,r=24,b=74;
  const pw=trajectory.width-l-r,ph=trajectory.height-t-b;
  const px=value=>l+(value-xlo)/(xhi-xlo)*pw,py=value=>t+ph-(value-zlo)/(zhi-zlo)*ph,selected=sampleIndex();
  trajectoryCtx.clearRect(0,0,trajectory.width,trajectory.height);
  trajectoryCtx.strokeStyle='#89919a';trajectoryCtx.strokeRect(l,t,pw,ph);
  trajectoryCtx.font='10px system-ui';trajectoryCtx.textAlign='right';
  for(let tick=0;tick<=4;tick++){
    const xValue=xlo+(xhi-xlo)*tick/4,xPosition=px(xValue);
    const zValue=zlo+(zhi-zlo)*tick/4,zPosition=py(zValue);
    trajectoryCtx.strokeStyle='rgba(130,140,150,.32)';trajectoryCtx.beginPath();
    trajectoryCtx.moveTo(xPosition,t);trajectoryCtx.lineTo(xPosition,t+ph);
    trajectoryCtx.moveTo(l,zPosition);trajectoryCtx.lineTo(l+pw,zPosition);
    trajectoryCtx.stroke();
    trajectoryCtx.fillStyle=MUTED;trajectoryCtx.textAlign='center';
    trajectoryCtx.fillText(fmt(xValue),xPosition,t+ph+16);
    trajectoryCtx.textAlign='right';trajectoryCtx.fillText(fmt(zValue),l-8,zPosition+3);
  }
  trajectoryCtx.fillStyle=FG;trajectoryCtx.font='12px system-ui';trajectoryCtx.textAlign='center';
  trajectoryCtx.fillText('source X [m] — '+DATA.position_frame_id,l+pw/2,trajectory.height-12);
  trajectoryCtx.save();trajectoryCtx.translate(16,t+ph/2);trajectoryCtx.rotate(-Math.PI/2);
  trajectoryCtx.fillText('source Z [m]',0,0);trajectoryCtx.restore();
  positions.forEach((position,index)=>{
    const x=px(position[0]),y=py(position[2]);trajectoryCtx.fillStyle=index===selected?ACCENT:'#3478a8';
    trajectoryCtx.beginPath();trajectoryCtx.arc(x,y,index===selected?7:4,0,2*Math.PI);trajectoryCtx.fill();
    trajectoryCtx.fillStyle=MUTED;trajectoryCtx.textAlign='left';
    trajectoryCtx.fillText(String(DATA.samples[index].time_s),x+6,y-6);
  });
  trajectoryCtx.fillStyle=MUTED;trajectoryCtx.textAlign='center';
  trajectoryCtx.fillText('exact position samples; X-Z projection, points only',l+pw/2,trajectory.height-34);
  document.getElementById('trajectory-status').textContent='Selected t='+DATA.samples[selected].time_s+' s; full X/Y/Z position is shown below.';
}
function updatePose(){const sample=DATA.samples[sampleIndex()];document.getElementById('pose').textContent='t='+sample.time_s+' s | position frame='+DATA.position_frame_id+' | position=['+sample.source_position_m.map(fmt).join(', ')+'] m | snapshot='+sample.snapshot_id+' | provider='+sample.provider_id+' | model lineage='+sample.model_lineage_id+' | result='+sample.result_id;}
function draw(){drawHeatmap();drawTrace();drawTrajectory();updatePose();}
populate();document.getElementById('identity').textContent=DATA.samples.length+' exact samples | '+DATA.directions.length+' directions | '+DATA.wavelengths_m.length+' wavelengths | direction frame='+DATA.direction_frame_id;
document.getElementById('metadata').textContent=JSON.stringify({schema:DATA.schema,product:DATA.product,quantity:DATA.quantity,units:DATA.units,direction_frame_id:DATA.direction_frame_id,angular_coordinate_convention:DATA.angular_coordinate_convention,position_frame_id:DATA.position_frame_id,binning:DATA.binning,guardrails:DATA.guardrails,samples:DATA.samples.map(sample=>({time_s:sample.time_s,result_id:sample.result_id,snapshot_id:sample.snapshot_id,provider_id:sample.provider_id,model_lineage_id:sample.model_lineage_id,source_position_m:sample.source_position_m,direction_status:sample.direction_status}))},null,2);
for(const control of [timeSelect,wavelengthSelect,directionSelect])control.addEventListener('change',draw);
heat.addEventListener('mousemove',event=>{const rect=heat.getBoundingClientRect(),px=(event.clientX-rect.left)*heat.width/rect.width,py=(event.clientY-rect.top)*heat.height/rect.height,p=heat._plot;if(!p||px<p.left||px>p.left+p.pw||py<p.top||py>p.top+p.ph)return;const ai=Math.min(A-1,Math.floor((px-p.left)/p.cw)),ei=Math.min(E-1,Math.floor((p.top+p.ph-py)/p.ch)),cell=heat._cells[ei*A+ai],az0=-180+360*ai/A,az1=-180+360*(ai+1)/A,el0=-90+180*ei/E,el1=-90+180*(ei+1)/E,wi=wavelengthIndex(),sample=DATA.samples[sampleIndex()];const mean=cell.valid.length?fmt(cell.sum/cell.valid.length)+' W sr⁻¹ m⁻¹':'no valid intensity';const values=cell.valid.map(d=>'d'+d+'='+fmt(sample.values_W_sr_m[d][wi])+(sample.absolute_standard_uncertainty_W_sr_m?' ± '+fmt(sample.absolute_standard_uncertainty_W_sr_m[d][wi]):''));document.getElementById('tooltip').textContent='azimuth ['+fmt(az0)+', '+fmt(az1)+')°, elevation ['+fmt(el0)+', '+fmt(el1)+')° | sampled directions='+cell.sampled.length+' | valid='+cell.valid.length+' | invalid='+cell.invalid.length+' | mean='+mean+' | valid direction samples: '+(values.length?values.join('; '):'none');});
document.getElementById('export').addEventListener('click',()=>{
  const si=sampleIndex(),wi=wavelengthIndex(),di=directionIndex(),sample=DATA.samples[si];
  const selectedUncertainty=sample.absolute_standard_uncertainty_W_sr_m;
  const spec={schema:'plume.signature.angular-timeline-view-spec@1',product:DATA.product,quantity:DATA.quantity,units:DATA.units,source_samples:DATA.samples.map(item=>({time_s:item.time_s,result_id:item.result_id,snapshot_id:item.snapshot_id,provider_id:item.provider_id,model_lineage_id:item.model_lineage_id,source_position_m:item.source_position_m})),selected_sample:{time_s:sample.time_s,result_id:sample.result_id,snapshot_id:sample.snapshot_id,source_position_m:sample.source_position_m,angular_validity_mask:sample.validity_mask.map(row=>row[wi]),angular_standard_uncertainty_W_sr_m:selectedUncertainty?selectedUncertainty.map(row=>row[wi]):null},selected_direction_trace:{direction_index:di,validity_by_sample:DATA.samples.map(item=>item.validity_mask[di][wi]),standard_uncertainty_W_sr_m_by_sample:DATA.samples.map(item=>item.absolute_standard_uncertainty_W_sr_m?item.absolute_standard_uncertainty_W_sr_m[di][wi]:null)},wavelength_m:DATA.wavelengths_m[wi],wavelength_index:wi,direction_index:di,direction:DATA.directions[di],direction_frame_id:DATA.direction_frame_id,angular_coordinate_convention:DATA.angular_coordinate_convention,position_frame_id:DATA.position_frame_id,angular_binning:DATA.binning,temporal_selection:'exact-sample-only',temporal_interpolation:false,direction_trace_interpolation:false,color_scale:'shared across exact samples at selected wavelength',guardrails:DATA.guardrails};
  const blob=new Blob([JSON.stringify(spec,null,2)+'\n'],{type:'application/json'}),link=document.createElement('a');link.href=URL.createObjectURL(blob);link.download='signature_timeline_view_spec.json';link.click();URL.revokeObjectURL(link.href);
});
draw();
</script></body></html>
'''


def write_interactive_signature_timeline_gallery(
  timeline: SignatureTimeline,
  output_path: str | Path,
  *,
  binning: SignatureAngularBinning | None = None,
) -> Path:
  """Write a standalone exact-time angular Signature explorer.

  Angular bins and selected-direction traces are built from the timeline's
  retained exact samples. The page never interpolates in time and excludes
  invalid values from bin aggregates.
  """

  if not isinstance(timeline, SignatureTimeline):
    raise TypeError('timeline must be SignatureTimeline')
  ####
  selected_binning = binning or SignatureAngularBinning()
  if not isinstance(selected_binning, SignatureAngularBinning):
    raise TypeError('binning must be SignatureAngularBinning or None')
  ####
  payload = _payload(timeline, selected_binning)
  data = json.dumps(
    payload,
    allow_nan=False,
    ensure_ascii=True,
    separators=(',', ':'),
  ).replace('</', '<\\/')
  output = Path(output_path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(_PAGE.replace('__TIMELINE_DATA__', data), encoding='utf-8')
  manifest = {
    'schema': SIGNATURE_TIMELINE_INTERACTIVE_SCHEMA,
    'html_file': output.name,
    'direction_frame_id': timeline.direction_frame_id,
    'position_frame_id': timeline.position_frame_id,
    'angular_coordinate_convention': dict(_ANGULAR_COORDINATE_CONVENTION),
    'times_s': list(timeline.times_s),
    'wavelengths_m': list(timeline.wavelengths_m),
    'product': payload['product'],
    'quantity': payload['quantity'],
    'units': payload['units'],
    'source_samples': [
      {
        'time_s': sample.time_s,
        'result_id': sample.result.metadata.result_id,
        'snapshot_id': sample.result.metadata.snapshot.snapshot_id,
        'provider_id': sample.result.metadata.provenance.provider_id,
        'model_lineage_id': sample.result.metadata.provenance.model_lineage_id,
        'source_position_m': list(
          sample.result.metadata.snapshot.source_pose.translation_m
        ),
        'validity_mask': [list(row) for row in sample.result.validity_mask],
        'direction_status': [
          status.code.value for status in sample.result.direction_status
        ],
        'absolute_standard_uncertainty_W_sr_m': (
          None
          if sample.result.absolute_standard_uncertainty is None
          else [
            list(row)
            for row in sample.result.absolute_standard_uncertainty
          ]
        ),
      }
      for sample in timeline.samples
    ],
    'binning': payload['binning'],
    'guardrails': payload['guardrails'],
  }
  manifest_path = output.with_name('signature_timeline_interactive_manifest.json')
  manifest_path.write_text(
    json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + '\n',
    encoding='utf-8',
  )
  return output
