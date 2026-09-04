from __future__ import annotations

import csv

from scripts.validate_external_corpus_alignment import (
  REVIEWED_SEMANTIC_CROSSWALKS,
  reconcile_operator_ids,
  COMMITTED_OPERATOR_REGISTRY,
)


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
  assert report['reviewed_semantic_crosswalks'][0]['external_operator_id'] == (
    'operator.sample.canonical_jet_probe_lines'
  )
  assert report['reviewed_semantic_crosswalks'][0]['internal_operator_ids'] == [
    'op.field.profile-probe'
  ]
####


def test_primary_gate_crosswalk_is_explicit_but_does_not_reconcile_namespace() -> None:
  by_external_id = {
    entry['external_operator_id']: entry
    for entry in REVIEWED_SEMANTIC_CROSSWALKS
  }
  assert by_external_id['operator.extract.sectioned_tube_mach_disk_position'][
    'internal_operator_ids'
  ] == ['op.visual.feature-extractor']
  assert by_external_id['operator.spectrum.peak_normalize_after_sensor_sampling'][
    'mapping_kind'
  ] == 'ordered-pipeline'
  assert by_external_id['operator.image.integrate_alsi_band_and_area'][
    'review_status'
  ] == 'no-safe-equivalent-reviewed'
  assert by_external_id['operator.image.integrate_alsi_band_and_area'][
    'internal_operator_ids'
  ] == []

  report = reconcile_operator_ids(
    (
      {'measurement_operator_id': 'operator.extract.sectioned_tube_mach_disk_position'},
      {'measurement_operator_id': 'operator.image.integrate_alsi_band_and_area'},
      {'measurement_operator_id': 'operator.unreviewed'},
    ),
    (
      row['operator_id']
      for row in csv.DictReader(COMMITTED_OPERATOR_REGISTRY.open(newline='', encoding='utf-8'))
    ),
  )
  assert report['crosswalk_status'] == 'pending'
  assert report['semantic_crosswalk']['status'] == 'valid'
  assert report['scoped_reviewed_external_only'] == [
    'operator.extract.sectioned_tube_mach_disk_position',
    'operator.image.integrate_alsi_band_and_area',
  ]
  assert report['unreviewed_external_only'] == ['operator.unreviewed']
####


def test_complete_scoped_crosswalk_covers_the_external_namespace_without_exact_aliasing() -> None:
  external_alignment = tuple(
    {'measurement_operator_id': entry['external_operator_id']}
    for entry in REVIEWED_SEMANTIC_CROSSWALKS
  )
  registry_ids = (
    row['operator_id']
    for row in csv.DictReader(COMMITTED_OPERATOR_REGISTRY.open(newline='', encoding='utf-8'))
  )

  report = reconcile_operator_ids(external_alignment, registry_ids)

  assert report['external_count'] == 35
  assert report['semantic_crosswalk_status'] == 'complete-scoped'
  assert report['semantic_crosswalk']['status'] == 'valid'
  assert report['unreviewed_external_only'] == []
  assert report['exact_namespace_match'] is False
####
