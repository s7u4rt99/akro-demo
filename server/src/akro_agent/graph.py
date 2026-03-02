"""LangGraph orchestration: planner -> researcher -> enricher -> synthesizer <-> critic (revision loop)."""

from __future__ import annotations

from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from akro_agent.agents.planner import run_planner
from akro_agent.agents.researcher import run_researcher
from akro_agent.agents.synthesizer import run_synthesizer
from akro_agent.agents.critic import run_critic
from akro_agent.models import ResearchPlan, ResearchReport, ResearchEvidence
from akro_agent.fetch import enrich_evidence

MAX_REVISIONS = 1


class ResearchState(TypedDict, total=False):
    """State for the research graph."""

    query: str
    use_enrichment: bool
    use_critic: bool
    plan: ResearchPlan
    evidence_list: list
    report: ResearchReport
    critic_verdict: str
    critic_feedback: str
    confidence_notes: str
    synthesis_iteration: int


def _node_planner(state: ResearchState) -> dict:
    print("running planner\n")
    plan = run_planner(state["query"])
    print(f"planner results: {plan}\n")
    return {"plan": plan}


def _node_researcher(state: ResearchState) -> dict:
    print("running researcher\n")
    evidence_list = run_researcher(state["plan"])
    print(f"researcher results: {evidence_list}\n")
    return {"evidence_list": evidence_list}


def _node_enricher(state: ResearchState) -> dict:
    print("running enricher\n")
    evidence_list = state["evidence_list"]
    if state.get("use_enrichment", True):
        evidence_list = enrich_evidence(evidence_list)
    print(f"enricher results: {evidence_list}\n")
    return {"evidence_list": evidence_list}


def _node_synthesizer(state: ResearchState) -> dict:
    print("running synthesizer\n")
    revision_feedback = state.get("critic_feedback") or None
    previous = state.get("report")
    iteration = state.get("synthesis_iteration", 0)
    print(f"synthesizer iteration: {iteration}\n")
    report = run_synthesizer(
        state["query"],
        state["evidence_list"],
        revision_feedback=revision_feedback,
        previous_report=previous,
    )
    next_iteration = iteration + 1 if revision_feedback else iteration
    print(f"synthesizer results: {report}\n")
    return {"report": report, "synthesis_iteration": next_iteration}


def _node_critic(state: ResearchState) -> dict:
    print("running critic\n")
    report, verdict = run_critic(state["report"])
    print(f"critic verdict: {verdict}\n")
    return {
        "report": report,
        "critic_verdict": verdict.verdict,
        "critic_feedback": verdict.feedback or "",
        "confidence_notes": verdict.confidence_notes or "",
    }


def _after_synthesizer(state: ResearchState) -> Literal["critic", "__end__"]:
    """If use_critic, go to critic; else end."""
    if state.get("use_critic", True):
        return "critic"
    return "__end__"


def _after_critic(state: ResearchState) -> Literal["synthesizer", "__end__"]:
    if not state.get("use_critic", True):
        return "__end__"
    if state.get("critic_verdict") != "revise":
        return "__end__"
    iteration = state.get("synthesis_iteration", 0)
    if iteration >= MAX_REVISIONS:
        return "__end__"
    return "synthesizer"


def build_research_graph() -> StateGraph:
    """Build and compile the research graph with critic revision loop."""
    builder = StateGraph(ResearchState)

    builder.add_node("planner", _node_planner)
    builder.add_node("researcher", _node_researcher)
    builder.add_node("enricher", _node_enricher)
    builder.add_node("synthesizer", _node_synthesizer)
    builder.add_node("critic", _node_critic)

    builder.add_edge("planner", "researcher")
    builder.add_edge("researcher", "enricher")
    builder.add_edge("enricher", "synthesizer")
    builder.add_conditional_edges("synthesizer", _after_synthesizer, {"critic": "critic", "__end__": END})
    builder.add_conditional_edges("critic", _after_critic, {"synthesizer": "synthesizer", "__end__": END})

    builder.set_entry_point("planner")
    return builder.compile()


# Single compiled graph instance
_research_graph = None


def get_research_graph():
    global _research_graph
    if _research_graph is None:
        _research_graph = build_research_graph()
    return _research_graph
