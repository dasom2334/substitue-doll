"""ingest CLI 스모크 테스트 (합성 더미만 — CLAUDE.md §6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitue_doll.cli import main
from substitue_doll.store.sqlite_repository import SqliteRepository


def _write_input(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "input.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_ingest_with_me_flag(tmp_path: Path) -> None:
    input_path = _write_input(tmp_path, "[철수] 안녕\n[영희] 오랜만")
    db = tmp_path / "store.db"

    exit_code = main(["ingest", str(input_path), "--db", str(db), "--me", "철수"])

    assert exit_code == 0
    with SqliteRepository(db) as repo:
        assert [r.speaker for r in repo.load_all()] == ["나", "영희"]


def test_ingest_confirms_interactively(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = _write_input(tmp_path, "[철수] 안녕\n[영희] 오랜만")
    db = tmp_path / "store.db"
    monkeypatch.setattr("builtins.input", lambda _prompt: "1")  # 후보 1번(철수) 선택

    exit_code = main(["ingest", str(input_path), "--db", str(db)])

    assert exit_code == 0
    with SqliteRepository(db) as repo:
        assert [r.speaker for r in repo.load_all()] == ["나", "영희"]


def test_ingest_unknown_choice_aborts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    input_path = _write_input(tmp_path, "[철수] 안녕\n[영희] 오랜만")
    db = tmp_path / "store.db"
    monkeypatch.setattr("builtins.input", lambda _prompt: "없는라벨")

    exit_code = main(["ingest", str(input_path), "--db", str(db)])

    assert exit_code == 1
    with SqliteRepository(db) as repo:
        assert repo.count() == 0


def test_ingest_invalid_me_flag_fails(tmp_path: Path) -> None:
    # PR #16 리뷰 #1: --me 오타는 조용히 저장되지 않고 실패로 드러난다.
    input_path = _write_input(tmp_path, "[철수] 안녕\n[영희] 오랜만")
    db = tmp_path / "store.db"

    exit_code = main(["ingest", str(input_path), "--db", str(db), "--me", "없는사람"])

    assert exit_code == 1
    with SqliteRepository(db) as repo:
        assert repo.count() == 0


def test_ingest_empty_file_is_success(tmp_path: Path) -> None:
    # PR #16 리뷰 #3: 빈 입력은 오류가 아니다 — "저장할 게 없음"으로 정상 종료.
    input_path = _write_input(tmp_path, "")
    db = tmp_path / "store.db"

    exit_code = main(["ingest", str(input_path), "--db", str(db)])

    assert exit_code == 0
    with SqliteRepository(db) as repo:
        assert repo.count() == 0


def test_ingest_missing_file_fails_cleanly(tmp_path: Path) -> None:
    # PR #16 리뷰 #2: 없는 파일은 트레이스백 없이 메시지 + exit 1.
    exit_code = main(["ingest", str(tmp_path / "없음.txt"), "--db", str(tmp_path / "s.db")])

    assert exit_code == 1
