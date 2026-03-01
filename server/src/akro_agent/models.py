"""Pydantic models for the research pipeline."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SubQuery(BaseModel):
    """A single sub-question from the planner."""

    question: str = Field(..., description="The sub-question to research")
    priority: int = Field(1, ge=1, le=5, description="Priority 1=highest, 5=lowest")


class ResearchPlan(BaseModel):
    """Structured plan produced by the Planner agent."""

    sub_queries: list[SubQuery] = Field(
        ..., description="Ordered list of sub-questions to research"
    )
    summary: str = Field("", description="Brief summary of the research approach")


class EvidenceChunk(BaseModel):
    """A single piece of evidence from search."""

    content: str = Field(..., description="Snippet or summary of the evidence")
    source: str = Field("", description="URL or source identifier")
    sub_query: str = Field("", description="Which sub-query this evidence answers")


class ResearchEvidence(BaseModel):
    """Collected evidence for a sub-query."""

    sub_query: str
    chunks: list[EvidenceChunk] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Final synthesized report."""

    query: str = Field(..., description="Original user query")
    summary: str = Field(..., description="Executive summary")
    sections: list[dict] = Field(
        default_factory=list,
        description="Structured sections, e.g. [{'title': '...', 'content': '...', 'sources': [...]}]",
    )
    sources: list[str] = Field(default_factory=list, description="All cited sources")
    confidence_notes: str = Field(
        "", description="Optional notes on confidence or gaps (from Critic)"
    )


class CriticVerdict(BaseModel):
    """Critic output: accept report or request revision with feedback."""

    verdict: str = Field(..., description="One of: accept, revise")
    feedback: str = Field("", description="Revision instructions for the synthesizer (when verdict is 'revise')")
    confidence_notes: str = Field("", description="Paragraph for report.confidence_notes (used when accepting)")


# ---- Slide designer (AI-generated deck spec) ----


class ChartSpec(BaseModel):
    """Spec for a chart to embed on a slide."""

    chart_type: str = Field("bar", description="One of: bar, column, line, pie")
    title: str = Field("", description="Chart title")
    categories: list[str] = Field(default_factory=list, description="Category labels (e.g. x-axis)")
    series_name: str = Field("", description="Name of the data series")
    values: list[float] = Field(default_factory=list, description="Numeric values")


class ContentSlideSpec(BaseModel):
    """Spec for one content slide (from slide designer LLM)."""

    title: str = Field(..., description="Slide title")
    bullets: list[str] = Field(default_factory=list, description="3-6 bullet points; keep each short")
    layout: str = Field(
        "title_bullets",
        description="One of: title_bullets, quote, key_takeaway, two_column",
    )
    icon: str = Field(
        "📋",
        description="Emoji or icon hint: 📊 📈 📋 🔍 💡 📌 🎯 ⚠️ 📚 🔗 ✓",
    )
    chart: Optional[ChartSpec] = Field(None, description="Optional chart to show on this slide")


class SlideDeckSpec(BaseModel):
    """Full deck spec produced by the slide designer agent."""

    title_slide_title: str = Field(..., description="Main title for title slide")
    title_slide_subtitle: str = Field("Research Report", description="Subtitle")
    content_slides: list[ContentSlideSpec] = Field(
        default_factory=list,
        description="Ordered content slides (summary, then one per section, then confidence, then sources)",
    )
