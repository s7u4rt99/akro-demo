"""Researcher agent: runs web search and collects evidence for sub-queries."""

from akro_agent.models import EvidenceChunk, ResearchEvidence, ResearchPlan
from akro_agent.search import web_search


def run_researcher(plan: ResearchPlan) -> list[ResearchEvidence]:
    """
    For each sub-query in the plan, run web search and collect evidence chunks.
    """
    results: list[ResearchEvidence] = []
    for sq in plan.sub_queries:
        raw = web_search(sq.question)
        chunks = [
            EvidenceChunk(
                content=r.get("body", "") or r.get("title", ""),
                source=r.get("href", ""),
                sub_query=sq.question,
            )
            for r in raw
        ]
        results.append(ResearchEvidence(sub_query=sq.question, chunks=chunks))
    return results
