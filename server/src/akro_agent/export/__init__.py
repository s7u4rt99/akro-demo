"""
Export layer: render ResearchReport to PDF and PPTX.
"""

from __future__ import annotations

from pathlib import Path
from akro_agent.models import ResearchReport

from akro_agent.export.pdf_writer import write_pdf
from akro_agent.export.pptx_writer import write_pptx, write_pptx_from_spec


def export_to_pdf(report: ResearchReport, path: str | Path) -> Path:
    """Write report content to a PDF file. Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_pdf(report, path)
    return path


def export_to_pptx(report: ResearchReport, path: str | Path) -> Path:
    """Write report as a presentation (title, summary, sections, sources). Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_pptx(report, path)
    return path


def export_to_pptx_ai(report: ResearchReport, path: str | Path) -> Path:
    """Use the slide designer LLM to build a deck spec (icons, layout, optional charts), then write PPTX. Returns the path."""
    from akro_agent.agents.slide_designer import run_slide_designer
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    spec = run_slide_designer(report)
    write_pptx_from_spec(spec, path)
    return path


def export_all(
    report: ResearchReport,
    output_dir: str | Path,
    *,
    base_name: str | None = None,
    use_ai_slides: bool = False,
) -> dict[str, Path]:
    """
    Export report to both PDF and PPTX in output_dir.
    base_name: optional stem for files (default: sanitized query).
    use_ai_slides: if True, PPTX is built via the slide designer LLM (icons, charts).
    Returns dict with keys "pdf" and "pptx" and Path values.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if base_name is None:
        base_name = _sanitize_filename(report.query) or "research_report"
    pdf_path = output_dir / f"{base_name}.pdf"
    pptx_path = output_dir / f"{base_name}.pptx"
    export_to_pdf(report, pdf_path)
    if use_ai_slides:
        export_to_pptx_ai(report, pptx_path)
    else:
        export_to_pptx(report, pptx_path)
    return {"pdf": pdf_path, "pptx": pptx_path}


def _sanitize_filename(s: str, max_len: int = 80) -> str:
    """Make a safe filename stem from the query."""
    safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in s)
    safe = safe.strip().replace(" ", "_")
    while "__" in safe:
        safe = safe.replace("__", "_")
    return safe[:max_len] or "research_report"
