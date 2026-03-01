"""FastAPI server for the research API."""

import base64
import difflib
import io
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Allow running without pip install -e . or PYTHONPATH
_root = Path(__file__).resolve().parent.parent
_src = _root / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

# Load .env so OPENAI_API_KEY etc. are available for /chat and other endpoints
try:
    from dotenv import load_dotenv
    load_dotenv(_root / ".env")
except ImportError:
    pass

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from openai import OpenAI
from pydantic import BaseModel, Field

from akro_agent.orchestration import run_research, run_research_stream
from akro_agent.models import ResearchReport
from akro_agent.export import export_to_pdf, export_to_pptx, export_to_pptx_ai
from akro_agent.agents.critic import run_critic
from akro_agent.agents.reviser import run_reviser

# Output directory for PDF/PPTX (always written when generating).
# On Vercel the filesystem is read-only except /tmp, so use a temp dir there.
if os.environ.get("VERCEL"):
    OUT_DIR = Path("/tmp") / "akro-out"
else:
    OUT_DIR = _root / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _slug(s: str, max_len: int = 80) -> str:
    """Safe filename from query: alphanumeric and underscores only."""
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[-\s]+", "_", s).strip("_")
    return (s[:max_len] if len(s) > max_len else s) or "report"


def _extract_text_from_pdf_base64(pdf_base64: str, max_chars: int = 50_000) -> str:
    """Extract text from a base64-encoded PDF. Returns truncated string if over max_chars."""
    try:
        from pypdf import PdfReader
        raw = base64.b64decode(pdf_base64, validate=True)
        reader = PdfReader(io.BytesIO(raw))
        parts = []
        n = 0
        for page in reader.pages:
            if n >= max_chars:
                break
            text = (page.extract_text() or "").strip()
            if text:
                parts.append(text)
                n += len(text)
        out = "\n\n".join(parts)
        if len(out) > max_chars:
            out = out[:max_chars] + "\n\n[Document truncated for length.]"
        return out.strip()
    except Exception as e:
        import logging
        logging.warning("PDF text extraction failed: %s", e)
        return ""


def _get_pdf_context_via_openai(pdf_base64: str, user_query: str, max_context_chars: int = 12_000) -> str:
    """Send the full PDF to OpenAI Responses API and return extracted/summarized context for research."""
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        model = os.environ.get("OPENAI_MODEL_PDF", "gpt-4o")
        file_data = (
            pdf_base64 if pdf_base64.startswith("data:") else f"data:application/pdf;base64,{pdf_base64}"
        )
        prompt = (
            f"The user is running research with this query: \"{user_query}\"\n\n"
            "They have uploaded a PDF. Extract and summarize the key content: main topics, claims, definitions, evidence, and any questions the document raises. "
            "Output plain text suitable as research context (no markdown). Keep under 12000 characters."
        )
        input_items = [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_file", "file_data": file_data, "filename": "uploaded.pdf"},
                    {"type": "input_text", "text": prompt},
                ],
            }
        ]
        response = client.responses.create(
            model=model,
            input=input_items,
        )
        text = getattr(response, "output_text", None) or ""
        if not isinstance(text, str):
            text = str(text) if text else ""
        return (text[:max_context_chars] + "\n\n[Truncated for length.]") if len(text) > max_context_chars else text
    except Exception as e:
        logger.warning("PDF context via OpenAI failed, falling back to pypdf: %s", e)
        return ""


def _research_query_with_pdf_context(query: str, pdf_base64: Optional[str]) -> str:
    """If pdf_base64 is set, send full PDF to OpenAI for context and prepend to query; else return query."""
    if not pdf_base64:
        return query
    doc_text = _get_pdf_context_via_openai(pdf_base64, query)
    if not doc_text:
        doc_text = _extract_text_from_pdf_base64(pdf_base64)
    if not doc_text:
        return query
    return f"{query}\n\n[Context from uploaded PDF]:\n{doc_text}"


app = FastAPI(
    title="Akro Deep Research API",
    description="Multi-agent system: Planner → Researcher → Synthesizer → Critic",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    """Request body for /research."""

    query: str = Field(..., min_length=1, description="Research query")
    use_critic: bool = Field(True, description="Whether to run the Critic agent")
    use_enrichment: bool = Field(True, description="Whether to fetch URLs and use full-page content (reduces snippet hallucination)")
    include_pdf: bool = Field(False, description="If true, response includes report as base64-encoded PDF")
    include_pptx: bool = Field(False, description="If true, response includes report as base64-encoded PPTX")
    use_ai_slides: bool = Field(False, description="If include_pptx is true, use AI-designed slides (icons, layout)")
    pdf_base64: Optional[str] = Field(None, description="Optional uploaded PDF (base64); full PDF is sent to OpenAI for context, with pypdf fallback")


class ResearchResponse(BaseModel):
    """Response: full report as JSON; optionally PDF and PPTX as base64."""

    query: str
    summary: str
    sections: list[dict]
    sources: list[str]
    confidence_notes: str
    pdf_base64: Optional[str] = Field(None, description="Report as PDF (base64), present when include_pdf was true")
    pptx_base64: Optional[str] = Field(None, description="Report as PPTX (base64), present when include_pptx was true")


@app.post("/research", response_model=ResearchResponse)
def research(req: ResearchRequest) -> ResearchResponse:
    """Run deep research for the given query. Always generates PDF and PPTX, writes to server/out, and includes them in the response."""
    try:
        query = _research_query_with_pdf_context(req.query, req.pdf_base64)
        report: ResearchReport = run_research(
            query, use_critic=req.use_critic, use_enrichment=req.use_enrichment
        )
        # Show only the original user query to users (never the internal "[Context from uploaded PDF]" text)
        report.query = req.query
        # Always generate PDF and PPTX; write to server/out and include base64 in response
        slug = _slug(req.query)
        pdf_path = OUT_DIR / f"{slug}.pdf"
        pptx_path = OUT_DIR / f"{slug}.pptx"
        export_to_pdf(report, pdf_path)
        if req.use_ai_slides:
            export_to_pptx_ai(report, pptx_path)
        else:
            export_to_pptx(report, pptx_path)
        pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
        pptx_b64 = base64.b64encode(pptx_path.read_bytes()).decode("ascii")
        return ResearchResponse(
            query=report.query,
            summary=report.summary,
            sections=report.sections,
            sources=report.sources,
            confidence_notes=report.confidence_notes,
            pdf_base64=pdf_b64,
            pptx_base64=pptx_b64,
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
            query = _research_query_with_pdf_context(req.query, req.pdf_base64)
            for event_type, data in run_research_stream(
                query,
                use_critic=req.use_critic,
                use_enrichment=req.use_enrichment,
            ):
                if event_type == "report":
                    payload = json.loads(data)
                    payload["query"] = req.query
                    data = json.dumps(payload)
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
        query = _research_query_with_pdf_context(req.query, req.pdf_base64)
        report = run_research(
            query, use_critic=req.use_critic, use_enrichment=req.use_enrichment
        )
        report.query = req.query
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
        query = _research_query_with_pdf_context(req.query, req.pdf_base64)
        report = run_research(
            query, use_critic=req.use_critic, use_enrichment=req.use_enrichment
        )
        report.query = req.query
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
        query = _research_query_with_pdf_context(req.query, req.pdf_base64)
        report = run_research(
            query, use_critic=req.use_critic, use_enrichment=req.use_enrichment
        )
        report.query = req.query
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


class ReviseRequest(BaseModel):
    """Request body for revising an existing report (e.g. from chat)."""

    report: dict = Field(..., description="Current report as JSON (query, summary, sections, sources, confidence_notes)")
    user_instruction: str = Field(..., min_length=1, description="How to improve or change the report")
    run_critic: bool = Field(True, description="If true, run critic first and pass feedback to the reviser")


class ReviseResponse(BaseModel):
    report: dict = Field(..., description="Revised report as JSON")
    pdf_base64: str = Field(..., description="Revised report as PDF (base64)")
    pptx_base64: str = Field(..., description="Revised report as PPTX (base64)")


@app.post("/research/revise", response_model=ReviseResponse)
def research_revise(req: ReviseRequest) -> ReviseResponse:
    """Revise an existing report using the critic (optional) and reviser, then regenerate PDF and PPTX."""
    try:
        revised_report, pdf_b64, pptx_b64 = _run_revise_and_export(
            req.report, req.user_instruction, use_critic=req.run_critic
        )
        return ReviseResponse(
            report=revised_report,
            pdf_base64=pdf_b64,
            pptx_base64=pptx_b64,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health() -> dict:
    """Health check."""
    return {"status": "ok"}


# ---- Chat (for frontend research Q&A) ----

class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: Optional[str] = Field(None, description="text content")
    parts: Optional[list[dict]] = Field(None, description="AI SDK parts (type + text)")


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., description="Conversation history")
    context: Optional[dict] = Field(None, description="Optional { query, report } for research context")
    attachment_base64: Optional[str] = Field(None, description="Optional uploaded PDF (base64); passed to OpenAI as input_file when set")
    attachment_filename: Optional[str] = Field(None, description="Optional filename for the attached PDF (e.g. for display)")


def _message_text(m: ChatMessage) -> str:
    """Extract plain text from a chat message."""
    text = m.content or ""
    if not text and m.parts:
        for p in m.parts or []:
            if isinstance(p, dict) and p.get("type") == "text" and "text" in p:
                text += p["text"]
    return text.strip()


def _build_responses_input(
    messages: list[ChatMessage],
    context: Optional[dict],
    attachment_base64: Optional[str],
    attachment_filename: Optional[str],
) -> tuple[Optional[str], list[dict[str, Any]]]:
    """Build (instructions, input) for OpenAI Responses API. PDF is sent as input_file."""
    parts = [
        "You are a research assistant helping the user understand and discuss a research report."
    ]
    if context:
        q = context.get("query", "")
        r = (context.get("report") or "")[:8000]
        parts.append(f'The original research question was: "{q}"')
        parts.append(f"Here is the research report for context (truncated):\n{r}")
    parts.append(
        "Answer the user's questions about this research and any attached document. Be concise, helpful, and accurate."
    )
    instructions = "\n\n".join(parts)
    input_items: list[dict[str, Any]] = []
    for i, m in enumerate(messages):
        text = _message_text(m)
        role = "user" if m.role == "user" else "assistant"
        is_last_user = (
            m.role == "user"
            and i == len(messages) - 1
            and attachment_base64
        )
        if is_last_user and attachment_base64:
            logger.info(
                "Building Responses input with PDF attachment: filename=%s, base64_len=%s",
                attachment_filename or "attachment.pdf",
                len(attachment_base64),
            )
        if m.role == "assistant":
            if text:
                input_items.append(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": text}],
                    }
                )
            continue
        if m.role == "user":
            content: list[dict[str, Any]] = []
            if is_last_user and attachment_base64:
                file_data = (
                    attachment_base64
                    if attachment_base64.startswith("data:")
                    else f"data:application/pdf;base64,{attachment_base64}"
                )
                content.append(
                    {
                        "type": "input_file",
                        "file_data": file_data,
                        "filename": attachment_filename or "attachment.pdf",
                    }
                )
            if text:
                content.append({"type": "input_text", "text": text})
            if content:
                input_items.append({"type": "message", "role": "user", "content": content})
    return (instructions, input_items)


def _messages_to_openai(
    messages: list[ChatMessage],
    context: Optional[dict],
    attachment_text: Optional[str] = None,
    attachment_present_but_empty: bool = False,
) -> list[dict[str, str]]:
    """Convert frontend message format to OpenAI API format."""
    system_content = None
    if context or attachment_text or attachment_present_but_empty:
        parts = [
            "You are a research assistant helping the user understand and discuss a research report."
        ]
        if context:
            q = context.get("query", "")
            r = (context.get("report") or "")[:8000]
            parts.append(f'The original research question was: "{q}"')
            parts.append(f"Here is the research report for context (truncated):\n{r}")
        if attachment_text:
            parts.append(
                "The user has attached a PDF in this conversation. The following is the full text of that attached document. "
                "When they ask about 'this report', 'the attached document', 'the PDF', or 'the related report', answer using the content below."
            )
            parts.append(f"Attached document text:\n{attachment_text[:12000]}")
        elif attachment_present_but_empty:
            parts.append(
                "The user attached a PDF but its text could not be extracted (e.g. scanned/image PDF). "
                "Tell them you could not read the PDF content and suggest they paste key excerpts or use a text-based PDF."
            )
        parts.append("Answer the user's questions about this research and any attached document. Be concise, helpful, and accurate.")
        system_content = "\n\n".join(parts)
    out: list[dict[str, str]] = []
    if system_content:
        out.append({"role": "system", "content": system_content})
    for m in messages:
        role = "user" if m.role == "user" else "assistant"
        text = _message_text(m)
        if text:
            out.append({"role": role, "content": text})
    return out


GUARDRAIL_OFF_TOPIC_MESSAGE = (
    "Please keep your questions focused on this research report and its topic. "
    "I can only answer questions about the research content, findings, and methodology."
)

REVISION_TRIGGERS = (
    "improve", "revise", "update the report", "change the", "add a section",
    "fix the", "strengthen", "expand", "edit the report", "tweak", "rework",
    "add limitations", "improve the", "revise the", "update the", "update report",
    "edit report", "change report", "modify the report", "redo the", "improve report",
    "make the report", "add a paragraph", "add section", "expand the",
    "executive summary", "improve the summary", "better summary",
)


def _is_revision_request(message: str) -> bool:
    """Heuristic: True if the user message looks like a request to improve/revise the report."""
    if not message or not message.strip():
        return False
    lower = message.lower().strip()
    # Short messages like "improve it" or "update the report" should still trigger
    if len(lower) < 5:
        return False
    return any(trigger in lower for trigger in REVISION_TRIGGERS)


def _report_dict_to_markdown(report_dict: dict) -> str:
    """Convert report dict to markdown (same structure as frontend buildReportMarkdown)."""
    query = report_dict.get("query") or ""
    summary = report_dict.get("summary") or ""
    sections = report_dict.get("sections") or []
    sources = report_dict.get("sources") or []
    confidence_notes = report_dict.get("confidence_notes") or ""
    parts = [f"# {query}\n\n## Executive Summary\n\n{summary}\n\n"]
    for sec in sections:
        title = (sec.get("title") or "Section") if isinstance(sec, dict) else "Section"
        if title.strip().lower() == "executive summary":
            continue
        content = (sec.get("content") or "").strip() if isinstance(sec, dict) else ""
        if "reference" in title.lower() or "source" in title.lower():
            content = "\n".join(f"- {u}" for u in (sources if sources else content.split("\n")))
        parts.append(f"## {title}\n\n{content}\n\n")
    if confidence_notes:
        parts.append(f"## Confidence notes\n\n{confidence_notes}\n\n")
    return "".join(parts)


def _compute_report_diff(old_report_dict: dict, new_report_dict: dict, max_diff_lines: int = 1500) -> str:
    """Return unified diff of old vs new report (markdown). Truncated to max_diff_lines."""
    old_md = _report_dict_to_markdown(old_report_dict)
    new_md = _report_dict_to_markdown(new_report_dict)
    old_lines = old_md.splitlines(keepends=True)
    new_lines = new_md.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile="previous",
            tofile="revised",
            lineterm="",
        )
    )
    if len(diff_lines) > max_diff_lines:
        diff_lines = diff_lines[:max_diff_lines] + [f"\n... diff truncated (total {len(diff_lines)} lines)\n"]
    return "\n".join(diff_lines)


def _run_revise_and_export(report_dict: dict, user_instruction: str, use_critic: bool = True) -> tuple[dict, str, str]:
    """Run critic (optional) + reviser, export PDF/PPTX, return (revised_report_dict, pdf_base64, pptx_base64)."""
    logger.info("Reviser: validating report (sections=%s)", len(report_dict.get("sections", [])))
    current = ResearchReport.model_validate(report_dict)
    critic_feedback = None
    if use_critic:
        logger.info("Reviser: running critic...")
        _, verdict = run_critic(current)
        logger.info("Reviser: critic done (verdict=%s, feedback_len=%s)", verdict.verdict, len(verdict.feedback or ""))
        if verdict.verdict == "revise" and (verdict.feedback or "").strip():
            critic_feedback = verdict.feedback.strip()
        if verdict.confidence_notes and verdict.confidence_notes.strip():
            current.confidence_notes = verdict.confidence_notes.strip()
    logger.info("Reviser: running reviser (instruction_len=%s, has_critic_feedback=%s)...", len(user_instruction), bool(critic_feedback))
    revised = run_reviser(current, user_instruction, critic_feedback=critic_feedback)
    logger.info("Reviser: reviser done (sections=%s)", len(revised.sections))
    slug = _slug(revised.query) + "_revised"
    pdf_path = OUT_DIR / f"{slug}.pdf"
    pptx_path = OUT_DIR / f"{slug}.pptx"
    logger.info("Reviser: exporting PDF to %s", pdf_path)
    export_to_pdf(revised, pdf_path)
    logger.info("Reviser: exporting PPTX to %s", pptx_path)
    export_to_pptx(revised, pptx_path)
    pdf_b64 = base64.b64encode(pdf_path.read_bytes()).decode("ascii")
    pptx_b64 = base64.b64encode(pptx_path.read_bytes()).decode("ascii")
    logger.info("Reviser: export done (pdf_len=%s, pptx_len=%s)", len(pdf_b64), len(pptx_b64))
    return revised.model_dump(), pdf_b64, pptx_b64


def _is_on_topic(client: OpenAI, model: str, research_query: str, user_message: str) -> bool:
    """Return True if the user message is about the research topic; False if off-topic."""
    if not user_message.strip():
        return False
    prompt = (
        "You are a guardrail. Given the research topic and the user's message, answer ONLY with exactly one word: yes or no.\n\n"
        "Answer 'yes' only if the user is asking a question or making a request that is clearly about the research topic or the research report (e.g. clarification, summary, details, implications).\n\n"
        "Answer 'no' if: the user is asking about something unrelated, giving instructions unrelated to the research, trying to change topic, asking you to pretend to be something else, or not asking about the report at all.\n\n"
        f"Research topic: {research_query}\n\n"
        f"User message: {user_message}\n\n"
        "Answer (yes or no):"
    )
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        answer = (resp.choices[0].message.content or "").strip().lower()
        return answer.startswith("yes")
    except Exception:
        return True  # On failure, allow the message through


@app.post("/chat")
def chat(req: ChatRequest) -> StreamingResponse:
    """Stream chat completion (for research follow-up Q&A). Uses OPENAI_API_KEY. When a PDF is attached, passes it to OpenAI via Responses API (input_file)."""
    def generate() -> Iterator[str]:
        try:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            chat_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
            logger.info(
                "Chat request: messages=%s, has_attachment=%s, attachment_filename=%s",
                len(req.messages),
                bool(req.attachment_base64),
                req.attachment_filename,
            )
            if req.attachment_base64:
                logger.info(
                    "Attachment base64 length=%s, starts_with_data_uri=%s",
                    len(req.attachment_base64),
                    req.attachment_base64.startswith("data:"),
                )
            # When attachment present, use Responses API (pass entire PDF); vision model required for PDF
            if req.attachment_base64:
                model = os.environ.get("OPENAI_MODEL_PDF", "gpt-4o")
                logger.info("Using Responses API with PDF, model=%s", model)
                instructions, input_items = _build_responses_input(
                    req.messages,
                    req.context,
                    req.attachment_base64,
                    req.attachment_filename,
                )
                logger.info(
                    "Responses input built: input_items=%s, instructions_len=%s",
                    len(input_items),
                    len(instructions or ""),
                )
                if not input_items:
                    logger.warning("No input items after building Responses input")
                    yield f"event: error\ndata: {json.dumps({'detail': 'No user message'})}\n\n"
                    return
                logger.info("Calling client.responses.stream(...)")
                with client.responses.stream(
                    model=model,
                    input=input_items,
                    instructions=instructions or "",
                ) as stream:
                    chunk_count = 0
                    for event in stream:
                        event_type = getattr(event, "type", None) or ""
                        if "output_text" in str(event_type) and "delta" in str(event_type):
                            delta = getattr(event, "delta", None)
                            if delta:
                                chunk_count += 1
                                yield f"event: message\ndata: {json.dumps({'content': delta})}\n\n"
                    logger.info("Responses stream finished, chunk_count=%s", chunk_count)
                return
            # No attachment: check for report revision request (context.report_full + revision-like message)
            last_user_text = None
            for m in reversed(req.messages):
                if m.role == "user":
                    last_user_text = _message_text(m)
                    break
            report_full = req.context.get("report_full") if req.context else None
            has_report_full = report_full and isinstance(report_full, dict)
            is_revision = last_user_text and _is_revision_request(last_user_text)
            logger.info(
                "Revision check: has_report_full=%s, last_user_text_len=%s, is_revision=%s",
                has_report_full,
                len(last_user_text) if last_user_text else 0,
                is_revision,
            )
            if has_report_full and is_revision:
                logger.info("Report revision: starting (user_instruction=%s)", (last_user_text or "")[:80])
                # 1. Agent tells user they will update the report
                intro_msg = "I'll update the report based on your feedback. One moment..."
                yield f"event: message\ndata: {json.dumps({'content': intro_msg})}\n\n"
                # 2. Signal that update is in progress (frontend can show "Updating report...")
                yield "event: report_updating\ndata: {}\n\n"
                try:
                    revised_report, pdf_b64, pptx_b64 = _run_revise_and_export(
                        report_full, last_user_text, use_critic=True
                    )
                    logger.info("Report revision: completed successfully (report sections=%s)", len(revised_report.get("sections", [])))
                    diff_text = _compute_report_diff(report_full, revised_report)
                    payload = {
                        "report": revised_report,
                        "pdf_base64": pdf_b64,
                        "pptx_base64": pptx_b64,
                        "diff": diff_text,
                    }
                    yield f"event: report_updated\ndata: {json.dumps(payload)}\n\n"
                    yield f"event: message\ndata: {json.dumps({'content': 'The report, PDF, and PPTX have been updated. You can see the changes below and download the new files.'})}\n\n"
                except Exception as e:
                    logger.exception("Report revision failed: %s", e)
                    err_msg = "I couldn't update the report: " + str(e) + ". Please try again or rephrase your request."
                    yield f"event: message\ndata: {json.dumps({'content': err_msg})}\n\n"
                return

            # Normal chat: use Chat Completions with extracted text in system message
            attachment_text = None
            attachment_present_but_empty = False
            messages = _messages_to_openai(
                req.messages, req.context, attachment_text, attachment_present_but_empty
            )
            if not any(m.get("role") == "user" for m in messages):
                yield f"event: error\ndata: {json.dumps({'detail': 'No user message'})}\n\n"
                return

            if req.context and req.context.get("query"):
                last_user_msg = None
                for m in reversed(req.messages):
                    if m.role == "user":
                        last_user_msg = _message_text(m)
                        break
                # Don't guardrail revision requests (e.g. "improve the executive summary") — they're about the report
                if (
                    last_user_msg
                    and not _is_revision_request(last_user_msg)
                    and not _is_on_topic(
                        client, chat_model, req.context["query"], last_user_msg
                    )
                ):
                    yield f"event: message\ndata: {json.dumps({'content': GUARDRAIL_OFF_TOPIC_MESSAGE})}\n\n"
                    return

            stream = client.chat.completions.create(
                model=chat_model,
                messages=messages,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield f"event: message\ndata: {json.dumps({'content': chunk.choices[0].delta.content})}\n\n"
        except Exception as e:
            logger.exception("Chat request failed: %s", e)
            yield f"event: error\ndata: {json.dumps({'detail': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
