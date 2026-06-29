"""SQLite 저장소 라운드트립·영속성 테스트 (합성 더미만 — CLAUDE.md §6)."""

from __future__ import annotations

from pathlib import Path

from substitue_doll.core.record import RefinedRecord
from substitue_doll.store.sqlite_repository import SqliteRepository


def _sample() -> list[RefinedRecord]:
    """합성 더미 — 실제 인물/대화 아님."""
    return [
        RefinedRecord(
            speaker="나", text="오늘 힘들었어", order=0, source="structured", ts="2024-03-01T21:12"
        ),
        RefinedRecord(
            speaker="상대", text="무슨 일?", order=1, source="structured", ts="2024-03-01T21:13"
        ),
        RefinedRecord(speaker="나", text="그냥 좀 지쳤어", order=2, source="plain"),
    ]


def test_roundtrip_preserves_records_and_order(tmp_path: Path) -> None:
    records = _sample()
    with SqliteRepository(tmp_path / "store.db") as repo:
        repo.add_many(records)

        assert repo.load_all() == records  # 값·순서 동일
        assert repo.count() == len(records)


def test_add_single(tmp_path: Path) -> None:
    rec = RefinedRecord(speaker="나", text="혼잣말", order=0, source="plain")
    with SqliteRepository(tmp_path / "store.db") as repo:
        repo.add(rec)

        assert repo.load_all() == [rec]


def test_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    records = _sample()
    with SqliteRepository(db) as repo:
        repo.add_many(records)

    with SqliteRepository(db) as reopened:  # 같은 파일 다시 열기
        assert reopened.count() == len(records)
        assert reopened.load_all()[0].text == "오늘 힘들었어"


def test_optional_fields_default_none(tmp_path: Path) -> None:
    with SqliteRepository(tmp_path / "store.db") as repo:
        repo.add(RefinedRecord(speaker="나", text="x", order=0, source="plain"))

        loaded = repo.load_all()[0]
        assert loaded.ts is None
        assert loaded.event is None
        assert loaded.emotion is None
