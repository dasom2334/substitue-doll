"""임베딩 포트 — 텍스트→벡터 변환기 추상 (2단계, Issue #12 PR-4).

임베딩 모델(변환기)과 벡터 인덱스(저장·검색)는 **별개 부품**이다. 구체 모델
(sentence-transformers 등)은 embed 레이어의 어댑터로 두고, 엔진은 이 포트만 안다(§8).
"""

from __future__ import annotations

from typing import Protocol


class Embedder(Protocol):
    """임베딩 포트."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """텍스트 목록을 같은 순서의 벡터 목록으로 변환한다."""
        ...
