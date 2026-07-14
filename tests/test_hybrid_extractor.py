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


def test_dated_prose_does_not_trigger_fallback() -> None:
    # PR #13 리뷰 #1 회귀 방지: 날짜가 문장 속에 있는 평문 회고는 LLM을 부르면 안 된다.
    fallback = FakeFallback()
    entries = HybridExtractor(fallback).extract("2024.3.1 그날 정말 힘들었다\n그래서 밤새 울었다")

    assert fallback.calls == []
    assert entries[0].source == "plain"


def test_english_log_format_triggers_fallback() -> None:
    # 다국어: 영어권 로그(AM/PM)도 구조 신호로 잡혀 폴백으로 간다(파싱은 LLM 몫).
    fallback = FakeFallback(
        [ExtractedEntry(text="hi", order=0, source="structured", speaker="John", ts=None)]
    )
    segment = "2024-03-01 9:12 PM | John | hi"
    entries = HybridExtractor(fallback).extract(segment)

    assert fallback.calls == [segment]
    assert entries[0].speaker == "John"


def test_time_only_log_triggers_fallback() -> None:
    # 사용자 리뷰 #4 "이중 사각지대": 날짜 없이 시각만 반복되는 로그가
    # 룰도 못 뜯고 폴백 신호에도 안 걸리면 안 된다 — 시각 2줄 반복 = 신호.
    fallback = FakeFallback(
        [ExtractedEntry(text="안녕", order=0, source="structured", speaker="민수", ts="9:12")]
    )
    segment = "9:12 민수 안녕\n9:13 지영 반가워"
    entries = HybridExtractor(fallback).extract(segment)

    assert fallback.calls == [segment]  # 안전망(LLM) 작동
    assert entries[0].speaker == "민수"


def test_single_time_in_prose_no_fallback() -> None:
    # 평문 속 시각 1회는 여전히 신호가 아니다 — LLM 비용 방지 유지.
    fallback = FakeFallback()
    entries = HybridExtractor(fallback).extract("우리 오후 3:00에 만나기로 했다\n기대된다")

    assert fallback.calls == []
    assert entries[0].source == "plain"


def test_time_repeated_prose_may_call_fallback_but_keeps_plain() -> None:
    # PR #22 리뷰 #3(의도된 트레이드오프): 시각 2회 이상 회고 평문은 폴백을 부를 수 있다
    # (사각지대 해소의 비용). 단 폴백이 빈 결과면 룰의 평문 결과가 유지돼 손상은 없다.
    fallback = FakeFallback()  # 빈 결과 = 폴백 실패/판단 보류
    entries = HybridExtractor(fallback).extract("3:00에 만났고\n5:30에 헤어졌지\n좋은 하루였다")

    assert len(fallback.calls) == 1  # LLM 비용 1회 — 허용된 오탐
    assert all(e.source == "plain" for e in entries)  # 데이터 손상 없음


def test_fully_parsed_kakao_segment_skips_fallback() -> None:
    # 날짜 구분선은 커버리지 분모에서 제외 — 전부 파싱된 구간이 구분선 때문에
    # 임계 미달로 보여 불필요한 LLM을 부르면 안 된다.
    fallback = FakeFallback()
    segment = (
        "--------------- 2024년 3월 1일 금요일 ---------------\n"
        "[민수] [오후 9:12] 안녕\n"
        "오후 9:13, 지영 : 반가워"
    )
    entries = HybridExtractor(fallback).extract(segment)

    assert fallback.calls == []
    assert [e.speaker for e in entries] == ["민수", "지영"]


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
