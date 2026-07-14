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


KAKAO_LIKE = """--------------- 2024년 3월 1일 금요일 ---------------
[민수] [오후 9:12] 오늘 힘들었어
오후 9:15, 지영 : 헐 왜"""


def test_date_separator_state_attaches_date(  # 사용자 리뷰 #2·#3
) -> None:
    entries = RuleExtractor().extract(KAKAO_LIKE)

    assert len(entries) == 2  # 구분선은 발화가 아니다
    assert entries[0].speaker == "민수"
    assert entries[0].ts == "2024년 3월 1일 오후 9:12"  # 구분선 날짜가 시각에 보충됨
    assert entries[0].text == "오늘 힘들었어"  # [오후 9:12]가 본문에 남지 않음
    assert entries[1].speaker == "지영"
    assert entries[1].ts == "2024년 3월 1일 오후 9:15"


def test_bare_date_line_preserved_as_plain() -> None:
    # PR #22 리뷰 #1: 장식 없는 순수 날짜 줄은 감정 앵커 회상일 수 있다 — 소실 금지(§4).
    entries = RuleExtractor().extract("오늘 기분 이상해\n2024년 3월 1일\n그날 생각나서")

    assert len(entries) == 1
    assert entries[0].source == "plain"
    assert "2024년 3월 1일" in entries[0].text  # 날짜 줄이 보존된다

    alone = RuleExtractor().extract("2024. 5. 1.")
    assert [e.text for e in alone] == ["2024. 5. 1."]


def test_weekday_date_line_is_separator() -> None:
    # 장식 없어도 요일이 붙으면 구분선(메신저 내보내기 형태) — 의도된 트레이드오프.
    entries = RuleExtractor().extract("2024년 3월 1일 금요일\n[민수] [오후 9:12] 안녕")

    assert len(entries) == 1
    assert entries[0].ts == "2024년 3월 1일 오후 9:12"


def test_time_comma_plain_sentence_not_structured() -> None:
    # PR #22 리뷰 #2: 시각+콤마 뒤 공백 든 어구는 화자가 아니다.
    entries = RuleExtractor().extract("오후 3:00, 근데 말이야: 밥 먹자")

    assert entries == [
        ExtractedEntry(text="오후 3:00, 근데 말이야: 밥 먹자", order=0, source="plain")
    ]


def test_dotted_date_with_spaces_parses() -> None:  # 사용자 리뷰 #2 (맥 내보내기류)
    entries = RuleExtractor().extract("2024. 5. 1. 오후 3:21, 민수 : 안녕")

    assert entries[0].speaker == "민수"
    assert entries[0].ts == "2024. 5. 1. 오후 3:21"
    assert entries[0].text == "안녕"


def test_simple_colon_leading_ts_extracted() -> None:  # 사용자 리뷰 #6
    entries = RuleExtractor().extract("민수: 2024.3.1 오후 9:12 안녕")

    assert entries[0].ts == "2024.3.1 오후 9:12"  # 날짜가 본문에 묻히지 않는다
    assert entries[0].text == "안녕"


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
