"""Build the offline Radiant Plume demo from the repository's typed products."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path
import shutil
import subprocess
import tempfile

from visualization_demo_cases import (
    CASE_PATH,
    REPO_ROOT,
    _curved_integral_result,
    _gray_ray_result,
    _straight_integral_result,
)
from exhaust_plume.api.v1 import (
    ENGINEERING_FLUX_SECTION_V1,
    VISUAL_SECTIONED_TUBE_V1,
    EngineeringFluxSectionRequest,
    Pose,
    SnapshotMetadata,
    SpectralSignatureRequest,
    TimeModel,
    VisualSampling,
    VisualSectionedTubeRequest,
    canonical_digest,
    make_spectral_radiance_image_request,
    to_fpa_detector_frame,
    to_spectral_radiance_image,
)
from exhaust_plume.models.moc.fan import solve_source_point_expansion_fan
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.products.mission_timeline import (
    MissionState,
    MissionVisualizationSample,
    MissionVisualizationTimeline,
)
from exhaust_plume.products.model_signature import (
    GrayRadiationProfile,
    ModelSignatureSampling,
    evaluate_model_signature,
)
from exhaust_plume.products.model_visualization import (
    evaluate_standardized_model_visualization,
    standardize_moc_expansion_fan_visualization,
    standardize_model_visualization,
)
from exhaust_plume.products.signature_timeline import SignatureTimeline, SignatureTimelineSample
from exhaust_plume.products.workflow_model_gallery import _polygon_radial_intervals
from exhaust_plume.products.workflow_visual import build_sectioned_tube_mesh
from exhaust_plume.providers.straight_integral_visual import (
    StraightIntegralVisualConfiguration,
    StraightIntegralVisualDefinition,
    StraightIntegralVisualProvider,
)
from exhaust_plume.validation.fpa_operators import (
    DetectorResponse,
    FpaPixelGeometry,
    integrate_spectral_ray_result_to_fpa,
)
from exhaust_plume.validation.fpa_visualization import FpaSourceReference, FpaVisualizationInput


TEMPLATE = Path(__file__).with_name('visualization_demo')
SCENES = ('shape', 'signature', 'detector')
FRAME = 'demo-source-local'
RADIAL_SEGMENTS = 24


def pose(frame_id, position=(0.0, 0.0, 0.0)):
    return Pose(frame_id=frame_id, translation_m=position, rotation_xyzw=(0.0, 0.0, 0.0, 1.0))


def packet(result, request=None):
    entry = {
        'content_sha256': canonical_digest(result),
        'result': result.model_dump(mode='json'),
    }
    if request is not None:
        entry['request'] = request.model_dump(mode='json')
    return entry


def source(result):
    metadata = result.metadata
    return {
        'capability': metadata.capability.model_dump(mode='json'),
        'result_id': metadata.result_id,
        'content_sha256': canonical_digest(result),
        'request_sha256': metadata.request_digest_sha256,
        'snapshot_id': metadata.snapshot.snapshot_id,
        'time_s': metadata.snapshot.time_s,
        'frame_id': metadata.output_frame_id,
        'provider_id': metadata.provenance.provider_id,
        'provider_version': metadata.provenance.provider_version,
        'model_lineage_id': metadata.provenance.model_lineage_id,
        'claims': metadata.claims.model_dump(mode='json'),
        'applicability': metadata.applicability.model_dump(mode='json'),
    }


def shape_view(visual, bundle):
    mesh = build_sectioned_tube_mesh(visual, radial_segments=RADIAL_SEGMENTS, cap_ends=False)
    return {
        'mesh': mesh.model_dump(),
        'radial_segments': RADIAL_SEGMENTS,
        'sections': [section.model_dump(mode='json') for section in visual.sections],
        'source': {**source(visual), 'bundle_sha256': bundle.digest_sha256()},
    }


def curved_demo(config, optical):
    # Use a prescribed crossflow sweep to make the modeled bend legible at presentation scale.
    config = {**config, 'case_id': 'demo-curved-crossflow', 'entrainment_kgpspm': 0.9}
    base_flow = (1.0, 5.0, -15.0)
    velocity = config['source']['velocity_mps']
    length = hypot(*velocity)
    horizontal = hypot(*velocity[:2])
    directions = (
        tuple(component / length for component in velocity),
        (-velocity[1] / horizontal, velocity[0] / horizontal, 0.0),
    )
    wavelengths = tuple(optical['wavelengths_m'])
    sampling = ModelSignatureSampling(source_to_observer_directions=directions, transverse_sample_count=17)
    signature_request = SpectralSignatureRequest(
        direction_frame_id=FRAME,
        wavelengths_m=wavelengths,
        source_to_observer_directions=sampling.source_to_observer_directions,
    )
    visual_samples, signature_samples, exact, views = [], [], [], []
    for time_s, flow_factor, position in (
        (0.0, 1.0, (0.0, 0.0, 0.0)),
        (1.0, 0.35, (0.8, 0.1, 0.2)),
        (2.0, 1.7, (1.6, 0.3, 0.4)),
        (3.0, 2.2, (2.4, 0.6, 0.6)),
    ):
        ambient = {**config['ambient'], 'velocity_mps': [flow_factor * value for value in base_flow]}
        exact_config = {**config, 'ambient': ambient}
        bundle = standardize_model_visualization(
            _curved_integral_result(exact_config), frame_id=FRAME, section_count=33,
        )
        state = MissionState(
            time_s=time_s, source_pose=pose('demo-trajectory', position), ambient_state=ambient,
            operating_point_id=config['case_id'],
        )
        state_digest = state.fingerprint_sha256
        bundle_digest = bundle.digest_sha256()
        snapshot = SnapshotMetadata(
            snapshot_id=state_digest, session_id='radiant-plume-demo-curved', time_s=time_s, source_pose=state.source_pose,
            dynamic_state_digest_sha256=canonical_digest(state.snapshot_dynamic_state()),
            ambient_state_digest_sha256=canonical_digest(ambient), provider_state_digest_sha256=bundle_digest,
        )
        visual_request = VisualSectionedTubeRequest(
            output_frame_id=FRAME, sampling=VisualSampling(maximum_section_count=33), requested_channels=('temperature',),
        )
        visual = evaluate_standardized_model_visualization(bundle, visual_request, snapshot, time_model=TimeModel.PRESCRIBED_TRANSIENT)
        profile = GrayRadiationProfile.from_blackbody(
            wavelengths, optical['source_temperature_K'], tuple(optical['absorption_coefficient_per_m']),
            emissivity=optical['emissivity'], profile_id=optical['profile_id'],
        )
        signature = evaluate_model_signature(
            bundle, profile, sampling=sampling, time_s=time_s, source_pose=state.source_pose,
            dynamic_state=state.snapshot_dynamic_state(), ambient_state=ambient, time_model=TimeModel.PRESCRIBED_TRANSIENT,
        )
        visual_samples.append(MissionVisualizationSample(state, bundle, visual))
        signature_samples.append(SignatureTimelineSample(signature_request, signature))
        values = [
            [value if valid else None for value, valid in zip(row, mask, strict=True)]
            for row, mask in zip(signature.spectral_radiant_intensity, signature.validity_mask, strict=True)
        ]
        views.append({
            'time_s': time_s, 'position_m': position, 'pose_frame': state.source_pose.frame_id, 'ambient_velocity_mps': ambient['velocity_mps'],
            'shape': shape_view(visual, bundle), 'intensity': values,
            'direction_status': [status.code.value for status in signature.direction_status],
            'signature_source': {**source(signature), 'bundle_sha256': bundle_digest},
        })
        exact.append({
            'scenario': exact_config, 'state_sha256': state_digest, 'model_bundle': bundle.model_dump(),
            'visual': packet(visual, visual_request), 'signature': packet(signature, signature_request),
        })

    visual_timeline = MissionVisualizationTimeline(tuple(visual_samples))
    signature_timeline = SignatureTimeline(tuple(signature_samples))
    if tuple(sample.state.time_s for sample in visual_timeline.samples) != signature_timeline.times_s:
        raise ValueError('demo mission products must use identical evaluated times')
    return {
        'wavelengths_um': [wavelength * 1e6 for wavelength in wavelengths],
        'directions': directions, 'direction_labels': ['Along exit axis', 'Across exit axis'], 'samples': views,
    }, exact


def detector_demo(optical, response):
    width, height = 48, 30
    # Leave an unmapped corner visible and include exterior rays with genuine zero radiance.
    pixels = tuple((row, column) for row in range(height) for column in range(width) if not (row < 5 and column >= width - 6))
    config = {
        **optical,
        'case_id': 'demo-orthographic-gray-imaging',
        'absorption_coefficient_per_m': (0.23, 0.55, 0.9),
        'support': {
            'frame_id': 'demo-imaging-local',
            'centers_m': [(x, 0.0, 0.42 * x - 0.48) for x in (0.0, 0.55, 1.08, 1.65, 2.15)],
            'radii_m': (0.29, 0.44, 0.38, 0.26, 0.13),
        },
        'rays': [
            {'origin_m': (-0.45 + 2.9 * column / (width - 1), -2.0, 1.25 - 2.5 * row / (height - 1)),
             'direction': (0.0, 1.0, 0.0)}
            for row, column in pixels
        ],
    }
    request, result, wavelengths, _ = _gray_ray_result(config)
    geometry = FpaPixelGeometry(width, height, pixels, (1e-16,) * len(pixels))
    image_request = make_spectral_radiance_image_request(request, result, geometry=geometry, pixel_frame_id='demo-pixels')
    radiance = to_spectral_radiance_image(image_request, request, result, geometry=geometry)
    detector = DetectorResponse(
        wavelengths_m=wavelengths, quantum_efficiency=tuple(response['quantum_efficiency']),
        optical_throughput=tuple(response['optical_throughput']), response_id=response['detector_response_id'],
    )
    image = integrate_spectral_ray_result_to_fpa(request, result, geometry=geometry, detector=detector, exposure_s=response['exposure_s'])
    fpa_input = FpaVisualizationInput(
        image=image, source=FpaSourceReference.from_ray_result(result), detector_response=detector,
        validation_status='synthetic-operator-demonstration',
    )
    frame = to_fpa_detector_frame(fpa_input, geometry=geometry)
    if frame.pixel_geometry_sha256 != radiance.pixel_geometry_sha256 or frame.validity_mask != radiance.validity_mask:
        raise ValueError('demo radiance and detector panels must share pixel geometry and coverage')
    spectrum = radiance.source_spectral_radiance_W_m2_sr_m
    bright = max(pixels, key=lambda rc: frame.expected_electrons_e[rc[0]][rc[1]])
    zero = next((r, c) for r, c in pixels if not any(spectrum[r][c]))
    view = {
        'width': width, 'height': height, 'bright': bright, 'zero': zero, 'masked': (2, width - 3),
        'wavelengths_um': [wavelength * 1e6 for wavelength in wavelengths],
        'radiance': spectrum, 'transmittance': radiance.background_transmittance,
        'electrons': frame.expected_electrons_e, 'validity': radiance.validity_mask,
        'statuses': [[status.code.value for status in row] for row in radiance.pixel_status],
        'rays': [
            {'index': index, 'pixel': pixel, 'origin_m': request.ray_origins_m[index],
             'direction': request.ray_directions[index], 't_m': (request.ray_t_min_m[index], request.ray_t_max_m[index])}
            for index, pixel in enumerate(pixels)
        ],
        'exposure_s': frame.exposure_s, 'detector': frame.detector.model_dump(mode='json'),
        'source': {'ray': source(result), 'radiance': source(radiance), 'frame_sha256': canonical_digest(frame),
                   'measurement_operator_sha256': frame.measurement_operator_sha256, 'pixel_geometry_sha256': frame.pixel_geometry_sha256},
    }
    return view, {
        'support': config['support'], 'absorption_coefficient_per_m': config['absorption_coefficient_per_m'],
        'ray_transfer': packet(result, request), 'radiance': packet(radiance, image_request), 'detector_frame': packet(frame),
    }


def field_demo():
    fan = solve_source_point_expansion_fan(
        CharacteristicState(x_m=1.0, y_m=0.2, theta_rad=0.0, mach=1.6, gamma=1.4),
        total_pressure_Pa=1_000_000.0, ambient_pressure_Pa=100_000.0, characteristic_count=14,
    )
    bundle = standardize_moc_expansion_fan_visualization(fan, reference_total_temperature_K=1200.0)
    field = bundle.fields[0]
    axial = [point[0] for polygon in field.polygons_xr_m for point in polygon]
    lower, upper = min(axial), max(axial)
    stations = [lower + i * (upper - lower) / 20 for i in range(1, 20)]
    slices = []
    for station in stations:
        intervals = [
            (index, start, end)
            for index, polygon in enumerate(field.polygons_xr_m)
            for start, end in _polygon_radial_intervals(polygon, station)
        ]
        slices.append({'x_m': station, 'intervals': intervals})
    return {
        'polygons': field.polygons_xr_m, 'mach': field.channels['mach'], 'labels': field.region_labels,
        'paths': [path.model_dump() for path in bundle.paths], 'slices': slices,
        'source': {'model_id': bundle.model_id, 'field_id': field.field_id, 'frame_id': bundle.frame_id,
                   'bundle_sha256': bundle.digest_sha256(), 'validation_level': bundle.claims.validation_level},
    }, bundle.model_dump()


def engineering_demo(config):
    evaluator = REPO_ROOT / 'src/exhaust_plume/providers/straight_integral_engineering_flux.py'
    code_revision = 'sha256:' + sha256(evaluator.read_bytes()).hexdigest()
    provider = StraightIntegralVisualProvider(StraightIntegralVisualConfiguration(code_revision=code_revision))
    output, exact = [], []
    for label, coefficient in [('Baseline', config['entrainment_coefficient']), ('Higher entrainment', 2 * config['entrainment_coefficient'])]:
        scenario = {**config, 'entrainment_coefficient': coefficient}
        result = _straight_integral_result(scenario)
        definition = StraightIntegralVisualDefinition(FRAME, result)
        session = provider.create_session(definition=definition)
        try:
            snapshot = session.create_snapshot(time_s=0.0, source_pose=pose(FRAME), dynamic_state=scenario, ambient_state={})
            flux_request = EngineeringFluxSectionRequest(
                output_frame_id=FRAME, centerline_reference_id=definition.centerline_reference_id,
                centerline_arclength_m=tuple(state.x_m for state in result.states),
            )
            visual_request = VisualSectionedTubeRequest(
                output_frame_id=FRAME, sampling=VisualSampling(maximum_section_count=len(result.states)),
            )
            flux = snapshot.evaluate(ENGINEERING_FLUX_SECTION_V1, flux_request)
            visual = snapshot.evaluate(VISUAL_SECTIONED_TUBE_V1, visual_request)
        finally:
            session.close()
        sections = {section.arc_length_m: section for section in visual.sections}
        output.append({
            'label': label, 'coefficient': coefficient, 'source': {'flux': source(flux), 'geometry': source(visual)},
            'stations': [
                {'x_m': sample.station_arclength_m, 'mass_kg_s': sample.section.mass_flow_kg_s,
                 'momentum_n': hypot(*sample.section.momentum_flux_N),
                 'radius_m': sections[sample.station_arclength_m].radius_major_m}
                for sample in flux.samples if sample.section is not None
            ],
        })
        exact.append({'scenario': scenario, 'flux': packet(flux, flux_request), 'geometry': packet(visual, visual_request)})
    if [row['x_m'] for row in output[0]['stations']] != [row['x_m'] for row in output[1]['stations']]:
        raise ValueError('engineering comparison requires matching native stations')
    return output, exact


def chrome_binary():
    for name in ('chromium', 'chromium-browser', 'google-chrome', 'google-chrome-stable'):
        if path := shutil.which(name):
            return Path(path)
    mac = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
    return mac if mac.is_file() else None


def capture_stills(output, chrome):
    with tempfile.TemporaryDirectory(prefix='plume-demo-chrome-') as profile:
        for scene in SCENES:
            path = output / f'{scene}.png'
            completed = subprocess.run([
                str(chrome), '--headless', '--disable-background-networking', '--no-first-run', '--hide-scrollbars',
                f'--user-data-dir={profile}', '--window-size=1280,720', '--force-device-scale-factor=1',
                f'--screenshot={path}', (output / 'index.html').as_uri() + f'?scene={scene}',
            ], capture_output=True, text=True, timeout=30)
            if completed.returncode != 0:
                raise RuntimeError(f'Chromium could not capture the {scene} scene: {completed.stderr.strip() or completed.returncode}')
            if not path.is_file():
                raise RuntimeError(f'Chromium did not write {path}')


def write_bundle(output, chrome):
    config = json.loads(CASE_PATH.read_text(encoding='utf-8'))
    curved, curved_exact = curved_demo(config['curved_integral'], config['gray_optics'])
    detector, detector_exact = detector_demo(config['gray_optics'], config['fpa'])
    field, field_exact = field_demo()
    engineering, engineering_exact = engineering_demo(config['straight_integral'])
    view = {'curved': curved, 'detector': detector, 'field': field, 'engineering': engineering}
    exact = {'curved': curved_exact, 'detector': detector_exact, 'field': field_exact, 'engineering': engineering_exact}
    for name in ('index.html', 'demo.css', 'demo.js', 'PRESENTER.md'):
        shutil.copyfile(TEMPLATE / name, output / name)
    (output / 'data.js').write_text('window.PLUME_DEMO = ' + json.dumps(view, allow_nan=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    (output / 'source_results.json').write_text(json.dumps(exact, allow_nan=False, indent=2) + '\n', encoding='utf-8')
    if chrome is not None:
        capture_stills(output, chrome)
    names = ['index.html', 'demo.css', 'demo.js', 'data.js', 'PRESENTER.md', 'source_results.json']
    if chrome is not None:
        names.extend(f'{scene}.png' for scene in SCENES)
    manifest = {
        'schema': 'radiant-plume.visualization-demo@1',
        'artifacts': {name: sha256((output / name).read_bytes()).hexdigest() for name in names},
        'cases': {
            'curved': [{'shape': sample['shape']['source'], 'signature': sample['signature_source']} for sample in curved['samples']],
            'imaging': detector['source'], 'field': field['source'], 'engineering': [entry['source'] for entry in engineering],
        },
    }
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return names


def build(output, chrome):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.radiant-demo-', dir=output.parent) as directory:
        staging = Path(directory)
        names = write_bundle(staging, chrome)
        output.mkdir(exist_ok=True)
        for filename in (*names, 'manifest.json'):
            (staging / filename).replace(output / filename)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=REPO_ROOT / 'build' / 'visualization-demo')
    parser.add_argument('--chrome', type=Path, help='Chrome or Chromium executable for the three fallback stills')
    parser.add_argument('--skip-stills', action='store_true', help='Build the interactive bundle only')
    args = parser.parse_args()
    chrome = None if args.skip_stills else args.chrome or chrome_binary()
    if chrome is None and not args.skip_stills:
        parser.error('Chrome or Chromium is required for stills. Supply --chrome or --skip-stills.')
    build(args.output_dir.resolve(), chrome)
    print(args.output_dir.resolve() / 'index.html')


if __name__ == '__main__':
    main()
