# Radiant Plume visualization demo backlog

All eight tasks are implemented in the offline demo. Build the bundle from the
repository root with the project dependencies and Chrome or Chromium installed.

```bash
python3 scripts/generate_visualization_demo.py
```

Open `build/visualization-demo/index.html` in Chrome or Chromium. The bundle
includes `PRESENTER.md`, three fallback PNGs, the exact typed results, and a
manifest with source identities and file digests. Use `--output-dir` to choose
a destination, `--chrome` to select a browser binary, or `--skip-stills` to
generate only the interactive files. Keep the folder together when sharing it.
[Demo generator](../scripts/generate_visualization_demo.py)

Aim for a 90-second live demo for a technical audience seeing Radiant Plume for
the first time. Open on a curved 3D plume. Let someone pick a section, change
the viewing direction in Signature, then pick a pixel and trace its source
radiance through to expected detector electrons. End with the contributing
ray and spectrum visible beside the selected pixel.

## Demo sequence

| Time | What the presenter does | What the audience sees |
| --- | --- | --- |
| 0–25 s | Orbit the plume, then select a section where it bends. | The selected ring, oriented cross-section, and station temperature update together. The centerline and scale stay visible. |
| 25–45 s | Switch between two sampled observer directions. | The direction marker and selected spectrum move together. Both spectra use the same axes, so the change in unresolved radiant intensity is easy to see. |
| 45–90 s | Open the synthetic imaging case. Select a bright pixel, then an invalid one. | The valid pixel exposes its contributing ray, source spectrum, and expected detector signal. The invalid pixel shows its status and a distinct mask. |

## First demo backlog

| Order | Task | Build from | Done when |
| --- | --- | --- | --- |
| 1 | **Prepare the two demo cases.** Bind Shape and Signature to the same curved plume case. Prepare a separate synthetic Sightline case with a spatially structured 2D pixel grid. Derive both the radiance image and detector frame from that case's exact ray request, result, and pixel geometry. | The whitepaper curved-integral and gray model Signature examples, plus its two-pixel FPA operator example as a reference. [Case definitions](../fixtures/products/visualization_demo_cases_v1.json) | One command produces a manifest with each case's source identities and generated artifacts. The imaging grid includes a bright interior, a valid zero-source pixel, and a masked pixel. The two cases have distinct visible labels. |
| 2 | **Build the opening Shape view.** Put the 3D envelope and centerline on the first screen. Link station selection to a highlighted ring, its oriented cross-section, and the retained radius and temperature readouts. | The sectioned-tube renderer and model gallery. [Five-lane visualization standard](model_visualization_standard_v1.md) | The bend is legible at the default camera and can be rotated. Click or keyboard-select a station and see its ring, section, and values update together. Label the envelope as display geometry and show the station's actual units. |
| 3 | **Make the Signature direction change visible.** Give two exact sampled directions memorable labels such as “along the axis” and “across the plume” when the vectors support those labels. Link the direction marker, spectrum, and wavelength-by-direction heatmap. | The existing Signature gallery and the curved gray Signature case. [Signature view requirements](visualization_evaluation_plan_v1.md#spectral-radiant-intensity) | Selecting either direction moves all three views together. The two spectra show a visible difference at one or more retained wavelengths on fixed axes. Labels identify the quantity as unresolved spectral radiant intensity, and the selected vector and validity are inspectable. |
| 4 | **Trace a pixel from Sightline to the detector.** Put the selected-wavelength radiance image beside the expected-electron frame. Use one pixel selection to highlight the same row and column in both and expose its contributing rays and spectra. | The existing ray, spectral radiance image, and FPA galleries. [Radiance image contract](spectral_radiance_image_contract_v1.md) · [Detector frame contract](fpa_detector_frame_contract_v1.md) | Both panels have their own units. The wavelength selector changes the source image while the detector panel continues to show the integrated value for its labeled exposure and response. The same pixel selection works in both panels. A valid zero and an invalid pixel are visibly different. |
| 5 | **Package and rehearse the walkthrough.** Put the three scenes behind one entry point, with preset selections and a reset. Ship the demo as a local bundle with a short presenter script and a still from each scene. | The existing standalone HTML viewers and PNG outputs. [Renderer coverage](visualization_evaluation_plan_v1.md) | The bundle opens offline. At 1280×720 the presenter can run the three beats in 90 seconds, read both image legends on screen, and export the selected view with its source identity. Stills cover every beat if live interaction is unavailable. |

Tasks 2–4 can proceed independently once task 1 fixes the data and initial
selections. Task 5 assembles those outputs. Use a consistent background and
typography across scenes, fixed scales within comparisons, and a reserved
mask color. Put units, case labels, and fidelity on screen. Keep digests and
operator details one click away.

## Follow-on backlog

| Order | Task | Done when |
| --- | --- | --- |
| 6 | **Scrub a plume and its Signature through time.** Reuse the exact-sample mission and Signature timelines. | One scrubber selects declared, compatible snapshots and updates geometry, source pose, and the selected Signature trace. Camera and plot bounds stay fixed while stepping through the sequence. [Mission-time model visualization](visualization_evaluation_plan_v1.md) |
| 7 | **Open a flow field for closer inspection.** Add a second Shape case with a retained zone or cell field. Move the section marker through a declared Mach or temperature field. | A click identifies the source cell or zone and shows its retained value. The selected station opens the radial profile when that lane carries the necessary data. [Five-lane visualization standard](model_visualization_standard_v1.md) |
| 8 | **Inspect and compare engineering outputs.** Add an engineering section view for momentum and mass flow at exact stations. Offer geometry/provider comparisons for cases with compatible frames and quantities. | Selecting a station highlights its geometry and available quantities. Comparisons show comparable results on shared axes with separate provenance. Support bounds and projected area can appear as labeled context. [Visualization survey](visualization_survey_v1.md) |

The first demo uses engineering and synthetic results with their existing claim
limits. Acceptance for physical spectra and measured detector frames stays in
the product roadmap. [Product suite completion plan](product_suite_completion_plan_v1.md)
