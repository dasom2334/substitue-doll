"""LLM 폴백 추출기 테스트 — 가짜 LlmClient로 결정적 검증 (합성 더미만, CLAUDE.md §6)."""

from __future__ import annotations

from substitue_doll.core.extraction import ExtractedEntry
from substitue_doll.extract.llm import LlmExtractor


class FakeClient:
    """정해진 응답을 돌려주는 가짜 LlmClient."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class BoomClient:
    def complete(self, prompt: str) -> str:
        raise RuntimeError("provider down")


def test_valid_json_becomes_entries() -> None:
    client = FakeClient(
        '[{"speaker": "나", "ts": "2024/3/1 21:12", "text": "안녕"},'
        ' {"speaker": null, "ts": null, "text": "혼잣말이었다"}]'
    )
    entries = LlmExtractor(client).extract("아무 구간")

    assert entries == [
        ExtractedEntry(
            text="안녕", order=0, source="structured", speaker="나", ts="2024/3/1 21:12"
        ),
        ExtractedEntry(text="혼잣말이었다", order=1, source="plain"),
    ]
    assert "아무 구간" in client.prompts[0]  # 구간 텍스트가 프롬프트에 담김


def test_code_fenced_json_is_stripped() -> None:
    client = FakeClient('```json\n[{"speaker": "나", "ts": null, "text": "안녕"}]\n```')
    entries = LlmExtractor(client).extract("x")
    assert len(entries) == 1
    assert entries[0].speaker == "나"


def test_invalid_json_returns_empty() -> None:
    assert LlmExtractor(FakeClient("이건 JSON이 아님")).extract("x") == []


def test_non_list_json_returns_empty() -> None:
    assert LlmExtractor(FakeClient('{"speaker": "나"}')).extract("x") == []


def test_item_without_text_returns_empty() -> None:
    assert LlmExtractor(FakeClient('[{"speaker": "나", "ts": null}]')).extract("x") == []


def test_client_failure_returns_empty() -> None:
    assert LlmExtractor(BoomClient()).extract("x") == []
