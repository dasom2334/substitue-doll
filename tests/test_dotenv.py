"""CLI의 .env 로더 테스트 — env 매핑을 주입해 전역(os.environ)을 건드리지 않는다.

PR #20 리뷰 #1: 전역 오염 테스트는 assert 실패 시 정리가 안 돌아 flaky의 원인이 된다.
"""

from __future__ import annotations

from pathlib import Path

from substitue_doll.cli import _load_dotenv


def _load(tmp_path: Path, content: str, env: dict[str, str] | None = None) -> dict[str, str]:
    env_file = tmp_path / ".env"
    env_file.write_text(content, encoding="utf-8")
    result = env if env is not None else {}
    _load_dotenv(env_file, env=result)
    return result


def test_loads_key_values_and_skips_comments(tmp_path: Path) -> None:
    env = _load(tmp_path, "# 주석\nLLM_MODEL=test-model\n\nHF_HUB_OFFLINE=1\n잘못된줄\n")

    assert env == {"LLM_MODEL": "test-model", "HF_HUB_OFFLINE": "1"}


def test_existing_env_wins_over_dotenv(tmp_path: Path) -> None:
    env = _load(tmp_path, "LLM_MODEL=file-model\n", env={"LLM_MODEL": "shell-model"})

    assert env["LLM_MODEL"] == "shell-model"


def test_export_prefix_skipped_not_misparsed(tmp_path: Path) -> None:
    # PR #20 리뷰 #4: "export KEY=V"가 "export KEY"라는 오파싱 키로 등록되면 안 된다.
    env = _load(tmp_path, "export LLM_MODEL=x\n")

    assert env == {}


def test_value_may_contain_equals(tmp_path: Path) -> None:
    env = _load(tmp_path, "KEY=a=b\n")

    assert env["KEY"] == "a=b"


def test_bom_is_stripped(tmp_path: Path) -> None:
    # PR #20 리뷰 #3: UTF-8 BOM으로 저장된 .env의 첫 변수가 조용히 무시되면 안 된다.
    env_file = tmp_path / ".env"
    env_file.write_bytes("﻿LLM_MODEL=bom-model\n".encode())
    env: dict[str, str] = {}
    _load_dotenv(env_file, env=env)

    assert env["LLM_MODEL"] == "bom-model"


def test_unreadable_file_warns_and_continues(tmp_path: Path) -> None:
    # PR #20 리뷰 #2: 비UTF-8 .env가 CLI 전체를 트레이스백으로 죽이면 안 된다.
    env_file = tmp_path / ".env"
    env_file.write_bytes(b"\xff\xfe\x00")
    env: dict[str, str] = {}
    _load_dotenv(env_file, env=env)  # 예외 없이 경고 후 통과

    assert env == {}


def test_missing_file_is_noop(tmp_path: Path) -> None:
    env: dict[str, str] = {}
    _load_dotenv(tmp_path / "없음.env", env=env)

    assert env == {}
