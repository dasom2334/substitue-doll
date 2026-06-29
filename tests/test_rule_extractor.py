"""룰 추출기 테스트 (합성 더미만 — CLAUDE.md §6)."""

from __future__ import annotations

from substitue_doll.core.extraction import ExtractedEntry
from substitue_doll.extract.rule import RuleExtractor

# 평문 + 서로 다른 두 구조 포맷이 섞인 입력 (Issue #4 §1 예시).
MIXED = """오늘 우울해서 옛날 대화 다시 봤어.

[나] 2024.3.1 오후 9:12 오늘 힘들었어
[상대] 2024.3.1 오후 9:13 무슨 일?

2024-03-02 21:00, 나 : 또 생각났어

이거 보니까 더 그립다."""


def test_mixed_input_segments_and_extracts() -> None:
    entries = RuleExtractor().extract(MIXED)

    assert entries == [
        ExtractedEntry(text="오늘 우울해서 옛날 대화 다시 봤어.", order=0, source="plain"),
        ExtractedEntry(
            text="오늘 힘들었어",
            order=1,
            source="structured",
            speaker="나",
            ts="2024.3.1 오후 9:12",
        ),
        ExtractedEntry(
            text="무슨 일?", order=2, source="structured", speaker="상대", ts="2024.3.1 오후 9:13"
        ),
        ExtractedEntry(
            text="또 생각났어", order=3, source="structured", speaker="나", ts="2024-03-02 21:00"
        ),
        ExtractedEntry(text="이거 보니까 더 그립다.", order=4, source="plain"),
    ]


def test_pure_plaintext_is_one_plain_entry() -> None:
    entries = RuleExtractor().extract("그냥 오늘 좀 지쳤어\n들어줄 사람이 없네")

    assert entries == [
        ExtractedEntry(text="그냥 오늘 좀 지쳤어\n들어줄 사람이 없네", order=0, source="plain"),
    ]


def test_simple_colon_format() -> None:
    entries = RuleExtractor().extract("나: 안녕\n상대 : 오랜만이야")

    assert entries == [
        ExtractedEntry(text="안녕", order=0, source="structured", speaker="나"),
        ExtractedEntry(text="오랜만이야", order=1, source="structured", speaker="상대"),
    ]


def test_empty_input_yields_nothing() -> None:
    assert RuleExtractor().extract("") == []
    assert RuleExtractor().extract("\n\n   \n") == []


def test_consecutive_plain_lines_grouped() -> None:
    entries = RuleExtractor().extract("첫 줄\n둘째 줄")
    assert len(entries) == 1
    assert entries[0].source == "plain"
    assert entries[0].text == "첫 줄\n둘째 줄"


def test_url_not_mistaken_as_structured() -> None:
    # "http://..."가 화자 라벨로 오인되면 안 된다(speaker="http").
    entries = RuleExtractor().extract("http://example.com 봐봐")
    assert entries == [ExtractedEntry(text="http://example.com 봐봐", order=0, source="plain")]


def test_colon_sentence_not_mistaken_as_structured() -> None:
    # 공백이 든 평문 문장은 화자 라벨로 오인되면 안 된다.
    entries = RuleExtractor().extract("오늘은 정말: 힘든 하루였어")
    assert entries == [ExtractedEntry(text="오늘은 정말: 힘든 하루였어", order=0, source="plain")]


def test_long_whitespace_line_no_redos() -> None:
    # ReDoS 회귀 방지: 긴 공백 줄도 선형 시간에 처리되고 평문으로 분류된다.
    import time

    line = "2024.3.1" + " " * 50_000 + "끝"
    start = time.perf_counter()
    entries = RuleExtractor().extract(line)
    elapsed = time.perf_counter() - start

    assert elapsed < 1.0  # 고치기 전엔 수 초; 고친 뒤 ~수 ms
    assert len(entries) == 1
    assert entries[0].source == "plain"
