"""Model router: Ollama + OpenAI-compatible APIs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

Provider = Literal["ollama", "openai"]


@dataclass
class ModelInfo:
    id: str
    provider: Provider
    name: str
    available: bool = True


@dataclass
class ChatMessage:
    role: Literal["system", "user", "assistant"]
    content: str


class ModelRouter:
    """Routes chat completion requests to Ollama or OpenAI-compatible endpoints."""

    def __init__(self) -> None:
        self._override_provider: Provider | None = None
        self._override_model: str | None = None
        self._agent_models: dict[str, str] = {}

    def set_global(self, provider: Provider | None = None, model: str | None = None) -> None:
        if provider is not None:
            self._override_provider = provider
        if model is not None:
            self._override_model = model

    def set_agent_model(self, agent: str, model: str | None) -> None:
        if model:
            self._agent_models[agent] = model
        elif agent in self._agent_models:
            del self._agent_models[agent]

    def resolve(self, agent: str | None = None) -> tuple[Provider, str]:
        provider: Provider = self._override_provider or settings.default_provider
        model = self._override_model or settings.default_model

        if agent:
            agent_key = agent.lower()
            per_agent = {
                "planner": settings.planner_model,
                "coder": settings.coder_model,
                "reviewer": settings.reviewer_model,
                "tester": settings.tester_model,
            }.get(agent_key)
            if agent_key in self._agent_models:
                model = self._agent_models[agent_key]
            elif per_agent:
                model = per_agent

        return provider, model

    def get_chat_model(self, agent: str | None = None, temperature: float = 0.2) -> BaseChatModel:
        provider, model = self.resolve(agent)
        if provider == "ollama":
            return ChatOllama(
                model=model,
                base_url=settings.ollama_base_url,
                temperature=temperature,
            )
        if not settings.openai_base_url and not settings.openai_api_key:
            # Fall back to Ollama if OpenAI not configured
            logger.warning("OpenAI provider selected but not configured; falling back to Ollama")
            return ChatOllama(
                model=model,
                base_url=settings.ollama_base_url,
                temperature=temperature,
            )
        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key or "not-needed",
            base_url=settings.openai_base_url,
            temperature=temperature,
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        agent: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        llm = self.get_chat_model(agent=agent, temperature=temperature)
        lc_messages = []
        for m in messages:
            if m.role == "system":
                lc_messages.append(SystemMessage(content=m.content))
            elif m.role == "user":
                lc_messages.append(HumanMessage(content=m.content))
            else:
                lc_messages.append(AIMessage(content=m.content))
        result = await llm.ainvoke(lc_messages)
        content = result.content
        if isinstance(content, list):
            return "".join(
                part.get("text", "") if isinstance(part, dict) else str(part) for part in content
            )
        return str(content)

    async def health(self) -> dict[str, Any]:
        ollama = await self._check_ollama()
        openai = await self._check_openai()
        return {
            "ollama": ollama,
            "openai": openai,
            "active": {
                "provider": self._override_provider or settings.default_provider,
                "model": self._override_model or settings.default_model,
                "agent_models": dict(self._agent_models),
            },
        }

    async def list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        ollama = await self._check_ollama()
        if ollama.get("ok"):
            for name in ollama.get("models", []):
                models.append(ModelInfo(id=f"ollama:{name}", provider="ollama", name=name))
        openai = await self._check_openai()
        if openai.get("ok") and openai.get("models"):
            for name in openai["models"]:
                models.append(ModelInfo(id=f"openai:{name}", provider="openai", name=name))
        if not models:
            # Recommended defaults even if offline
            for name in (
                settings.model_tier_low,
                settings.model_tier_mid,
                settings.model_tier_high,
            ):
                models.append(
                    ModelInfo(id=f"ollama:{name}", provider="ollama", name=name, available=False)
                )
        return models

    def recommend_for_ram(self, ram_gb: float) -> dict[str, str]:
        if ram_gb < 12:
            tier, model = "low", settings.model_tier_low
        elif ram_gb < 24:
            tier, model = "mid", settings.model_tier_mid
        else:
            tier, model = "high", settings.model_tier_high
        return {"tier": tier, "model": model, "provider": "ollama"}

    async def _check_ollama(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{settings.ollama_base_url}/api/tags")
                r.raise_for_status()
                data = r.json()
                names = [m.get("name", "") for m in data.get("models", [])]
                return {"ok": True, "models": names, "url": settings.ollama_base_url}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "url": settings.ollama_base_url}

    async def _check_openai(self) -> dict[str, Any]:
        if not settings.openai_base_url:
            return {"ok": False, "error": "openai_base_url not set"}
        try:
            headers = {}
            if settings.openai_api_key:
                headers["Authorization"] = f"Bearer {settings.openai_api_key}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{settings.openai_base_url.rstrip('/')}/models", headers=headers)
                if r.status_code >= 400:
                    return {"ok": True, "models": [], "note": "endpoint reachable but /models failed"}
                data = r.json()
                names = [m.get("id", "") for m in data.get("data", [])]
                return {"ok": True, "models": names[:50], "url": settings.openai_base_url}
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": str(exc), "url": settings.openai_base_url}


model_router = ModelRouter()
