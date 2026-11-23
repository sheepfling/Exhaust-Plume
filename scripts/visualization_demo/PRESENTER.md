# Radiant Plume demo script

Open index.html in Chrome or Chromium. The bundle works offline. **Reset**
restores the starting selections and camera for the current scene.

| Time | Action | Say |
| --- | --- | --- |
| 0–25 s | Drag the 3D plume to orbit it. Click a centerline marker or move the station slider. | “This is the modeled envelope. Pick a station and see its oriented cross-section and retained mixture temperature.” |
| 25–45 s | Open **Signature** and select **Across exit axis**. | “These two sampled directions have different spectra. Both curves use the same scale. This is the unresolved radiant intensity of the source.” |
| 45–90 s | Open **Sightline + FPA**. Click **Bright**, switch wavelength, then click **Valid zero** and **Masked**. | “This separate, synthetic case connects the pixel to its ray and spectrum. Wavelength changes the radiance panel. The detector integrates the sampled wavelengths over the displayed exposure. A valid zero and an unmapped pixel mean different things.” |

Use shape.png, signature.png, and detector.png for a still walkthrough. For
questions, **Timeline** steps through four prescribed samples, **Flow field**
opens the retained expansion fan cells, and **Engineering** compares native
flux sections on shared scales.

**Export view** saves selections, plot settings, and displayed source
identities. The exact results are in source_results.json and their identities
and the bundle files are listed in manifest.json.
