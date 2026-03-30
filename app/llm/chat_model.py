from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from app.core.settings import settings


@lru_cache(maxsize=1)
def get_chat_model() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_api_key or None,
        base_url=settings.llm_base_url,
        temperature=0.2,
        max_tokens=800,
        timeout=60,
        max_retries=1,
    )
