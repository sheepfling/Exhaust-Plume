# Calibration, Uncertainty, and Scientific-Data Plan

## 1. Purpose

The reduced-order model contains closures that cannot be determined from the
Euler equations alone. This document prevents those closures from becoming
anonymous constants tuned against the same cases later presented as validation.

The goals are:

- trace every coefficient to data and code;
- separate calibration from validation;
- preserve measurement and model uncertainty;
- detect unidentifiable parameters;
- make every fitted result reproducible;
- propagate uncertainty into cell count, plume length, and IR signature.

## 2. Quantities that require calibration or external data

### 2.1 Shock-train closures

Candidate parameters include:

```text
inward shear-layer spreading rate                 S_i
cell-spacing correction relative to baseline      C_lambda
pressure-oscillation decay coefficient             C_d
mean-pressure relaxation coefficient               C_pbar
total-pressure loss continuation coefficient       C_p0
core-Mach continuation parameters                  model-specific
Mach-disk topology threshold or classifier         model-specific
```

The classical first-cell coefficient is a correlation benchmark. Any modified
coefficient used downstream must be treated as calibrated.

### 2.2 Integral-plume closures

```text
entrainment coefficient                            E
profile-shape parameters                           beta_u, beta_T, beta_Y
ambient coflow correction                          model-specific
compressibility correction                         model-specific
turbulent Schmidt/Prandtl surrogates                model-specific
```

### 2.3 Radiation closures or external tables

```text
gray absorption coefficient                        calibration-only test model
cross-section interpolation floor                  numerical metadata
narrow-band or correlated-k parameters             table provenance
atmospheric transmission model                     external source
sensor spectral response                           manufacturer/user source
```

### 2.4 Chemistry and particles

```text
reaction mechanism and version
mixing/chemistry coupling approximation
particle size distribution
particle complex refractive index
particle emissivity/absorption/scattering model
nucleation, growth, oxidation, and breakup closures
```

## 3. Scientific data record

Every imported dataset receives an immutable manifest.

```yaml
dataset_id: nasa_example_campaign_case_set_v1
kind: flow_structure
source:
  title: "..."
  organization: "..."
  persistent_identifier: "..."
  access_date: "YYYY-MM-DD"
  license_or_use_note: "..."
files:
  - path: raw/source_file.ext
    sha256: "..."
coordinate_system: axial_radial
units:
  x: m
  pressure: Pa
operating_conditions:
  nozzle_exit_mach: "column or scalar"
  pressure_ratio_definition: "explicit definition"
measurement_uncertainty:
  pressure_relative: "value or unknown"
processing:
  script: tools/validation/ingest_example.py
  commit: "git sha"
  output_sha256: "..."
allowed_uses:
  calibration: true
  validation: false
notes: "..."
```

Unknown measurement uncertainty must be recorded as unknown, not silently set
to zero.

## 4. Data directory layout

Recommended repository layout:

```text
validation_data/
  manifests/
    <dataset_id>.yaml
  analytic/
    small generated fixtures
  processed/
    small versioned CSV/NPZ fixtures
  large_data_manifest/
    content hashes and retrieval instructions

tools/
  validation/
    ingest_<dataset>.py
    calibrate_shock_train.py
    validate_shock_train.py
    calibrate_integral_plume.py
    validate_radiation.py
```

Do not place large source datasets in the package wheel. Small processed
fixtures may be checked into the repository when licensing permits.

## 5. Operating-condition identity

Every case must define pressure ratios unambiguously. Distinguish at least:

```text
nozzle pressure ratio              p_0 / p_a
exit pressure ratio                p_e / p_a
fully expanded pressure condition  p_j = p_a
```

Also record:

```text
M_e
D_e or equivalent diameter
gamma or mixture model
T_e / T_a
rho_e / rho_a
ambient Mach/coflow velocity
boundary-layer or shear-layer thickness when available
nozzle geometry and exit profile source
```

A case lacking the quantities required by a closure may still be used for
qualitative comparison but not parameter fitting.

## 6. Calibration/validation split

Split by independent physical cases, not by randomly dividing points from the
same trace.

Preferred hierarchy:

1. Hold out complete operating conditions.
2. Hold out complete test campaigns or facilities.
3. Hold out a pressure-ratio range.
4. Only when data are scarce, hold out complete repeated runs.

Never fit coefficients to a centerline-pressure trace and claim validation
against other points on that same trace.

Dataset manifests must state one of:

```text
CALIBRATION
VALIDATION
QUALITATIVE_ONLY
```

A change in role requires a new calibration record.

## 7. Calibration parameter contract

```python
class CalibrationParameter(BaseModel):
    name: str
    transform: ParameterTransform
    lower_bound: float
    upper_bound: float
    initial_value: float
    units: str
    description: str
    ####
```

Positive parameters should normally be fitted in log space:

\[
z=\ln c,
\qquad c=e^z.
\]

Bounded fractions may use a logistic transformation. Do not let the optimizer
explore physically impossible values and then clip the result.

## 8. Observable definitions

Calibrate against directly interpretable observables rather than internal
state variables that were not measured.

### 8.1 Flow structure

```text
first-cell length / D_j
subsequent cell boundaries / D_j
maximum plume radius / D_j
centerline pressure extrema / p_a
pressure-oscillation amplitude
Mach-disk location and diameter, when topology applies
supersonic-core length / D_j
```

### 8.2 Mixing plume

```text
centerline velocity / exit velocity
centerline temperature ratio
plume half-width / D_j
species mole or mass fraction
mass-flow growth
```

### 8.3 Radiation

```text
spectral radiance at calibrated pixels
band-integrated radiant intensity
image radial/axial profiles
angular signature
spectral line or band ratios
```

Comparisons must preserve the measurement instrument's spatial, spectral, and
temporal response where known.

## 9. Normalized residuals

For scalar observation \(y_i\) with measurement standard uncertainty
\(\sigma_{m,i}\) and numerical uncertainty \(\sigma_{n,i}\), use

\[
r_i
=
\frac{y_i^{model}-y_i^{obs}}
{\sqrt{\sigma_{m,i}^2+\sigma_{n,i}^2+\sigma_{floor,i}^2}}.
\]

The floor represents documented unresolved discrepancy or prevents one
nominally zero uncertainty from dominating. It must be reported and subjected
to sensitivity analysis.

Weighted least-squares objective:

\[
J(\boldsymbol\theta)
=
\frac12
\sum_i w_i r_i^2.
\]

Weights are chosen before inspecting validation performance and are recorded in
the calibration artifact.

For a full covariance matrix \(\mathbf\Sigma\), use

\[
J
=
\frac12
\mathbf e^T\mathbf\Sigma^{-1}\mathbf e.
\]

Do not assume independent pixels or spectral bins when the measurement system
creates strong correlations.

## 10. Calibration stages

Calibrate in dependency order.

### Stage C0 — First-cell scale only

Fit or verify no free parameters if the first cell is governed by the selected
MOC model. Compare against the classical spacing correlation and held-out data.
Do not use downstream decay parameters here.

### Stage C1 — Shock-train spacing and decay

Fit:

```text
S_i
C_lambda adjustment, if required
C_d
optional mean-pressure relaxation
```

Use cell boundaries and centerline pressure amplitudes. Hold out complete
operating conditions.

### Stage C2 — Integral mixing

Fit entrainment and profile parameters using velocity, temperature, width, and
species measurements downstream of the coherent core. Do not re-fit shock-cell
parameters unless a joint model is explicitly justified.

### Stage C3 — Radiation transport

Do not tune molecular line strengths. Validate spectroscopy against source
tools. Calibration may cover instrument response, uncertain background, or a
reduced gray/narrow-band surrogate, with clear separation from fundamental
spectroscopic data.

### Stage C4 — Chemistry and particles

Calibrate only closure quantities not defined by the selected kinetic
mechanism or optical-property source. Hold out propellant conditions or test
campaigns where possible.

## 11. Optimizer policy

Start with deterministic bounded optimization:

```text
scipy.optimize.least_squares
loss = linear for well-characterized Gaussian residuals
robust loss only when justified and documented
```

Run multiple initial points within the admissible parameter domain. Report:

```text
initial points
successful/failed solves
final objective
active bounds
Jacobian condition metrics
parameter correlation
```

A single optimizer result without start-point sensitivity is insufficient.

## 12. Identifiability and sensitivity

Calculate local scaled sensitivity:

\[
S_{ij}
=
\frac{\partial \ln y_i}{\partial \ln \theta_j}
\]

for positive quantities, or an appropriately scaled finite-difference analogue.

Inspect the singular values of the weighted Jacobian. Parameters with nearly
collinear effects should be:

- fixed from independent evidence;
- combined into a lower-dimensional parameter;
- assigned broader uncertainty;
- or removed from the current model.

Do not report precise estimates for unidentifiable coefficients.

## 13. Numerical uncertainty

Before calibration, establish discretization uncertainty for each observable.
Use at least three refinements and estimate an error bound or convergence band.

Examples:

```text
MOC characteristic count
ODE tolerance and output step
ray/image grid
spectral grid and cross-section table resolution
```

Calibration must not fit coefficients to compensate for unresolved numerical
error.

## 14. Parameter uncertainty

At minimum, estimate covariance from the calibrated Jacobian when assumptions
are defensible:

\[
\operatorname{Cov}(\hat\theta)
\approx
s^2
(\mathbf J^T\mathbf W\mathbf J)^{-1}.
\]

For nonlinear or bounded cases, prefer profile likelihood, bootstrap across
independent cases, or Bayesian sampling.

The selected method and assumptions are part of the calibration artifact.

## 15. Forward uncertainty propagation

For uncertain inputs and calibration parameters \(\mathbf z\), propagate to
outputs \(g(\mathbf z)\) using one of:

```text
linear covariance propagation for small uncertainties
Latin hypercube or Sobol sampling
Monte Carlo sampling
polynomial/surrogate model after direct-solver verification
```

Required output summaries:

```text
median or nominal value
5th and 95th percentiles, or configured interval
probability of each termination reason
cell-count distribution
shock-train endpoint distribution
IR band-signal distribution versus angle
```

Cell count and termination reason are discrete; do not summarize them only by a
mean.

## 16. Model discrepancy

Measurement uncertainty, parameter uncertainty, and model discrepancy are
different quantities.

Use validation residuals to characterize discrepancy over the documented
applicability domain. Do not hide systematic error by inflating measurement
uncertainty.

A result should distinguish:

```text
input uncertainty
calibration parameter uncertainty
numerical uncertainty
observed validation discrepancy
unmodeled-physics validity flags
```

## 17. Calibration artifact

Each fitted model produces a content-addressed artifact:

```yaml
calibration_id: shock_train_round_jet_v1
model_kind: reduced_shock_train
code_commit: "..."
configuration_schema_version: "1.0"
parameter_values:
  inward_spreading_rate: "..."
  pressure_decay_coefficient: "..."
parameter_covariance_file: covariance.npy
calibration_datasets:
  - dataset_a
validation_datasets:
  - dataset_b
objective_definition: objective.yaml
optimizer:
  method: scipy_least_squares
  settings: {}
fit_metrics: {}
validation_metrics: {}
applicability:
  exit_mach: [lower, upper]
  pressure_ratio: [lower, upper]
  temperature_ratio: [lower, upper]
files:
  covariance.npy: "sha256"
  objective.yaml: "sha256"
```

The identifier should change whenever data, code, objective, or fitted values
change.

## 18. Applicability checks

Before using a calibration, compare the requested case to its applicability
bounds. Return:

```text
INSIDE_CALIBRATION_DOMAIN
NEAR_DOMAIN_BOUNDARY
OUTSIDE_CALIBRATION_DOMAIN
```

Outside-domain use requires an explicit caller override and produces a validity
flag in all downstream results.

## 19. Reproducibility commands

Every calibration directory contains exact commands, for example:

```bash
python -m tools.validation.ingest_example --manifest validation_data/manifests/example.yaml
python -m tools.validation.calibrate_shock_train --config calibration/shock_train_v1.yaml
python -m tools.validation.validate_shock_train --calibration calibration/shock_train_v1/result.yaml
```

The command records:

```text
Python version
package version and git commit
dependency lock or environment export
platform
random seed
input hashes
output hashes
```

## 20. Acceptance gate

- [ ] Every closure parameter has units, bounds, and physical meaning.
- [ ] Calibration and validation cases are disjoint.
- [ ] Dataset files are hashed and sourced.
- [ ] Pressure-ratio definitions are explicit.
- [ ] Numerical convergence is established before fitting.
- [ ] Multiple optimizer starts are reported.
- [ ] Identifiability is assessed.
- [ ] Parameter uncertainty is reported.
- [ ] Forward uncertainty reaches cell count, endpoints, and IR outputs.
- [ ] Applicability bounds are machine-checkable.
- [ ] The calibration is reproducible without network access during tests.
