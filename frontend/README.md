# Akro Agent (Frontend)

Next.js app for the Akro deep-research product: submit a query, watch progress, view the report, preview and download PDF/PPTX, and chat with the research via streamed Q&A.

**Prerequisites:** Node.js 18+ and a running Akro backend (see [server/README.md](../server/README.md)). The frontend talks to the backend at the URL set in `NEXT_PUBLIC_BACKEND_URL`.

---

## Setup

All commands are run from the `frontend/` directory.

```bash
cd frontend

# Install dependencies
npm install

# Environment (optional if backend is at localhost:8000)
cp .env.example .env
# Edit .env and set NEXT_PUBLIC_BACKEND_URL if your backend runs elsewhere
# Example: NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | No (default: `http://localhost:8000`) | Backend API base URL, no trailing slash. Set when backend is on another host/port (e.g. production or a different machine). |

---

## Run

**Development:**

```bash
npm run dev
```

- App: [http://localhost:3000](http://localhost:3000)
- Ensure the backend is running (e.g. `uvicorn api.main:app --reload --host 0.0.0.0 --port 8000` from `server/`). The frontend will call `NEXT_PUBLIC_BACKEND_URL` for research and chat.

**Production build:**

```bash
npm run build
npm start
```

Runs the built app (default port 3000). Point `NEXT_PUBLIC_BACKEND_URL` to your deployed backend when building for production.

---

## How to use the product

1. **Home** — Landing page with a search box. Enter a research question and submit to go to the research flow.
2. **Research page** (`/research`) — After you submit a query:
   - The app calls the backend `POST /research` (with options for PDF/PPTX in the response).
   - You see progress while the pipeline runs (planning, search, synthesis, etc.).
   - When done: the report is shown on the page; if PDF/PPTX are returned, you get an embedded PDF preview and **Download PDF** / **Download PPTX** buttons.
   - Reports and files are also written to `server/out/` on the backend.
3. **Chat** — Use the chat panel to ask follow-up questions about the research. The frontend streams replies from the backend `POST /chat` (SSE). You can reference the last report and, when available, the generated PDF for context.

**Theme:** Use the theme toggle (top-right) to switch between light and dark mode.

---

## Project layout

```
frontend/
├── README.md           # This file
├── .env.example        # NEXT_PUBLIC_BACKEND_URL
├── package.json
├── app/
│   ├── layout.tsx      # Root layout, theme provider
│   ├── page.tsx        # Home / landing
│   ├── research/
│   │   └── page.tsx    # Research page (uses ResearchView)
│   └── globals.css
└── components/
    ├── landing-hero.tsx    # Home search + submit
    ├── research-view.tsx   # Research flow, report, PDF/PPTX preview & download
    ├── research-chat.tsx   # Chat panel (streaming)
    ├── research-loading.tsx # Loading / progress
    ├── research-report.tsx # Report display
    ├── document-preview.tsx# PDF preview
    └── theme-toggle.tsx    # Light/dark toggle
```

---

## Scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Next.js dev server (default port 3000) |
| `npm run build` | Production build |
| `npm start` | Run production server (after `npm run build`) |
| `npm run lint` | Run ESLint |

---

## Backend dependency

The frontend expects the backend to expose:

- `POST /research` — Run research; request body can include `query`, `include_pdf`, `include_pptx`, etc. Returns report JSON and optionally `pdf_base64` / `pptx_base64`.
- `POST /chat` — Streamed chat; request body includes messages; response is SSE stream.
- `GET /health` — Health check (optional; useful for readiness checks).

For full API details and request/response shapes, see [server/README.md](../server/README.md) and the backend’s interactive docs at `http://<backend>/docs`.
