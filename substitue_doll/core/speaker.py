"""화자 식별 — '나' 판별 (1B-iii, Issue #12 PR-2).

추출 결과의 화자 라벨에서 사용자 본인("나")을 추론한다(Issue #4 §9-8: 추론 우선,
애매하면 1회 확인). 애매할 때 이 모듈은 **needs_confirmation=True 를 반환만** 한다 —
사용자에게 묻는 것은 껍데기(CLI)의 몫이다 (CLAUDE.md §8: 엔진은 입출력을 모른다).
"""

from __future__ import annotations

from dataclasses import dataclass

from substitue_doll.core.extraction import ExtractedEntry

# 본인을 가리키는 화자 라벨(소문자 비교). 정확히 하나가 등장할 때만 확신한다.
_SELF_MARKERS = frozenset({"나", "본인", "me", "i"})


@dataclass(frozen=True)
class SpeakerResolution:
    """화자 판별 결과.

    candidates: 등장한 화자 라벨(등장 순, 중복 제거).
    me: 판별된 '나' 라벨. 애매하면 None.
    needs_confirmation: True면 껍데기가 사용자에게 1회 확인해야 한다.
    """

    candidates: tuple[str, ...]
    me: str | None
    needs_confirmation: bool


def resolve_me(entries: list[ExtractedEntry]) -> SpeakerResolution:
    """추출 엔트리의 화자들에서 '나'를 추론한다.

    - 본인 마커("나"/"본인"/"me"/"i", 대소문자 무시)가 **정확히 하나** → 확신, 확인 불필요.
    - 마커가 없거나 여럿 → 애매: me=None, needs_confirmation=True.
    - 화자가 아예 없으면(평문뿐) 확인할 것도 없음: me=None, needs_confirmation=False.
    """
    candidates: list[str] = []
    for entry in entries:
        if entry.speaker is not None and entry.speaker not in candidates:
            candidates.append(entry.speaker)

    matches = [c for c in candidates if c.lower() in _SELF_MARKERS]
    if len(matches) == 1:
        return SpeakerResolution(tuple(candidates), matches[0], False)
    return SpeakerResolution(tuple(candidates), None, bool(candidates))
