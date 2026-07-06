"""인입 파이프라인 — 엔진 (1C, Issue #12 PR-3).

입력 → 추출(Extractor) → 화자 판별(resolve_me) → 정제(주입) → RefinedRecord → 저장(Repository).
모든 의존은 포트/콜러블로 주입받는 순수 오케스트레이션이다(CLAUDE.md §8).

'나' 확인이 필요한데 `me`가 주어지지 않으면 **아무것도 저장하지 않고** 결과에
needs_confirmation을 담아 반환한다 — 사용자에게 묻는 것은 껍데기의 몫이다.

화자 규칙:
- 평문 엔트리는 사용자 본인의 서술로 간주해 화자를 "나"로 저장한다.
- 판별/확인된 '나' 라벨은 "나"로 정규화해 저장한다(하류 검색이 내 발화를 일관되게 찾도록).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from substitue_doll.core.extraction import Extractor
from substitue_doll.core.record import RefinedRecord
from substitue_doll.core.repository import Repository
from substitue_doll.core.speaker import SpeakerResolution, resolve_me

ME_LABEL = "나"


@dataclass(frozen=True)
class IngestResult:
    """인입 결과.

    stored: 저장된 레코드 수(확인 대기로 저장 안 했으면 0).
    resolution: 화자 판별 결과 — needs_confirmation이면 껍데기가 확인 후 me를 넣어 재호출.
    """

    stored: int
    resolution: SpeakerResolution


def ingest(
    text: str,
    *,
    extractor: Extractor,
    repository: Repository,
    refine: Callable[[str], str],
    me: str | None = None,
) -> IngestResult:
    """자유 형식 입력을 추출·정제해 저장한다."""
    entries = extractor.extract(text)
    resolution = resolve_me(entries)
    if me is not None and resolution.candidates and me not in resolution.candidates:
        # 잘못된 인자는 경계에서 즉시 시끄럽게 — 조용히 통과하면 '나' 발화 0건인
        # 손상 데이터가 저장된다 (PR #16 리뷰 #1). 화자가 아예 없으면(평문뿐) me는 무시.
        raise ValueError(f"me 라벨이 화자 후보에 없다: {me!r} (후보: {resolution.candidates})")
    if resolution.needs_confirmation and me is None:
        return IngestResult(stored=0, resolution=resolution)
    effective_me = me if me is not None else resolution.me

    records: list[RefinedRecord] = []
    for entry in entries:
        if entry.speaker is None or entry.speaker == effective_me:
            speaker = ME_LABEL
        else:
            speaker = entry.speaker
        records.append(
            RefinedRecord(
                speaker=speaker,
                text=refine(entry.text),
                order=entry.order,
                source=entry.source,
                ts=entry.ts,
            )
        )
    repository.add_many(records)
    return IngestResult(stored=len(records), resolution=resolution)
