# Reference Sources and Provenance Plan

## 1. Purpose

Identify the primary references and validation-data families that should
support equations, correlations, test fixtures, and calibration. This file is
a source map, not permission to copy data without checking usage terms.

Every imported fixture must record:

```text
source title
authors or issuing organization
publication/report identifier
publication year
retrieval date
raw file checksum
units
processing script
license or usage note
```

## 2. Compressible-flow equations

### Primary textbook

John D. Anderson, *Modern Compressible Flow: With Historical Perspective*,
third edition.

Use for:

```text
isentropic relations
Prandtl-Meyer flow
normal shocks
oblique shocks
theta-beta-M relation
method-of-characteristics foundations
```

Equation implementation must still be checked independently and tested against
analytic values.

### NASA Glenn educational equations

Use the NASA Glenn compressible-flow and rocket-thrust equation pages as a
secondary check for:

```text
area-Mach relation
choked mass flow
nozzle thrust terms
```

Do not use an educational page as the only validation source.

## 3. Shock-cell spacing and topology

Use the classical Prandtl/Pack near-adapted circular-jet shock-cell literature
for the baseline relation:

\[
L_s\approx1.306D_j\sqrt{M_j^2-1}.
\]

Use later finite-shear-layer analyses for spacing corrections and shock
amplitude behavior.

Rules:

- Treat the relation as a correlation/check, not a governing law.
- Record Mach, pressure ratio, temperature ratio, diameter convention, and
  boundary-layer/shear-layer assumptions.
- Do not extrapolate a near-adapted relation into Mach-disk regimes.

## 4. Flow-structure validation data

### NASA NTRS 20080024224

Underexpanded supersonic round-jet planar-laser-induced-fluorescence data,
including an exit Mach near 2.6 and a range of exit-to-ambient pressure ratios.

Use for:

```text
shock-cell topology
first-cell length
cell spacing
plume boundary
qualitative/quantitative image comparison
```

Verify exact case metadata from the report before creating fixtures.

### NASA NTRS 20060004779

Fluorescence-imaging measurements of underexpanded sonic jets over a broad
pressure-ratio range, with comparisons including shock wavelength and
Mach-disk geometry.

Use initially for:

```text
Mach-disk-required classifier
cell wavelength trends
maximum jet diameter trends
```

Do not claim Mach-disk prediction until that topology is implemented.

### NASA NTRS 19840007357

Historical shock-capturing/turbulent jet-mixing plume-solver work that includes
strongly underexpanded behavior and downstream mixing.

Use for:

```text
architecture comparison
Mach-disk and post-disk model requirements
mixing-continuation expectations
```

## 5. Infrared validation

### NASA NTRS 19960015541

Axisymmetric heated-plume work combining measured temperature/pressure or
constituent fields with infrared imaging and a ray-tracing/band-radiation
comparison.

Use for the first experimental radiation validation because it separates plume
field uncertainty from complex reacting rocket chemistry better than an
operational rocket image.

Comparison metrics should include:

```text
pixel radiance
centerline and radial image profiles
integrated band radiant intensity
view-angle dependence if available
```

## 6. Spectroscopic data

### HITRAN

Use for line definitions, units, pressure broadening, partition functions, and
reference lower-temperature spectroscopy where applicable.

### HITEMP

Use high-temperature line lists for selected combustion species and wavelength
windows.

### HAPI

Use as a reproducible reference generator for:

```text
line-by-line cross sections
transmittance
radiance
temperature/pressure interpolation fixtures
```

Store the database version, isotopologue policy, line shape, wing cutoff, and
partition-function source with every generated table.

## 7. Equilibrium chemistry

### NASA CEA

Primary source:

```text
NASA RP-1311, Parts I and II
Computer Program for Calculation of Complex Chemical Equilibrium Compositions
and Applications
```

Use for:

```text
equilibrium composition
frozen/equilibrium nozzle expansion
thermodynamic properties
theoretical rocket performance
reference shock/equilibrium cases
```

Store raw CEA inputs and outputs. Do not retain only a manually copied result
table.

## 8. Finite-rate chemistry and transport

### Cantera

Use official Cantera documentation and versioned mechanisms for:

```text
species thermodynamics
reaction kinetics
equilibrium checks
transport properties
homogeneous-reactor verification
```

The mechanism file, Cantera version, phase name, and transport model are part
of the result provenance.

## 9. Atmosphere and sensor propagation

The intrinsic plume radiation result must remain independent of atmospheric
and sensor models.

For later atmospheric propagation, select a versioned, validated model capable
of returning:

```text
spectral path transmittance
path radiance
observer/source geometry
atmospheric profile
```

For every sensor, store:

```text
spectral response
aperture
optical throughput
integration time
detector conversion model
range
field of view
```

## 10. Source-ingestion checklist

Before adding any external fixture:

- [ ] Verify the report identifier and exact case.
- [ ] Preserve the raw source file.
- [ ] Record checksum and retrieval date.
- [ ] Confirm units and coordinate conventions.
- [ ] Write a deterministic processing script.
- [ ] Keep raw and processed data separate.
- [ ] Document excluded or digitized quantities.
- [ ] Record uncertainty bars when supplied.
- [ ] Separate calibration cases from validation cases.
- [ ] Add a README beside the fixture.

## 11. Citation rule for code and docs

Use stable report numbers, DOIs, book editions, and database versions in
docstrings and model notes. Avoid source comments that point only to an
unversioned web page.

A correlation implementation must cite the precise source used for its
coefficient and validity range.
