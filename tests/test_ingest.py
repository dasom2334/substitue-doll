"""인입 파이프라인(엔진) 테스트 — 실제 룰 추출기+SQLite로 E2E (합성 더미만, §6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitue_doll.core.ingest import ingest
from substitue_doll.extract.rule import RuleExtractor
from substitue_doll.refine.stub import refine
from substitue_doll.store.sqlite_repository import SqliteRepository

MIXED = """오늘 우울해서 옛날 대화 다시 봤어.

[나] 2024.3.1 오후 9:12 오늘 힘들었어
[상대] 2024.3.1 오후 9:13 무슨 일?"""

AMBIGUOUS = "[철수] 안녕\n[영희] 오랜만"


def _ingest(text: str, db: Path, me: str | None = None) -> tuple[int, bool]:
    with SqliteRepository(db) as repo:
        result = ingest(text, extractor=RuleExtractor(), repository=repo, refine=refine, me=me)
        return result.stored, result.resolution.needs_confirmation


def test_mixed_input_stored_end_to_end(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    stored, needs_confirmation = _ingest(MIXED, db)

    assert (stored, needs_confirmation) == (3, False)
    with SqliteRepository(db) as repo:
        records = repo.load_all()
    assert [r.speaker for r in records] == ["나", "나", "상대"]  # 평문→나, 마커→나 정규화
    assert records[0].source == "plain"
    assert records[1].ts == "2024.3.1 오후 9:12"
    assert [r.order for r in records] == [0, 1, 2]


def test_ambiguous_without_me_stores_nothing(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    stored, needs_confirmation = _ingest(AMBIGUOUS, db)

    assert (stored, needs_confirmation) == (0, True)
    with SqliteRepository(db) as repo:
        assert repo.count() == 0  # 확인 전엔 아무것도 저장하지 않는다


def test_ambiguous_with_me_normalizes_label(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    stored, _ = _ingest(AMBIGUOUS, db, me="철수")

    assert stored == 2
    with SqliteRepository(db) as repo:
        records = repo.load_all()
    assert [r.speaker for r in records] == ["나", "영희"]  # 확인된 라벨은 '나'로 정규화


def test_me_not_in_candidates_raises(tmp_path: Path) -> None:
    # PR #16 리뷰 #1: me 오타가 조용히 통과해 '나' 발화 0건 데이터를 만들면 안 된다.
    db = tmp_path / "store.db"
    with SqliteRepository(db) as repo:
        with pytest.raises(ValueError, match="화자 후보에 없다"):
            ingest(
                AMBIGUOUS, extractor=RuleExtractor(), repository=repo, refine=refine, me="없는사람"
            )
        assert repo.count() == 0  # 아무것도 저장되지 않음


def test_me_ignored_when_no_speakers(tmp_path: Path) -> None:
    # 화자가 아예 없는 평문 입력에서는 me가 무의미하므로 무시하고 진행한다.
    db = tmp_path / "store.db"
    stored, needs_confirmation = _ingest("그냥 힘든 하루였다", db, me="철수")

    assert (stored, needs_confirmation) == (1, False)
    with SqliteRepository(db) as repo:
        assert repo.load_all()[0].speaker == "나"  # 평문은 본인 서술
