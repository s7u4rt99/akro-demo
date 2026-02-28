"""FastAPI server for the research API."""

import json
import sys
import tempfile
from pathlib import Path
from typing import Iterator

# Allow running without pip install -e . or PYTHONPATH
_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from akro_agent.orchestration import run_research, run_research_stream
from akro_agent.models import ResearchReport
from akro_agent.export import export_to_pdf, export_to_pptx, export_to_pptx_ai

app = FastAPI(
    title="Akro Deep Research API",
    description="Multi-agent system: Planner → Researcher → Synthesizer → Critic",
    version="0.1.0",
)


class ResearchRequest(BaseModel):
    """Request body for /research."""

    query: str = Field(..., min_length=1, description="Research query")
    use_critic: bool = Field(True, description="Whether to run the Critic agent")
    use_enrichment: bool = Field(True, description="Whether to fetch URLs and use full-page content (reduces snippet hallucination)")


class ResearchResponse(BaseModel):
    """Response: full report as JSON."""

    query: str
    summary: str
    sections: list[dict]
    sources: list[str]
    confidence_notes: str


@app.post("/research", response_model=ResearchResponse)
def research(req: ResearchRequest) -> ResearchResponse:
    """Run deep research for the given query."""
    try:
        report: ResearchReport = run_research(
            req.query, use_critic=req.use_critic, use_enrichment=req.use_enrichment
        )
        return ResearchResponse(
            query=report.query,
            summary=report.summary,
            sections=report.sections,
            sources=report.sources,
            confidence_notes=report.confidence_notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/research/stream")
def research_stream(req: ResearchRequest) -> StreamingResponse:
    """Run deep research and stream progress as Server-Sent Events (SSE)."""
    def generate() -> Iterator[str]:
        try:
            for event_type, data in run_research_stream(
                req.query,
                use_critic=req.use_critic,
                use_enrichment=req.use_enrichment,
            ):
                yield f"event: {event_type}\ndata: {data}\n\n"
        except ValueError as e:
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/research/export/pdf")
def export_pdf(req: ResearchRequest) -> FileResponse:
    """Run research and return the report as a PDF file."""
    try:
        report = run_research(
            req.query, use_critic=req.use_critic, use_enrichment=req.use_enrichment
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            path = Path(f.name)
        export_to_pdf(report, path)
        return FileResponse(
            path,
            media_type="application/pdf",
            filename="research_report.pdf",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/research/export/pptx")
def export_pptx(req: ResearchRequest) -> FileResponse:
    """Run research and return the report as a PPTX presentation."""
    try:
        report = run_research(
            req.query, use_critic=req.use_critic, use_enrichment=req.use_enrichment
        )
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            path = Path(f.name)
        export_to_pptx(report, path)
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename="research_report.pptx",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/research/export/pptx/ai")
def export_pptx_ai(req: ResearchRequest) -> FileResponse:
    """Run research and return an AI-designed PPTX (icons, layout, optional charts)."""
    try:
        report = run_research(
            req.query, use_critic=req.use_critic, use_enrichment=req.use_enrichment
        )
        with tempfile.NamedTemporaryFile(suffix=".pptx", delete=False) as f:
            path = Path(f.name)
        export_to_pptx_ai(report, path)
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename="research_report_ai.pptx",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok"}
