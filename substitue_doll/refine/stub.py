"""정제 스텁 — 0단계.

지금은 입력을 그대로 돌려주는 no-op이다. 실제 정제(사적 정보 제거, 직업·MBTI 보존,
사건+감정 저장 등 — CLAUDE.md §4)는 빌드 4단계에서 이 함수를 대체한다.

데이터 위생(CLAUDE.md §6): 정제가 실체화되기 전에는 합성/더미 데이터로만 테스트한다.
"""

from __future__ import annotations


def refine(raw: str) -> str:
    """입력 텍스트를 정제해 반환한다.

    스텁 단계에서는 아무것도 제거하지 않고 그대로 반환한다.
    """
    return raw
