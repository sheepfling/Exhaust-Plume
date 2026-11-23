"""Lifecycle adapter for exact model-lane local-field sampling."""

from __future__ import annotations

from exhaust_plume.contracts.common_v1 import SnapshotMetadata
from exhaust_plume.contracts.lifecycle_v1 import CapabilityEvaluator
from exhaust_plume.contracts.local_field_v1 import (
  SpatialLocalFieldRequest,
  SpatialLocalFieldResult,
)
from exhaust_plume.contracts.model_lane_visualization_v1 import (
  ModelLaneVisualizationRequest,
  ModelLaneVisualizationResult,
)
from exhaust_plume.contracts.visual_v1 import (
  VisualSampling,
  VisualSectionedTubeRequest,
)
from exhaust_plume.products.model_lane_local_field import (
  evaluate_model_lane_local_field,
)


class ModelLaneLocalFieldEvaluator:
  """Evaluate local-field requests from the exact same snapshot's lane data."""

  def __init__(
    self,
    model_lane_evaluator: CapabilityEvaluator[
      ModelLaneVisualizationRequest,
      ModelLaneVisualizationResult,
    ],
  ) -> None:
    if not callable(getattr(model_lane_evaluator, 'evaluate', None)):
      raise TypeError('model_lane_evaluator must implement evaluate(request, snapshot)')
    self._model_lane_evaluator = model_lane_evaluator

  def evaluate(
    self,
    request: SpatialLocalFieldRequest,
    snapshot: SnapshotMetadata,
  ) -> SpatialLocalFieldResult:
    if not isinstance(request, SpatialLocalFieldRequest):
      raise TypeError('request must be a SpatialLocalFieldRequest')
    if not isinstance(snapshot, SnapshotMetadata):
      raise TypeError('snapshot must be SnapshotMetadata')
    source_request = ModelLaneVisualizationRequest(
      visual_request=VisualSectionedTubeRequest(
        output_frame_id=request.coordinate_frame_id,
        sampling=VisualSampling(maximum_section_count=2),
        include_visual_bounds=False,
      )
    )
    source = self._model_lane_evaluator.evaluate(source_request, snapshot)
    if not isinstance(source, ModelLaneVisualizationResult):
      raise TypeError('model-lane evaluator returned an invalid result type')
    return evaluate_model_lane_local_field(source, request)
