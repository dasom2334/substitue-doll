"""하이브리드 추출기 — 룰 우선, 자신 없는 구간만 LLM 폴백 (1B-ii, Issue #12 PR-1).

폴백 트리거(Issue #4 §9-9): 구간에 **구조 신호**(날짜 타임스탬프·대괄호 라벨)가 있는데
룰의 줄 커버리지(구조로 파싱된 줄 비율)가 임계 미만이면 폴백 추출기를 호출한다.
- 신호가 없으면(순수 평문) 폴백하지 않는다 — 불필요한 LLM 비용 방지.
- 폴백이 빈 결과를 주면(실패) 룰 결과를 유지한다 — 안전 방향.

순수 계층: I/O 없음, 폴백 추출기는 포트(Extractor)로 주입받는다 (CLAUDE.md §8).
"""

from __future__ import annotations

import re
from dataclasses import replace

from substitue_doll.core.extraction import ExtractedEntry, Extractor
from substitue_doll.extract.rule import (
    DATE_PATTERN,
    DATE_SEPARATOR,
    TIME_PATTERN,
    RuleExtractor,
    is_date_separator,
)

# 구조 신호는 "구간이 로그 형태인가"로 판정한다(패턴은 rule.py와 공유 — 이중 관리 방지):
# ① 줄머리 대괄호 라벨, 또는 줄머리 날짜가 시각/구분자(| ,)와 동반 (줄 단위)
# ② 날짜 구분선 존재, 또는 **시각 패턴이 2줄 이상 반복** (구간 단위 — 날짜 없이 시각만
#    찍히는 실제 메신저 내보내기의 사각지대 해소; 사용자 리뷰 #4 "이중 사각지대")
# 날짜/시각이 문장 속에 한 번 있는 평문 회고는 여전히 신호가 아니다 — LLM 비용 방지
# (PR #13 리뷰 #1). 낯선 포맷의 실제 파싱은 폴백(LLM)의 몫이다.
_SIGNAL = re.compile(rf"^\[[^\]]{{1,30}}\]|^(?:{DATE_PATTERN})(?:[ ]+{TIME_PATTERN}|[ ]*[|,])")
_TIME_HINT = re.compile(TIME_PATTERN)


def _split_segments(text: str) -> list[str]:
    """빈 줄 기준으로 구간을 나눈다(룰 추출기의 평문 flush 경계와 동일)."""
    segments: list[list[str]] = [[]]
    for line in text.splitlines():
        if line.strip():
            segments[-1].append(line)
        elif segments[-1]:
            segments.append([])
    return ["\n".join(seg) for seg in segments if seg]


class HybridExtractor:
    """룰 → (커버리지 임계 미달 구간만) LLM 폴백 추출기."""

    def __init__(
        self,
        fallback: Extractor,
        rule: RuleExtractor | None = None,
        coverage_threshold: float = 0.8,
    ) -> None:
        self._rule = rule if rule is not None else RuleExtractor()
        self._fallback = fallback
        self._threshold = coverage_threshold

    def extract(self, text: str) -> list[ExtractedEntry]:
        merged: list[ExtractedEntry] = []
        for segment in _split_segments(text):
            entries = self._rule.extract(segment)
            if self._needs_fallback(segment, entries):
                fallback_entries = self._fallback.extract(segment)
                if fallback_entries:
                    entries = fallback_entries
            for entry in entries:
                merged.append(replace(entry, order=len(merged)))
        return merged

    def _needs_fallback(self, segment: str, entries: list[ExtractedEntry]) -> bool:
        lines = [line.strip() for line in segment.splitlines() if line.strip()]
        # 날짜 구분선은 발화가 아니므로 커버리지 분모에서 제외한다(전부 파싱된 구간이
        # 구분선 때문에 임계 미달로 보이는 오탐 방지).
        content_lines = [
            line for line in lines if not is_date_separator(DATE_SEPARATOR.match(line))
        ]
        if not content_lines:
            return False
        has_signal = (
            any(_SIGNAL.search(line) for line in lines)
            or len(content_lines) < len(lines)  # 날짜 구분선 존재
            or sum(1 for line in content_lines if _TIME_HINT.search(line)) >= 2  # 시각 반복
        )
        if not has_signal:
            return False  # 구조 신호 없음 → 평문으로 취급, 폴백 안 함
        structured = sum(1 for e in entries if e.source == "structured")
        return structured / len(content_lines) < self._threshold
