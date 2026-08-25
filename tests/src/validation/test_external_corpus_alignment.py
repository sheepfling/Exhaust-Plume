from __future__ import annotations

from scripts.validate_external_corpus_alignment import reconcile_operator_ids


def test_operator_reconciliation_does_not_guess_namespace_aliases() -> None:
  report = reconcile_operator_ids(
    (
      {'measurement_operator_id': 'operator.extract.feature'},
      {'measurement_operator_id': 'operator.sensor.band'},
      {'measurement_operator_id': None},
    ),
    ('op.visual.feature-extractor', 'op.sensor.bandpass-detector'),
  )
  assert report['exact_namespace_match'] is False
  assert report['crosswalk_status'] == 'pending'
  assert report['external_count'] == 2
  assert report['committed_count'] == 2
  assert report['external_only'] == ['operator.extract.feature', 'operator.sensor.band']
  assert report['committed_only'] == [
    'op.sensor.bandpass-detector',
    'op.visual.feature-extractor',
  ]
