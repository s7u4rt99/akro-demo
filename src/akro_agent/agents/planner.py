"""Planner agent: turns user query into a structured research plan."""

from akro_agent.llm import complete
from akro_agent.models import ResearchPlan


SYSTEM = """You are a research planner for a scholarly report. Given a user query, produce a structured research plan that will support a full academic-style report with claims, evidence, counter-arguments, and implications.

Output a JSON object with:
- "sub_queries": list of objects, each with "question" (string) and "priority" (integer 1-5, 1=most important).
- "summary": brief string describing the research approach.

Create 5-8 sub-questions that together support:
1. Main claims or themes (what are the key positions/findings?)
2. Supporting evidence and examples for those claims
3. Critical perspectives, counter-arguments, or alternative views
4. Methodology or scope (what kind of sources, time period, definitions?)
5. Implications or significance (so what? for whom?)

Order by priority. Phrase questions so that search results will yield both supportive and critical material."""


def run_planner(query: str) -> ResearchPlan:
    """Produce a research plan (sub-queries + summary) for the given query."""
    out = complete(
        SYSTEM,
        f"User query: {query}",
        response_format=ResearchPlan,
        temperature=0.3,
    )
    assert isinstance(out, ResearchPlan)
    return out
