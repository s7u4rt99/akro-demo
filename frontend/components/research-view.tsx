"use client"

import { useSearchParams } from "next/navigation"
import { useEffect, useState, useRef, useCallback } from "react"
import { ResearchLoading } from "@/components/research-loading"
import { ResearchReport } from "@/components/research-report"
import { DocumentPreview } from "@/components/document-preview"
import { ResearchChat, type ChatMessage } from "@/components/research-chat"
import { ThemeToggle } from "@/components/theme-toggle"
import { ArrowLeft, PanelRightOpen, PanelRightClose } from "lucide-react"
import Link from "next/link"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

const RESEARCH_CACHE_KEY = "akro_research"

type ResearchPhase =
  | "analyzing"
  | "searching"
  | "synthesizing"
  | "generating"
  | "complete"

function buildReportMarkdown(data: {
  query: string
  summary: string
  sections: Array<{ title?: string; content?: string }>
  sources: string[]
  confidence_notes: string
}): string {
  let md = `# ${data.query}\n\n## Executive Summary\n\n${data.summary}\n\n`
  for (const sec of data.sections || []) {
    const title = sec.title || "Section"
    let content = (sec.content || "").trim()
    // References/Sources: use top-level sources so each URL is on its own line (canonical list)
    if (title.toLowerCase().includes("reference") || title.toLowerCase().includes("source")) {
      const urls = (data.sources || []).length ? data.sources : content.split(/\r?\n+/).map((l) => l.trim()).filter(Boolean)
      content = urls.map((url) => `- ${url}`).join("\n")
    }
    md += `## ${title}\n\n${content}\n\n`
  }
  if (data.confidence_notes) {
    md += `## Confidence notes\n\n${data.confidence_notes}\n\n`
  }
  return md
}

interface ResearchCache {
  query: string
  report: string
  pdfBase64: string | null
  pptxBase64: string | null
  chatMessages: ChatMessage[]
}

function getCacheKey(q: string) {
  return `${RESEARCH_CACHE_KEY}:${encodeURIComponent(q)}`
}

function loadResearchCache(query: string): ResearchCache | null {
  if (typeof window === "undefined" || !query) return null
  try {
    const raw = sessionStorage.getItem(getCacheKey(query))
    if (!raw) return null
    const data = JSON.parse(raw) as ResearchCache
    if (data?.query && data?.report) return data
  } catch {
    // ignore
  }
  return null
}

function saveResearchCache(cache: ResearchCache) {
  if (typeof window === "undefined" || !cache.query) return
  try {
    sessionStorage.setItem(getCacheKey(cache.query), JSON.stringify(cache))
  } catch (e) {
    if (e instanceof DOMException && e.name === "QuotaExceededError") {
      try {
        sessionStorage.setItem(getCacheKey(cache.query), JSON.stringify({
          ...cache,
          pdfBase64: null,
          pptxBase64: null,
        }))
      } catch {
        // ignore
      }
    }
  }
}

export function ResearchView() {
  const searchParams = useSearchParams()
  const query = searchParams.get("q") || ""
  const [phase, setPhase] = useState<ResearchPhase>("analyzing")
  const [report, setReport] = useState("")
  const [isComplete, setIsComplete] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([])
  const [pdfBase64, setPdfBase64] = useState<string | null>(null)
  const [pptxBase64, setPptxBase64] = useState<string | null>(null)
  const [progress, setProgress] = useState(0)
  const fetchedRef = useRef(false)

  // When query changes, reset so we either restore from cache or run research for the new query
  useEffect(() => {
    fetchedRef.current = false
    setChatMessages([])
  }, [query])

  const startResearch = useCallback(async () => {
    if (!query) return

    setPhase("analyzing")
    setProgress(0)

    // Simulated progress: advance toward 90% over ~2 min, then 100% on completion
    const PROGRESS_DURATION_MS = 120_000 // 2 min to reach 90%
    const TARGET = 90
    const startTime = Date.now()
    const progressInterval = setInterval(() => {
      const elapsed = Date.now() - startTime
      const p = Math.min(TARGET, (TARGET * elapsed) / PROGRESS_DURATION_MS)
      setProgress(p)
    }, 500)

    const phaseTimers = [
      setTimeout(() => setPhase("searching"), 2000),
      setTimeout(() => setPhase("synthesizing"), 5000),
      setTimeout(() => setPhase("generating"), 8000),
    ]

    try {
      const response = await fetch(`${BACKEND_URL}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          use_critic: true,
          use_enrichment: true,
          include_pdf: true,
          include_pptx: true,
        }),
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error((err as { detail?: string }).detail || "Research failed")
      }

      const data = await response.json()
      const reportMd = buildReportMarkdown({
        query: data.query,
        summary: data.summary,
        sections: data.sections || [],
        sources: data.sources || [],
        confidence_notes: data.confidence_notes || "",
      })

      clearInterval(progressInterval)
      phaseTimers.forEach(clearTimeout)
      setProgress(100)
      setReport(reportMd)
      setPdfBase64(data.pdf_base64 || null)
      setPptxBase64(data.pptx_base64 || null)
      setPhase("complete")
      setIsComplete(true)
      saveResearchCache({
        query,
        report: reportMd,
        pdfBase64: data.pdf_base64 || null,
        pptxBase64: data.pptx_base64 || null,
        chatMessages: [],
      })
    } catch (err) {
      console.error("Research error:", err)
      clearInterval(progressInterval)
      phaseTimers.forEach(clearTimeout)
      setProgress(100)
      setPhase("complete")
      setIsComplete(true)
      setReport(
        "# Research could not be completed\n\nAn error occurred while generating the research report. Please try again."
      )
    }
  }, [query])

  // Restore from cache on load, or run research
  useEffect(() => {
    if (fetchedRef.current) return
    if (!query) return

    const cached = loadResearchCache(query)
    if (cached) {
      fetchedRef.current = true
      setReport(cached.report)
      setPdfBase64(cached.pdfBase64)
      setPptxBase64(cached.pptxBase64)
      setChatMessages(cached.chatMessages ?? [])
      setPhase("complete")
      setProgress(100)
      setIsComplete(true)
      return
    }

    fetchedRef.current = true
    startResearch()
  }, [query, startResearch])

  // Persist cache when report or chat changes (so refresh keeps chat)
  useEffect(() => {
    if (!isComplete || !query || !report) return
    saveResearchCache({
      query,
      report,
      pdfBase64,
      pptxBase64,
      chatMessages,
    })
  }, [isComplete, query, report, pdfBase64, pptxBase64, chatMessages])

  return (
    <div className="min-h-screen flex flex-col bg-background">
      <header className="sticky top-0 z-50 border-b border-border bg-background/80 backdrop-blur-xl">
        <div className="flex items-center justify-between px-4 md:px-6 h-14">
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm"
            >
              <ArrowLeft className="w-4 h-4" />
              <span className="hidden sm:inline">Back</span>
            </Link>
            <div className="h-4 w-px bg-border" />
            <h1 className="text-sm font-mono text-muted-foreground truncate max-w-md">
              {query}
            </h1>
          </div>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {isComplete && (
              <button
                onClick={() => setChatOpen(!chatOpen)}
                className="flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all"
              >
                {chatOpen ? (
                  <PanelRightClose className="w-4 h-4" />
                ) : (
                  <PanelRightOpen className="w-4 h-4" />
                )}
                <span className="hidden sm:inline">Chat</span>
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <div className={`flex-1 flex flex-col overflow-y-auto transition-all duration-300 ${chatOpen ? "md:mr-[400px]" : ""}`}>
          {!isComplete && (
            <div className="flex-1 flex items-center justify-center p-8">
              <ResearchLoading phase={phase} query={query} progress={progress} />
            </div>
          )}

          {report && (
            <div className={`transition-opacity duration-500 ${isComplete ? "opacity-100" : "opacity-0"}`}>
              <div className="max-w-4xl mx-auto p-4 md:p-8">
                <ResearchReport content={report} />

                {isComplete && (
                  <div className="mt-8 animate-float-up" style={{ animationDelay: "0.3s", opacity: 0 }}>
                    <DocumentPreview
                      query={query}
                      report={report}
                      pdfBase64={pdfBase64}
                      pptxBase64={pptxBase64}
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {chatOpen && (
          <div className="fixed right-0 top-14 bottom-0 w-full md:w-[400px] border-l border-border bg-card z-40">
            <ResearchChat
              query={query}
              report={report}
              messages={chatMessages}
              setMessages={setChatMessages}
            />
          </div>
        )}
      </div>
    </div>
  )
}
