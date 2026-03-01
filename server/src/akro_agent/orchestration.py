"""Orchestrator: runs the research pipeline via LangGraph (with critic revision loop)."""

from __future__ import annotations

import json
from typing import Iterator

from akro_agent.graph import get_research_graph
from akro_agent.models import ResearchReport


def run_research(
    query: str,
    *,
    use_critic: bool = True,
    use_enrichment: bool = True,
) -> ResearchReport:
    """
    Run the full pipeline via LangGraph: Planner -> Researcher -> Enricher -> Synthesizer -> Critic.
    If the critic returns "revise", the graph loops back to the Synthesizer (up to MAX_REVISIONS).
    """
    graph = get_research_graph()
    initial: dict = {
        "query": query,
        "use_enrichment": use_enrichment,
        "use_critic": use_critic,
        "synthesis_iteration": 0,
    }
    final = graph.invoke(initial)
    return final["report"]


def run_research_stream(
    query: str,
    *,
    use_critic: bool = True,
    use_enrichment: bool = True,
) -> Iterator[tuple[str, str]]:
    """
    Run the pipeline via LangGraph and yield (event_type, json_data) for SSE.
    Events: plan, search_done, enrich_done, synthesis_done, critic_done, report, done.
    On revision loop, synthesis_done and critic_done may repeat.
    """
    graph = get_research_graph()
    initial: dict = {
        "query": query,
        "use_enrichment": use_enrichment,
        "use_critic": use_critic,
        "synthesis_iteration": 0,
    }
    state: dict = dict(initial)
    for node_name, state_update in graph.stream(initial):
        state.update(state_update)
        if node_name == "planner" and "plan" in state_update:
            yield "plan", state_update["plan"].model_dump_json()
        elif node_name == "researcher" and "evidence_list" in state_update:
            ev = state_update["evidence_list"]
            yield "search_done", json.dumps({
                "sub_queries": len(ev),
                "total_chunks": sum(len(e.chunks) for e in ev),
            })
        elif node_name == "enricher" and "evidence_list" in state_update:
            ev = state_update["evidence_list"]
            yield "enrich_done", json.dumps({"chunks": sum(len(e.chunks) for e in ev)})
        elif node_name == "synthesizer" and "report" in state_update:
            yield "synthesis_done", json.dumps({"iteration": state_update.get("synthesis_iteration", 0)})
        elif node_name == "critic" and "report" in state_update:
            yield "critic_done", json.dumps({
                "verdict": state_update.get("critic_verdict", "accept"),
            })
    yield "report", state["report"].model_dump_json()
    yield "done", "{}"
