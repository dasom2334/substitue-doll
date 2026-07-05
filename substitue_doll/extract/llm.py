"""LLM 폴백 추출기 — 1B-ii (Issue #12 PR-1).

룰이 자신 없는 구간만 이 추출기로 온다(HybridExtractor가 결정). LlmClient(포트)에
구간 텍스트를 주고 JSON 배열로 (화자, 시각, 발화)를 받아 ExtractedEntry로 변환한다.

응답 파싱에 실패하면 빈 리스트를 반환한다 — 호출자(하이브리드)는 이를 "폴백 실패"로
보고 룰 결과를 유지한다(안전 방향).
"""

from __future__ import annotations

import json

from substitue_doll.core.extraction import ExtractedEntry
from substitue_doll.core.llm import LlmClient

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
