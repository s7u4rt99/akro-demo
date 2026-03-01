"""PDF export: report content as a document."""

from __future__ import annotations

import html
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from akro_agent.models import ResearchReport


def _escape(s: str) -> str:
    """Escape for ReportLab Paragraph (XML-style markup). Newlines -> <br/>."""
    s = html.escape(s or "")
    return s.replace("\n", "<br/>")


def write_pdf(report: ResearchReport, path: str | Path) -> None:
    """Write report content to a PDF file."""
    path = Path(path)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=12,
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=14,
        spaceAfter=8,
    )
    body_style = styles["Normal"]
    ref_style = ParagraphStyle(
        "References",
        parent=styles["Normal"],
        fontSize=9,
        leftIndent=12,
        rightIndent=12,
        spaceAfter=4,
    )

    flowables = []

    # Title (query)
    flowables.append(Paragraph(_escape(report.query), title_style))
    flowables.append(Spacer(1, 0.2 * inch))

    # Summary
    flowables.append(Paragraph("Summary", heading_style))
    flowables.append(Paragraph(_escape(report.summary), body_style))
    flowables.append(Spacer(1, 0.15 * inch))

    # Sections
    for sec in report.sections:
        title = sec.get("title") or "Section"
        content = sec.get("content") or ""
        title_lower = title.strip().lower()
        # Use top-level report.sources for References/Sources (same as frontend) so refs always appear
        if title_lower == "references" or title_lower == "sources":
            flowables.append(Paragraph(_escape(title), heading_style))
            if report.sources:
                for src in report.sources:
                    flowables.append(Paragraph(_escape(src), ref_style))
                    flowables.append(Spacer(1, 0.04 * inch))
            elif content:
                flowables.append(Paragraph(_escape(content), ref_style))
        else:
            flowables.append(Paragraph(_escape(title), heading_style))
            flowables.append(Paragraph(_escape(content), body_style))
        flowables.append(Spacer(1, 0.1 * inch))

    # Confidence notes
    if report.confidence_notes:
        flowables.append(Paragraph("Confidence & limitations", heading_style))
        flowables.append(Paragraph(_escape(report.confidence_notes), body_style))
        flowables.append(Spacer(1, 0.15 * inch))

    doc.build(flowables)
