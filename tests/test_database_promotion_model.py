from __future__ import annotations

from dataclasses import replace

import pytest

from lightning.database.promotion import (
    FileObservation,
    FileObservations,
    PromotionJournal,
    PromotionPhase,
    RestartAction,
    decide_restart,
)


OLD = "a" * 64
NEW = "b" * 64
OTHER = "c" * 64


@pytest.fixture
def journal():
    return PromotionJournal(
        operation_id="promotion-01",
        old_checkpoint_id="checkpoint-old",
        new_checkpoint_id="checkpoint-new",
        old_sha256=OLD,
        new_sha256=NEW,
        live_name="profile.db",
        candidate_name="profile.new",
        previous_name="profile.previous",
        phase=PromotionPhase.STAGED,
    )


def observations(live=OLD, candidate=NEW, previous=OLD):
    return FileObservations(*(
        FileObservation.missing() if digest is None else
        FileObservation.unknown() if digest == "?" else FileObservation.hashed(digest)
        for digest in (live, candidate, previous)
    ))


@pytest.mark.parametrize(
    ("phase", "files", "accepted", "action"),
    [
        (PromotionPhase.PREPARED, observations(), OLD, RestartAction.PROTECT_PREVIOUS),
        (PromotionPhase.PREPARED, observations(previous=None), OLD, RestartAction.PROTECT_PREVIOUS),
        (PromotionPhase.PREVIOUS_PROTECTED, observations(), OLD, RestartAction.RETRY_PUBLISH),
        (PromotionPhase.FILE_PUBLISHED, observations(live=NEW, candidate=None, previous=OLD), OLD,
         RestartAction.VERIFY_AND_COMMIT_AUTHORITY),
        (PromotionPhase.FILE_PUBLISHED, observations(), OLD, RestartAction.RETRY_PUBLISH),
        (PromotionPhase.AUTHORITY_PUBLISHED, observations(live=NEW, candidate=None, previous=OLD), NEW,
         RestartAction.ACTIVATE_NEW),
        (PromotionPhase.ACTIVATED, observations(live=NEW, candidate=None, previous=OLD), NEW,
         RestartAction.ACTIVATE_NEW),
    ],
)
def test_restart_decisions_for_each_durable_boundary(journal, phase, files, accepted, action):
    journal = replace(journal, phase=phase)
    assert decide_restart(journal, files, accepted_sha256=accepted).action is action


@pytest.mark.parametrize(
    ("phase", "files", "accepted"),
    [
        (PromotionPhase.STAGED, observations(live=OTHER), OLD),
        (PromotionPhase.PREPARED, observations(live=OLD, candidate=None, previous=OLD), OLD),
        (PromotionPhase.PREPARED, observations(live=OLD, candidate=NEW, previous=OTHER), OLD),
        (PromotionPhase.PREVIOUS_PROTECTED, observations(live=OLD, candidate=NEW, previous=None), OLD),
        (PromotionPhase.FILE_PUBLISHED, observations(live=OTHER, candidate=NEW, previous=OLD), OLD),
        (PromotionPhase.FILE_PUBLISHED, observations(live=NEW, candidate=None, previous=None), OLD),
        (PromotionPhase.AUTHORITY_PUBLISHED, observations(live=OLD, candidate=NEW, previous=OLD), NEW),
        (PromotionPhase.AUTHORITY_PUBLISHED, observations(live=NEW, candidate=None, previous=None), NEW),
        (PromotionPhase.ACTIVATED, observations(live=NEW, candidate=None, previous=OTHER), NEW),
        (PromotionPhase.PREPARED, observations(live="?", candidate=NEW, previous=OLD), OLD),
    ],
)
def test_missing_or_ambiguous_restart_evidence_blocks(journal, phase, files, accepted):
    journal = replace(journal, phase=phase)
    assert decide_restart(journal, files, accepted_sha256=accepted).action is RestartAction.BLOCK_REPAIR


def test_accepted_authority_is_never_rolled_back_to_old(journal):
    journal = replace(journal, phase=PromotionPhase.AUTHORITY_PUBLISHED)
    result = decide_restart(journal, observations(live=OLD, candidate=NEW, previous=OLD), accepted_sha256=NEW)
    assert result.action is RestartAction.BLOCK_REPAIR


def test_no_journal_requires_live_to_match_accepted_authority():
    assert decide_restart(None, observations(live=OLD), accepted_sha256=OLD).action is RestartAction.KEEP_CURRENT
    assert decide_restart(None, observations(live=NEW), accepted_sha256=OLD).action is RestartAction.BLOCK_REPAIR


def test_authority_missing_or_unreadable_blocks(journal):
    assert decide_restart(journal, observations(), accepted_sha256=None).action is RestartAction.BLOCK_REPAIR
    assert decide_restart(journal, observations(), accepted_sha256=OLD, authority_readable=False).action is RestartAction.BLOCK_REPAIR


def test_journal_round_trip_and_sequential_phase_rules(journal):
    assert PromotionJournal.from_record(journal.to_record()) == journal
    prepared = journal.advance(PromotionPhase.PREPARED)
    assert prepared.phase is PromotionPhase.PREPARED
    with pytest.raises(ValueError, match="one durable step"):
        prepared.advance(PromotionPhase.FILE_PUBLISHED)
    with pytest.raises(ValueError, match="distinct"):
        replace(journal, previous_name="profile.db")


def test_bad_journal_record_is_rejected(journal):
    record = journal.to_record()
    record["unexpected"] = "field"
    with pytest.raises(ValueError, match="fields"):
        PromotionJournal.from_record(record)
    with pytest.raises(ValueError, match="SHA-256"):
        replace(journal, new_sha256="not-a-digest")


def test_file_observation_requires_a_typed_state():
    with pytest.raises(ValueError, match="FileState"):
        FileObservation("missing")
