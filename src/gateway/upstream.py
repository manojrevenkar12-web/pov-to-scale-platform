"""Model backends. AzureOpenAI talks to an Azure OpenAI resource with an Entra ID token (no keys);
FakeUpstream answers locally for tests and the demo."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

import httpx


class UpstreamError(Exception):
    def __init__(self, status: int, message: str = ""):
        super().__init__(f"upstream {status}: {message}")
        self.status = status


@dataclass
class Completion:
    content: str
    input_tokens: int
    output_tokens: int
    model: str


class Upstream(Protocol):
    def complete(self, deployment: str, messages: list[dict], max_tokens: int) -> Completion: ...


@dataclass
class AzureOpenAI:
    endpoint: str  # https://<resource>.openai.azure.com
    token: Callable[[], str]  # Entra ID access token for https://cognitiveservices.azure.com
    api_version: str = "2024-10-21"
    timeout: float = 60.0

    def complete(self, deployment: str, messages: list[dict], max_tokens: int) -> Completion:
        url = f"{self.endpoint}/openai/deployments/{deployment}/chat/completions?api-version={self.api_version}"
        r = httpx.post(
            url,
            json={"messages": messages, "max_tokens": max_tokens},
            headers={"Authorization": f"Bearer {self.token()}"},
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise UpstreamError(r.status_code, r.text[:200])
        body = r.json()
        return Completion(
            body["choices"][0]["message"]["content"],
            body["usage"]["prompt_tokens"],
            body["usage"]["completion_tokens"],
            deployment,
        )


@dataclass
class FakeUpstream:
    """Deterministic backend: echoes, counts ~4 characters per token, can be told to fail."""

    failing: dict[str, int] = field(default_factory=dict)  # deployment -> status to return
    calls: list[tuple[str, list[dict]]] = field(default_factory=list)

    def complete(self, deployment: str, messages: list[dict], max_tokens: int) -> Completion:
        self.calls.append((deployment, messages))
        if deployment in self.failing:
            raise UpstreamError(self.failing[deployment], "simulated")
        prompt = " ".join(m.get("content", "") for m in messages)
        answer = f"[{deployment}] {prompt[:200]}"
        return Completion(answer, max(1, len(prompt) // 4), min(max_tokens, max(1, len(answer) // 4)), deployment)
