"""Ollama LLM 클라이언트 어댑터 (Issue #12 PR-6).

docker compose로 띄운 로컬 Ollama 서버(/api/generate)에 프롬프트를 보내 응답을 받는다.
- **로컬 인퍼런스 — 데이터가 외부로 나가지 않는다**(§4 근거, 임베딩과 동일한 결정).
- 표준 라이브러리(urllib)만 사용 — 의존성 0.
- 설정은 환경변수(`OLLAMA_BASE_URL`/`LLM_MODEL`)를 **읽기만** 한다(§3). 생성자 인자가 우선.
"""

from __future__ import annotations

import json
import os
import urllib.request

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:7b"  # 한국어 고려 기본값 — .env로 교체 가능


class OllamaClient:
    """LlmClient 포트의 Ollama 구현(로컬)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout_seconds: float = 300.0,
    ) -> None:
        env_url = os.environ.get("OLLAMA_BASE_URL")
        env_model = os.environ.get("LLM_MODEL")
        self._base_url = (base_url or env_url or DEFAULT_BASE_URL).rstrip("/")
        self._model = model or env_model or DEFAULT_MODEL
        self._timeout = timeout_seconds

    def complete(self, prompt: str) -> str:
        payload = json.dumps({"model": self._model, "prompt": prompt, "stream": False}).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            f"{self._base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self._timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        answer = data.get("response")
        if not isinstance(answer, str):
            raise RuntimeError(f"Ollama 응답 형식이 예상과 다릅니다: {type(answer).__name__}")
        return answer
