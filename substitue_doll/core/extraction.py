"""구조 추출 — 순수 도메인 (CLAUDE.md §8, Issue #4 §3·§10).

자유 형식 입력에서 추출한 **정제 전** 단위(`ExtractedEntry`)와, 추출기 포트(`Extractor`).
정제물(`RefinedRecord`)과 구분한다: 추출 → 정제 → 저장 순서에서 이건 "정제 전" 단계다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from substitue_doll.core.record import Source


@dataclass(frozen=True)
class ExtractedEntry:
    """입력에서 추출한 발화 한 건(정제 전).

    speaker: 구조 구간의 화자 라벨. 평문 구간은 None(화자 미상).
    text: 발화/문장.
    order: 입력 내 추출 순서(0부터).
    source: "structured"(구조 추출) | "plain"(평문).
    ts: 시각 문자열(있으면). 정규화는 하지 않고 원문 토막을 담는다.
    """

    text: str
    order: int
    source: Source
    speaker: str | None = None
    ts: str | None = None


class Extractor(Protocol):
    """추출기 포트 — 자유 형식 입력 → 추출 단위 리스트(원래 순서)."""

    def extract(self, text: str) -> list[ExtractedEntry]:
        """입력 텍스트에서 (구조/평문) 단위를 순서대로 추출한다."""
        ...
