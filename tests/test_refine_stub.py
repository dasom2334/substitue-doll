"""정제 스텁 스모크 테스트."""

from __future__ import annotations

from substitue_doll.refine.stub import refine


def test_refine_stub_is_noop(synthetic_messages: list[str]) -> None:
    """스텁 단계의 refine은 입력을 그대로 반환한다."""
    for msg in synthetic_messages:
        assert refine(msg) == msg
