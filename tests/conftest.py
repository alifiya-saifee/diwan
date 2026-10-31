import json

import httpx
import pytest

from diwan.providers.chat import PROVIDERS

KEYS = ["META_API_KEY", "MODEL_API_KEY", "BASETEN_API_KEY", "FIREWORKS_API_KEY", "FIREWORKS_MODEL", "MODAL_ENDPOINT_URL",
        "MODAL_MODEL", "MODAL_API_KEY", "NVIDIA_API_KEY", "NVIDIA_MODEL", "WHATSAPP_TOKEN", "WHATSAPP_PHONE_ID", "WHATSAPP_VERIFY_TOKEN", "WHATSAPP_APP_SECRET", "WHATSAPP_PROVIDER", "AISENSY_PROJECT_ID", "AISENSY_PROJECT_API_PWD", "AISENSY_API_KEY", "AISENSY_WEBHOOK_TOKEN", "DIWAN_OFFLINE", "DIWAN_TAPE", "DIWAN_OPEN_ORDER", "DIWAN_OPEN_FALLBACK"]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    """Tests never see the developer's .env or real keys."""
    monkeypatch.setattr("diwan.config.ROOT", tmp_path)
    for k in KEYS:
        monkeypatch.delenv(k, raising=False)
    for p in PROVIDERS.values():
        monkeypatch.setattr(p, "transport", None)
    monkeypatch.setenv("DIWAN_LOCAL_ASR", "0")  # tests never load the local Whisper model
    monkeypatch.setenv("DIWAN_REPLY_WAIT", "0")  # each message answered at once; tests/test_burst.py sets a wait


def fake(reply: dict, seen: list | None = None):
    def handle(req: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(reply)}}],
                                         "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    return httpx.MockTransport(handle)


