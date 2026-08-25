from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from scripts.verify_validation_corpus import (
  load_manifest,
  sha256_file,
  verify_archive,
  verify_manifest,
)

ROOT = Path(__file__).resolve().parents[3]


def _write_zip(path: Path, member: str) -> None:
  with ZipFile(path, 'w') as archive:
    archive.writestr(member, 'fixture')
  ####
####


def test_intake_manifest_records_the_two_external_archives() -> None:
  manifest = load_manifest()
  assert manifest['status'] == 'corpus-verified-alignment-pending'
  assert [archive['archive_id'] for archive in manifest['archives']] == [
    'validation-corpus-v8',
    'mvp-validation-alignment-v1',
  ]
  assert all(len(archive['sha256']) == 64 for archive in manifest['archives'])
  assert manifest['archives'][0]['retrieval']['status'] == 'verified'
  assert manifest['archives'][1]['retrieval']['status'] == 'missing'
####


def test_missing_archives_are_not_treated_as_validation_success(tmp_path: Path) -> None:
  manifest = load_manifest()
  checks = verify_manifest(
    manifest,
    corpus_path=tmp_path / 'missing-corpus.zip',
    alignment_path=tmp_path / 'missing-alignment.zip',
  )
  assert tuple(check.status for check in checks) == ('missing', 'missing')
####


def test_matching_archive_digest_and_safe_members_verify(tmp_path: Path) -> None:
  archive_path = tmp_path / 'fixture.zip'
  _write_zip(archive_path, 'raw/observation.csv')
  digest = sha256_file(archive_path)
  check = verify_archive(
    {
      'archive_id': 'fixture',
      'filename': archive_path.name,
      'sha256': digest,
    },
    archive_path,
  )
  assert check.status == 'verified'
  assert check.member_count == 1
  assert check.unsafe_members == ()
####


def test_digest_mismatch_is_reported_before_zip_inspection(tmp_path: Path) -> None:
  archive_path = tmp_path / 'fixture.zip'
  _write_zip(archive_path, 'raw/observation.csv')
  check = verify_archive(
    {
      'archive_id': 'fixture',
      'filename': archive_path.name,
      'sha256': sha256(b'wrong').hexdigest(),
    },
    archive_path,
  )
  assert check.status == 'hash-mismatch'
  assert check.actual_sha256 == sha256_file(archive_path)
####


def test_path_traversal_member_is_rejected_even_with_matching_digest(tmp_path: Path) -> None:
  archive_path = tmp_path / 'unsafe.zip'
  _write_zip(archive_path, '../escape.txt')
  check = verify_archive(
    {
      'archive_id': 'fixture',
      'filename': archive_path.name,
      'sha256': sha256_file(archive_path),
    },
    archive_path,
  )
  assert check.status == 'unsafe-archive'
  assert check.unsafe_members == ('../escape.txt',)
####
