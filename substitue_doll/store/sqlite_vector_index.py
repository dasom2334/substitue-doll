"""SQLite 벡터 인덱스 — 같은 DB 파일에 벡터 저장 + 브루트포스 코사인 top-k.

레코드와 벡터를 **한 파일**에 두는 파일 티어 구현(Issue #4 §6). 1인분 데이터(수천 발화)엔
완전탐색 코사인으로 충분하다 — sqlite-vec(ANN)나 pgvector로의 교체는 VectorIndex 포트
뒤에서 어댑터만 바꾸면 된다(Issue #12 PR-4 리스크 대응: 확장 로딩 의존 없음).

벡터는 float32 배열 BLOB로 저장한다.
"""

from __future__ import annotations

import math
import sqlite3
from array import array
from pathlib import Path

_CREATE = """
CREATE TABLE IF NOT EXISTS record_vectors (
    record_id INTEGER PRIMARY KEY,
    vector    BLOB NOT NULL
)
"""


def _to_blob(vector: list[float]) -> bytes:
    return array("f", vector).tobytes()


def _from_blob(blob: bytes) -> list[float]:
    values = array("f")
    values.frombytes(blob)
    return list(values)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SqliteVectorIndex:
    """VectorIndex 포트의 SQLite 구현(브루트포스 검색)."""

    def __init__(self, db_path: Path | str) -> None:
        self._conn = sqlite3.connect(str(db_path))
        try:
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(_CREATE)
            self._conn.commit()
        except Exception:
            self._conn.close()
            raise

    def add_many(self, items: list[tuple[int, list[float]]]) -> None:
        self._conn.executemany(
            "INSERT OR REPLACE INTO record_vectors (record_id, vector) VALUES (?, ?)",
            [(record_id, _to_blob(vector)) for record_id, vector in items],
        )
        self._conn.commit()

    def search(self, vector: list[float], k: int) -> list[int]:
        if k <= 0:
            return []
        cursor = self._conn.execute("SELECT record_id, vector FROM record_vectors")
        scored = [
            (_cosine(vector, _from_blob(row["vector"])), int(row["record_id"]))
            for row in cursor.fetchall()
        ]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [record_id for _, record_id in scored[:k]]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM record_vectors").fetchone()
        return int(row["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SqliteVectorIndex:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
