"""하이브리드 추출기 테스트 — 폴백 트리거·병합·안전 방향 (합성 더미만, CLAUDE.md §6)."""

from __future__ import annotations

from substitue_doll.core.extraction import ExtractedEntry
from substitue_doll.extract.hybrid import HybridExtractor


class FakeFallback:
    """호출 기록을 남기고 정해진 결과를 돌려주는 가짜 폴백 추출기."""

    def __init__(self, result: list[ExtractedEntry] | None = None) -> None:
        self.result = result or []
        self.calls: list[str] = []

    def extract(self, text: str) -> list[ExtractedEntry]:
        self.calls.append(text)
        return list(self.result)


# 룰이 못 뜯는 파이프 구분 포맷(날짜 신호는 있음) — 합성 더미.
PIPE_SEGMENT = "2024/3/1 21:12 | 나 | 안녕\n2024/3/1 21:13 | 상대 | 오랜만"


def test_rule_parseable_segment_skips_fallback() -> None:
    fallback = FakeFallback()
    entries = HybridExtractor(fallback).extract("[나] 2024.3.1 오후 9:12 오늘 힘들었어")

    assert fallback.calls == []  # 커버리지 충분 → LLM 안 부름
    assert entries[0].speaker == "나"


def test_plain_text_without_signal_skips_fallback() -> None:
    fallback = FakeFallback()
    entries = HybridExtractor(fallback).extract("그냥 오늘 좀 지쳤어\n들어줄 사람이 없네")

    assert fallback.calls == []  # 구조 신호 없음 → 평문, LLM 안 부름
    assert entries == [
        ExtractedEntry(text="그냥 오늘 좀 지쳤어\n들어줄 사람이 없네", order=0, source="plain")
    ]


def test_low_coverage_with_signal_triggers_fallback() -> None:
    fallback = FakeFallback(
        [
            ExtractedEntry(
                text="안녕", order=0, source="structured", speaker="나", ts="2024/3/1 21:12"
            ),
            ExtractedEntry(
                text="오랜만", order=1, source="structured", speaker="상대", ts="2024/3/1 21:13"
            ),
        ]
    )
    entries = HybridExtractor(fallback).extract(PIPE_SEGMENT)

    assert fallback.calls == [PIPE_SEGMENT]  # 해당 구간만 폴백
    assert [e.speaker for e in entries] == ["나", "상대"]


def test_fallback_failure_keeps_rule_result() -> None:
    fallback = FakeFallback([])  # 폴백 실패(빈 결과)
    entries = HybridExtractor(fallback).extract(PIPE_SEGMENT)

    assert len(fallback.calls) == 1
    assert entries == [ExtractedEntry(text=PIPE_SEGMENT, order=0, source="plain")]  # 룰 결과 유지


def test_mixed_segments_only_uncertain_goes_to_llm_and_order_is_global() -> None:
    fallback = FakeFallback(
        [ExtractedEntry(text="안녕", order=0, source="structured", speaker="나", ts=None)]
    )
    text = "오늘 우울해서 옛날 대화 다시 봤어.\n\n" + PIPE_SEGMENT + "\n\n[나] 고마웠어"
    entries = HybridExtractor(fallback).extract(text)

    assert fallback.calls == [PIPE_SEGMENT]  # 자신 없는 구간만
    assert [e.order for e in entries] == list(range(len(entries)))  # 전역 order 연속
    assert entries[0].source == "plain"
    assert entries[1] == ExtractedEntry(text="안녕", order=1, source="structured", speaker="나")
    assert entries[2].speaker == "나"  # 대괄호 구간은 룰이 처리
