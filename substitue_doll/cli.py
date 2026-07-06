"""CLI — 엔진을 호출하는 얇은 껍데기 (CLAUDE.md §8).

사용:
  python -m substitue_doll.cli ingest <입력파일> [--db 경로] [--me 라벨]
  python -m substitue_doll.cli index  [--db 경로]
  python -m substitue_doll.cli search <질의> [--db 경로] [-k N]

- ingest: 자유 형식 텍스트를 인입한다. '나'가 애매하면 후보를 보여주고 1회 확인한다
  (--me 로 미리 주면 묻지 않는다 — Issue #4 §9-8).
- index: 저장된 정제물 전체를 임베딩해 같은 DB 파일의 벡터 인덱스에 적재한다(2단계).
- search: 질의와 의미가 가까운 발화 top-k를 출력한다(검색 단독 확인용).
- 추출기는 현재 룰 기반(RuleExtractor)만 연결한다. LLM 폴백(HybridExtractor)은
  제공자 어댑터가 생기는 시점(Issue #12 PR-5 게이트)에 교체 연결한다.
- 기본 DB 경로는 **리포 루트에서 실행**을 전제로 한 상대경로 `data/` 다(.gitignore 대상).
  다른 위치에서 실행하면 그 위치에 data/가 생기니 `--db`로 명시하라 (PR #16 리뷰 #4).

종료 코드: 0 = 성공(저장/검색 결과 없음 포함), 1 = 오류/확인 중단.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from substitue_doll.core.embedding import Embedder
from substitue_doll.core.ingest import IngestResult, ingest
from substitue_doll.core.retrieval import build_index, retrieve
from substitue_doll.extract.rule import RuleExtractor
from substitue_doll.refine.stub import refine
from substitue_doll.store.sqlite_repository import SqliteRepository
from substitue_doll.store.sqlite_vector_index import SqliteVectorIndex

DEFAULT_DB = Path("data") / "substitue.db"  # 리포 루트 실행 전제 — 모듈 docstring 참조


def _make_embedder() -> Embedder:
    """임베더 팩토리 — 무거운 의존성(torch)을 명령 실행 시점에만 로드한다."""
    from substitue_doll.embed.sentence_transformer import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder()


def _confirm_me(candidates: tuple[str, ...]) -> str | None:
    """'나' 후보를 보여주고 1회 확인한다(껍데기의 몫).

    입력은 **번호 우선**으로 해석한다 — 후보 라벨이 "1" 같은 숫자 문자열이어도
    번호 선택으로 본다(드문 엣지, 의도된 규칙).
    """
    print("'나'를 판별하지 못했습니다. 본인 라벨을 골라주세요:")
    for i, candidate in enumerate(candidates, start=1):
        print(f"  {i}. {candidate}")
    answer = input("번호 또는 라벨 입력: ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(candidates):
        return candidates[int(answer) - 1]
    if answer in candidates:
        return answer
    return None


def _run_ingest(input_path: Path, db_path: Path, me: str | None) -> IngestResult | None:
    """인입 실행. 실패(파일/인자 오류·확인 중단)면 None."""
    try:
        text = input_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"입력 파일을 읽을 수 없습니다: {exc}", file=sys.stderr)
        return None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    extractor = RuleExtractor()
    with SqliteRepository(db_path) as repository:
        # 호출을 한 곳에 모아 인자 표류·이중 생성 방지 (PR #16 리뷰 — HybridExtractor
        # 교체 시 이중 추출=이중 비용이 되는 것도 막는다).
        def _ingest_with(me_label: str | None) -> IngestResult:
            return ingest(
                text, extractor=extractor, repository=repository, refine=refine, me=me_label
            )

        try:
            result = _ingest_with(me)
        except ValueError as exc:
            print(f"인입 실패: {exc}", file=sys.stderr)
            return None
        if result.stored == 0 and result.resolution.needs_confirmation and me is None:
            chosen = _confirm_me(result.resolution.candidates)
            if chosen is None:
                print("알 수 없는 선택 — 인입을 중단합니다.", file=sys.stderr)
                return None
            result = _ingest_with(chosen)
        return result


def _cmd_ingest(args: argparse.Namespace) -> int:
    result = _run_ingest(args.input, args.db, args.me)
    if result is None:
        return 1
    if result.stored:
        print(f"{result.stored}건 저장 완료")
        return 0
    # 빈 입력 등 "저장할 게 없음"은 오류가 아니다 (PR #16 리뷰 #3).
    print("저장할 내용이 없습니다.")
    return 0


def _cmd_index(args: argparse.Namespace) -> int:
    try:
        embedder = _make_embedder()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    with SqliteRepository(args.db) as repository, SqliteVectorIndex(args.db) as index:
        indexed = build_index(repository=repository, embedder=embedder, index=index)
    print(f"{indexed}건 인덱싱 완료")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    try:
        embedder = _make_embedder()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    with SqliteRepository(args.db) as repository, SqliteVectorIndex(args.db) as index:
        records = retrieve(
            args.query, embedder=embedder, index=index, repository=repository, k=args.k
        )
    if not records:
        print("검색 결과가 없습니다. 먼저 ingest 후 index를 실행했는지 확인하세요.")
        return 0
    for rank, record in enumerate(records, start=1):
        ts = f" ({record.ts})" if record.ts else ""
        print(f"{rank}. [{record.speaker}]{ts} {record.text}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="substitue-doll")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="대화/텍스트 인입")
    ingest_parser.add_argument("input", type=Path, help="입력 텍스트 파일")
    ingest_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 파일 경로")
    ingest_parser.add_argument("--me", default=None, help="본인 화자 라벨(확인 질문 생략)")

    index_parser = subparsers.add_parser("index", help="저장된 정제물 임베딩 인덱스 구축")
    index_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 파일 경로")

    search_parser = subparsers.add_parser("search", help="유사 발화 top-k 검색")
    search_parser.add_argument("query", help="검색 질의")
    search_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 파일 경로")
    search_parser.add_argument("-k", type=int, default=5, help="반환 개수(기본 5)")

    args = parser.parse_args(argv)
    if args.command == "ingest":
        return _cmd_ingest(args)
    if args.command == "index":
        return _cmd_index(args)
    if args.command == "search":
        return _cmd_search(args)
    return 2  # pragma: no cover — argparse의 required=True가 막는다


if __name__ == "__main__":
    raise SystemExit(main())
