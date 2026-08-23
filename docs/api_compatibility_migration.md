# Canonical provider API migration

The v1 provider lifecycle is now owned by `exhaust_plume.api.v1` and the
provider-specific implementations under `exhaust_plume.providers`.

New code should use the canonical typed lifecycle:

```python
from exhaust_plume.api import v1
from exhaust_plume.providers import PrescribedVisualProvider

provider = PrescribedVisualProvider()
session = provider.create_session(definition=definition)
snapshot = session.create_snapshot(
    time_s=0.0,
    source_pose=source_pose,
    dynamic_state={},
    ambient_state={},
)
result = snapshot.evaluate(
    v1.VISUAL_SECTIONED_TUBE_V1,
    v1.VisualSectionedTubeRequest(
        output_frame_id="source-local",
        sampling=v1.VisualSampling(maximum_section_count=32),
    ),
)
```

The shipped alpha surface remains available for 0.1.x consumers:

```python
from exhaust_plume.api import PrescribedSectionedTubeProvider, ProductRequest

session = PrescribedSectionedTubeProvider(...).create_session()
legacy_snapshot = session.snapshot(SnapshotRequest(time_s=0.0))
legacy_result = legacy_snapshot.get_product(ProductRequest(...))
```

`exhaust_plume.api.prescribed.PrescribedSectionedTubeProvider` is now a
compatibility shell. It delegates lifecycle validation and visual evaluation
to `exhaust_plume.providers.PrescribedVisualProvider`, then preserves the
legacy UUID/envelope/content-hash result for the old caller. This keeps the
old import and exception behavior stable while preventing a second active
visual-provider implementation.

The migration schedule is:

- `0.1.x`: old imports and legacy envelopes remain supported; no warning is
  emitted when behavior is unchanged.
- `0.1.x`: targeted compatibility warnings identify exact replacements where
  terminology or behavior changes, such as `num_plumes` → `max_cells`.
- `0.2.0` or later: legacy provider shells may be removed only after a new
  major-version decision and a published migration review.

The canonical facade aliases the shipped wire models, so this migration does
not change schema fields, units, frames, capability IDs, or major versions.
