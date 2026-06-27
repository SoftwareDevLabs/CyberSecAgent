from __future__ import annotations

import os
from typing import Any


def build_llm_from_env() -> Any:
    """Build a LangChain BaseChatModel from environment variables.

    Reads:
      CYBERGUARD_LLM_PROVIDER  — 'openai-compatible' (default) | 'anthropic'
      CYBERGUARD_LLM_MODEL     — model name string (required)
      CYBERGUARD_LLM_API_KEY   — API key (required)
      CYBERGUARD_LLM_BASE_URL  — base URL for openai-compatible endpoints
    """
    provider = os.environ.get("CYBERGUARD_LLM_PROVIDER", "openai-compatible")
    model = os.environ["CYBERGUARD_LLM_MODEL"]
    api_key = os.environ["CYBERGUARD_LLM_API_KEY"]

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, api_key=api_key)

    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=os.environ.get("CYBERGUARD_LLM_BASE_URL"),
    )
