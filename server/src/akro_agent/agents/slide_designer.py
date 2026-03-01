"""Slide designer agent: uses an LLM to turn a research report into a rich slide deck spec (icons, layout, optional charts)."""

from __future__ import annotations

from akro_agent.llm import complete
from akro_agent.models import ResearchReport, SlideDeckSpec


SYSTEM = """You are an expert presentation designer. Given a scholarly research report, produce a slide deck specification (JSON) that will be turned into a beautiful PowerPoint.

Output a JSON object with:
- "title_slide_title": the research query or a short punchy title (string).
- "title_slide_subtitle": short subtitle, e.g. "Research Report" or a one-liner (string).
- "content_slides": a list of slide objects. Each slide has:
  - "title": slide heading (string).
  - "bullets": list of 3-6 short bullet points (one line each; max ~15 words per bullet). Extract or summarize from the report; do not copy long paragraphs.
  - "layout": one of "title_bullets", "quote", "key_takeaway", "two_column". Use "key_takeaway" for conclusion or main finding slides; "quote" for a striking finding or caveat; "title_bullets" for most.
  - "icon": one emoji that fits the slide theme. Choose from: 📊 (data) 📈 (growth) 📋 (list) 🔍 (research) 💡 (insight) 📌 (key point) 🎯 (goal) ⚠️ (caution) 📚 (sources) 🔗 (links) ✓ (conclusion) 📉 (decline) 🌐 (global).
  - "chart": either null or an object with "chart_type" ("bar", "column", "line", "pie"), "title", "categories" (list of labels), "series_name", "values" (list of numbers). Only add a chart when the section clearly has comparable data (e.g. strength of evidence, pros vs cons counts, or a small comparison). Otherwise omit or set to null.

Create one content slide for: Executive Summary, then one per report section (Methodology, Literature Review, each major claim/finding, Discussion, Implications, Conclusion). If the report has "Confidence & limitations", add a slide for that. Add a final slide for References/Sources (icon 📚; bullets can be the first 5-8 source URLs or "See full references in document").

Keep the deck concise: typically 8-14 content slides. Bullets must be short and scannable."""


def run_slide_designer(report: ResearchReport) -> SlideDeckSpec:
    """Produce a slide deck spec (titles, bullets, icons, layouts, optional charts) from the report."""
    report_text = (
        f"Query: {report.query}\n\n"
        f"Summary:\n{report.summary}\n\n"
        "Sections:\n"
    )
    for sec in report.sections:
        report_text += f"\n## {sec.get('title', 'Section')}\n{sec.get('content', '')}\n"
    if report.confidence_notes:
        report_text += f"\n## Confidence & limitations\n{report.confidence_notes}\n"
    if report.sources:
        report_text += "\n## Sources\n" + "\n".join(report.sources[:15]) + "\n"

    out = complete(
        SYSTEM,
        f"Turn this research report into a slide deck spec (JSON):\n\n{report_text}",
        response_format=SlideDeckSpec,
        temperature=0.4,
    )
    assert isinstance(out, SlideDeckSpec)
    return out
