"""답변 초안 엔진(3단계) 테스트 — 가짜 LLM·임베더로 결정적 (합성 더미만, §6)."""

from __future__ import annotations

from pathlib import Path

from substitue_doll.core.record import RefinedRecord
from substitue_doll.core.reply import build_prompt, reply
from substitue_doll.core.retrieval import build_index
from substitue_doll.store.sqlite_repository import SqliteRepository
from substitue_doll.store.sqlite_vector_index import SqliteVectorIndex


class FakeLlm:
    def __init__(self, draft: str = "그랬구나... 오늘 많이 힘들었겠다") -> None:
        self.draft = draft
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"  {self.draft}\n"  # 공백 포함 — strip 검증용


class KeywordEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] if "우울" in t or "힘들" in t else [0.0, 1.0] for t in texts]


def _record(speaker: str, text: str, order: int) -> RefinedRecord:
    return RefinedRecord(speaker=speaker, text=text, order=order, source="structured")


def test_build_prompt_includes_examples_and_situation() -> None:
    examples = [_record("나", "오늘 좀 힘들었어", 0)]
    prompt = build_prompt("친구가 우울하대", examples)

    assert "- [나] 오늘 좀 힘들었어" in prompt
    assert "친구가 우울하대" in prompt


def test_build_prompt_without_examples() -> None:
    assert "(예시 없음)" in build_prompt("상황", [])


def test_build_prompt_placeholder_in_example_not_polluted() -> None:
    # PR #18 리뷰 #1: 예시 텍스트에 플레이스홀더가 있어도 상황으로 치환되면 안 된다.
    examples = [_record("나", "이거 봐 {situation} 라고 쓰면?", 0)]
    prompt = build_prompt("우울해", examples)

    assert "이거 봐 {situation} 라고 쓰면?" in prompt  # 리터럴 유지
    assert "이거 봐 우울해 라고" not in prompt


def test_reply_retrieves_context_and_strips_draft(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    embedder = KeywordEmbedder()
    with SqliteRepository(db) as repo, SqliteVectorIndex(db) as index:
        repo.add_many([_record("나", "오늘 우울했어", 0), _record("나", "여행 가고 싶다", 1)])
        build_index(repository=repo, embedder=embedder, index=index)

        llm = FakeLlm()
        result = reply(
            "요즘 너무 힘들어", llm=llm, embedder=embedder, index=index, repository=repo, k=1
        )

    assert result.draft == "그랬구나... 오늘 많이 힘들었겠다"  # strip 확인
    assert [e.text for e in result.examples] == ["오늘 우울했어"]  # 의미 축 일치 근거
    assert "오늘 우울했어" in llm.prompts[0]  # 근거가 프롬프트에 들어감
