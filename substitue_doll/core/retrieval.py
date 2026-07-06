"""검색(RAG retrieval) 엔진 — 2단계 (Issue #12 PR-4).

인덱싱: 저장된 정제물 전부를 임베딩해 벡터 인덱스에 적재.
검색: 질의를 임베딩해 top-k 유사 레코드를 반환.

모든 의존(Embedder·VectorIndex·Repository)은 포트로 주입받는 순수 오케스트레이션(§8).
인덱싱 단위 = 정제물 레코드(발화) 하나.
"""

from __future__ import annotations

from typing import Protocol

from substitue_doll.core.embedding import Embedder
from substitue_doll.core.record import RefinedRecord
from substitue_doll.core.repository import Repository


class VectorIndex(Protocol):
    """벡터 인덱스 포트 — (레코드 id, 벡터) 저장과 top-k 검색."""

    def add_many(self, items: list[tuple[int, list[float]]]) -> None:
        """(record_id, vector) 목록을 적재한다."""
        ...

    def search(self, vector: list[float], k: int) -> list[int]:
        """질의 벡터와 유사한 순서로 record_id를 최대 k개 반환한다."""
        ...

    def count(self) -> int:
        """적재된 벡터 수."""
        ...


def build_index(*, repository: Repository, embedder: Embedder, index: VectorIndex) -> int:
    """저장된 정제물 전체를 임베딩해 인덱스에 적재한다. 적재 건수를 반환."""
    items = repository.load_all_with_ids()
    if not items:
        return 0
    vectors = embedder.embed([record.text for _, record in items])
    index.add_many(
        [(record_id, vector) for (record_id, _), vector in zip(items, vectors, strict=True)]
    )
    return len(items)


def retrieve(
    query: str,
    *,
    embedder: Embedder,
    index: VectorIndex,
    repository: Repository,
    k: int = 5,
) -> list[RefinedRecord]:
    """질의와 의미가 가까운 정제물 top-k를 유사도 순으로 반환한다."""
    (query_vector,) = embedder.embed([query])
    record_ids = index.search(query_vector, k)
    return repository.load_by_ids(record_ids)
