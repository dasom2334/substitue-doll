"""전 구간 통합 테스트 — ingest → index → reply 한 흐름 (합성 더미만, CLAUDE.md §6).

모드1 종합 리뷰(PR #20) 권고: 개별 단위 테스트가 못 잡는 이음새 회귀 방지 —
인입에서 정규화된 화자("나")가 저장→임베딩→검색→프롬프트의 [나] 예시까지
일관되게 흐르는지를 하나의 흐름으로 검증한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from substitue_doll.cli import main
from substitue_doll.core.reply import reply
from substitue_doll.store.sqlite_repository import SqliteRepository
from substitue_doll.store.sqlite_vector_index import SqliteVectorIndex


class KeywordEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "우울" in t else [0.0, 1.0] for t in texts]


class CapturingLlm:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "그랬구나 ㅋㅋ 힘내"


def test_ingest_index_reply_full_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    embedder = KeywordEmbedder()
    monkeypatch.setattr("substitue_doll.cli._make_embedder", lambda: embedder)
    input_path = tmp_path / "input.txt"
    input_path.write_text("[철수] 오늘 너무 우울했어\n[영희] 왜 무슨 일이야", encoding="utf-8")
    db = tmp_path / "store.db"

    # 인입(화자 확인 포함) → 인덱스 — 실제 CLI 경로로
    assert main(["ingest", str(input_path), "--db", str(db), "--me", "철수"]) == 0
    assert main(["index", "--db", str(db)]) == 0

    # 생성 — 저장물이 검색을 거쳐 프롬프트 근거로 흐른다
    llm = CapturingLlm()
    with SqliteRepository(db) as repository, SqliteVectorIndex(db) as index:
        result = reply(
            "우울한 하루였어", llm=llm, embedder=embedder, index=index, repository=repository, k=1
        )

    assert result.draft == "그랬구나 ㅋㅋ 힘내"
    # 이음새 검증: 인입 때 "철수"로 들어온 화자가 '나'로 정규화되어
    # 검색 결과와 프롬프트의 [나] 예시까지 일관되게 유지된다.
    assert result.examples[0].speaker == "나"
    assert result.examples[0].text == "오늘 너무 우울했어"
    assert "- [나] 오늘 너무 우울했어" in llm.prompts[0]
