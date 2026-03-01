"""Critic agent: reviews the report and returns a verdict (accept or revise with feedback)."""

from akro_agent.llm import complete
from akro_agent.models import CriticVerdict, ResearchReport


SYSTEM = """You are a critical reviewer of scholarly research reports. Given the report, output a JSON object with:
- "verdict": either "accept" or "revise". Use "revise" only if the report has substantive issues (e.g. missing counter-arguments, weak evidence discussion, unclear methodology, or sections that don't match the evidence). Use "accept" if the report is adequate and only needs confidence notes.
- "feedback": if verdict is "revise", give 2-4 clear, actionable instructions for the synthesizer (e.g. "Add a paragraph on counter-arguments in Claim 2", "Strengthen the methodology section with scope limitations"). If "accept", leave empty.
- "confidence_notes": a short paragraph (3-5 sentences) that: (1) assesses methodology and evidence base, (2) notes gaps or limitations, (3) states how confident a reader should be (strong/moderate/limited evidence), (4) optionally suggests follow-up. Use this when accepting; when revising you can still draft notes.

Be strict but fair: request revision only when the report would clearly benefit from another pass."""


def run_critic(report: ResearchReport) -> tuple[ResearchReport, CriticVerdict]:
    """Review the report and return (report with confidence_notes set when accepting), CriticVerdict."""
    report_json = report.model_dump_json(indent=2)
    user_prompt = f"Review this research report:\n\n{report_json}"
    out = complete(SYSTEM, user_prompt, response_format=CriticVerdict, temperature=0.2)
    assert isinstance(out, CriticVerdict)
    report.confidence_notes = out.confidence_notes.strip()
    return report, out


def run_critic_simple(report: ResearchReport) -> ResearchReport:
    """Legacy: add confidence_notes only (no verdict). Used when use_critic is True but no revision loop."""
    report, _ = run_critic(report)
    return report
