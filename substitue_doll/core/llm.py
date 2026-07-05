"""LLM 클라이언트 포트 — 순수 추상 (CLAUDE.md §8, Issue #12).

엔진·추출기는 이 Protocol에만 의존한다. 구체 제공자(Anthropic/OpenAI 등) 어댑터는
제공자 결정 후 별도 레이어에 둔다. 테스트는 가짜 구현으로 결정적으로 수행한다.
"""

from __future__ import annotations

from typing import Protocol


class LlmClient(Protocol):
    """LLM 호출 포트 — 프롬프트를 넣고 텍스트 응답을 받는다."""

    def complete(self, prompt: str) -> str:
        """프롬프트에 대한 모델 응답 텍스트를 반환한다."""
        ...
