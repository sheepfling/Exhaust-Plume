# Calibration, Uncertainty, and Sensitivity Plan

## 1. Purpose

The shock-train decay, turbulent entrainment, reduced-order radial profiles,
and some particle models require empirical closure coefficients. This document
defines how those coefficients are estimated, versioned, validated, and
propagated into reported uncertainty.

A value copied from a paper or adjusted until a plot looks plausible is not a
production calibration unless its source, units, applicability, objective
function, uncertainty, and validation evidence are recorded.

## 2. Uncertainty categories

Keep the following categories separate.

### 2.1 Numerical uncertainty

Caused by finite characteristic count, grid spacing, ODE tolerances, spectral
resolution, ray count, interpolation, and iterative convergence.

### 2.2 Parametric uncertainty

Caused by uncertain measured or supplied inputs such as:

```text
exit pressure
exit temperature
mass flow
exit diameter
ambient state
species fractions
sensor range and angle
```

### 2.3 Closure uncertainty

Caused by empirical parameters such as:

```text
coherent-core spreading rate
pressure-amplitude decay coefficient
cell-spacing correction
entrainment coefficient
radial-profile width
particle size-distribution parameters
```

### 2.4 Model-form uncertainty

Caused by omitted physics or approximations such as:

```text
planar instead of axisymmetric characteristics
uniform instead of profiled nozzle exit
frozen instead of reacting chemistry
gray instead of spectral radiation
neglected particles
quiescent instead of moving ambient
```

Model-form uncertainty shall not be disguised as a narrow parameter confidence
interval.

### 2.5 Measurement uncertainty

Comes from experimental instruments, image extraction, calibration, spatial
registration, and reported confidence intervals.

## 3. Calibration parameter registry

Every calibratable parameter shall have a registry entry:

```text
parameter_id
symbol
units
model module
physical interpretation
allowed range
transformation used during optimization
nominal value
prior or regularization
source data ids
applicability range
covariance group
version introduced
```

### 3.1 Initial shock-train parameters

Recommended registry entries:

| ID | Symbol | Meaning |
|---|---:|---|
| `shock.core_spreading_rate` | \(S_i\) | Inward coherent-core shear-layer growth per axial distance. |
| `shock.spacing_coefficient` | \(C_\lambda\) | Local cell-spacing coefficient. |
| `shock.pressure_decay` | \(C_d\) | Pressure-oscillation amplitude decay coefficient. |
| `shock.initial_shear_ratio` | \(\delta_0/D_j\) | Initial shear-layer thickness ratio. |
| `shock.total_pressure_loss_scale` | \(C_{p0}\) | Optional reduced-order correction to cell-averaged loss. |

### 3.2 Initial integral-plume parameters

| ID | Symbol | Meaning |
|---|---:|---|
| `mixing.entrainment` | \(E\) | Ambient entrainment coefficient. |
| `mixing.velocity_shape` | \(C_u\) | Radial velocity-profile shape or width. |
| `mixing.temperature_shape` | \(C_T\) | Radial temperature-profile shape or width. |
| `mixing.species_shape` | \(C_Y\) | Radial mixture-fraction profile shape or width. |

Molecular spectroscopic line strengths shall not be treated as free plume-fit
parameters. Database uncertainty may be propagated, but arbitrary opacity
multipliers require explicit justification and shall be labeled model
corrections.

## 4. Calibration data contract

Each observation record shall include:

```text
case_id
source_id
facility and configuration
independent variables
measured quantity
measurement location or image coordinates
value
units
standard uncertainty or covariance
processing method
calibration_or_validation split
quality flags
license and redistribution status
```

Examples of observables include:

```text
first-cell length
cell-center positions
Mach-disk location and diameter
centerline pressure maxima and minima
supersonic-core length
plume half-width
centerline velocity and temperature
spectral radiance pixels
band-integrated radiant intensity
```

Raw source data and derived features must be stored separately. Derived feature
scripts shall be reproducible.

## 5. Nondimensionalization

Fit dimensionless observables wherever practical:

\[
\frac{x}{D_j},
\qquad
\frac{r}{D_j},
\qquad
\frac{p-p_a}{p_a},
\qquad
\frac{u-u_a}{u_j-u_a},
\qquad
\frac{T-T_a}{T_j-T_a}.
\]

This improves conditioning and makes applicability across nozzle sizes more
transparent.

## 6. Calibration and validation split

Calibration cases and validation cases must be disjoint by configuration, not
merely by individual image pixels from the same run.

Recommended split hierarchy:

```text
hold out complete operating conditions
hold out complete nozzle geometries when enough data exist
hold out complete facilities when multiple facilities exist
```

The split and its random seed, when randomized, are part of calibration
provenance.

Data may be assigned to:

```text
calibration
validation
exploratory_only
excluded_with_reason
```

A dataset used to tune a coefficient cannot later be described as independent
validation.

## 7. Residual definitions

For observation \(y_i\), prediction \(m_i(\boldsymbol\theta)\), and standard
uncertainty \(\sigma_i\), define

\[
r_i
=
\frac{m_i(\boldsymbol\theta)-y_i}{\sigma_i}.
\]

For correlated observations with covariance \(\Sigma_y\), use

\[
\mathbf r
=
L^{-1}
\left[
\mathbf m(\boldsymbol\theta)-\mathbf y
\right],
\]

where

\[
LL^T=\Sigma_y.
\]

Do not treat every pixel in an image as statistically independent when the
instrument point-spread function or processing creates correlation.

## 8. Objective function

A default deterministic objective is

\[
\boxed{
J(\boldsymbol\theta)
=
\sum_i
w_i\rho(r_i)
+
\lambda R(\boldsymbol\theta).
}
\]

Here:

- \(w_i\) balances observable families or cases;
- \(\rho\) is a robust loss, such as Huber loss;
- \(R\) is a prior or regularization term;
- \(\lambda\) controls regularization.

Huber loss is

\[
\rho_\delta(r)
=
\begin{cases}
\frac12r^2,& |r|\le\delta,\\
\delta\left(|r|-\frac12\delta\right),& |r|>\delta.
\end{cases}
\]

Weights and robust-loss thresholds must be recorded, not hidden inside a fit
script.

## 9. Parameter transformations and bounds

Positive coefficients should be optimized in log space:

\[
\eta_j=\ln\theta_j.
\]

Bounded fractions may use a logit transformation. Physical bounds remain
explicit and are verified after inverse transformation.

The optimizer must not explore negative spreading rates, negative opacities,
or invalid species fractions.

## 10. Optimization strategy

Recommended sequence:

```text
1. Evaluate nominal parameters on all calibration cases.
2. Run one-at-a-time sensitivity scans.
3. Remove or fix parameters that are unidentifiable from available data.
4. Use bounded multistart least squares for the reduced parameter set.
5. Inspect residual structure by case and observable family.
6. Compute local covariance or posterior samples.
7. Freeze the candidate calibration.
8. Evaluate the untouched validation set once.
```

For expensive models, a surrogate may be used, but its approximation error must
be included and checked against direct solver evaluations.

## 11. Sensitivity analysis

### 11.1 Local dimensionless sensitivity

For output \(y_i\) and parameter \(\theta_j\), define

\[
\boxed{
S_{ij}
=
\frac{\theta_j}{s_i}
\frac{\partial y_i}{\partial\theta_j},
}
\]

where \(s_i\) is an output scale, usually \(|y_i|\) or a documented reference
scale.

Use central finite differences with step-size convergence checks unless an
analytic or automatic derivative is available.

### 11.2 Global sensitivity

For nonlinear multi-parameter models, use Latin hypercube or Sobol sampling to
estimate variance-based sensitivity. The sampling design and seed are saved as
artifacts.

### 11.3 Identifiability

Let \(J_\theta\) be the residual Jacobian. Inspect singular values of

\[
J_\theta^TJ_\theta.
\]

Strongly collinear or near-null parameter combinations are not separately
identifiable. Fix, combine, or regularize them rather than reporting artificial
precision.

## 12. Parameter covariance

For a locally linear least-squares solution,

\[
\Sigma_\theta
\approx
s^2
\left(J_\theta^TWJ_\theta\right)^{-1},
\]

where \(s^2\) is an appropriate residual variance estimate. Use a pseudoinverse
only for diagnostics; a rank-deficient covariance indicates unidentifiable
parameters and must be reported.

A production calibration stores the full covariance matrix and parameter order,
not only one standard deviation per parameter.

## 13. Uncertainty propagation

### 13.1 Linearized propagation

For output vector \(\mathbf y=f(\mathbf z)\), input/parameter covariance
\(\Sigma_z\), and Jacobian \(G=\partial f/\partial\mathbf z\),

\[
\boxed{
\Sigma_y
\approx
G\Sigma_zG^T.
}
\]

This is appropriate only near a smooth operating point with approximately
linear response.

### 13.2 Monte Carlo propagation

```text
1. Sample physical inputs from their distributions.
2. Sample calibration parameters jointly from their covariance or posterior.
3. Preserve physical constraints and correlations.
4. Run the complete requested model level.
5. Record failed/out-of-validity samples separately.
6. Report quantiles and failure probability.
```

The random seed and sample count are part of provenance.

### 13.3 Numerical uncertainty combination

Numerical convergence error shall be estimated separately by refinement. It may
be combined with parametric uncertainty only after the numerical estimate is
shown to be sufficiently small or is explicitly represented.

## 14. Model discrepancy

When validation residuals show systematic structure, do not immediately widen
parameter priors until the model appears to fit. Record a model-discrepancy term
or validity limitation.

Examples:

```text
cell-spacing bias increasing with pressure ratio
consistent plume-width bias under flight coflow
spectral residual concentrated in particle-continuum regions
view-angle bias caused by vehicle occlusion omission
```

The discrepancy should inform the next fidelity phase.

## 15. Validation metrics

Report multiple metrics rather than a single aggregate score:

\[
\mathrm{RMSE}
=
\sqrt{\frac1N\sum_i(m_i-y_i)^2},
\]

\[
\mathrm{NRMSE}
=
\frac{\mathrm{RMSE}}{y_{\max}-y_{\min}},
\]

\[
\mathrm{bias}
=
\frac1N\sum_i(m_i-y_i),
\]

and uncertainty-weighted chi-square where appropriate:

\[
\chi^2
=
\mathbf r^T\mathbf r.
\]

For images and spectra also report:

```text
integrated radiant-intensity error
peak-location error
spectral-angle error
spatial registration error
band-integrated error
```

## 16. Calibration artifact layout

Recommended repository structure:

```text
calibrations/
  shock_train/
    <calibration_id>/
      calibration.yaml
      covariance.npy
      source_cases.yaml
      split.yaml
      fit_metrics.json
      validation_metrics.json
      residuals.parquet
      plots/
      README.md
  integral_mixing/
  particles/
```

Large or restricted source data should remain outside the package and be
referenced by checksum and acquisition instructions.

## 17. Calibration YAML requirements

```yaml
schema_version: "1.0"
calibration_id: shock-train-example
calibration_version: "1"
model_level: reduced_shock_train
parameters:
  shock.core_spreading_rate:
    value: 0.05
    units: dimensionless
    standard_uncertainty: 0.01
  shock.spacing_coefficient:
    value: 1.306
    units: dimensionless
    standard_uncertainty: 0.05
covariance_file: covariance.npy
calibration_cases: []
validation_cases: []
applicability:
  mach_range: [1.2, 4.5]
  nozzle_pressure_ratio_range: [1.0, 25.0]
  geometry: circular_axisymmetric
  ambient_flow: quiescent
limitations: >-
  Example only. Replace with a documented fit before production use.
```

Illustrative values must be labeled as such and may not become silent defaults.

## 18. Runtime applicability checks

Before applying a calibration, compare current nondimensional inputs with its
applicability metadata. Return warnings or `OUTSIDE_MODEL_VALIDITY` for
extrapolation beyond configured limits.

Applicability variables may include:

```text
exit Mach
fully expanded Mach
nozzle pressure ratio
temperature ratio
density ratio
Reynolds number
exit boundary-layer thickness ratio
ambient Mach
propellant or gas family
```

## 19. Calibration release gate

A calibration may be marked `validated` only when:

- source data and extraction scripts are reproducible;
- calibration and validation cases are disjoint;
- objective, weights, bounds, and transformations are recorded;
- parameter identifiability has been assessed;
- covariance or posterior samples are stored;
- validation metrics are reported by case and observable;
- applicability ranges and model-form limits are explicit;
- the artifact has an immutable ID, version, and checksums;
- regression tests load the calibration and reproduce reference predictions.

## 20. Acceptance gate

The uncertainty framework is complete when:

- every empirical coefficient is registered and versioned;
- numerical, parametric, closure, model-form, and measurement uncertainties are
  distinguishable;
- calibration data are not reused as independent validation;
- local sensitivity and identifiability reports are generated;
- covariance-aware or posterior-aware sampling is supported;
- outputs can include intervals or quantiles plus failed-sample fractions;
- calibration applicability is checked at runtime;
- deterministic and uncertainty-enabled results both preserve provenance;
- no illustrative coefficient is presented as a validated default.
