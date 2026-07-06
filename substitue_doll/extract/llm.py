"""LLM 폴백 추출기 — 1B-ii (Issue #12 PR-1).

룰이 자신 없는 구간만 이 추출기로 온다(HybridExtractor가 결정). LlmClient(포트)에
구간 텍스트를 주고 JSON 배열로 (화자, 시각, 발화)를 받아 ExtractedEntry로 변환한다.

응답 파싱에 실패하면 빈 리스트를 반환한다 — 호출자(하이브리드)는 이를 "폴백 실패"로
보고 룰 결과를 유지한다(안전 방향).

전량 폐기 정책(의도된 설계): 응답 배열 중 **한 항목이라도** 스키마 위반이면 전체를
폐기한다. 부분 수용은 오염된 항목을 정제·저장으로 전파시킬 수 있어, 룰 결과 유지가
더 안전하다. "부분 수용으로 개선"하지 말 것 (PR #13 리뷰 #3).
"""

from __future__ import annotations

import json

from substitue_doll.core.extraction import ExtractedEntry
from substitue_doll.core.llm import LlmClient

# 주의: 사용자 입력이 <<< >>> 사이에 그대로 들어가므로 프롬프트 인젝션이 이론상 가능하다.
# 방어선: ① 아래 스키마 검증(형식 안 맞으면 전량 폐기) ② 결과는 저장 전 §4 정제를 거침.
# 실데이터 단계에서 구분자를 호출마다 랜덤 토큰으로 바꾸는 강화를 고려 (PR #13 리뷰 #2).
_PROMPT_TEMPLATE = """다음 텍스트에서 대화 발화를 추출해라.

규칙:
- 출력은 JSON 배열 **만**. 설명·코드펜스 금지.
- 각 원소: {"speaker": 화자 문자열 또는 null, "ts": 시각 문자열 또는 null, "text": 발화 문자열}
- 대화 발화가 아닌 서술은 speaker=null 로 둔다. 원문 순서를 유지한다.
- 텍스트를 요약하거나 고치지 말고 그대로 담아라.

텍스트:
<<<
{payload}
>>>"""


def _strip_fences(raw: str) -> str:
    """모델이 코드펜스로 감쌌을 때 안쪽만 꺼낸다."""
    text = raw.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1 and text.endswith("```"):
            return text[first_newline + 1 : -3].strip()
    return text


class LlmExtractor:
    """LlmClient를 주입받아 구간 텍스트를 추출하는 폴백 추출기."""

    def __init__(self, client: LlmClient) -> None:
        self._client = client

    def extract(self, text: str) -> list[ExtractedEntry]:
        # `.format()`이 아니라 `.replace()`인 이유(모드1 종합 리뷰): 이 템플릿엔 JSON 예시의
        # 리터럴 중괄호가 있고 사용자 텍스트에도 `{}`가 올 수 있어 format은 깨진다.
        # 단일 치환 replace는 재스캔이 없어 안전 — "일관성 정리"로 format 전환 금지.
        prompt = _PROMPT_TEMPLATE.replace("{payload}", text)
        try:
            raw = self._client.complete(prompt)
        except Exception:
            # 폴백은 파이프라인을 죽이지 않는다 — 제공자 실패(네트워크 등)는 빈 결과로.
            return []
        try:
            data = json.loads(_strip_fences(raw))
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []

        entries: list[ExtractedEntry] = []
        for item in data:
            if not isinstance(item, dict):
                return []
            body = item.get("text")
            if not isinstance(body, str) or not body.strip():
                return []
            speaker = item.get("speaker")
            ts = item.get("ts")
            if speaker is not None and not isinstance(speaker, str):
                return []
            if ts is not None and not isinstance(ts, str):
                return []
            if isinstance(speaker, str):
                speaker = speaker.strip() or None  # 빈 화자("")는 None으로 정규화 (리뷰 #4)
            if isinstance(ts, str):
                ts = ts.strip() or None
            entries.append(
                ExtractedEntry(
                    text=body.strip(),
                    order=len(entries),
                    source="structured" if speaker else "plain",
                    speaker=speaker,
                    ts=ts,
                )
            )
        return entries
