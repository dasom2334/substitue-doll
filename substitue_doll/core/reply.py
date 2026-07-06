"""답변 초안 생성 엔진 — 3단계 (Issue #12 PR-5).

새 상황과 의미가 가까운 과거 발화 top-k를 검색해 근거로 넣고, LLM에게 "나"의
말투로 추천 답변 초안을 생성시킨다. 초안은 **생성만** 한다 — 발송하지 않는다
(CLAUDE.md §0). 모든 의존(LlmClient·Embedder·VectorIndex·Repository)은 포트로
주입받는 순수 오케스트레이션이다(§8).
"""

from __future__ import annotations

from dataclasses import dataclass

from substitue_doll.core.embedding import Embedder
from substitue_doll.core.llm import LlmClient
from substitue_doll.core.record import RefinedRecord
from substitue_doll.core.repository import Repository
from substitue_doll.core.retrieval import VectorIndex, retrieve

_PROMPT_TEMPLATE = """너는 아래 "나"라는 사람의 말투를 그대로 재현하는 대필가다.

과거 대화 예시(말투·맥락 근거, 새 상황과 의미가 가까운 순 — [나]가 본인, 나머지는 상대):
{examples}

상대가 방금 이렇게 말했다(또는 이런 상황이다):
{situation}

규칙:
- 위 상대의 말/상황에 대해 **"나"가 보낼 답장**을 작성해라 — 상황을 따라 말하지 말 것.
- "나"의 말투(어미·길이·ㅋㅋ/이모티콘 습관 등)를 예시의 [나] 발화에서 그대로 따라라.
- 답장 **하나만** 출력해라. 설명·따옴표·머리말 금지.
- 예시에 없는 사적 사실을 지어내지 마라."""


@dataclass(frozen=True)
class ReplyResult:
    """답변 초안 결과.

    draft: 생성된 초안(발송은 사용자 몫).
    examples: 근거로 쓰인 과거 발화(투명성·디버깅용).
    """

    draft: str
    examples: list[RefinedRecord]


def build_prompt(situation: str, examples: list[RefinedRecord]) -> str:
    """검색된 과거 발화를 근거로 넣는 프롬프트를 조립한다.

    단일 패스 `.format()` 사용 — 순차 replace와 달리 치환값을 재스캔하지 않으므로,
    예시/상황 텍스트에 플레이스홀더 문자열이 들어 있어도 오염되지 않는다 (PR #18 리뷰 #1).
    """
    lines = [f"- [{record.speaker}] {record.text}" for record in examples]
    example_block = "\n".join(lines) if lines else "- (예시 없음)"
    return _PROMPT_TEMPLATE.format(examples=example_block, situation=situation)


def reply(
    situation: str,
    *,
    llm: LlmClient,
    embedder: Embedder,
    index: VectorIndex,
    repository: Repository,
    k: int = 5,
) -> ReplyResult:
    """새 상황에 대한 '나' 말투의 답변 초안을 생성한다."""
    examples = retrieve(situation, embedder=embedder, index=index, repository=repository, k=k)
    draft = llm.complete(build_prompt(situation, examples)).strip()
    return ReplyResult(draft=draft, examples=examples)
