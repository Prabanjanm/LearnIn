"""
Unit tests for app/core/gemini_client.py - the thin wrapper around the
Gemini vision API used as the preferred scanned-PDF OCR engine.

Never calls the real Gemini API: `genai.Client` construction is monkeypatched
with a fake, exactly like FakeDriveClient stands in for the real Drive
service in tests/test_paper_processing_flow.py.
"""
import types

import pytest

from app.common.exceptions.exceptions import GeminiConfigError
from app.core import gemini_client as gemini_client_module
from app.core.config import settings
from app.core.gemini_client import GeminiClient, get_gemini_client


class FakeGenaiModels:
    def __init__(self, response_text="hello from gemini", raise_error=None):
        self.response_text = response_text
        self.raise_error = raise_error
        self.calls = []

    def generate_content(self, *, model, contents):
        self.calls.append({"model": model, "contents": contents})
        if self.raise_error:
            raise self.raise_error
        return types.SimpleNamespace(text=self.response_text)


class FakeGenaiClient:
    def __init__(self, models: FakeGenaiModels):
        self.models = models


def test_raises_gemini_config_error_when_no_api_key_is_set(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", None)

    client = GeminiClient()
    with pytest.raises(GeminiConfigError):
        client.extract_text_from_image(b"fake-png-bytes")


def test_extract_text_from_image_calls_the_sdk_and_returns_stripped_text(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    fake_models = FakeGenaiModels(response_text="  Question 1: what is 2+2?  \n")
    monkeypatch.setattr(
        gemini_client_module.genai, "Client",
        lambda api_key: FakeGenaiClient(fake_models),
    )

    client = GeminiClient()
    result = client.extract_text_from_image(b"fake-png-bytes", mime_type="image/png")

    assert result == "Question 1: what is 2+2?"
    assert len(fake_models.calls) == 1
    assert fake_models.calls[0]["model"] == gemini_client_module.GEMINI_OCR_MODEL


def test_extract_text_from_image_propagates_sdk_errors(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    fake_models = FakeGenaiModels(raise_error=RuntimeError("network unreachable"))
    monkeypatch.setattr(
        gemini_client_module.genai, "Client",
        lambda api_key: FakeGenaiClient(fake_models),
    )

    client = GeminiClient()
    with pytest.raises(RuntimeError):
        client.extract_text_from_image(b"fake-png-bytes")


def test_client_is_built_once_and_reused(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    build_calls = []

    def fake_build(api_key):
        build_calls.append(api_key)
        return FakeGenaiClient(FakeGenaiModels())

    monkeypatch.setattr(gemini_client_module.genai, "Client", fake_build)

    client = GeminiClient()
    client.extract_text_from_image(b"a")
    client.extract_text_from_image(b"b")

    assert len(build_calls) == 1


def test_get_gemini_client_returns_a_singleton():
    assert get_gemini_client() is get_gemini_client()
