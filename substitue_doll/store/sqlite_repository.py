"""SQLite 정제물 저장소 어댑터 (Issue #4 §6: 파일 티어).

core.Repository 포트의 SQLite 구현. 표준 라이브러리 `sqlite3`만 사용(의존성 0).
시즌2 프로덕션에서 Postgres+pgvector 어댑터로 교체 가능.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from substitue_doll.core.record import RefinedRecord

# `order`는 SQL 예약어라 컬럼명은 `ord`를 쓴다.
_CREATE = """
CREATE TABLE IF NOT EXISTS refined_records (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    speaker TEXT    NOT NULL,
    text    TEXT    NOT NULL,
    ord     INTEGER NOT NULL,
    source  TEXT    NOT NULL,
    ts      TEXT,
    event   TEXT,
    emotion TEXT
)
"""
_COLUMNS = "speaker, text, ord, source, ts, event, emotion"


class SqliteRepository:
    """정제물을 SQLite 파일에 저장하는 Repository 구현."""

    def __init__(self, db_path: Path | str) -> None:
        self._conn = sqlite3.connect(str(db_path))
        try:  # 초기화 실패 시 연결을 닫고 재raise (핸들/락 누수 방지)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(_CREATE)
            self._conn.commit()
        except Exception:
            self._conn.close()
            raise

    def add(self, record: RefinedRecord) -> None:
        self.add_many([record])

    def add_many(self, records: Iterable[RefinedRecord]) -> None:
        rows = [(r.speaker, r.text, r.order, r.source, r.ts, r.event, r.emotion) for r in records]
        self._conn.executemany(
            f"INSERT INTO refined_records ({_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def load_all(self) -> list[RefinedRecord]:
        cursor = self._conn.execute(f"SELECT {_COLUMNS} FROM refined_records ORDER BY id")
        return [
            RefinedRecord(
                speaker=row["speaker"],
                text=row["text"],
                order=row["ord"],
                source=row["source"],
                ts=row["ts"],
                event=row["event"],
                emotion=row["emotion"],
            )
            for row in cursor.fetchall()
        ]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM refined_records").fetchone()
        return int(row["n"])

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> SqliteRepository:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
