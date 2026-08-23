# Finite Shock Train and Termination Plan

## 1. Purpose

Predict a finite sequence of coherent shock cells rather than asking the user
how many “plumes” to construct.

This phase introduces reduced-order closures for shear-layer growth and
shock-amplitude decay. These closures must be calibrated and must remain
separate from governing gas-dynamic equations.

## 2. Distinct endpoints

The implementation must report separate distances:

```text
shock_train_end_x_m
supersonic_core_end_x_m
thermal_plume_end_x_m
ir_domain_end_x_m
```

They are not interchangeable.

### Shock-train end

Coherent pressure oscillations are no longer resolvable.

### Supersonic-core end

The remaining coherent core is no longer supersonic.

### Thermal-plume end

Temperature and velocity disturbances have mixed toward ambient.

### IR-domain end

Further plume slices contribute negligibly to a selected spectral band and
viewing condition.

## 3. Inputs

```text
FirstCellResult
NozzleExitState
AmbientState
TerminationPolicy
ShockTrainCalibration
max_cells
max_axial_distance_m
```

## 4. Calibration contract

`ShockTrainCalibration` shall contain:

```text
calibration_id
source_description
applicable_mach_range
applicable_pressure_ratio_range
applicable_temperature_ratio_range
mixing_layer_growth_rate
pressure_amplitude_decay_coefficient
cell_spacing_coefficient
finite_shear_layer_spacing_correction
parameter_covariance | None
```

No empirical value may exist only as a module-level number without provenance.

## 5. Reduced-order coherent-core model

## 5.1 Inward mixing-layer growth

Let the inward shear-layer thickness be:

\[
\boxed{
\delta_i(x)=\delta_{i,0}+S_i x.
}
\]

Here \(S_i\) is a closure.

The coherent-core diameter is:

\[
\boxed{
D_c(x)
=
\max\left[D_j-2\delta_i(x),0\right].
}
\]

The geometric core endpoint is:

\[
\boxed{
x_{c,\mathrm{geom}}
=
\frac{D_j-2\delta_{i,0}}{2S_i}
}
\]

when \(S_i>0\).

## 5.2 Local fully expanded state

At the beginning of cell \(n\), use the local core stagnation pressure
\(p_{0,n}\) and ambient pressure:

\[
\boxed{
M_{j,n}
=
\sqrt{
\frac{2}{\gamma-1}
\left[
\left(\frac{p_{0,n}}{p_a}\right)^{(\gamma-1)/\gamma}
-1
\right]
}.
}
\]

If the term inside the square root is nonpositive or
\(M_{j,n}\le1+\epsilon_M\), the coherent supersonic cell system terminates.

## 5.3 Local cell spacing

Use:

\[
\boxed{
L_n
=
C_\lambda
D_c(x_n)
\sqrt{M_{j,n}^2-1}
\,
\Phi_\delta(x_n).
}
\]

Where:

- \(C_\lambda\) begins near the classical circular-jet value \(1.306\).
- \(\Phi_\delta\) is a calibrated finite-shear-layer correction.
- Neither is a universal constant.

A minimal first correction may use:

\[
\Phi_\delta
=
\max
\left[
1-C_\delta\frac{\delta_i}{D_j},
\Phi_{\min}
\right].
\]

The cell boundaries are:

\[
\boxed{
x_{n+1}=x_n+L_n.
}
\]

## 5.4 Pressure oscillation amplitude

Measure the first cell:

\[
A_{p,0}
=
\frac{
p_{\max,0}-p_{\min,0}
}{
2p_a
}.
\]

Use the decay closure:

\[
\boxed{
\frac{dA_p}{dx}
=
-\frac{C_d}{D_c(x)}A_p.
}
\]

The exact integrated form is:

\[
\boxed{
A_p(x)
=
A_{p,0}
\exp
\left[
-C_d
\int_0^x\frac{d\xi}{D_c(\xi)}
\right].
}
\]

For cell stepping, use:

\[
A_{p,n+1}
=
A_{p,n}
\exp
\left[
-C_d
\frac{L_n}
{D_{c,\mathrm{mid},n}}
\right].
\]

## 5.5 Mean pressure residual

For each cell:

\[
\boxed{
r_{\overline p,n}
=
\frac{\overline p_n-p_a}{p_a}.
}
\]

Track both mean mismatch and oscillation amplitude. One zero crossing of
\(p-p_a\) is not termination.

## 5.6 Total-pressure loss

The local core stagnation pressure must account for every modeled shock:

\[
\boxed{
p_{0,n+1}
=
p_{0,n}
\prod_{k\in\text{shocks of cell }n}
\left(
\frac{p_{0,2}}{p_{0,1}}
\right)_k.
}
\]

Do not apply an isentropic total-pressure reconstruction across a shock without
explicitly accounting for entropy loss.

## 6. Cell geometry options

Implement an interface:

```text
ShockCellGeometryModel
  solve_cell(...)
```

### Level A: Resolved first cell

The first cell uses the validated characteristic/free-boundary solver.

### Level B: Reduced-order downstream cells

The initial implementation may scale a nondimensional first-cell template:

\[
\hat x=\frac{x-x_n}{L_n},
\qquad
\hat r=\frac{r}{D_c(x_n)}.
\]

Pressure and wave strength are scaled using \(A_{p,n}\), while thermodynamic
states are recomputed from the local core state.

Every Level B result must carry:

```text
geometry_fidelity = SCALED_REDUCED_ORDER
```

It must not be labeled as a newly solved MOC cell.

### Level C: Re-solved downstream cells

A later implementation may call the first-cell solver for each updated local
state and effective diameter:

```text
geometry_fidelity = RECOMPUTED_PLANAR_MOC
```

## 7. Termination policy

Define:

\[
d_n=\frac{D_c(x_n)}{D_j}.
\]

Terminate physically if any criterion persists as configured.

### Core diameter

\[
\boxed{
d_n\le\epsilon_D.
}
\]

### Core Mach

\[
\boxed{
M_{c,n}\le1+\epsilon_M.
}
\]

### Pressure oscillation

\[
\boxed{
A_{p,n}\le\epsilon_{\mathrm{osc}}
}
\]

for `persistence_cells` consecutive cells.

### Mean pressure plus oscillation

\[
\boxed{
|r_{\overline p,n}|
\le\epsilon_{\mathrm{mean}}
\quad\land\quad
A_{p,n}\le\epsilon_{\mathrm{osc}}.
}
\]

### Model topology

Terminate the current model with a validity status when:

```text
MACH_DISK_REQUIRED
DETACHED_SHOCK_REQUIRED
NOZZLE_SEPARATION_NOT_MODELED
MODEL_VALIDITY_EXCEEDED
```

### Safety limits

```text
x >= max_axial_distance_m  → DOMAIN_LIMIT
n >= max_cells             → MAX_CELL_LIMIT
```

Safety limits are not physical equilibration.

## 8. Iteration algorithm

```text
1. Initialize from FirstCellResult.
2. Record first-cell metrics.
3. Evaluate termination after the completed first cell.
4. Update mixing-layer thickness and coherent-core diameter.
5. Update local total pressure from shock losses.
6. Calculate local fully expanded Mach.
7. Calculate local cell spacing.
8. Calculate pressure-amplitude decay.
9. Generate the next reduced-order or re-solved cell.
10. Record cell metrics and diagnostics.
11. Apply persistence logic.
12. Stop on the first physical, validity, or safety condition.
```

The output cell count is:

\[
\boxed{
N_{\mathrm{cells}}
=
\min\{n:\text{termination policy is satisfied}\}.
}
\]

## 9. Result contracts

### ShockCellMetrics

```text
cell_index
start_x_m
end_x_m
length_m
effective_core_diameter_m
core_mach
mean_pressure_Pa
maximum_pressure_Pa
minimum_pressure_Pa
pressure_oscillation_ratio
mean_pressure_residual
inlet_total_pressure_Pa
outlet_total_pressure_Pa
geometry_fidelity
```

### ShockTrainResult

```text
cells
cell_count
shock_train_end_x_m
supersonic_core_end_x_m
termination_reason
termination_metrics
was_domain_truncated
calibration_id
uncertainty | None
status
diagnostics
```

## 10. Uncertainty propagation

If the calibration supplies a covariance matrix, support Monte Carlo or local
linear propagation for:

```text
cell_count
shock_train_end_x_m
first_cell_length_m
last_pressure_amplitude
```

At minimum, expose sensitivity sweeps for \(S_i\), \(C_d\), and \(C_\lambda\).

A single deterministic value without calibration provenance is not sufficient
for a scientific result.

## 11. Verification tests

1. \(S_i\to0\) prevents geometric core shrinkage.
2. Larger \(S_i\) shortens the coherent-core length.
3. \(C_d\to0\) prevents pressure-amplitude decay.
4. Larger \(C_d\) decreases cell count.
5. \(p_e/p_a\to1\) produces zero or vanishingly weak cells.
6. Each shock decreases \(p_0\).
7. Cell spacing remains positive and finite.
8. Persistence logic does not stop on one isolated weak cell.
9. `DOMAIN_LIMIT` and `MAX_CELL_LIMIT` remain distinguishable from physical
   termination.
10. Reduced-order cells carry the correct fidelity label.

## 12. Validation gate

Calibrate on one dataset and validate against another.

Required comparison quantities:

```text
first-cell length / fully expanded diameter
subsequent mean cell spacing
centerline pressure maxima and minima
pressure-amplitude decay
Mach-disk location if used only as an out-of-scope classifier
potential-core length
```

Do not tune and validate against the same cases without an explicit split.

## 13. Acceptance gate

Phase 2 is complete when:

- cell count is an output, not a required physical input;
- every termination has a reason and metrics;
- physical and safety termination are distinct;
- calibration parameters have provenance;
- sensitivity tests behave monotonically;
- at least one calibration/validation split is documented;
- no downstream cell is mislabeled as resolved MOC when it is template-scaled.
