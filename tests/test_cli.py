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


class _KeywordEmbedder:
    """테스트용 임베더 — '우울' 포함 여부를 축으로 쓰는 결정적 2차원 벡터."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "우울" in t else [0.0, 1.0] for t in texts]


def test_index_and_search_commands(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 무거운 실모델 대신 팩토리를 가짜로 바꿔 CLI 경로만 검증 (2단계).
    monkeypatch.setattr("substitue_doll.cli._make_embedder", lambda: _KeywordEmbedder())
    input_path = _write_input(tmp_path, "[나] 오늘 우울해\n[상대] 여행 가자")
    db = tmp_path / "store.db"
    assert main(["ingest", str(input_path), "--db", str(db)]) == 0

    assert main(["index", "--db", str(db)]) == 0
    assert main(["search", "우울한 하루", "--db", str(db), "-k", "1"]) == 0


def test_search_empty_db_is_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("substitue_doll.cli._make_embedder", lambda: _KeywordEmbedder())
    exit_code = main(["search", "아무거나", "--db", str(tmp_path / "빈.db")])

    assert exit_code == 0  # 결과 없음은 오류가 아니다
