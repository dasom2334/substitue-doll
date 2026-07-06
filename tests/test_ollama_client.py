"""Ollama 어댑터 테스트 — HTTP를 가짜로 대체해 결정적으로 (합성 더미만, §6)."""

from __future__ import annotations

import io
import json
from typing import Any

import pytest

from substitue_doll.llm.ollama import OllamaClient


class _FakeResponse(io.BytesIO):
    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def test_complete_posts_prompt_and_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return _FakeResponse(json.dumps({"response": "그랬구나, 힘들었겠다"}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = OllamaClient(base_url="http://fake:11434", model="test-model")

    assert client.complete("프롬프트") == "그랬구나, 힘들었겠다"
    assert captured["url"] == "http://fake:11434/api/generate"
    assert captured["body"] == {"model": "test-model", "prompt": "프롬프트", "stream": False}


def test_env_vars_used_as_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://env-host:1234/")
    monkeypatch.setenv("LLM_MODEL", "env-model")

    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        body = json.loads(request.data.decode("utf-8"))
        assert request.full_url == "http://env-host:1234/api/generate"  # 후행 슬래시 제거
        assert body["model"] == "env-model"
        return _FakeResponse(json.dumps({"response": "ok"}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert OllamaClient().complete("x") == "ok"


def test_constructor_args_override_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "env-model")

    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        assert json.loads(request.data.decode("utf-8"))["model"] == "arg-model"
        return _FakeResponse(json.dumps({"response": "ok"}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert OllamaClient(model="arg-model").complete("x") == "ok"


def test_unexpected_response_shape_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: Any, timeout: float) -> _FakeResponse:
        return _FakeResponse(json.dumps({"error": "no model"}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="응답 형식"):
        OllamaClient().complete("x")
