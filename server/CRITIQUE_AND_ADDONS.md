# Critique & add-ons (for interview discussion)

Use this as a cheat sheet when they ask “how would you improve this?” or “what would you add?”.

---

## Self-critique: what’s weak or could be better

1. **No tests**  
   - Agents and orchestration are testable (pure functions + injected LLM/search), but there are no unit or integration tests.  
   - **If asked:** “I’d add pytest tests that mock the LLM and Tavily, and assert on plan shape, evidence structure, and report schema.”

2. **Search fails open**  
   - If Tavily fails after retries, we return `[]` and the synthesizer gets no evidence. The report can still be generated and may hallucinate.  
   - **If asked:** “I’d fail closed for critical paths: e.g. require a minimum number of chunks per sub-query, or return a 503 / structured error so the client doesn’t get an ungrounded report.”

3. **No caching**  
   - Same query (or same sub-query) always hits Tavily + OpenAI again. Cost and latency add up.  
   - **If asked:** “I’d add a small cache (e.g. in-memory or Redis) keyed by normalized query, with TTL, for both search results and possibly planner output.”

4. **Orchestration is sequential**  
   - Researcher runs one sub-query after another. Could run searches in parallel (e.g. `concurrent.futures`) to reduce latency.  
   - **If asked:** “I’d parallelize the Researcher step across sub-queries, with a limit on concurrency to respect Tavily rate limits.”

5. **No observability**  
   - No structured logs, tracing, or metrics. Hard to debug or tune in production.  
   - **If asked:** “I’d add structured logging (e.g. JSON) with correlation IDs, and optional timing/metrics per agent (e.g. planner_ms, search_ms).”

6. **Config is scattered**  
   - `MAX_RESULTS_PER_QUERY`, `search_depth`, etc. are in code.  
   - **If asked:** “I’d centralize in a config module or request body (e.g. `max_results`, `search_depth`) so behaviour is tunable without code changes.”

7. **Report schema is loose**  
   - `sections` is `list[dict]`; the LLM might return inconsistent keys.  
   - **If asked:** “I’d define a Pydantic model for each section (title, content, sources) and validate the synthesizer output against it.”

---

## Add-ons already in the repo

- **Tavily** (instead of DDG): better relevance and API design for agents; you use it with `search_depth` and retries.  
- **Tavily search_depth + retries**: `search_depth="advanced"` for deeper results; retries with exponential backoff so transient failures don’t kill the run.  
- **URL fetch + main-content extraction (Enricher)**: After search, we fetch each result URL (httpx, 10s timeout), extract main text with **trafilatura**, and replace snippet with full-page content when available. This grounds the synthesizer in real page content and reduces **snippet hallucination**. Failures fall back to the original snippet; enrichment can be turned off via `use_enrichment: false` or `--no-enrichment` for speed.
- **SSE streaming** (`POST /research/stream`): progress events (`plan`, `search_done`, `enrich_done`, `synthesis_done`, `critic_done`, `report`, `done`) so a client can show a live pipeline and then render the final report.  
- **.env and dotenv**: Keys and config from `.env`; project root resolved so CLI/API work from any cwd.  
- **Path hack for imports**: CLI and API add `src` to `sys.path` so `python cli.py` and `uvicorn api.main:app` work without `pip install -e .`.

---

## Add-ons you could mention (or implement later)

- **Caching**: Cache Tavily (and optionally planner) by query; mention TTL and invalidation.  
- **Parallel search**: Run Researcher sub-queries in parallel with a concurrency limit.  
- **Structured sections**: Pydantic model for report sections and validate synthesizer output.  
- **Tavily topic / time_range**: Use `topic="news"` and `time_range` for time-sensitive queries.  
- **Rate limiting**: Per-api-key or per-IP rate limit on `/research` and `/research/stream`.  
- **Structured logging**: JSON logs with request id and per-step timings.  
- **Min evidence guard**: Require at least N chunks (or N sources) before synthesis; otherwise return 503 or a clear “insufficient evidence” response.

---

## How to demo SSE in the interview

```bash
# Terminal: start server
uvicorn api.main:app --reload

# Another terminal: stream events (you’ll see event lines then the final report in "report")
curl -N -X POST http://localhost:8000/research/stream \
  -H "Content-Type: application/json" \
  -d '{"query": "What caused the 2024 chip shortage?"}'
```

Explain: “The client gets a stream of events so a UI can show ‘Planning…’, ‘Searching…’, ‘Synthesizing…’, then the full report. The last event is the same JSON as the non-streaming `/research` response.”
