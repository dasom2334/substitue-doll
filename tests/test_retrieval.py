"""검색(2단계) 테스트 — 가짜 임베더로 결정적 검증 (합성 더미만, CLAUDE.md §6)."""

from __future__ import annotations

from pathlib import Path

from substitue_doll.core.record import RefinedRecord
from substitue_doll.core.retrieval import build_index, retrieve
from substitue_doll.store.sqlite_repository import SqliteRepository
from substitue_doll.store.sqlite_vector_index import SqliteVectorIndex


class FakeEmbedder:
    """정해진 텍스트→벡터 매핑을 돌려주는 가짜(결정적). 미지정 텍스트는 원점 근처."""

    def __init__(self, table: dict[str, list[float]]) -> None:
        self.table = table

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.table.get(text, [0.01, 0.01, 0.01]) for text in texts]


def _record(text: str, order: int) -> RefinedRecord:
    return RefinedRecord(speaker="나", text=text, order=order, source="plain")


# "우울" 축과 "여행" 축을 가진 3차원 가짜 의미 공간.
TABLE = {
    "오늘 우울해": [1.0, 0.0, 0.0],
    "기분이 가라앉아": [0.9, 0.1, 0.0],
    "여행 가고 싶다": [0.0, 1.0, 0.0],
    "제주도 어땠어?": [0.1, 0.9, 0.0],
}


def _setup(db: Path) -> None:
    embedder = FakeEmbedder(TABLE)
    with SqliteRepository(db) as repo:
        repo.add_many([_record(t, i) for i, t in enumerate(TABLE) if t != "기분이 가라앉아"])
        with SqliteVectorIndex(db) as index:
            assert build_index(repository=repo, embedder=embedder, index=index) == 3


def test_retrieve_ranks_by_semantic_similarity(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    _setup(db)
    embedder = FakeEmbedder(TABLE)

    with SqliteRepository(db) as repo, SqliteVectorIndex(db) as index:
        results = retrieve("기분이 가라앉아", embedder=embedder, index=index, repository=repo, k=2)

    # 단어가 안 겹쳐도 의미 축이 같은 "오늘 우울해"가 1위여야 한다.
    # (2위는 코사인상 "제주도 어땠어?"[0.1,0.9] ≈ 0.21 > "여행 가고 싶다"[0,1] ≈ 0.11)
    assert [r.text for r in results] == ["오늘 우울해", "제주도 어땠어?"]


def test_build_index_empty_repository(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with SqliteRepository(db) as repo, SqliteVectorIndex(db) as index:
        assert build_index(repository=repo, embedder=FakeEmbedder({}), index=index) == 0
        assert index.count() == 0


def test_k_larger_than_corpus_returns_all(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    _setup(db)
    with SqliteRepository(db) as repo, SqliteVectorIndex(db) as index:
        results = retrieve(
            "오늘 우울해", embedder=FakeEmbedder(TABLE), index=index, repository=repo, k=10
        )
    assert len(results) == 3


def test_vector_index_persists_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    _setup(db)
    with SqliteVectorIndex(db) as reopened:
        assert reopened.count() == 3
        top = reopened.search(TABLE["여행 가고 싶다"], k=1)
    with SqliteRepository(db) as repo:
        assert repo.load_by_ids(top)[0].text == "여행 가고 싶다"


def test_reindex_overwrites_instead_of_duplicating(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    _setup(db)
    embedder = FakeEmbedder(TABLE)
    with SqliteRepository(db) as repo, SqliteVectorIndex(db) as index:
        build_index(repository=repo, embedder=embedder, index=index)  # 재인덱싱
        assert index.count() == 3  # INSERT OR REPLACE — 중복 없음


def test_load_by_ids_preserves_ranking_order(tmp_path: Path) -> None:
    db = tmp_path / "store.db"
    with SqliteRepository(db) as repo:
        repo.add_many([_record("a", 0), _record("b", 1), _record("c", 2)])
        ids = [record_id for record_id, _ in repo.load_all_with_ids()]
        reversed_ids = list(reversed(ids))
        assert [r.text for r in repo.load_by_ids(reversed_ids)] == ["c", "b", "a"]
        assert repo.load_by_ids([]) == []


def test_load_by_ids_over_sqlite_variable_limit(tmp_path: Path) -> None:
    # PR #17 리뷰 #3: id가 SQLite 변수 한도(999)를 넘어도 청크 조회로 동작한다.
    db = tmp_path / "store.db"
    with SqliteRepository(db) as repo:
        repo.add_many([_record(f"t{i}", i) for i in range(1200)])
        ids = [record_id for record_id, _ in repo.load_all_with_ids()]

        loaded = repo.load_by_ids(ids)

        assert len(loaded) == 1200
        assert loaded[0].text == "t0"
        assert loaded[-1].text == "t1199"
