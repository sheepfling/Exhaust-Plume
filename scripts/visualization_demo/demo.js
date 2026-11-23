'use strict';

const data = window.PLUME_DEMO;
const $ = id => document.getElementById(id);
const scene = $('scene');
const colors = {mint: '#82e6ce', warm: '#ffbd74', mask: '#ad6b9d', grid: '#29464a'};
const palette = [[26, 63, 67], [38, 136, 119], [201, 148, 85], [255, 227, 162]];
const format = (value, digits = 2) => value == null ? '—' : value.toFixed(digits);
const sci = value => value == null ? '—' : value === 0 ? '0' : value.toExponential(2);
const vector = value => value.map(item => format(item, 3)).join(', ');
const escaped = value => String(value).replace(/[&<>"']/g, character => (
  {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]
));
const headings = {
  shape: ['Curved plume · Engineering example', 'Inside the plume envelope', 'Curved integral model · Display geometry'],
  signature: ['Curved plume · Engineering example', 'How direction changes the spectrum', 'Gray radiation model · Source emission'],
  detector: ['Synthetic imaging case · Orthographic ray grid', 'Follow a pixel to the detector', 'Gray transfer · Capsule support · Expected response'],
  timeline: ['Curved plume · Prescribed samples', 'Four snapshots in crossflow', 'Selected samples · Source pose shown separately'],
  field: ['Planar expansion fan · Research example', 'Inspect the retained flow cells', 'Cell-associated Mach · Half-open axial slices'],
  engineering: ['Straight integral · Engineering example', 'Compare native flux sections', 'Shared source frame · Separate runs'],
};
const initial = () => ({
  station: 17, direction: 0, signatureBand: 2, wavelength: 2, sample: 0,
  pixel: [...data.detector.bright], yaw: -0.25, pitch: -0.28, slice: 6, cell: null, engineeringStation: 10,
});
let state = initial();
let active;

function heatColor(fraction) {
  const index = Math.max(0, Math.min(1, fraction)) * (palette.length - 1);
  const first = Math.min(palette.length - 2, Math.floor(index));
  return 'rgb(' + palette[first].map((value, channel) =>
    Math.round(value + (palette[first + 1][channel] - value) * (index - first))
  ).join(',') + ')';
}

function chart({title, xs, series, extent, xLabel, yLabel, selected, compact = false}) {
  const width = 600, height = compact ? 190 : 325;
  const left = 82, right = 22, top = 20, bottom = 48;
  const [minimum, maximum] = extent;
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const x = value => left + (value - xMin) / (xMax - xMin || 1) * (width - left - right);
  const y = value => top + (maximum - value) / (maximum - minimum || 1) * (height - top - bottom);
  const base = height - bottom;
  const ticks = Array.from({length: 5}, (_, index) => minimum + index * (maximum - minimum) / 4);
  const xTicks = xs.length > 6 ? [xs[0], xs[Math.floor(xs.length / 2)], xs.at(-1)] : xs;
  const grid = ticks.map(value =>
    `<line x1="${left}" y1="${y(value)}" x2="${width - right}" y2="${y(value)}" stroke="${colors.grid}"/>
     <text x="${left - 8}" y="${y(value) + 4}" text-anchor="end">${Math.abs(value) >= 10000 || (value !== 0 && Math.abs(value) < 0.01) ? sci(value) : format(value)}</text>`
  ).join('');
  const guides = xTicks.map(value =>
    `<line x1="${x(value)}" x2="${x(value)}" y1="${top}" y2="${base}" stroke="${colors.grid}"/>
     <text x="${x(value)}" y="${base + 17}" text-anchor="middle">${Number(value.toFixed(2))}</text>`
  ).join('');
  const selectedLine = selected == null ? '' :
    `<line x1="${x(xs[selected])}" y1="${top}" x2="${x(xs[selected])}" y2="${base}" stroke="${colors.warm}" stroke-dasharray="4 5"/>`;
  const traces = series.map(({values, color, emphasis = true, connect = true}) => {
    let path = '', open = false;
    const points = values.map((value, index) => {
      if (value == null) {
        open = false;
        return '';
      }
      const point = `${x(xs[index])} ${y(value)}`;
      path += `${open ? 'L' : 'M'}${point}`;
      open = true;
      return `<circle cx="${x(xs[index])}" cy="${y(value)}" r="${index === selected ? 5 : 3}" fill="${color}"/>`;
    }).join('');
    return `<g opacity="${emphasis ? 1 : 0.65}">${connect ? `<path d="${path}" fill="none" stroke="${color}" stroke-width="2.6"/>` : ''}${points}</g>`;
  }).join('');
  return `<svg class="plot" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escaped(title)}">
    ${grid}${guides}${selectedLine}${traces}
    <text x="${(width + left - right) / 2}" y="${height - 8}" text-anchor="middle">${escaped(xLabel)}</text>
    <text transform="rotate(-90 17 ${base / 2})" x="17" y="${base / 2}" text-anchor="middle">${escaped(yLabel)}</text>
  </svg>`;
}

const curved = data.curved;
const allShapes = curved.samples.map(sample => sample.shape);
const shapeBounds = [0, 1, 2].map(axis => [
  Math.min(...allShapes.map(shape => shape.mesh.bounds.minimum_m[axis])),
  Math.max(...allShapes.map(shape => shape.mesh.bounds.maximum_m[axis])),
]);
const orbitCenter = shapeBounds.map(([low, high]) => (low + high) / 2);
const orbitRadius = Math.hypot(...shapeBounds.map(([low, high]) => (high - low) / 2));
const maxSectionRadius = Math.max(...allShapes.flatMap(shape => shape.sections.map(section => section.radius_major_m)));
const signatureMax = 1.08 * Math.max(...curved.samples.flatMap(sample => sample.intensity.flat()).filter(value => value != null));

function canvasContext(canvas) {
  const {width, height} = canvas.getBoundingClientRect();
  const density = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(width * density));
  canvas.height = Math.max(1, Math.round(height * density));
  const context = canvas.getContext('2d');
  context.scale(density, density);
  return {context, width, height};
}

function drawOrbit(canvas, shape) {
  const {context: ctx, width, height} = canvasContext(canvas);
  const cosine = Math.cos(state.yaw), sine = Math.sin(state.yaw);
  const cp = Math.cos(state.pitch), sp = Math.sin(state.pitch);
  function rotate(point) {
    const [x, y, z] = point.map((value, index) => value - orbitCenter[index]);
    const horizontal = cosine * x - sine * y;
    const depth = sine * x + cosine * y;
    return [horizontal, cp * z - sp * depth, cp * depth + sp * z];
  }
  const fitPoints = (active === 'timeline' ? allShapes : [shape]).flatMap(item => item.mesh.vertices.map(rotate));
  const [[minX, maxX], [minY, maxY]] = [0, 1].map(axis => {
    const positions = fitPoints.map(point => point[axis]);
    return [Math.min(...positions), Math.max(...positions)];
  });
  const scale = Math.min((width - 72) / (maxX - minX), (height - 80) / (maxY - minY));
  function project(point) {
    const [x, y, depth] = rotate(point);
    return [width / 2 + scale * (x - (maxX + minX) / 2), height / 2 - scale * (y - (maxY + minY) / 2), depth];
  }
  function path(points, stroke, widthPx = 1, close = false) {
    if (!points.length) return;
    ctx.beginPath();
    ctx.moveTo(...points[0].slice(0, 2));
    points.slice(1).forEach(point => ctx.lineTo(...point.slice(0, 2)));
    if (close) ctx.closePath();
    if (stroke) {
      ctx.strokeStyle = stroke;
      ctx.lineWidth = widthPx;
      ctx.stroke();
    }
  }
  ctx.fillStyle = '#0a1b1f';
  ctx.fillRect(0, 0, width, height);
  const mesh = shape.mesh;
  const vertices = mesh.vertices.map(project);
  const triangles = mesh.faces.map(face => face.map(index => vertices[index]));
  triangles.sort((a, b) => a[0][2] + a[1][2] + a[2][2] - b[0][2] - b[1][2] - b[2][2]);
  for (const face of triangles) {
    const depth = face.reduce((sum, point) => sum + point[2], 0) / 3;
    const brightness = Math.max(0, Math.min(1, 0.55 + depth / orbitRadius));
    ctx.fillStyle = `rgba(${Math.round(32 + 47 * brightness)},${Math.round(100 + 95 * brightness)},${Math.round(101 + 62 * brightness)},.28)`;
    path(face, null, 1, true);
    ctx.fill();
  }
  const centers = shape.sections.map(section => project(section.center_m));
  for (let index = 0; index < centers.length; index += 2) {
    const ring = vertices.slice(index * shape.radial_segments, (index + 1) * shape.radial_segments);
    path(ring, 'rgba(115, 221, 200, .52)', .8, true);
  }
  path(centers, '#e2f9ed', 1.2);
  for (const [index, [x, y]] of centers.entries()) {
    ctx.beginPath();
    ctx.arc(x, y, index === state.station ? 4.7 : 2, 0, 2 * Math.PI);
    ctx.fillStyle = index === state.station ? colors.warm : '#b4e9da';
    ctx.fill();
  }
  const ring = vertices.slice(state.station * shape.radial_segments, (state.station + 1) * shape.radial_segments);
  path(ring, colors.warm, 3, true);

  const ruler = [[24, height - 21], [24 + scale, height - 21]];
  path(ruler, '#c3d4cf', 1.5);
  for (const [x, y] of ruler) path([[x, y - 4], [x, y + 4]], '#c3d4cf');
  ctx.fillStyle = '#c3d4cf';
  ctx.font = '12px sans-serif';
  ctx.fillText('1 m', 28 + scale, height - 17);
  return centers;
}

function ellipse(section) {
  const scale = 63 / maxSectionRadius;
  return `<svg class="plot" viewBox="0 0 300 166" role="img" aria-label="Selected ellipse in the oriented section plane">
    <line x1="40" y1="77" x2="260" y2="77" stroke="${colors.grid}"/>
    <line x1="150" y1="8" x2="150" y2="146" stroke="${colors.grid}"/>
    <ellipse cx="150" cy="77" rx="${section.radius_major_m * scale}" ry="${section.radius_minor_m * scale}"
      fill="#264941" stroke="${colors.warm}" stroke-width="2"/>
    <circle cx="150" cy="77" r="3" fill="#f5e6c9"/>
    <text x="255" y="70">u</text><text x="156" y="13">v</text>
    <text x="150" y="158" text-anchor="middle">Section plane · fixed scale</text>
  </svg>`;
}

function metric(label, value) {
  return `<div><dt>${label}</dt><dd>${value}</dd></div>`;
}

function viewShape(timeline = false) {
  const sample = curved.samples[timeline ? state.sample : 0];
  const shape = sample.shape;
  scene.innerHTML = `<div class="grid">
    <div class="panel">
      <div class="panel-head"><h2>Plume envelope</h2><p class="note">Drag to orbit · Select a centerline marker</p></div>
      <canvas id="orbit" class="${timeline ? 'compact' : ''}" aria-label="Three-dimensional plume envelope"></canvas>
      <div class="strip">
        <label for="station">Station</label>
        <input type="range" id="station" min="0" max="${shape.sections.length - 1}" value="${state.station}">
        <output id="station-distance" for="station"></output>
      </div>
      ${timeline ? `<div class="strip"><label for="time">Mission time</label>
        <input type="range" id="time" min="0" max="${curved.samples.length - 1}" value="${state.sample}">
        <output for="time" id="time-value"></output></div>` : ''}
    </div>
    <div class="stack">
      <div class="panel">
        <div class="panel-head"><h2>Oriented cross-section</h2><p id="station-number" class="note"></p></div>
        <div id="ellipse"></div><div class="pad"><dl class="metrics" id="section-metrics"></dl></div>
      </div>
      ${timeline ? `<div class="panel scrub">
        <div class="panel-head"><h2>Signature across snapshots</h2><p class="note">Along axis · ${curved.wavelengths_um[2]} µm</p></div>
        <div id="time-chart"></div><div class="pad"><p id="pose" class="note"></p></div>
      </div>` : `<div class="panel"><div class="panel-head"><h2>Temperature along the centerline</h2></div><div id="temperature-chart"></div></div>`}
    </div>
  </div>`;
  const orbit = $('orbit');
  let centers, drag = null;
  function update() {
    const now = curved.samples[timeline ? state.sample : 0];
    const current = now.shape;
    const section = current.sections[state.station];
    centers = drawOrbit(orbit, current);
    $('station').value = state.station;
    $('station-distance').textContent = `${format(section.arc_length_m)} m`;
    $('station-number').textContent = `Station ${state.station + 1} / ${current.sections.length}`;
    $('ellipse').innerHTML = ellipse(section);
    $('section-metrics').innerHTML = [
      metric('Semi-axes', `${format(section.radius_major_m, 3)} × ${format(section.radius_minor_m, 3)} m`),
      metric('Mixture temperature', `${format(current.mesh.section_channels.temperature[state.station], 1)} K`),
    ].join('');
    if (timeline) {
      $('time-value').textContent = `${format(now.time_s, 1)} s`;
      $('pose').textContent = `Source pose [${vector(now.position_m)}] m · ${now.pose_frame}`;
      $('time-chart').innerHTML = chart({
        title: 'Exact radiant intensity samples over mission time', xs: curved.samples.map(item => item.time_s), extent: [0, signatureMax],
        series: [{values: curved.samples.map(item => item.intensity[0][2]), color: colors.mint, connect: false}],
        selected: state.sample, xLabel: 'Time (s)', yLabel: 'W sr⁻¹ m⁻¹', compact: true,
      });
    } else {
      const temperatures = current.mesh.section_channels.temperature;
      $('temperature-chart').innerHTML = chart({
        title: 'Retained mixture temperature along the centerline', xs: current.sections.map(item => item.arc_length_m),
        extent: [Math.min(...temperatures) - 15, Math.max(...temperatures) + 15],
        series: [{values: temperatures, color: colors.mint, connect: false}], selected: state.station,
        xLabel: 'Arc length (m)', yLabel: 'Temperature (K)', compact: true,
      });
    }
    showSource();
  }
  $('station').oninput = event => { state.station = Number(event.target.value); update(); };
  if (timeline) $('time').oninput = event => { state.sample = Number(event.target.value); update(); };
  orbit.onpointerdown = event => {
    drag = {x: event.clientX, y: event.clientY, yaw: state.yaw, pitch: state.pitch};
    orbit.setPointerCapture(event.pointerId);
  };
  orbit.onpointermove = event => {
    if (!drag) return;
    state.yaw = drag.yaw + (event.clientX - drag.x) * 0.012;
    state.pitch = Math.max(-1.4, Math.min(1.4, drag.pitch + (event.clientY - drag.y) * 0.012));
    centers = drawOrbit(orbit, curved.samples[timeline ? state.sample : 0].shape);
  };
  orbit.onpointerup = event => {
    if (!drag) return;
    if (Math.hypot(event.clientX - drag.x, event.clientY - drag.y) < 4) {
      const rect = orbit.getBoundingClientRect();
      let nearest = 24;
      centers.forEach(([x, y], index) => {
        const distance = Math.hypot(x + rect.left - event.clientX, y + rect.top - event.clientY);
        if (distance < nearest) {
          nearest = distance;
          state.station = index;
        }
      });
    }
    drag = null;
    update();
  };
  orbit.onpointercancel = () => { drag = null; };
  update();
}

function viewSignature() {
  const sample = curved.samples[0];
  const values = sample.intensity;
  scene.innerHTML = `<div class="grid">
    <div class="panel">
      <div class="panel-head"><h2>Unresolved spectral radiant intensity</h2><p class="note">Fixed scale across directions</p></div>
      <div id="signature-chart"></div>
      <div class="strip selection-buttons" id="directions">
        ${curved.direction_labels.map((label, index) =>
          `<button type="button" data-direction="${index}">${label}</button>`).join('')}
      </div>
    </div>
    <div class="stack">
      <div class="panel pad"><h2>Sampled observer directions</h2><div id="direction-map"></div><p class="note" id="direction-info"></p></div>
      <div class="panel pad"><h2>Direction × wavelength</h2><p class="note">Radiant intensity · W sr⁻¹ m⁻¹</p>
        <div class="heat" id="signature-heat"></div>
      </div>
    </div>
  </div>`;
  function update() {
    const selected = state.direction;
    const direction = curved.directions[selected];
    $('signature-chart').innerHTML = chart({
      title: 'Comparison of both exact direction spectra', xs: curved.wavelengths_um, extent: [0, signatureMax],
      series: values.map((row, index) => ({
        values: row, color: index === 0 ? colors.mint : colors.warm, emphasis: index === selected,
      })),
      selected: state.signatureBand, xLabel: 'Wavelength (µm)', yLabel: 'W sr⁻¹ m⁻¹',
    });
    $('directions').querySelectorAll('button').forEach((button, index) => {
      button.setAttribute('aria-pressed', index === selected);
    });
    $('direction-map').innerHTML = `<svg class="plot" viewBox="0 0 290 142" role="img" aria-label="Exact observer directions projected into XY">
      <circle cx="125" cy="78" r="53" fill="#10282a" stroke="${colors.grid}"/>
      <path d="M62 78H188 M125 15V140" stroke="${colors.grid}"/>
      ${curved.directions.map((item, index) => {
        const x = 125 + 54 * item[0], y = 78 - 54 * item[1], color = index ? colors.warm : colors.mint;
        return `<g opacity="${index === selected ? 1 : .45}"><path d="M125 78 L${x} ${y}" stroke="${color}" stroke-width="2"/>
          <circle cx="${x}" cy="${y}" r="${index === selected ? 6 : 4}" fill="${color}"/></g>`;
      }).join('')}
      <text x="202" y="80">+x</text><text x="135" y="20">+y</text><text x="225" y="124">XY view</text>
      </svg>`;
    $('direction-info').textContent = `[${vector(direction)}] · ${sample.direction_status[selected]}`;
    $('signature-heat').innerHTML = [
      '<span></span>',
      ...curved.wavelengths_um.map(w => `<span class="note">${w} µm</span>`),
      ...values.flatMap((row, directionIndex) => [
        `<span class="note">${directionIndex === 0 ? 'Along' : 'Across'}</span>`,
        ...row.map((value, band) => {
          const fraction = value == null ? 0 : value / signatureMax;
          return `<button type="button" data-heat="${directionIndex},${band}"
            aria-label="${curved.direction_labels[directionIndex]}, ${curved.wavelengths_um[band]} micrometres, ${sci(value)}"
            aria-current="${directionIndex === selected && band === state.signatureBand}"> ${sci(value)} </button>`;
        }),
      ]),
    ].join('');
    $('signature-heat').querySelectorAll('button').forEach(button => {
      const [directionIndex, band] = button.dataset.heat.split(',').map(Number);
      const value = values[directionIndex][band];
      const fraction = value == null ? 0 : value / signatureMax;
      button.style.backgroundColor = value == null ? colors.mask : heatColor(fraction);
      button.style.color = fraction > .42 ? '#081315' : '#eef4ec';
    });
    showSource();
  }
  $('directions').onclick = event => {
    const button = event.target.closest('[data-direction]');
    if (!button) return;
    state.direction = Number(button.dataset.direction);
    update();
  };
  $('signature-heat').onclick = event => {
    const button = event.target.closest('[data-heat]');
    if (!button) return;
    const key = button.dataset.heat;
    [state.direction, state.signatureBand] = key.split(',').map(Number);
    update();
    $('signature-heat').querySelector(`[data-heat="${key}"]`).focus();
  };
  update();
}

const detector = data.detector;
const rayByPixel = new Map(detector.rays.map(ray => [ray.pixel.join(','), ray]));
const radianceMax = Math.max(...detector.radiance.flat(2));
const electronsMax = Math.max(...detector.electrons.flat());

function detectorMap(canvas, values, ceiling) {
  const {context: ctx, width, height} = canvasContext(canvas);
  const scale = Math.min(width / detector.width, height / detector.height);
  const cellWidth = scale, cellHeight = scale;
  const x0 = (width - scale * detector.width) / 2;
  const y0 = (height - scale * detector.height) / 2;
  ctx.fillStyle = '#0a1b1f';
  ctx.fillRect(0, 0, width, height);
  detector.validity.forEach((row, r) => {
    row.forEach((valid, c) => {
      ctx.fillStyle = valid ? heatColor(values[r][c] / ceiling) : colors.mask;
      const x = x0 + c * cellWidth, y = y0 + r * cellHeight;
      ctx.fillRect(x, y, cellWidth + .35, cellHeight + .35);
      if (!valid) {
        ctx.strokeStyle = '#4e3250';
        ctx.beginPath();
        ctx.moveTo(x, y + cellHeight);
        ctx.lineTo(x + cellWidth, y);
        ctx.stroke();
      }
    });
  });
  const [row, column] = state.pixel;
  const x = x0 + column * cellWidth, y = y0 + row * cellHeight;
  ctx.strokeStyle = '#10191a';
  ctx.lineWidth = 3.6;
  ctx.strokeRect(x - .4, y - .4, cellWidth + .8, cellHeight + .8);
  ctx.strokeStyle = '#fff6dd';
  ctx.lineWidth = 1.4;
  ctx.strokeRect(x - .4, y - .4, cellWidth + .8, cellHeight + .8);
  return {x0, y0, cellWidth, cellHeight};
}

function viewDetector() {
  scene.innerHTML = `<div class="detector-body">
    <div class="stack">
      <div class="grid equal">
        <div class="panel">
          <div class="panel-head"><h2>Source spectral radiance</h2>
            <div class="legend"><span>0</span><span class="gradient"></span><span>${sci(radianceMax)}</span><span>W m⁻² sr⁻¹ m⁻¹</span></div>
          </div><canvas class="pixel-map" id="radiance-map" tabindex="0" aria-label="Source radiance pixels. Click or use the arrow keys to select."></canvas>
        </div>
        <div class="panel">
          <div class="panel-head"><h2>Expected detector electrons</h2>
            <div class="legend"><span>0</span><span class="gradient"></span><span>${sci(electronsMax)}</span><span>e⁻</span></div>
          </div><canvas class="pixel-map" id="electron-map" tabindex="0" aria-label="Expected detector pixels. Click or use the arrow keys to select."></canvas>
        </div>
      </div>
      <div class="panel pad stack">
        <div class="selection-buttons">
          <label for="wavelength" class="note">Source wavelength</label>
          <select id="wavelength">${detector.wavelengths_um.map((w, i) => `<option value="${i}">${w} µm</option>`).join('')}</select>
          <button type="button" data-pixel="bright">Bright</button>
          <button type="button" data-pixel="zero">Valid zero</button>
          <button type="button" data-pixel="masked">Masked</button>
        </div>
        <p class="note"><span class="swatch"></span> Unmapped pixel · Zero-based rows and columns</p>
      </div>
    </div>
    <div class="panel stack pad">
      <h2>Pixel and sightline</h2>
      <p class="note" id="pixel-status" aria-live="polite"></p>
      <dl class="metrics" id="pixel-values"></dl>
      <p class="note" id="ray-info"></p>
      <div id="pixel-spectrum"></div>
      <p class="note" id="detector-info"></p>
    </div>
  </div>`;
  const left = $('radiance-map'), right = $('electron-map');
  let maps = [];
  function update() {
    const [row, column] = state.pixel;
    const valid = detector.validity[row][column];
    const ray = rayByPixel.get(state.pixel.join(','));
    maps = [
      detectorMap(left, detector.radiance.map(line => line.map(pixel => pixel[state.wavelength])), radianceMax),
      detectorMap(right, detector.electrons, electronsMax),
    ];
    const spectrum = valid ? detector.radiance[row][column] : detector.wavelengths_um.map(() => null);
    const radiance = spectrum[state.wavelength];
    const status = valid ? (spectrum.every(value => value === 0) ? 'valid · zero source radiance' : 'valid') :
      `masked · ${detector.statuses[row][column].replaceAll('_', ' ')}`;
    $('pixel-status').textContent = `Row ${row} · Column ${column} · ${status}`;
    $('pixel-values').innerHTML = [
      metric(`Radiance at ${detector.wavelengths_um[state.wavelength]} µm`, sci(radiance)),
      metric('Expected electrons', valid ? `${sci(detector.electrons[row][column])} e⁻` : '—'),
    ].join('');
    $('ray-info').textContent = ray
      ? `Ray ${ray.index} · Origin [${vector(ray.origin_m)}] m · Direction [${ray.direction.join(', ')}] · Window ${ray.t_m.join('–')} m · τ ${format(detector.transmittance[row][column][state.wavelength], 3)}`
      : 'No ray is mapped to this pixel.';
    $('pixel-spectrum').innerHTML = chart({
      title: 'Selected pixel source spectral radiance', xs: detector.wavelengths_um, extent: [0, radianceMax],
      series: [{values: spectrum, color: colors.mint}], selected: state.wavelength,
      xLabel: 'Wavelength (µm)', yLabel: 'W m⁻² sr⁻¹ m⁻¹', compact: true,
    });
    const transmission = detector.detector.optical_throughput.map(value => format(value, 2)).join(' / ');
    const qe = detector.detector.quantum_efficiency.map(value => format(value, 2)).join(' / ');
    $('detector-info').textContent = `${detector.exposure_s * 1000} ms exposure · QE ${qe} · optical throughput ${transmission}`;
    $('wavelength').value = state.wavelength;
    scene.querySelectorAll('[data-pixel]').forEach(button => {
      button.setAttribute('aria-pressed', detector[button.dataset.pixel].join(',') === state.pixel.join(','));
    });
    showSource();
  }
  $('wavelength').onchange = event => { state.wavelength = Number(event.target.value); update(); };
  scene.querySelectorAll('[data-pixel]').forEach(button => {
    button.onclick = () => { state.pixel = [...detector[button.dataset.pixel]]; update(); };
  });
  [left, right].forEach((canvas, index) => {
    canvas.onclick = event => {
      const {x0, y0, cellWidth, cellHeight} = maps[index];
      const rect = canvas.getBoundingClientRect();
      const row = Math.floor((event.clientY - rect.top - y0) / cellHeight);
      const column = Math.floor((event.clientX - rect.left - x0) / cellWidth);
      if (row < 0 || row >= detector.height || column < 0 || column >= detector.width) return;
      state.pixel = [row, column];
      update();
    };
    canvas.onkeydown = event => {
      const changes = {ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1]};
      const delta = changes[event.key];
      if (!delta) return;
      event.preventDefault();
      state.pixel = state.pixel.map((value, axis) => Math.max(0, Math.min(
        (axis === 0 ? detector.height : detector.width) - 1, value + delta[axis],
      )));
      update();
    };
  });
  update();
}

const field = data.field;
const fieldPoints = field.polygons.flat();
const fieldBounds = [0, 1].map(axis => [
  Math.min(...fieldPoints.map(point => point[axis])), Math.max(...fieldPoints.map(point => point[axis])),
]);
const machMin = Math.min(...field.mach), machMax = Math.max(...field.mach);

function viewField() {
  scene.innerHTML = `<div class="grid">
    <div class="panel">
      <div class="panel-head"><h2>Meridional field</h2>
        <div class="legend"><span>${format(machMin)}</span><span class="gradient"></span><span>${format(machMax)} Mach</span></div>
      </div>
      <div id="field-map"></div>
      <div class="strip"><label for="slice">Axial slice</label>
        <input id="slice" type="range" min="0" max="${field.slices.length - 1}" value="${state.slice}"><output id="slice-value" for="slice"></output>
      </div>
    </div>
    <div class="stack">
      <div class="panel pad stack"><h2>Source cell</h2><p id="cell-info" class="note" aria-live="polite"></p></div>
      <div class="panel"><div class="panel-head"><h2>Radial Mach profile</h2></div><div id="profile"></div></div>
    </div>
  </div>`;
  const [[xMin, xMax], [rMin, rMax]] = fieldBounds;
  const panelWidth = 680, panelHeight = 280;
  const scale = Math.min(564 / (xMax - xMin), 185 / (rMax - rMin));
  const x = value => 54 + (value - xMin) * scale;
  const r = value => 218 - (value - rMin) * scale;
  function update() {
    const sample = field.slices[state.slice];
    $('slice-value').textContent = `${format(sample.x_m, 3)} m`;
    $('field-map').innerHTML = `<svg class="plot" viewBox="0 0 ${panelWidth} ${panelHeight}" role="group" aria-label="Selectable retained Mach cells">
      ${field.polygons.map((polygon, index) => `<polygon tabindex="0" role="button" aria-pressed="${state.cell === index}" data-cell="${index}"
          aria-label="${escaped(field.labels[index])}, Mach ${format(field.mach[index], 3)}"
          points="${polygon.map(([ax, radius]) => `${x(ax)},${r(radius)}`).join(' ')}"
          fill="${heatColor((field.mach[index] - machMin) / (machMax - machMin))}"
          stroke="${state.cell === index ? '#fff7df' : '#0d1d21'}" stroke-width="${state.cell === index ? 3 : 1.5}"/>`).join('')}
      <line x1="${x(sample.x_m)}" x2="${x(sample.x_m)}" y1="25" y2="222" stroke="${colors.warm}" stroke-width="2" stroke-dasharray="4 5" pointer-events="none"/>
      <text x="${x(xMin)}" y="240">${format(xMin, 2)}</text>
      <text x="${x(xMax)}" y="240" text-anchor="end">${format(xMax, 2)}</text>
      <text x="${(x(xMin) + x(xMax)) / 2}" y="262" text-anchor="middle">Axial position (m)</text>
      <text x="24" y="142" transform="rotate(-90 24 142)" text-anchor="middle">Radius (m)</text>
      <text x="49" y="${r(rMin) + 4}" text-anchor="end">${format(rMin, 2)}</text>
      <text x="49" y="${r(rMax) + 4}" text-anchor="end">${format(rMax, 2)}</text>
    </svg>`;
    const cell = state.cell;
    $('cell-info').textContent = cell == null ? 'Select a polygon to see its cell-associated Mach value.' :
      `${field.labels[cell]} · Mach ${format(field.mach[cell], 4)}`;
    const sliceRadii = sample.intervals.flatMap(([, start, end]) => [start, end]);
    const lowerRadius = sliceRadii.length ? Math.min(...sliceRadii) : rMin;
    const upperRadius = sliceRadii.length ? Math.max(...sliceRadii) : rMax;
    const radial = value => 76 + (value - lowerRadius) / (upperRadius - lowerRadius) * 340;
    const mach = value => 137 - (value - machMin) / (machMax - machMin) * 100;
    $('profile').innerHTML = `<svg class="plot" viewBox="0 0 440 190" role="img" aria-label="Exact radial intersections with the selected axial plane">
      <path d="M76 28 V137 H416" fill="none" stroke="${colors.grid}"/>
      <text x="62" y="41" text-anchor="end">${format(machMax)}</text>
      <text x="62" y="141" text-anchor="end">${format(machMin)}</text>
      <text x="25" y="90" transform="rotate(-90 25 90)" text-anchor="middle">Mach</text>
      <text x="76" y="154" text-anchor="middle">${format(lowerRadius, 3)}</text>
      <text x="416" y="154" text-anchor="middle">${format(upperRadius, 3)}</text>
      <text x="246" y="176" text-anchor="middle">Radius (m)</text>
      ${sample.intervals.map(([index, start, end]) => `<line x1="${radial(start)}" x2="${radial(end)}"
        y1="${mach(field.mach[index])}" y2="${mach(field.mach[index])}"
        stroke="${index === cell ? colors.warm : colors.mint}" stroke-width="${index === cell ? 5 : 3}"/>`).join('')}
    </svg>`;
    showSource();
  }
  $('slice').oninput = event => { state.slice = Number(event.target.value); update(); };
  const fieldMap = $('field-map');
  function selectCell(event) {
    const target = event.target.closest('[data-cell]');
    if (!target) return;
    state.cell = Number(target.dataset.cell);
    update();
    fieldMap.querySelector(`[data-cell="${state.cell}"]`).focus();
  }
  fieldMap.onclick = selectCell;
  fieldMap.onkeydown = event => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    selectCell(event);
  };
  update();
}

const engineering = data.engineering;
const engineeringAxis = engineering[0].stations.map(station => station.x_m);
const engineeringQuantities = [
  ['mass_kg_s', 'Mass flow', 'kg s⁻¹'], ['momentum_n', 'Momentum flux magnitude', 'N'], ['radius_m', 'Section radius', 'm'],
];

function viewEngineering() {
  scene.innerHTML = `<div class="grid">
    <div class="stack">
      <div class="panel">
        <div class="panel-head"><h2>Baseline and higher entrainment</h2><p class="note">Mint · Baseline  Amber · Higher entrainment</p></div>
        <div class="strip"><label for="engineering-station">Native station</label>
          <input type="range" id="engineering-station" min="0" max="${engineeringAxis.length - 1}" value="${state.engineeringStation}">
          <output id="engineering-distance" for="engineering-station"></output>
        </div>
      </div>
      <div class="grid equal" id="flux-charts"></div>
    </div>
    <div class="stack" id="flux-summary"></div>
  </div>`;
  function update() {
    const index = state.engineeringStation;
    $('engineering-distance').textContent = `${format(engineeringAxis[index])} m`;
    $('flux-charts').innerHTML = engineeringQuantities.map(([key, label, unit]) => {
      const series = engineering.map((run, i) => ({
        values: run.stations.map(item => item[key]), color: i === 0 ? colors.mint : colors.warm, connect: false,
      }));
      if (key === 'radius_m') {
        const mirrored = series.map(run => ({...run, values: run.values.map(value => -value)}));
        series.push(...mirrored);
      }
      const values = series.flatMap(item => item.values);
      const maximum = Math.max(...values);
      const minimum = Math.min(...values);
      const margin = Math.max(maximum - minimum, Math.abs(maximum) * .06) * .09;
      const title = key === 'radius_m' ? 'Section outline' : label;
      return `<div class="panel"><div class="panel-head"><h2>${title}</h2></div>${chart({
        title, xs: engineeringAxis, extent: [minimum - margin, maximum + margin], series, selected: index,
        xLabel: 'Arc length (m)', yLabel: unit, compact: true,
      })}</div>`;
    }).join('');
    $('flux-summary').innerHTML = engineering.map(run => {
      const station = run.stations[index];
      return `<div class="panel pad stack"><h2>${run.label} · α = ${run.coefficient}</h2><dl class="metrics">
        ${engineeringQuantities.map(([key, label, unit]) => metric(label, `${format(station[key], 3)} ${unit}`)).join('')}
      </dl></div>`;
    }).join('');
    showSource();
  }
  $('engineering-station').oninput = event => { state.engineeringStation = Number(event.target.value); update(); };
  update();
}

function viewSpec() {
  const common = {schema: 'radiant-plume.demo.view@1', scene: active};
  const sample = curved.samples[active === 'timeline' ? state.sample : 0];
  switch (active) {
    case 'shape':
    case 'timeline':
      return {...common, time_s: sample.time_s, station_index: state.station,
        yaw_rad: state.yaw, pitch_rad: state.pitch, shared_bounds_m: shapeBounds, shape_source: sample.shape.source,
        camera_fit: active === 'timeline' ? 'shared over all evaluated snapshots' : 'fit to the opening sample',
        ...(active === 'timeline' ? {
          signature_source: sample.signature_source, trace_sources: curved.samples.map(item => item.signature_source),
          direction_index: 0, wavelength_index: 2, trace_extent_w_sr_m: [0, signatureMax], temporal_interpolation: 'none',
        } : {})};
    case 'signature':
      return {...common, direction_index: state.direction, wavelength_index: state.signatureBand,
        fixed_axis_extent_w_sr_m: [0, signatureMax], source: sample.signature_source};
    case 'detector':
      return {...common, pixel_row_col: state.pixel, wavelength_index: state.wavelength,
        selected_ray_index: rayByPixel.get(state.pixel.join(','))?.index ?? null,
        radiance_extent: [0, radianceMax], electrons_extent: [0, electronsMax], source: detector.source};
    case 'field':
      return {...common, axial_station_m: field.slices[state.slice].x_m,
        selected_cell_index: state.cell, mach_extent: [machMin, machMax], source: field.source};
    case 'engineering':
      return {...common, station_arclength_m: engineeringAxis[state.engineeringStation],
        sources: engineering.map(run => run.source)};
  }
}

function showSource() {
  $('source').textContent = JSON.stringify(viewSpec(), null, 2);
}

const views = {
  shape: () => viewShape(), timeline: () => viewShape(true),
  signature: viewSignature, detector: viewDetector, field: viewField, engineering: viewEngineering,
};

function selectScene(name) {
  active = Object.hasOwn(views, name) ? name : 'shape';
  const [label, title, status] = headings[active];
  $('case').textContent = label;
  $('title').textContent = title;
  $('status').textContent = status;
  document.querySelectorAll('nav button').forEach(button => {
    if (button.dataset.scene === active) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  });
  views[active]();
}

document.querySelectorAll('nav button').forEach(button => {
  button.onclick = () => selectScene(button.dataset.scene);
});
$('reset').onclick = () => {
  state = initial();
  selectScene(active);
};
$('export').onclick = () => {
  const blob = new Blob([JSON.stringify(viewSpec(), null, 2) + '\n'], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `radiant-plume-${active}-view.json`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
};
let redraw;
window.addEventListener('resize', () => {
  clearTimeout(redraw);
  redraw = setTimeout(() => views[active](), 100);
});
selectScene(new URLSearchParams(window.location.search).get('scene'));
