# Take-home readiness: rubrics and talking points

This document maps the submission to the assignment criteria and suggests what to emphasize (and what to improve) for the technical interview.

---

## Assignment criteria (as given)

You are assessed on:

1. **Correctness of output** (stochastic functions notwithstanding)
2. **How testable, modular and clean your code is**
3. **Other interesting add-ons you can think of**

---

## 1. Correctness of output

**How prepared you are:** Strong.

- **Structured pipeline:** Planner → Researcher → Enricher → Synthesizer → Critic. Each step has clear inputs/outputs (Pydantic models: `ResearchPlan`, `ResearchEvidence`, `ResearchReport`). The critic can request revisions; the graph loops back to the Synthesizer (up to 2 times) so the final report is revised, not raw.
- **Grounded synthesis:** The Enricher fetches each search result URL and extracts main content (trafilatura), so the Synthesizer works from full-page text when available, which reduces snippet hallucination. You can disable enrichment for speed (`use_enrichment: false`).
- **Report schema:** The Synthesizer prompt enforces a consistent structure (methodology, literature review, claim → evidence → counter-arguments → strength → assessment, discussion, implications, conclusion, references). Output is parsed and validated as `ResearchReport`.
- **Stochastic but controllable:** LLM calls are the main source of variance. You use a fixed model via `OPENAI_MODEL`; same query can be re-run. No randomness in orchestration or export.

**Notable points to mention:**

- “We use LangGraph so the critic’s ‘revise’ verdict actually loops back to the Synthesizer; the report isn’t one-shot.”
- “Enricher grounds the report in real page content instead of search snippets only; that directly targets correctness and hallucination.”
- “Report structure is prompt-driven and we parse into a Pydantic report model; the API and CLI both consume the same structure.”

**Potential gaps:**

- Search can fail (e.g. Tavily down) and currently fails *open*: we pass empty evidence to the Synthesizer, so the report can still be generated and may hallucinate. A stronger design would fail closed (e.g. require minimum evidence or return 503).
- Report “sections” are still `list[dict]` in the model; the LLM could return inconsistent keys. Tighter correctness would use a Pydantic model per section and validate synthesizer output.

---

## 2. Testability, modularity, clean code

**How prepared you are:** Good on structure; weak on tests.

**Modularity:**

- **Agents are separate modules** with single-entry functions: `run_planner(query)`, `run_researcher(plan)`, `enrich_evidence(evidence_list)`, `run_synthesizer(...)`, `run_critic(report)`. Each can be tested in isolation.
- **Orchestration is separate:** `graph.py` defines the LangGraph; `orchestration.py` exposes `run_research()` and `run_research_stream()`. The graph calls the agent functions; it doesn’t inline logic.
- **Export layer is isolated:** `export/pdf_writer.py`, `export/pptx_writer.py`, and optional AI slide designer. Export takes a `ResearchReport` and writes files; no LLM inside export.
- **API layer is thin:** `api/main.py` parses request, calls orchestration or export, returns response. Keys and config come from `.env` (e.g. `python-dotenv`).

**Clean code:**

- Pydantic for plans, evidence, and reports. TypedDict for graph state. Clear separation of “data shapes” vs “agents” vs “orchestration.”
- Single responsibility per file: planner, researcher, synthesizer, critic, fetch (enricher), graph, export.
- CLI and API both use the same orchestration and export functions; no duplicated pipeline logic.

**Testability (current gap):**

- **No tests in the repo.** The design is testable (pure-ish functions, injectable LLM/search), but there are no unit or integration tests.
- **If asked:** “I’d add pytest tests that mock the LLM and Tavily: (1) unit tests for each agent with fixed prompt/output, asserting on plan shape, evidence structure, and report schema; (2) an integration test that runs the graph with mocks and asserts on final report structure and that critic revision loop is exercised when the mock critic returns ‘revise’.”

**Notable points to mention:**

- “Agents are pure functions from inputs to outputs; we could add pytest with mocks tomorrow.”
- “Orchestration is in LangGraph; the revision loop is explicit in the graph, not buried in if/else.”
- “CLI and API share the same `run_research` and export functions; behavior is consistent and testable in one place.”

**Potential gaps:**

- No dependency injection for LLM or search in the agent modules; they import and call real clients. To unit-test agents you’d either mock at the import level or refactor to accept an LLM/search interface.
- Some magic numbers and config (e.g. `MAX_RESULTS_PER_QUERY`, `search_depth`) live in code; centralizing in config or request body would make behavior easier to test and tune.

---

## 3. Interesting add-ons

**Already in the repo (strong to mention):**

- **Tavily** with `search_depth` and retries (exponential backoff) for robust search.
- **Enricher:** fetch each result URL, extract main content with trafilatura, replace snippet with full-page text when available. Reduces snippet hallucination; can be disabled for speed.
- **SSE streaming** (`POST /research/stream`): progress events (plan, search_done, enrich_done, synthesis_done, critic_done, report, done) so a UI can show a live pipeline and then the full report.
- **PDF and PPTX export:** full report as PDF; PPTX with one slide per point/source.
- **Chat:** `POST /chat` for follow-up Q&A, with optional PDF context (uploaded or last report) for grounded answers.
- **Multiple entry points:** FastAPI (including `/docs`), CLI (`python cli.py "query"` with `--pdf`, `--pptx`), and Next.js frontend with preview and download.

**Suggested add-ons to propose (or implement later):**

- **Caching:** Cache Tavily (and optionally planner) by normalized query with TTL; reduces cost and latency for repeated/similar queries.
- **Parallel search:** Run Researcher sub-queries in parallel (e.g. `concurrent.futures`) with a concurrency cap to respect rate limits.
- **Structured sections:** Pydantic model for each report section (title, content, sources); validate synthesizer output for stricter correctness.
- **Min evidence guard:** Require a minimum number of chunks or sources before synthesis; otherwise return 503 or “insufficient evidence” instead of an ungrounded report.
- **Observability:** Structured logging (e.g. JSON) with request ID and per-step timings (planner_ms, search_ms, etc.); optional metrics for tuning and debugging.
- **Rate limiting:** Per API key or per IP on `/research` and `/research/stream` for production safety.
- **Tavily options:** Use `topic` (e.g. "news") and `time_range` for time-sensitive queries.

---

## Quick reference: what to say when

| Question | Suggested angle |
|----------|------------------|
| “How does your system work?” | Planner → Researcher → Enricher → Synthesizer → Critic; LangGraph with revision loop; Enricher grounds synthesis in full-page content. |
| “How do you ensure correctness?” | Structured report schema, Enricher to reduce snippet hallucination, critic revision loop. Acknowledge: we could add min-evidence guard and stricter section validation. |
| “How testable is it?” | Agents are modular and pure-function-like; orchestration is separate. No tests yet; would add pytest with mocked LLM/Tavily and assert on plan, evidence, and report shape. |
| “What would you add?” | Caching, parallel search, structured sections, min evidence guard, structured logging, rate limiting. |
| “Demo streaming?” | `curl -N -X POST http://localhost:8000/research/stream -H "Content-Type: application/json" -d '{"query": "..."}'` — show events then final report. |

---

## Summary

- **Correctness:** Strong pipeline design and grounding; minor gaps (fail-open search, loose section schema).
- **Modularity/clean code:** Clear separation of agents, orchestration, and export; single entry points and shared code paths.
- **Testability:** Design supports tests; no tests in repo yet — be ready to describe a concrete pytest plan.
- **Add-ons:** Several already shipped (Enricher, SSE, PDF/PPTX, chat); good list of next steps (caching, parallel search, guards, observability).

Use this with [server/CRITIQUE_AND_ADDONS.md](server/CRITIQUE_AND_ADDONS.md) for deeper technical details and curl examples (e.g. SSE demo).
