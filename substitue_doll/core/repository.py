"""정제물 저장소 포트(인터페이스) — 순수 추상 (CLAUDE.md §8).

엔진/파이프라인은 이 Protocol에만 의존하고, 구체 구현(SQLite 등)은 store 레이어에 둔다.
이렇게 두면 모드2 프로덕션에서 Postgres+pgvector 어댑터로 교체해도 엔진은 한 줄도 안 바뀐다
(Issue #4 §6 저장 티어).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from substitue_doll.core.record import RefinedRecord


class Repository(Protocol):
    """정제물 저장소 포트."""

    def add(self, record: RefinedRecord) -> None:
        """레코드 하나를 저장한다."""
        ...

    def add_many(self, records: Iterable[RefinedRecord]) -> None:
        """레코드 여러 건을 저장한다(순서 보존)."""
        ...

    def load_all(self) -> list[RefinedRecord]:
        """저장된 레코드를 저장 순서대로 모두 반환한다."""
        ...

    def count(self) -> int:
        """저장된 레코드 수."""
        ...
