"""One client for every chat model we use. Meta's Model API, Baseten, Fireworks and a Modal endpoint all speak
OpenAI-compatible Chat Completions, so a provider is only a base URL, a key name and a model name.

Plug and play: put a key in .env and the provider becomes available; nothing else changes.
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

import httpx

from diwan.config import env, offline


class ProviderError(RuntimeError):
    pass


@dataclass
class Reply:
    data: dict
    usage: dict


@dataclass
class ChatProvider:
    id: str
    label: str
    base_env: str
    base_default: str | None
    key_envs: tuple[str, ...]
    model_env: str
    model_default: str | None
    open_weights: bool = False
    key_required: bool = True
    extra: dict = field(default_factory=dict)  # provider-specific request fields
    schema_in_prompt: bool = False             # the endpoint ignores response_format: ask for the JSON in words instead
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    def base_url(self) -> str | None:
        return env(self.base_env, self.base_default)

    def model(self) -> str | None:
        return env(self.model_env, self.model_default)

    def _key(self) -> str | None:
        return next((k for k in (env(n) for n in self.key_envs) if k), None)

    def missing(self) -> list[str]:
        """What has to be set before this provider can be used (names only, never values)."""
        out = []
        if not self.base_url():
            out.append(self.base_env)
        if self.key_required and not self._key():
            out.append(self.key_envs[0])
        if not self.model():
            out.append(self.model_env)
        return out

    def available(self) -> bool:
        return not offline() and not self.missing()

    def complete_json(self, system: str, user: str, schema: dict, *, reasoning: str | None = "low",
                      timeout: float = 90) -> Reply:
        """One structured call: the reply must be JSON matching `schema` ({"name", "schema", "strict"})."""
        if not self.available():
            raise ProviderError(f"{self.label} is not set up: missing {', '.join(self.missing()) or 'online mode'}")
        body = {"model": self.model(), "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                "response_format": {"type": "json_schema", "json_schema": schema}, **self.extra}
        if self.schema_in_prompt:
            body.pop("response_format")
            body["messages"][0]["content"] += ("\n\nReply with one JSON object only, no markdown, no other text, matching this JSON schema:\n"
                                               + json.dumps(schema["schema"]))
        if reasoning and self.id == "meta":
            body["reasoning_effort"] = reasoning
        headers = {"Authorization": f"Bearer {self._key()}"} if self._key() else {}
        t0 = time.monotonic()
        try:
            with httpx.Client(transport=self.transport, timeout=timeout) as c:
                r = c.post(f"{self.base_url().rstrip('/')}/chat/completions", json=body, headers=headers)
        except httpx.HTTPError as e:
            raise ProviderError(f"{self.label}: {type(e).__name__}") from None
        if r.status_code in (400, 422) and "response_format" in r.text:
            # this endpoint has no strict JSON mode: ask for the same JSON in words, then check it as usual
            body.pop("response_format")
            body["messages"][0]["content"] += ("\n\nReply with one JSON object only, no other text, matching this JSON schema:\n"
                                               + json.dumps(schema["schema"]))
            try:
                with httpx.Client(transport=self.transport, timeout=timeout) as c:
                    r = c.post(f"{self.base_url().rstrip('/')}/chat/completions", json=body, headers=headers)
            except httpx.HTTPError as e:
                raise ProviderError(f"{self.label}: {type(e).__name__}") from None
        if r.status_code >= 400:
            raise ProviderError(f"{self.label}: HTTP {r.status_code} {r.text[:300]}")
        out = r.json()
        text = out["choices"][0]["message"].get("content") or ""
        u = out.get("usage") or {}
        return Reply(parse_json(text), {"provider": self.id, "model": self.model(),
                                        "latency_ms": round((time.monotonic() - t0) * 1000),
                                        "input_tokens": u.get("prompt_tokens"), "output_tokens": u.get("completion_tokens")})


def parse_json(text: str) -> dict:
    """Models on some hosts wrap JSON in a code fence; take the object either way."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ProviderError("reply was not JSON")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ProviderError(f"reply was not valid JSON: {e.msg}") from None


PROVIDERS: dict[str, ChatProvider] = {
    "meta": ChatProvider("meta", "Meta Model API (Muse Spark)", "META_API_BASE", "https://api.meta.ai/v1",
                         ("META_API_KEY", "MODEL_API_KEY"), "META_MODEL_SPARK", "muse-spark-1.3"),
    "baseten": ChatProvider("baseten", "Baseten (Muse Spark Open)", "BASETEN_API_BASE", "https://inference.baseten.co/v1",
                            ("BASETEN_API_KEY",), "BASETEN_MODEL", "meta-models/muse-spark-open-1026", open_weights=True),
    # Model names on these two are set once the account is live; we do not guess them.
    "fireworks": ChatProvider("fireworks", "Fireworks (Muse Spark Open)", "FIREWORKS_API_BASE", "https://api.fireworks.ai/inference/v1",
                              ("FIREWORKS_API_KEY",), "FIREWORKS_MODEL", None, open_weights=True),
    "modal": ChatProvider("modal", "Modal endpoint (Muse Spark Open)", "MODAL_ENDPOINT_URL", None,
                          ("MODAL_API_KEY",), "MODAL_MODEL", None, open_weights=True, key_required=False),
    # Meta's open-weights Muse Glimmer on NVIDIA's free endpoint: development and fictional data only (40 requests a minute)
    "nvidia": ChatProvider("nvidia", "NVIDIA endpoint (Muse Glimmer)", "NVIDIA_API_BASE", "https://integrate.api.nvidia.com/v1",
                           ("NVIDIA_API_KEY",), "NVIDIA_MODEL", "meta/muse-glimmer-30b", open_weights=True,
                           extra={"max_tokens": 4096, "chat_template_kwargs": {"enable_thinking": False}}, schema_in_prompt=True),
}


def for_tier(tier: str) -> ChatProvider | None:
    """`spark` runs on Meta's API; `open` runs on the first open-weight host that is set up (DIWAN_OPEN_ORDER)."""
    if tier == "spark":  # Muse Spark on Meta's API; without it, Meta's open Muse Glimmer on NVIDIA's endpoint
        for pid in ("meta", "nvidia"):
            if PROVIDERS[pid].available():
                return PROVIDERS[pid]
        return None
    if tier == "open":
        for pid in env("DIWAN_OPEN_ORDER", "baseten,fireworks,modal,nvidia").split(","):
            p = PROVIDERS.get(pid.strip())
            if p and p.available():
                return p
        return None
    raise ValueError(f"unknown tier {tier!r}")
