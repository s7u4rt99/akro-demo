"""Researcher agent: runs web search and collects evidence for sub-queries."""

from __future__ import annotations

import concurrent.futures
from typing import List

from akro_agent.models import EvidenceChunk, ResearchEvidence, ResearchPlan, SubQuery
from akro_agent.search import web_search

# Run up to this many Tavily searches in parallel (avoids rate limits)
MAX_CONCURRENT_SEARCHES = 6


def _search_one(sq: SubQuery) -> ResearchEvidence:
    """Run web search for one sub-query and return ResearchEvidence."""
    raw = web_search(sq.question)
    chunks = [
        EvidenceChunk(
            content=r.get("body", "") or r.get("title", ""),
            source=r.get("href", ""),
            sub_query=sq.question,
        )
        for r in raw
    ]
    return ResearchEvidence(sub_query=sq.question, chunks=chunks)


def run_researcher(plan: ResearchPlan) -> list[ResearchEvidence]:
    """
    For each sub-query in the plan, run web search and collect evidence chunks.
    Searches run in parallel to reduce total researcher time.
    """
    sub_queries = plan.sub_queries
    if not sub_queries:
        return []
    max_workers = min(MAX_CONCURRENT_SEARCHES, len(sub_queries))
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_search_one, sq) for sq in sub_queries]
        results: List[ResearchEvidence] = [
            f.result() for f in concurrent.futures.as_completed(futures)
        ]
    # Restore plan order (as_completed is unordered)
    order = {sq.question: i for i, sq in enumerate(sub_queries)}
    results.sort(key=lambda ev: order.get(ev.sub_query, 0))
    return results
