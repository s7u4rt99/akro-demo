"""Critic agent: reviews the report and adds confidence notes / gaps."""

from akro_agent.llm import complete
from akro_agent.models import ResearchReport


SYSTEM = """You are a critical reviewer of scholarly research reports. Given the report, output a short paragraph (3-5 sentences) that:
1. Assesses the methodology and evidence base (e.g. source quality, balance of supporting vs. critical perspectives).
2. Notes gaps, limitations, or biases in the evidence or argument.
3. States how confident a reader should be in the main conclusions (strong / moderate / limited evidence).
4. Optionally suggests follow-up research or questions.

Write in a formal tone. Output only the paragraph text, no JSON."""


def run_critic(report: ResearchReport) -> ResearchReport:
    """Add confidence_notes to the report based on critical review."""
    report_json = report.model_dump_json(indent=2)
    user_prompt = f"Review this research report:\n\n{report_json}"
    notes = complete(SYSTEM, user_prompt, temperature=0.2)
    assert isinstance(notes, str)
    report.confidence_notes = notes.strip()
    return report
