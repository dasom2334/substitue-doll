"""CLI — 엔진을 호출하는 얇은 껍데기 (CLAUDE.md §8).

사용:
  python -m substitue_doll.cli ingest <입력파일> [--db 경로] [--me 라벨]
  python -m substitue_doll.cli index  [--db 경로]
  python -m substitue_doll.cli search <질의> [--db 경로] [-k N]
  python -m substitue_doll.cli reply  <상황>  [--db 경로] [-k N]
  python -m substitue_doll.cli eval   <상황파일> [--db 경로] [-k N]

- ingest: 자유 형식 텍스트를 인입한다. '나'가 애매하면 후보를 보여주고 1회 확인한다
  (--me 로 미리 주면 묻지 않는다 — Issue #4 §9-8).
- index: 저장된 정제물 전체를 임베딩해 같은 DB 파일의 벡터 인덱스에 적재한다(2단계).
- search: 질의와 의미가 가까운 발화 top-k를 출력한다(검색 단독 확인용).
- reply: 새 상황에 대해 '나' 말투의 답변 **초안**을 생성한다(생성만, 발송 없음 — §0).
- eval: 상황 파일(한 줄 = 한 상황)로 MVP 평가(PLAN §5) — 상황별 top-k와 초안을 출력해
  사람이 관련성·말투 유사를 판정한다.
- LLM은 로컬 Ollama(`docker compose up -d` + 모델 pull — README 참조). 설정은
  `.env`(`OLLAMA_BASE_URL`/`LLM_MODEL`, `env.example` 참조).
- 추출기는 **룰 우선 + 자신 없는 구간만 LLM 폴백**(HybridExtractor). Ollama가 꺼져
  있어도 폴백이 빈 결과로 처리돼 ingest는 룰만으로 동작한다.
- 기본 DB 경로는 **리포 루트에서 실행**을 전제로 한 상대경로 `data/` 다(.gitignore 대상).
  다른 위치에서 실행하면 그 위치에 data/가 생기니 `--db`로 명시하라 (PR #16 리뷰 #4).

종료 코드: 0 = 성공(저장/검색 결과 없음 포함), 1 = 오류/확인 중단.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import MutableMapping
from pathlib import Path

from substitue_doll.core.embedding import Embedder
from substitue_doll.core.ingest import IngestResult, ingest
from substitue_doll.core.llm import LlmClient
from substitue_doll.core.reply import reply
from substitue_doll.core.retrieval import build_index, retrieve
from substitue_doll.extract.hybrid import HybridExtractor
from substitue_doll.extract.llm import LlmExtractor
from substitue_doll.refine.stub import refine
from substitue_doll.store.sqlite_repository import SqliteRepository
from substitue_doll.store.sqlite_vector_index import SqliteVectorIndex

DEFAULT_DB = Path("data") / "substitue.db"  # 리포 루트 실행 전제 — 모듈 docstring 참조


def _load_dotenv(path: Path = Path(".env"), env: MutableMapping[str, str] = os.environ) -> None:
    """`.env`를 환경변수로 로드한다 — 이미 설정된 변수는 유지(실제 환경이 우선).

    외부 의존 없이 `KEY=VALUE` 줄만 지원한다(따옴표·변수 확장·`export` 접두 미지원 —
    env.example 참조). env를 주입 가능하게 둔 것은 테스트가 전역을 오염시키지 않기
    위함(PR #20 리뷰). 설정 로드는 껍데기의 몫이다(§3·§8).
    """
    if not path.is_file():
        return
    try:
        content = path.read_text(encoding="utf-8-sig")  # -sig: BOM 자동 제거
    except (OSError, UnicodeDecodeError) as exc:
        # 부수 편의 기능의 실패가 CLI 전체를 막으면 안 된다 — 경고 후 실제 env로 진행.
        print(f".env를 읽지 못해 건너뜁니다: {exc}", file=sys.stderr)
        return
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key or " " in key:  # "export KEY=V" 등 오파싱 방지 — 조용히 스킵
            continue
        env.setdefault(key, value.strip())


def _make_embedder() -> Embedder:
    """임베더 팩토리 — 무거운 의존성(torch)을 명령 실행 시점에만 로드한다."""
    from substitue_doll.embed.sentence_transformer import SentenceTransformerEmbedder

    return SentenceTransformerEmbedder()


def _make_llm() -> LlmClient:
    """LLM 클라이언트 팩토리 — 로컬 Ollama(Issue #12 PR-6 결정). 생성은 네트워크 무비용."""
    from substitue_doll.llm.ollama import OllamaClient

    return OllamaClient()


def _confirm_me(candidates: tuple[str, ...]) -> str | None:
    """'나' 후보를 보여주고 1회 확인한다(껍데기의 몫).

    입력은 **번호 우선**으로 해석한다 — 후보 라벨이 "1" 같은 숫자 문자열이어도
    번호 선택으로 본다(드문 엣지, 의도된 규칙).
    """
    print("'나'를 판별하지 못했습니다. 본인 라벨을 골라주세요:")
    for i, candidate in enumerate(candidates, start=1):
        print(f"  {i}. {candidate}")
    try:
        answer = input("번호 또는 라벨 입력: ").strip()
    except EOFError:  # 비대화형(stdin 닫힘) — 트레이스백 없이 중단 경로로 (라이브 테스트 발견)
        return None
    if answer.isdigit() and 1 <= int(answer) <= len(candidates):
        return candidates[int(answer) - 1]
    if answer in candidates:
        return answer
    return None


def _run_ingest(input_path: Path, db_path: Path, me: str | None) -> IngestResult | None:
    """인입 실행. 실패(파일/인자 오류·확인 중단)면 None."""
    try:
        text = input_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:  # UnicodeDecodeError는 OSError가 아니다
        print(f"입력 파일을 읽을 수 없습니다: {exc}", file=sys.stderr)
        return None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # 룰 우선 + 자신 없는 구간만 LLM 폴백(1B-ii). Ollama가 꺼져 있어도 폴백 추출기가
    # 실패를 빈 결과로 삼켜 룰 결과가 유지된다(안전 방향) — ingest는 LLM 없이도 동작.
    extractor = HybridExtractor(fallback=LlmExtractor(_make_llm()))
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


def _cmd_reply(args: argparse.Namespace) -> int:
    try:
        # 가벼운 것 먼저 — llm 생성은 무비용, 임베더는 torch 로드로 무겁다.
        llm = _make_llm()
        embedder = _make_embedder()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    with SqliteRepository(args.db) as repository, SqliteVectorIndex(args.db) as index:
        try:
            result = reply(
                args.situation,
                llm=llm,
                embedder=embedder,
                index=index,
                repository=repository,
                k=args.k,
            )
        except Exception as exc:
            # 껍데기 경계: LlmClient 포트는 예외를 명세하지 않아(어댑터마다 다름)
            # 임의 실패를 모두 받아 트레이스백 없이 정돈한다 (§3).
            print(f"초안 생성 실패: {exc}", file=sys.stderr)
            return 1
    print(result.draft)
    if result.examples:
        print("\n--- 근거가 된 과거 발화 ---", file=sys.stderr)
        for record in result.examples:
            print(f"  [{record.speaker}] {record.text}", file=sys.stderr)
    return 0


def _cmd_eval(args: argparse.Namespace) -> int:
    """MVP 평가(PLAN §5): 상황별 top-k 관련성 + 초안 말투 유사를 사람이 판정하도록 출력.

    reply와 달리 근거까지 전부 stdout으로 낸다 — eval 출력은 리포트 전체가 판정
    대상이라 한 스트림으로 일원화한다(의도된 정책 차이).
    """
    try:
        situations = [
            line.strip() for line in args.situations.read_text(encoding="utf-8").splitlines()
        ]
    except (OSError, UnicodeDecodeError) as exc:  # UnicodeDecodeError는 OSError가 아니다
        print(f"상황 파일을 읽을 수 없습니다: {exc}", file=sys.stderr)
        return 1
    situations = [s for s in situations if s]
    if not situations:
        print("평가할 상황이 없습니다.", file=sys.stderr)
        return 1
    try:
        llm = _make_llm()
        embedder = _make_embedder()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    failures = 0
    with SqliteRepository(args.db) as repository, SqliteVectorIndex(args.db) as index:
        for number, situation in enumerate(situations, start=1):
            print(f"\n=== 상황 {number}/{len(situations)}: {situation}")
            try:
                result = reply(
                    situation,
                    llm=llm,
                    embedder=embedder,
                    index=index,
                    repository=repository,
                    k=args.k,
                )
            except Exception as exc:  # 부분 실패가 평가 배치 전체를 죽이지 않게 (PR #18 리뷰)
                failures += 1
                print(f"  생성 실패: {exc}")
                continue
            print("--- 검색 top-k (관련성 판정 대상):")
            for rank, record in enumerate(result.examples, start=1):
                print(f"  {rank}. [{record.speaker}] {record.text}")
            print("--- 생성 초안 (말투 유사 판정 대상):")
            print(f"  {result.draft}")
    print("\n판정 기준(PLAN §5): 상황별 top-k가 관련 있고 초안이 내 말투와 유사하면 MVP 통과.")
    return 1 if failures == len(situations) else 0  # 전부 실패했을 때만 오류


def main(argv: list[str] | None = None) -> int:
    _load_dotenv()
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

    reply_parser = subparsers.add_parser("reply", help="'나' 말투의 답변 초안 생성")
    reply_parser.add_argument("situation", help="새 상황(상대가 보낸 말 등)")
    reply_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 파일 경로")
    reply_parser.add_argument("-k", type=int, default=5, help="근거 발화 개수(기본 5)")

    eval_parser = subparsers.add_parser("eval", help="MVP 평가 — 상황 파일(한 줄=한 상황)")
    eval_parser.add_argument("situations", type=Path, help="상황 목록 파일")
    eval_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 파일 경로")
    eval_parser.add_argument("-k", type=int, default=5, help="근거 발화 개수(기본 5)")

    args = parser.parse_args(argv)
    if args.command == "ingest":
        return _cmd_ingest(args)
    if args.command == "index":
        return _cmd_index(args)
    if args.command == "search":
        return _cmd_search(args)
    if args.command == "reply":
        return _cmd_reply(args)
    if args.command == "eval":
        return _cmd_eval(args)
    return 2  # pragma: no cover — argparse의 required=True가 막는다


if __name__ == "__main__":
    raise SystemExit(main())
