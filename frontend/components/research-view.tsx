"use client"

import { useSearchParams } from "next/navigation"
import { useEffect, useState, useRef, useCallback } from "react"
import { ResearchLoading } from "@/components/research-loading"
import { ResearchReport } from "@/components/research-report"
import { DocumentPreview } from "@/components/document-preview"
import { ResearchChat, type ChatMessage } from "@/components/research-chat"
import { ThemeToggle } from "@/components/theme-toggle"
import { ArrowLeft, PanelRightOpen, PanelRightClose, ChevronDown, ChevronRight } from "lucide-react"
import Link from "next/link"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

const RESEARCH_CACHE_KEY = "akro_research"
const PENDING_PDF_KEY = "akro_pending_pdf"

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
    if (title.trim().toLowerCase() === "executive summary") continue
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

export type ReportData = {
  query: string
  summary: string
  sections: Array<{ title?: string; content?: string; sources?: string[] }>
  sources: string[]
  confidence_notes: string
}

/** Build ReportData from report markdown when reportData is missing (e.g. old cache). Enables revision routing. */
function reportMarkdownToReportData(report: string, queryFallback: string): ReportData {
  const lines = report.split(/\r?\n/)
  let query = queryFallback
  let summary = ""
  const sections: Array<{ title?: string; content?: string; sources?: string[] }> = []
  let confidence_notes = ""
  const sources: string[] = []
  let current: { title: string; content: string } | null = null
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (line.startsWith("# ")) {
      query = line.slice(2).trim() || queryFallback
      continue
    }
    if (line.startsWith("## ")) {
      if (current) {
        sections.push({ title: current.title, content: current.content.trim() })
      }
      const title = line.slice(3).trim()
      if (title.toLowerCase() === "executive summary") {
        current = { title: "Executive Summary", content: "" }
      } else if (title.toLowerCase() === "confidence notes") {
        current = null
        confidence_notes = lines.slice(i + 1).join("\n").trim()
        break
      } else {
        current = { title, content: "" }
      }
      continue
    }
    if (current) {
      current.content += (current.content ? "\n" : "") + line
    }
  }
  if (current) sections.push({ title: current.title, content: current.content.trim() })
  if (sections.length > 0 && sections[0].title === "Executive Summary") {
    summary = sections[0].content || ""
  }
  for (const s of sections) {
    const t = (s.title || "").toLowerCase()
    if (t.includes("reference") || t.includes("source")) {
      const content = s.content || ""
      const urls = content.split(/\r?\n/).map((l) => l.replace(/^\s*-\s*/, "").trim()).filter((l) => /^https?:\/\//i.test(l))
      sources.push(...urls)
    }
  }
  return { query, summary, sections, sources, confidence_notes }
}

interface ResearchCache {
  query: string
  report: string
  reportData?: ReportData | null
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
  const [reportData, setReportData] = useState<ReportData | null>(null)
  const [isReportUpdating, setIsReportUpdating] = useState(false)
  const [lastReportDiff, setLastReportDiff] = useState<string | null>(null)
  const [diffOpen, setDiffOpen] = useState(false)
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
      const pendingPdf = typeof window !== "undefined" ? sessionStorage.getItem(PENDING_PDF_KEY) : null
      if (pendingPdf) sessionStorage.removeItem(PENDING_PDF_KEY)
      const response = await fetch(`${BACKEND_URL}/research`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          use_critic: true,
          use_enrichment: true,
          include_pdf: true,
          include_pptx: true,
          ...(pendingPdf ? { pdf_base64: pendingPdf } : {}),
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
      const dataReport: ReportData = {
        query: data.query,
        summary: data.summary,
        sections: data.sections || [],
        sources: data.sources || [],
        confidence_notes: data.confidence_notes || "",
      }

      clearInterval(progressInterval)
      phaseTimers.forEach(clearTimeout)
      setProgress(100)
      setReport(reportMd)
      setReportData(dataReport)
      setPdfBase64(data.pdf_base64 || null)
      setPptxBase64(data.pptx_base64 || null)
      setLastReportDiff(null)
      setPhase("complete")
      setIsComplete(true)
      saveResearchCache({
        query,
        report: reportMd,
        reportData: dataReport,
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
      setLastReportDiff(null)
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
      setReportData(cached.reportData ?? null)
      setPdfBase64(cached.pdfBase64)
      setPptxBase64(cached.pptxBase64)
      setLastReportDiff(null)
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
      reportData: reportData ?? undefined,
      pdfBase64,
      pptxBase64,
      chatMessages,
    })
  }, [isComplete, query, report, reportData, pdfBase64, pptxBase64, chatMessages])

  const handleReportUpdating = useCallback(() => {
    setIsReportUpdating(true)
  }, [])

  const handleReportUpdateFailed = useCallback(() => {
    setIsReportUpdating(false)
  }, [])

  const handleReportUpdated = useCallback(
    (
      updatedReport: ReportData,
      pdfBase64Updated: string,
      pptxBase64Updated: string,
      diff?: string
    ) => {
      setReport(buildReportMarkdown(updatedReport))
      setReportData(updatedReport)
      setPdfBase64(pdfBase64Updated)
      setPptxBase64(pptxBase64Updated)
      setLastReportDiff(diff ?? null)
      setDiffOpen(!!diff)
      setIsReportUpdating(false)
    },
    []
  )

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
                {isReportUpdating && (
                  <div className="mb-4 flex items-center gap-2 rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-foreground">
                    <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
                    Updating report…
                  </div>
                )}
                {lastReportDiff && (
                  <div className="mb-4 rounded-lg border border-border bg-muted/30 overflow-hidden">
                    <button
                      type="button"
                      onClick={() => setDiffOpen((o) => !o)}
                      className="w-full flex items-center gap-2 px-4 py-3 text-left text-sm font-medium text-foreground hover:bg-muted/50 transition-colors"
                    >
                      {diffOpen ? (
                        <ChevronDown className="h-4 w-4 shrink-0" />
                      ) : (
                        <ChevronRight className="h-4 w-4 shrink-0" />
                      )}
                      What changed
                    </button>
                    {diffOpen && (
                      <div className="border-t border-border max-h-[400px] overflow-auto">
                        <pre className="p-4 text-xs font-mono whitespace-pre-wrap break-words">
                          {lastReportDiff.split("\n").map((line, i) => (
                            <div
                              key={i}
                              className={
                                line.startsWith("+") && !line.startsWith("+++")
                                  ? "text-green-600 dark:text-green-400"
                                  : line.startsWith("-") && !line.startsWith("---")
                                    ? "text-red-600 dark:text-red-400"
                                    : line.startsWith("@@")
                                      ? "text-muted-foreground"
                                      : ""
                              }
                            >
                              {line || " "}
                            </div>
                          ))}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
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
              reportData={reportData ?? (report && query ? reportMarkdownToReportData(report, query) : null)}
              onReportUpdating={handleReportUpdating}
              onReportUpdated={handleReportUpdated}
              onReportUpdateFailed={handleReportUpdateFailed}
              messages={chatMessages}
              setMessages={setChatMessages}
            />
          </div>
        )}
      </div>
    </div>
  )
}
