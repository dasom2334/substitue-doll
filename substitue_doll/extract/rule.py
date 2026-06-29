"""룰(정규식 휴리스틱) 기반 구조 추출기 — 1B-i (Issue #4 §3·§10).

특정 메신저 포맷을 나열하지 않고 **구조를 추론**한다: 줄 단위로 화자 라벨·타임스탬프·
구분자 패턴을 감지해 구조 줄을 추출하고, 매칭 안 되는 줄은 평문으로 모은다.

순수 함수 계층(I/O 없음). 신뢰도가 낮은(룰이 못 다루는) 입력의 LLM 폴백은 1B-ii.
한계: 단순 `화자: 텍스트` 패턴은 "메모: ..." 같은 줄을 구조로 오인할 수 있다
(합성 데이터엔 무해, 1B-ii에서 보완).
"""

from __future__ import annotations

import re

from substitue_doll.core.extraction import ExtractedEntry

_DATE = r"\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}"
_TIME = r"(?:오전|오후)?\s*\d{1,2}:\d{2}"
_TS = rf"{_DATE}(?:\s+{_TIME})?"

# 1) "타임스탬프, 화자 : 텍스트"
_TS_SPEAKER = re.compile(rf"^(?P<ts>{_TS})\s*,\s*(?P<speaker>[^:,]{{1,30}}?)\s*:\s*(?P<text>.+)$")
# 2) "[화자] (선택 타임스탬프) 텍스트"
_BRACKET = re.compile(r"^\[(?P<speaker>[^\]]{1,30})\]\s*(?P<rest>.+)$")
_LEADING_TS = re.compile(rf"^(?P<ts>{_TS})\s+(?P<text>.+)$")
# 3) "화자: 텍스트" (단순)
_SIMPLE = re.compile(r"^(?P<speaker>[^:/\s][^:/]{0,19})\s*:\s*(?P<text>.+)$")


class RuleExtractor:
    """정규식 휴리스틱 기반 구조 추출기(순수)."""

    def extract(self, text: str) -> list[ExtractedEntry]:
        entries: list[ExtractedEntry] = []
        plain_buf: list[str] = []

        def flush_plain() -> None:
            if plain_buf:
                entries.append(
                    ExtractedEntry(text="\n".join(plain_buf), order=len(entries), source="plain")
                )
                plain_buf.clear()

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                flush_plain()  # 빈 줄 = 구간 분리
                continue
            parsed = self._parse_structured(line)
            if parsed is None:
                plain_buf.append(line)
                continue
            flush_plain()
            speaker, ts, body = parsed
            entries.append(
                ExtractedEntry(
                    text=body,
                    order=len(entries),
                    source="structured",
                    speaker=speaker,
                    ts=ts,
                )
            )
        flush_plain()
        return entries

    @staticmethod
    def _parse_structured(line: str) -> tuple[str, str | None, str] | None:
        """구조 줄이면 (speaker, ts, text), 아니면 None."""
        m = _TS_SPEAKER.match(line)
        if m:
            return m["speaker"].strip(), m["ts"].strip(), m["text"].strip()
        m = _BRACKET.match(line)
        if m:
            speaker = m["speaker"].strip()
            rest = m["rest"].strip()
            tm = _LEADING_TS.match(rest)
            if tm:
                return speaker, tm["ts"].strip(), tm["text"].strip()
            return speaker, None, rest
        m = _SIMPLE.match(line)
        if m:
            return m["speaker"].strip(), None, m["text"].strip()
        return None
