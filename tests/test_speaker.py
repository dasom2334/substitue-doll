"""화자 식별 테스트 (합성 더미만 — CLAUDE.md §6)."""

from __future__ import annotations

from substitue_doll.core.extraction import ExtractedEntry
from substitue_doll.core.speaker import SpeakerResolution, resolve_me


def _structured(speaker: str, text: str, order: int) -> ExtractedEntry:
    return ExtractedEntry(text=text, order=order, source="structured", speaker=speaker)


def test_self_marker_identified() -> None:
    entries = [_structured("나", "안녕", 0), _structured("상대", "오랜만", 1)]

    assert resolve_me(entries) == SpeakerResolution(
        candidates=("나", "상대"), me="나", needs_confirmation=False
    )


def test_english_self_marker_case_insensitive() -> None:
    entries = [_structured("Me", "hi", 0), _structured("John", "hey", 1)]

    result = resolve_me(entries)
    assert result.me == "Me"
    assert result.needs_confirmation is False


def test_no_marker_needs_confirmation() -> None:
    entries = [_structured("철수", "안녕", 0), _structured("영희", "오랜만", 1)]

    assert resolve_me(entries) == SpeakerResolution(
        candidates=("철수", "영희"), me=None, needs_confirmation=True
    )


def test_multiple_markers_ambiguous() -> None:
    # "나"와 "Me"가 동시에 등장 — 어느 쪽이 본인인지 단정 불가.
    entries = [_structured("나", "안녕", 0), _structured("Me", "hi", 1)]

    result = resolve_me(entries)
    assert result.me is None
    assert result.needs_confirmation is True


def test_plain_only_no_confirmation() -> None:
    entries = [ExtractedEntry(text="그냥 힘든 하루였다", order=0, source="plain")]

    assert resolve_me(entries) == SpeakerResolution(
        candidates=(), me=None, needs_confirmation=False
    )


def test_single_unknown_speaker_needs_confirmation() -> None:
    entries = [_structured("철수", "안녕", 0)]

    result = resolve_me(entries)
    assert result.me is None
    assert result.needs_confirmation is True


def test_candidates_keep_first_appearance_order() -> None:
    entries = [
        _structured("상대", "먼저", 0),
        _structured("나", "다음", 1),
        _structured("상대", "또", 2),
    ]

    assert resolve_me(entries).candidates == ("상대", "나")
