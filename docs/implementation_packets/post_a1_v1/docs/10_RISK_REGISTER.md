# Risk Register

| Risk | Consequence | Control | Gate |
|---|---|---|---|
| Two public contract authorities | Third-party consumers bind to incompatible semantics | API-008 authority decision, adapters, schema-only canonical generation | A1-010 |
| Duplicate entrainment classes | Different numerical behavior under same name | Consolidate implementation and retain tested alias | A1-030 |
| Visual radius overclaims physical support | Downstream ray/engineering errors | Explicit support definition; top-hat boundary for W1 | A1-040 |
| Handoff taken at nozzle exit instead of pressure-equalized section | Momentum/energy composition error | Dedicated downstream handoff packet with pressure thrust | A1-070 |
| Sidecar serializes compatibility DTOs | Wire contract forks | Sidecar depends on API-008 and canonical schemas only | A1-060 |
| Crossflow trajectory fits hide scalar errors | False confidence in IR field | Calibrate trajectory and scalar/temperature dilution separately | A1-090 |
| Exact-main CI not recorded | Release confidence inferred from stale branches | A1-000 rerun and archive evidence | A1-000 |
| Root export cleanup breaks a1 users | Avoidable migration cost | Compatibility aliases, deprecation tests, migration guide | A1-010 |
| Ray contract advertised before physics | Consumers assume radiometric truth | Capability advertisement gate | A1-080 |
| Scope creep in provider PR | Hard-to-review mixed physics/API changes | One bounded packet per PR | all |
