"""룰(정규식 휴리스틱) 기반 구조 추출기 — 1B-i (Issue #4 §3·§10).

특정 메신저 포맷을 나열하지 않고 일반 구조 신호(날짜·시각·화자 라벨·구분자)를 감지한다.
실제 메신저 내보내기엔 날짜가 "하루 한 번 구분선"으로만 찍히고 아래 줄들엔 시각만 있는
형태가 흔하므로, extract()는 **날짜 구분선 상태**를 기억해 시각만 있는 발화에 날짜를 붙인다.

순수 함수 계층(I/O 없음). 룰이 못 다루는 형태(구분자 없는 자유 배치 등)는 1B-ii
하이브리드의 LLM 폴백이 받는다 — 신호 감지가 같은 패턴을 쓰도록 DATE/TIME 패턴은
공개 이름으로 둔다(이중 관리 방지).
한계: 단순 `화자: 텍스트` 패턴은 "메모: ..." 같은 줄을 구조로 오인할 수 있다
(합성 데이터엔 무해 — 폴백·후속 정제에서 보완).
"""

from __future__ import annotations

import re

from substitue_doll.core.extraction import ExtractedEntry

# ReDoS 방지: 가변 공백 매처가 겹치지 않도록 `\s` 대신 리터럴 `[ ]`만 쓰고,
# TIME_PATTERN 선행에 가변 공백을 두지 않는다(인접 `\s+`/`\s*`와 겹치면 백트래킹 폭발).
DATE_PATTERN = (
    r"\d{4}[.\-/][ ]?\d{1,2}[.\-/][ ]?\d{1,2}\.?"  # 2024.3.1 · 2024. 5. 1.
    r"|\d{4}년[ ]?\d{1,2}월[ ]?\d{1,2}일"  # 2024년 3월 1일
)
TIME_PATTERN = r"(?:(?:오전|오후)[ ]?)?\d{1,2}:\d{2}(?:[ ]?[AaPp][Mm])?"
_TS = rf"(?:{DATE_PATTERN})(?:[ ]+{TIME_PATTERN})?"

# 날짜 구분선 후보: 줄 전체가 (장식 +) 날짜 (+ 요일/장식). 단 **순수 날짜만 있는 줄은
# 구분선이 아니다** — 사용자가 날짜를 감정 앵커로 회상한 평문일 수 있어 보존해야 한다
# (§4 사건·감정, PR #22 리뷰 #1). 구분선 확정은 is_date_separator()가 장식/요일을 요구.
DATE_SEPARATOR = re.compile(
    rf"^(?P<lead>[-=~ ]*)(?P<date>{DATE_PATTERN})[ ]?"
    rf"(?P<weekday>[월화수목금토일]요일)?(?P<trail>[-=~ ]*)$"
)


def is_date_separator(match: re.Match[str] | None) -> bool:
    """구분선 판정 — 양성 증거(장식 문자 또는 요일) 최소 1개를 요구한다."""
    if match is None:
        return False
    has_decoration = any(ch in "-=~" for ch in match["lead"] + match["trail"])
    return bool(match["weekday"]) or has_decoration


# 1) "날짜(+시각), 화자 : 텍스트"
_TS_SPEAKER = re.compile(
    rf"^(?P<ts>{_TS})[ ]*,[ ]*(?P<speaker>[^:,]{{1,30}}?)[ ]*:[ ]*(?P<text>.+)$"
)
# 1b) "시각, 화자 : 텍스트" — 날짜는 구분선 상태에서 보충. 시각+콤마는 날짜+콤마보다
#     증거가 약하므로 화자에 공백 불허(_SIMPLE과 동일 방어) — "오후 3:00, 근데 말이야: …"
#     평문 오인 방지 (PR #22 리뷰 #2). 공백 이름은 폴백(시각 반복 신호)이 받는다.
_TIME_SPEAKER = re.compile(
    rf"^(?P<ts>{TIME_PATTERN})[ ]*,[ ]*(?P<speaker>[^\s:,/]{{1,30}}?)[ ]*:[ ]*(?P<text>.+)$"
)
# 2) "[화자] ..." — 뒤에 [시각] / 타임스탬프 / 본문
_BRACKET = re.compile(r"^\[(?P<speaker>[^\]]{1,30})\][ ]*(?P<rest>.+)$")
_BRACKET_TIME = re.compile(rf"^\[(?P<ts>{TIME_PATTERN})\][ ]*(?P<text>.+)$")
# "타임스탬프 + 본문" — 브래킷 뒤·콜론 뒤 텍스트에서 ts 분리용.
# `_TS|TIME` 교대인 이유: _TS는 날짜가 필수(시각은 옵션)라 **날짜 없는 순수 시각**을
# 못 잡는다 — 뒤의 TIME_PATTERN 대안이 그 경우를 받는다(왼쪽 우선이라 겹침 무해).
_LEADING_TS = re.compile(rf"^(?P<ts>{_TS}|{TIME_PATTERN})[ ]+(?P<text>.+)$")
# 3) "화자: 텍스트" (단순). speaker에 공백 불허 + 콜론 뒤 `/` 차단 →
#    "오늘은 정말: ..."(평문 문장)·"http://..."(URL) 오매칭 방지.
_SIMPLE = re.compile(r"^(?P<speaker>[^\s:/]{1,20})[ ]*:[ ]*(?!/)(?P<text>.+)$")


def _has_date(ts: str) -> bool:
    return re.search(DATE_PATTERN, ts) is not None


def _attach_date(ts: str | None, current_date: str | None) -> str | None:
    """시각만 있는 ts에 구분선의 날짜를 보충한다(이미 날짜가 있으면 그대로)."""
    if ts is None or current_date is None or _has_date(ts):
        return ts
    return f"{current_date} {ts}"


class RuleExtractor:
    """정규식 휴리스틱 기반 구조 추출기(순수, 호출 단위 날짜 상태)."""

    def extract(self, text: str) -> list[ExtractedEntry]:
        entries: list[ExtractedEntry] = []
        plain_buf: list[str] = []
        current_date: str | None = None  # 날짜 구분선 상태 — 시각만 있는 발화에 보충

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
            separator = DATE_SEPARATOR.match(line)
            if is_date_separator(separator):
                assert separator is not None  # is_date_separator가 보장
                flush_plain()
                current_date = separator["date"].strip()
                continue  # 구분선은 발화가 아니다 — 날짜 상태로만 반영
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
                    ts=_attach_date(ts, current_date),
                )
            )
        flush_plain()
        return entries

    @staticmethod
    def _parse_structured(line: str) -> tuple[str, str | None, str] | None:
        """구조 줄이면 (speaker, ts, text), 아니면 None.

        ⚠️ 시도 순서는 **특이성 내림차순 계약**이다(날짜+시각 → 시각 → 브래킷 → 단순 콜론).
        순서를 바꾸면 약한 패턴이 강한 증거의 줄을 선점해 ts/화자 정보가 손실된다.
        """
        for pattern in (_TS_SPEAKER, _TIME_SPEAKER):
            m = pattern.match(line)
            if m:
                return m["speaker"].strip(), m["ts"].strip(), m["text"].strip()
        m = _BRACKET.match(line)
        if m:
            speaker = m["speaker"].strip()
            rest = m["rest"].strip()
            tm = _BRACKET_TIME.match(rest) or _LEADING_TS.match(rest)
            if tm:
                return speaker, tm["ts"].strip(), tm["text"].strip()
            return speaker, None, rest
        m = _SIMPLE.match(line)
        if m and not m["speaker"].strip().isdigit():
            # 숫자만인 "화자"는 시각의 앞부분("9:12 …" → speaker=9)일 가능성이 높다 —
            # 구조로 오인하지 않고 평문으로 넘겨 폴백 신호(시각 반복)가 받게 한다.
            body = m["text"].strip()
            tm = _LEADING_TS.match(body)  # "화자: 날짜/시각 본문" — ts가 본문에 묻히지 않게
            if tm:
                return m["speaker"].strip(), tm["ts"].strip(), tm["text"].strip()
            return m["speaker"].strip(), None, body
        return None
