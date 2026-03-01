# Akro Agent

**A multi-agent system that does deep research from a single query.** Submit a question, and Akro plans sub-questions, searches the web, enriches results with full-page content, synthesizes a structured research report, and optionally revises it with a critic—then delivers the report as text, PDF, and PowerPoint.

---

## Try it

**Live app:** [**akro.stuartlong.org**](https://akro.stuartlong.org)

Use the deployed app to run a research query, preview the report, download PDF/PPTX, and chat with the research via follow-up questions—no local setup required.

---

## What it does

1. **You ask** — Enter a research question (e.g. *“What are the main causes of the 2024 chip shortage?”*).
2. **Akro plans** — A Planner agent breaks the query into 3–6 sub-questions and a short approach.
3. **Akro researches** — A Researcher runs web search (Tavily) per sub-question and collects snippets and URLs.
4. **Akro enriches** — An Enricher fetches each URL and extracts main content (trafilatura), so synthesis is grounded in real pages instead of snippets alone.
5. **Akro synthesizes** — A Synthesizer produces a scholarly report: methodology, literature review, findings (claim → evidence → counter-arguments → strength → assessment), discussion, implications, conclusion, and references.
6. **Akro criticizes (optional)** — A Critic reviews the report and either accepts it (with confidence notes) or asks for revisions; the pipeline can loop back to the Synthesizer up to 2 times.
7. **You get** — A full report (JSON/text), plus optional PDF and PPTX. The frontend shows a preview and download links; you can also chat with the research for Q&A.

The pipeline is orchestrated with **LangGraph**; the backend exposes a **FastAPI** HTTP API and a **CLI**, and the **Next.js** frontend provides a UI with streaming progress and chat.

---

## Architecture at a glance

| Layer        | Tech           | Purpose |
|-------------|----------------|--------|
| **Backend** | FastAPI (Python) | Research API, chat, PDF/PPTX export; runs on port 8000 |
| **Frontend**| Next.js        | Research UI, report preview, PDF/PPTX download, chat; runs on port 3000 |
| **Agents**  | OpenAI + LangGraph | Planner, Researcher, Enricher, Synthesizer, Critic |
| **Search**  | Tavily         | Web search with retries and optional deep results |

- **API:** `POST /research` (run research, optional PDF/PPTX in response), `POST /research/stream` (SSE progress + report), `POST /chat` (streamed Q&A), `GET /health`.
- **Output:** Reports are written to `server/out/` (PDF/PPTX) and can be returned as base64 in the API response for preview and download.

---

## Quick start (local)

**Prerequisites:** Python 3.10+, Node.js 18+, [OpenAI API key](https://platform.openai.com/api-keys), [Tavily API key](https://tavily.com) (free tier available).

1. **Backend** (from `server/`):
   ```bash
   cd server
   python3 -m venv .venv && source .venv/bin/activate
   pip install -e .
   cp .env.example .env   # set OPENAI_API_KEY and TAVILY_API_KEY
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```
2. **Frontend** (from `frontend/`):
   ```bash
   cd frontend
   npm install
   cp .env.example .env   # optional: set NEXT_PUBLIC_BACKEND_URL if backend isn’t at localhost:8000
   npm run dev
   ```
3. Open [http://localhost:3000](http://localhost:3000), enter a query, and run research. Use **Chat** for follow-up questions.

For step-by-step setup, API details, and CLI usage, see:

- **[server/README.md](server/README.md)** — Backend setup, run, API, CLI, pipeline, and export.
- **[frontend/README.md](frontend/README.md)** — Frontend setup, run, and how to use the UI.

---

## Config summary

| What | Where | Variable | Example |
|------|--------|----------|--------|
| Backend URL (used by frontend) | `frontend/.env` | `NEXT_PUBLIC_BACKEND_URL` | `http://localhost:8000` |
| OpenAI (research + chat) | `server/.env` | `OPENAI_API_KEY` | `sk-...` |
| Web search | `server/.env` | `TAVILY_API_KEY` | `tvly-...` |
| Optional model | `server/.env` | `OPENAI_MODEL` | `gpt-4o-mini` |

---

## Output files

When research runs, the backend writes:

- `server/out/<query_slug>.pdf`
- `server/out/<query_slug>.pptx`

The same files can be returned in the `/research` JSON as `pdf_base64` and `pptx_base64` so the frontend can preview and offer download without extra requests.
