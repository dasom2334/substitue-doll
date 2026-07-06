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
