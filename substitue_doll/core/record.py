"""정제물 레코드 — 순수 도메인 데이터 모델 (CLAUDE.md §4 데이터 경계, Issue #4 §5).

1단계에서는 골격만 채운다. `event`/`emotion`(사건+감정)은 4단계 실제 정제에서 채운다.
입출력을 모르는 순수 데이터 구조다 (§8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Source = Literal["structured", "plain"]


@dataclass(frozen=True)
class RefinedRecord:
    """정제된 발화 한 건.

    speaker: 화자(예: "나"/상대). 1B 추출에서 결정.
    text: 발화/문장.
    order: 한 입력 안에서의 순서(0부터).
    source: "structured"(대화 로그 추출) | "plain"(평문).
    ts: 시각(ISO 문자열, 없으면 None).
    event/emotion: 사건·감정 — 4단계 정제 전에는 None.
    """

    speaker: str
    text: str
    order: int
    source: Source
    ts: str | None = None
    event: str | None = None
    emotion: str | None = None
