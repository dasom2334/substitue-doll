"""CLI — 엔진을 호출하는 얇은 껍데기 (CLAUDE.md §8).

사용: python -m substitue_doll.cli ingest <입력파일> [--db 경로] [--me 라벨]
- 입력 파일 내용을 인입한다. '나'가 애매하면 후보를 보여주고 1회 확인한다
  (--me 로 미리 주면 묻지 않는다 — Issue #4 §9-8).
- 추출기는 현재 룰 기반(RuleExtractor)만 연결한다. LLM 폴백(HybridExtractor)은
  제공자 어댑터가 생기는 시점(Issue #12 PR-5 게이트)에 교체 연결한다.
- 기본 DB 경로는 **리포 루트에서 실행**을 전제로 한 상대경로 `data/` 다(.gitignore 대상).
  다른 위치에서 실행하면 그 위치에 data/가 생기니 `--db`로 명시하라 (PR #16 리뷰 #4).

종료 코드: 0 = 저장 성공 또는 저장할 내용 없음(정상), 1 = 오류/확인 중단.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from substitue_doll.core.ingest import IngestResult, ingest
from substitue_doll.extract.rule import RuleExtractor
from substitue_doll.refine.stub import refine
from substitue_doll.store.sqlite_repository import SqliteRepository

DEFAULT_DB = Path("data") / "substitue.db"  # 리포 루트 실행 전제 — 모듈 docstring 참조


def _confirm_me(candidates: tuple[str, ...]) -> str | None:
    """'나' 후보를 보여주고 1회 확인한다(껍데기의 몫)."""
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
    with SqliteRepository(db_path) as repository:
        try:
            result = ingest(
                text, extractor=RuleExtractor(), repository=repository, refine=refine, me=me
            )
        except ValueError as exc:
            print(f"인입 실패: {exc}", file=sys.stderr)
            return None
        if result.stored == 0 and result.resolution.needs_confirmation and me is None:
            chosen = _confirm_me(result.resolution.candidates)
            if chosen is None:
                print("알 수 없는 선택 — 인입을 중단합니다.", file=sys.stderr)
                return None
            result = ingest(
                text, extractor=RuleExtractor(), repository=repository, refine=refine, me=chosen
            )
        return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="substitue-doll")
    subparsers = parser.add_subparsers(dest="command", required=True)
    ingest_parser = subparsers.add_parser("ingest", help="대화/텍스트 인입")
    ingest_parser.add_argument("input", type=Path, help="입력 텍스트 파일")
    ingest_parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite 파일 경로")
    ingest_parser.add_argument("--me", default=None, help="본인 화자 라벨(확인 질문 생략)")
    args = parser.parse_args(argv)

    result = _run_ingest(args.input, args.db, args.me)
    if result is None:
        return 1
    if result.stored:
        print(f"{result.stored}건 저장 완료")
        return 0
    # 빈 입력 등 "저장할 게 없음"은 오류가 아니다 (PR #16 리뷰 #3).
    print("저장할 내용이 없습니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
