# Akro Deep Research (Server)

Multi-agent system for deep research: **Planner → Researcher → Enricher (URL fetch + main-content extraction) → Synthesizer → Critic**. Given a user query, the pipeline produces a structured report with summary, sections, sources, and optional confidence notes. The enricher fetches each result URL and replaces search snippets with full-page text to reduce snippet hallucination.

**Prerequisites:** Python 3.9+ (3.10+ recommended). All commands below assume you are in the `server/` directory.

---

## What you need

### 1. OpenAI API key (required)

- **Where:** [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
- **Steps:** Sign in or create an account → **Create new secret key** → copy the key (starts with `sk-`).
- **Set it:** Put the key in a `.env` file in the project root (see below). Do not commit `.env`.

### 2. Tavily API key (required for web search)

- **Where:** [https://tavily.com](https://tavily.com) — 1,000 free API credits/month.
- **Set it:** Add `TAVILY_API_KEY=tvly-your-key` to your `.env` file.
- All agents use the same OpenAI key for the LLM.

## Setup

**All commands below must be run from the `server/` directory** (this is the project root for the Python package).

```bash
# Go into the server directory (project root)
cd server

# Use system Python to create the venv (do not run this while another venv is active)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# Install the package (from server directory)
pip install -e .

# Alternative without editable install:
# pip install -r requirements.txt
# Then run commands with: PYTHONPATH=src python cli.py "query"
# Or: PYTHONPATH=src uvicorn api.main:app --reload

# Copy env template and add your keys (in server/)
cp .env.example .env
# Edit .env and set OPENAI_API_KEY=sk-your-actual-key and TAVILY_API_KEY=tvly-your-key
```

Optional in `.env`:

- `OPENAI_MODEL` — default `gpt-4o-mini`. Use `gpt-4o` for higher quality (more cost).

## Run

### Option A: HTTP API (FastAPI)

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

- **API base:** [http://localhost:8000](http://localhost:8000)
- **Interactive docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health check:** `GET /health` — use this to verify the server is up before calling `/research`.

```bash
curl http://localhost:8000/health
```

Then run research:

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the main causes of the 2024 chip shortage?"}'
```

**Request body for `POST /research`:**

| Field             | Type   | Default | Description |
|-------------------|--------|---------|-------------|
| `query`           | string | required | Research question |
| `use_critic`      | bool   | `true`  | Run the Critic agent (accept/revise loop) |
| `use_enrichment`  | bool   | `true`  | Fetch URLs and use full-page content (reduces snippet hallucination) |
| `include_pdf`     | bool   | `false` | Include the report as base64-encoded PDF in the response (`pdf_base64`) |
| `include_pptx`    | bool   | `false` | Include the report as base64-encoded PPTX in the response (`pptx_base64`) |

**Examples with flags:**

Skip the Critic step:

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Your question", "use_critic": false}'
```

Get the report plus PDF and PPTX in the same response (decode `pdf_base64` / `pptx_base64` from base64 to get the files):

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "What caused the 2024 chip shortage?", "include_pdf": true, "include_pptx": true}'
```

Disable URL enrichment (faster, but synthesis uses search snippets only):

```bash
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Your question", "use_enrichment": false}'
```

**Stream progress (SSE):** get live events (`plan`, `search_done`, `synthesis_done`, `report`, `done`) then the full report:

```bash
curl -N -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What caused the 2024 chip shortage?"}'
```

### Option B: CLI

```bash
python cli.py "What are the main causes of the 2024 chip shortage?"
```

JSON output:

```bash
python cli.py "Your question" --json
```

Stdin:

```bash
echo "Your question" | python cli.py
```

**Export to PDF and/or PPTX:** run research and write files to a directory (default: current directory):

```bash
python cli.py "Your question" --pdf
python cli.py "Your question" --pptx --output-dir ./out
python cli.py "Your question" --pdf --pptx --output-dir ./out
```

With `--pdf --pptx`, both files use a sanitized version of the query as the base name (e.g. `What_caused_the_2024_chip_shortage.pdf`).

## Project layout

```
akro-agent/
├── README.md
├── requirements.txt
├── pyproject.toml
├── .env.example          # Copy to .env and set OPENAI_API_KEY
├── cli.py                # CLI entry
├── api/
│   └── main.py           # FastAPI app
└── src/
    └── akro_agent/
        ├── __init__.py
        ├── models.py     # Pydantic: Plan, Evidence, Report
        ├── llm.py        # OpenAI client
        ├── search.py     # Tavily search
        ├── fetch.py      # URL fetch + main-content extraction (trafilatura)
        ├── orchestration.py
        ├── export/       # Export layer: PDF, PPTX
        │   ├── __init__.py   # export_to_pdf, export_to_pptx, export_all
        │   ├── pdf_writer.py
        │   └── pptx_writer.py
        └── agents/
            ├── planner.py
            ├── researcher.py
            ├── synthesizer.py
            └── critic.py
```

## Pipeline

1. **Planner** — Turns the query into 3–6 sub-questions and a short approach summary.
2. **Researcher** — Runs web search (Tavily) per sub-question and collects snippets + URLs.
3. **Enricher** — Fetches each unique URL, extracts main content (trafilatura), and replaces snippet with full-page text when available so synthesis is grounded in real content (reduces snippet hallucination). Can be disabled with `use_enrichment: false` or `--no-enrichment`.
4. **Synthesizer** — Builds a **scholarly research report**: methodology, literature review, findings (with claim → evidence → counter-arguments → strength of evidence → assessment per major claim), discussion, implications, conclusion, and references (bibliographic formatting).
5. **Critic** — Reviews the report and returns a verdict: **accept** (add confidence notes and finish) or **revise** (with actionable feedback). The pipeline is orchestrated with **LangGraph**: if the critic says "revise", the graph loops back to the Synthesizer (up to 2 revisions) so the report can be improved before finishing.

**Report structure:** Each report includes (1) Executive summary (2–3 paragraphs); (2) Methodology; (3) Literature review; (4) For each major claim: present claim, supporting evidence with examples, counter-arguments, evaluation of evidence strength, assessment; (5) Discussion; (6) Implications; (7) Conclusion; (8) References (formatted bibliography). Sections are 2–3 paragraphs with supporting and critical perspectives where the evidence allows.

Output is JSON (API), plain text (CLI default), or exported files (PDF/PPTX).

### Export layer

- **PDF**: Full report content (query, summary, sections, confidence notes, sources) as a document.
- **PPTX**: Presentation with title slide, then **one slide per point or bullet** for summary, each section, and confidence (no truncation); then one slide per source.

**API:** run research and download a file:

```bash
curl -X POST http://localhost:8000/research/export/pdf \
  -H "Content-Type: application/json" \
  -d '{"query": "What caused the 2024 chip shortage?"}' \
  -o report.pdf

curl -X POST http://localhost:8000/research/export/pptx \
  -H "Content-Type: application/json" \
  -d '{"query": "What caused the 2024 chip shortage?"}' \
  -o report.pptx
```
