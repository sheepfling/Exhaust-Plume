from __future__ import annotations

import json
from pathlib import Path

from exhaust_plume.providers import SignatureTableDefinition, StraightVisualDefinition


ROOT = Path(__file__).resolve().parents[3]


def test_provider_definition_fixtures_construct_product_inputs() -> None:
  straight_payload = json.loads(
    (ROOT / 'fixtures/providers/straight_visual_definition_v1.json').read_text(encoding='utf-8')
  )
  table_payload = json.loads(
    (ROOT / 'fixtures/providers/signature_table_definition_v1.json').read_text(encoding='utf-8')
  )
  straight = StraightVisualDefinition(**straight_payload)
  table = SignatureTableDefinition(**table_payload)
  assert straight.base_section_count == 9
  assert table.direction_cosine_nodes == (-0.5, 0.0, 0.5)
