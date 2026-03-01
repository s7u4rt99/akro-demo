"""Reviser agent: updates an existing report based on user instruction and optional critic feedback."""

from __future__ import annotations

import json
import logging
from typing import Optional

from pydantic import ValidationError

from akro_agent.llm import complete
from akro_agent.models import ResearchReport

logger = logging.getLogger(__name__)


SYSTEM = """You are a research report editor. You will be given:
1. The current research report (as JSON).
2. The user's instruction for how to improve or change the report (e.g. "improve the methodology section", "add a limitations paragraph", "strengthen the conclusion").
3. Optional: feedback from a critic (suggestions for revision).

Your task: Produce a revised report as a single JSON object with the same schema:
- "query": string (keep the same).
- "summary": string (update if the instruction affects the summary).
- "sections": list of objects, each with "title" (string), "content" (string), "sources" (list of URLs used in that section). Keep or reorder sections; edit content only where the instruction or critic asks. Do not invent new evidence or sources; only rephrase, expand, or restructure existing content. You may add short new paragraphs (e.g. limitations) if the instruction asks.
- "sources": list of ALL unique source URLs cited in the report (preserve existing; add only if you cite a new one from the report text).
- "confidence_notes": string (update if the instruction or critic touches on confidence/limitations).

Rules:
- Preserve the report structure (Methodology, Literature Review, Findings, Discussion, Implications, Conclusion, References) unless the instruction asks to change it.
- Do not make up facts or sources. Only edit and reorganize what is already in the report.
- Do not duplicate sections or content. To expand a section (e.g. "double the executive summary"), add new sentences or paragraphs—do not paste the same block twice. There must be exactly one executive summary (in the "summary" field); do not add an "Executive Summary" section to the sections list.
- Output valid JSON only (no markdown, no code fence)."""


def run_reviser(
    report: ResearchReport,
    user_instruction: str,
    critic_feedback: Optional[str] = None,
) -> ResearchReport:
    """Produce a revised report from the current report and the user's instruction (and optional critic feedback)."""
    logger.info("Reviser agent: starting (report sections=%s, instruction=%s)", len(report.sections), (user_instruction or "")[:60])
    report_json = report.model_dump_json(indent=2)
    parts = [
        "Current report:\n" + report_json,
        "\nUser instruction: " + user_instruction.strip(),
    ]
    if critic_feedback and critic_feedback.strip():
        parts.append("\nCritic feedback to address:\n" + critic_feedback.strip())
    parts.append("\n\nOutput the revised report as a single JSON object with keys: query, summary, sections, sources, confidence_notes.")
    user_prompt = "\n".join(parts)

    raw = complete(SYSTEM, user_prompt, response_format=None, temperature=0.3)
    logger.info("Reviser agent: LLM complete, parsing response")
    content = raw if isinstance(raw, str) else str(raw)
    if "```" in content:
        for start in ("```json", "```"):
            if start in content:
                content = content.split(start, 1)[-1].rsplit("```", 1)[0].strip()
    data = json.loads(content)
    if not isinstance(data, dict):
        data = report.model_dump()
    data["query"] = data.get("query") or report.query
    data["summary"] = data.get("summary") or report.summary
    data["sections"] = data.get("sections") if isinstance(data.get("sections"), list) else report.sections
    data["sources"] = data.get("sources") if isinstance(data.get("sources"), list) else report.sources
    data["confidence_notes"] = data.get("confidence_notes") or report.confidence_notes
    try:
        out = ResearchReport.model_validate(data)
    except ValidationError:
        data["sections"] = [x if isinstance(x, dict) else {} for x in data["sections"]]
        data["sources"] = [str(x) for x in data["sources"]]
        out = ResearchReport.model_validate(data)
    logger.info("Reviser agent: done (revised sections=%s)", len(out.sections))
    return out
