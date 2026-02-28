"""Orchestrator: runs the full research pipeline."""

from __future__ import annotations

import json
from typing import Iterator

from akro_agent.agents.planner import run_planner
from akro_agent.agents.researcher import run_researcher
from akro_agent.agents.synthesizer import run_synthesizer
from akro_agent.agents.critic import run_critic
from akro_agent.models import ResearchReport
from akro_agent.fetch import enrich_evidence


def run_research(
    query: str,
    *,
    use_critic: bool = True,
    use_enrichment: bool = True,
) -> ResearchReport:
    """
    Run the full pipeline: Planner -> Researcher -> [Enricher: fetch URLs + extract] -> Synthesizer -> [Critic].
    Enrichment fetches each result URL and replaces snippet with full-page content to reduce snippet hallucination.
    """
    print("running planner\n")
    plan = run_planner(query)
    print(f"planner results: {plan}\n")
    print("running researcher")
    evidence_list = run_researcher(plan)
    print(f"researcher results: {evidence_list}\n")
    if use_enrichment:
        print("running enrichment")
        evidence_list = enrich_evidence(evidence_list)
        print(f"enrichment results: {evidence_list}\n")
    print("running synthesizer")
    report = run_synthesizer(query, evidence_list)
    print(f"synthesizer results: {report}\n")
    if use_critic:
        print("running critic")
        report = run_critic(report)
        print(f"critic report: {report}\n")
    return report


def run_research_stream(
    query: str,
    *,
    use_critic: bool = True,
    use_enrichment: bool = True,
) -> Iterator[tuple[str, str]]:
    """
    Run the pipeline and yield (event_type, json_data) for SSE.
    Events: plan, search_done, enrich_done, synthesis_done, critic_done, report, done.
    """
    plan = run_planner(query)
    yield "plan", plan.model_dump_json()
    evidence_list = run_researcher(plan)
    yield "search_done", json.dumps({
        "sub_queries": len(evidence_list),
        "total_chunks": sum(len(e.chunks) for e in evidence_list),
    })
    if use_enrichment:
        evidence_list = enrich_evidence(evidence_list)
        yield "enrich_done", json.dumps({"chunks": sum(len(e.chunks) for e in evidence_list)})
    report = run_synthesizer(query, evidence_list)
    yield "synthesis_done", "{}"
    if use_critic:
        report = run_critic(report)
        yield "critic_done", "{}"
    yield "report", report.model_dump_json()
    yield "done", "{}"
