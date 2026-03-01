"""Web search (Tavily) with retries and configurable depth."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from tavily import TavilyClient

# Load .env from project root so TAVILY_API_KEY is available (e.g. when running CLI from any dir)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

MAX_RESULTS_PER_QUERY = 5
TAVILY_SEARCH_DEPTH_DEFAULT: Literal["basic", "advanced"] = "basic"  # "advanced" = deeper, 2 credits
MAX_RETRIES = 3
RETRY_BACKOFF_SEC = 1.0


def _get_tavily_client() -> TavilyClient:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise ValueError(
            "TAVILY_API_KEY is not set. Add it to .env (get a key from https://tavily.com)"
        )
    return TavilyClient(api_key=key)


def web_search(
    query: str,
    max_results: int = MAX_RESULTS_PER_QUERY,
    search_depth: Literal["basic", "advanced", "fast", "ultra-fast"] = TAVILY_SEARCH_DEPTH_DEFAULT,
) -> list[dict]:
    """
    Run a web search and return list of dicts with keys: title, href, body.
    Uses retries with exponential backoff on transient failures.
    """
    client = _get_tavily_client()
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.search(
                query,
                max_results=max_results,
                search_depth=search_depth,
            )
            results = response.get("results") or []
            return [
                {
                    "title": r.get("title", ""),
                    "href": r.get("url", ""),
                    "body": r.get("content", ""),
                }
                for r in results
            ]
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_BACKOFF_SEC * (2**attempt))
    return []  # fail open: return no results rather than raising
