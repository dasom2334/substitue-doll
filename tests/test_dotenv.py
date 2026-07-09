"""CLI의 .env 로더 테스트 — env.example이 실제로 동작하게 하는 부품."""

from __future__ import annotations

from pathlib import Path

import pytest

from substitue_doll.cli import _load_dotenv


def test_loads_key_values_and_skips_comments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# 주석\nLLM_MODEL=test-model\n\nHF_HUB_OFFLINE=1\n잘못된줄\n", encoding="utf-8"
    )
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)

    _load_dotenv(env_file)

    import os

    assert os.environ.get("LLM_MODEL") == "test-model"
    assert os.environ.get("HF_HUB_OFFLINE") == "1"
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)


def test_existing_env_wins_over_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 실제 환경변수(export)가 .env보다 우선한다.
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=file-model\n", encoding="utf-8")
    monkeypatch.setenv("LLM_MODEL", "shell-model")

    _load_dotenv(env_file)

    import os

    assert os.environ["LLM_MODEL"] == "shell-model"


def test_missing_file_is_noop(tmp_path: Path) -> None:
    _load_dotenv(tmp_path / "없음.env")  # 예외 없이 조용히 통과
