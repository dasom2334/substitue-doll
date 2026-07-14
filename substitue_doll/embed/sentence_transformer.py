"""sentence-transformers 임베더 어댑터 (2단계, Issue #12 PR-4).

로컬 인퍼런스라 **데이터가 외부로 나가지 않는다**(임베딩 선택의 결정 근거 — Issue #12).
무거운 의존성(torch)은 선택 설치다: `pip install -e ".[embed]"`.
"""

from __future__ import annotations

# 다국어(한국어 포함) 소형 모델 — 교체는 생성자 인자로.
DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


class SentenceTransformerEmbedder:
    """Embedder 포트의 sentence-transformers 구현(로컬)."""

    def __init__(self, model_name: str = DEFAULT_MODEL) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover — 설치 환경에선 도달 안 함
            raise RuntimeError(
                "sentence-transformers 미설치 — `pip install -e '.[embed]'` 후 사용하세요."
            ) from exc
        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, convert_to_numpy=True)
        return [[float(value) for value in vector] for vector in vectors]
