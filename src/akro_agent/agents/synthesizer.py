"""Synthesizer agent: combines evidence into a structured report."""

from __future__ import annotations

from typing import Optional

from akro_agent.llm import complete
from akro_agent.models import ResearchEvidence, ResearchReport


def _evidence_to_text(evidence_list: list[ResearchEvidence]) -> str:
    parts = []
    for ev in evidence_list:
        parts.append(f"## Sub-query: {ev.sub_query}\n")
        for c in ev.chunks:
            parts.append(f"- {c.content}\n  Source: {c.source}\n")
    return "\n".join(parts)


SYSTEM = """You are a scholarly research synthesizer. Given the original user query and collected evidence (with sources), produce a full academic-style research report as a single JSON object.

Output JSON with:
- "query": the original user query (string).
- "summary": an executive summary of 2-3 paragraphs. Summarize the main findings, the strength of evidence, and key caveats.
- "sections": a list of section objects. Each has "title" (string), "content" (string, 2-3 paragraphs for most sections), "sources" (list of source URLs used in that section).
- "sources": list of ALL unique source URLs cited anywhere in the report.
- "confidence_notes": leave as empty string "" (the critic will fill this later).

Required sections, in this order:

1. **Methodology** (2-3 paragraphs)
   - How the research was conducted (search approach, types of sources).
   - Scope and limitations (e.g. language, date range, availability of sources).
   - Any caveats about evidence quality or bias.

2. **Literature Review** (2-3 paragraphs)
   - Overview of key sources and prevailing views from the evidence.
   - Identify main schools of thought or consensus vs. debate.
   - Include concrete examples and cite sources.

3. **Findings: Major Claims and Analysis** — For each major claim or theme, include ONE section with this 5-part structure (2-3 paragraphs total per claim, with examples):
   (a) **Present the claim** clearly.
   (b) **Supporting evidence**: cite specific examples from the evidence; name sources where relevant.
   (c) **Counter-arguments / critical perspectives**: what do critics or alternative views say?
   (d) **Evaluation of strength of evidence**: rate or describe how strong the evidence is (strong / moderate / weak; explain why).
   (e) **Assessment**: brief conclusion for this claim (e.g. "Overall, the evidence suggests..." or "Remains contested because...").
   Use section titles like "Claim 1: [topic]", "Claim 2: [topic]", etc. Include at least 2-3 such claim sections if the evidence allows.

4. **Discussion** (2-3 paragraphs)
   - Synthesize findings across claims.
   - Discuss tensions, nuances, or gaps in the evidence.
   - Compare supporting and critical perspectives.

5. **Implications** (2-3 paragraphs)
   - What this means in practice, for policy, for future research, or for the reader.
   - Be specific where the evidence supports it.

6. **Conclusion** (2-3 paragraphs)
   - Restate main assessments and strength of evidence.
   - Summarize key limitations and open questions.

7. **References**
   - Format as a bibliography. For each cited source use a consistent format, e.g.:
     "Author or Site. Title or description. URL. [Accessed/retrieved if relevant.]"
   - List every URL from "sources" in this section. Use the "content" field to write the formatted references (one per line or numbered).

Write in formal, scholarly tone. Use only the provided evidence; do not invent facts. Cite sources by URL or by describing the source in the text. Be thorough: each section should feel complete with examples and balance between supporting and critical perspectives."""


def run_synthesizer(
    query: str,
    evidence_list: list[ResearchEvidence],
    revision_feedback: Optional[str] = None,
    previous_report: Optional[ResearchReport] = None,
) -> ResearchReport:
    """Synthesize evidence into a structured research report. Optionally revise using critic feedback."""
    evidence_text = _evidence_to_text(evidence_list)
    user_prompt = f"Original query: {query}\n\nCollected evidence:\n{evidence_text}"
    if revision_feedback and revision_feedback.strip():
        rev_instruction = (
            "The following revision was requested by the reviewer. Produce a revised report that addresses these points. "
            "Keep the same structure and evidence; improve only where requested.\n\n"
            f"Revision request:\n{revision_feedback.strip()}\n\n"
        )
        if previous_report:
            rev_instruction += f"Current report (for reference):\n{previous_report.model_dump_json(indent=2)}\n\n"
        user_prompt = rev_instruction + "---\n\nEvidence (unchanged):\n" + evidence_text
    out = complete(SYSTEM, user_prompt, response_format=ResearchReport, temperature=0.3)
    assert isinstance(out, ResearchReport)
    out.query = query
    return out
