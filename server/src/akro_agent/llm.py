"""Thin LLM client (OpenAI)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel
from pydantic_settings import BaseSettings

# Resolve .env from project root so it works regardless of cwd (e.g. CLI run from any dir)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DOTENV = _PROJECT_ROOT / ".env"


class LLMSettings(BaseSettings):
    """LLM configuration from environment."""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    class Config:
        env_file = _DOTENV
        extra = "ignore"


def _get_client() -> OpenAI:
    key = os.environ.get("OPENAI_API_KEY") or LLMSettings().openai_api_key
    if not key or key.startswith("sk-your-"):
        raise ValueError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key from https://platform.openai.com/api-keys"
        )
    return OpenAI(api_key=key)


def _get_model() -> str:
    return os.environ.get("OPENAI_MODEL") or LLMSettings().openai_model


def complete(
    system_prompt: str,
    user_prompt: str,
    *,
    response_format: type[BaseModel] | None = None,
    temperature: float = 0.3,
) -> str | BaseModel:
    """
    Call the LLM and return the response as text or as a parsed Pydantic model.
    """
    client = _get_client()
    model = _get_model()

    if response_format is not None:
        schema = response_format.model_json_schema()
        system_prompt = (
            system_prompt
            + "\n\nRespond with a single JSON object that matches this schema (no markdown, no code fence): "
            + json.dumps(schema)
        )

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    if response_format is not None:
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)
    content = resp.choices[0].message.content
    if content is None:
        raise RuntimeError("LLM returned empty content")

    if response_format is not None:
        return response_format.model_validate_json(content)
    return content
