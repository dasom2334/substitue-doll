"""테스트 공용 픽스처.

합성/더미 데이터만 둔다 — 실제 제3자 포함 로그는 정제 완성 이후에만 투입한다(CLAUDE.md §6).
"""

from __future__ import annotations

import pytest


@pytest.fixture
def synthetic_messages() -> list[str]:
    """합성 대화 더미 데이터. 실제 인물/대화가 아니다."""
    return [
        "오늘 좀 힘들었어",
        "[오후 3:21] 친구: 자니?",
        "그냥 들어줘서 고마워",
    ]
