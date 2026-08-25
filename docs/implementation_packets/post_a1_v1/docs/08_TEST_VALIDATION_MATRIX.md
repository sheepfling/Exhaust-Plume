# Test and Validation Matrix

## Repository gate for every PR

```text
python -m ruff check .
python -m pyright
python -m pytest
python -m build
install built wheel in a fresh environment
run tests/installed_smoke.py outside the checkout
```

CI runs Python 3.10, 3.11, 3.12, and 3.13.

## API gate

- strict extra-field rejection;
- finite numeric enforcement;
- frame/quaternion validation;
- deterministic canonical hashes;
- capability/result identity matching;
- static/dynamic time semantics;
- immutable concurrent reads;
- unsupported capability errors;
- valid partial-batch placeholders and masks;
- compatibility adapter round trips.

## Straight provider gate

- exact free-jet mass/radius/velocity/temperature/tracer histories;
- momentum and enthalpy closure;
- pressure-match rejection;
- explicit domain termination;
- coordinate transformation invariance.

## Washed provider gate

- zero-wash straight equivalence;
- uniform-crossflow exact constant-entrainment oracle;
- thrust scaling and wake contraction;
- torque/angular-momentum consistency;
- swirl reversal mirror symmetry;
- mass, vector momentum, energy, and tracer residuals;
- frame orthonormality and continuity;
- curvature/slenderness diagnostics;
- deterministic product serialization;
- consumer provider interchange.

## Sidecar gate

- health and schema endpoints;
- loopback-only bind;
- malformed JSON and oversize rejection;
- gzip and uncompressed parity;
- create/evaluate/delete lifecycle;
- exact canonical round trip;
- structured error parity with in-process API.

## Optical gate

- slab;
- chord length;
- layer ordering;
- thin/thick limits;
- miss ray;
- spatial/spectral refinement;
- ray-to-signature quadrature consistency.

## Validation terminology

- `VERIFIED`: equations/contracts tested against analytical or internal invariants.
- `CALIBRATED`: coefficients fitted to declared data.
- `VALIDATED`: held-out external evidence passes declared criteria.

Do not promote W1 beyond `EXPLORATORY_ANALYTICAL + VERIFIED` before calibration and held-out validation.
