"use client"

import { useState } from "react"
import { FileText, Presentation, Download, Loader2, FileDown } from "lucide-react"

interface DocumentPreviewProps {
  query: string
  report: string
  pdfBase64: string | null
  pptxBase64: string | null
}

function PdfPreview({ report }: { report: string }) {
  const lines = report.split("\n").slice(0, 30)

  return (
    <div className="bg-background rounded-lg border border-border p-6 font-serif text-xs leading-relaxed h-[400px] overflow-hidden relative">
      <div className="absolute top-3 left-3 flex items-center gap-1.5 text-red-400/80">
        <FileText className="w-3.5 h-3.5" />
        <span className="font-mono text-[10px] uppercase tracking-wider">PDF Preview</span>
      </div>
      <div className="mt-6 flex flex-col gap-1 text-muted-foreground/80">
        {lines.map((line, i) => {
          if (line.startsWith("# ")) {
            return <p key={i} className="text-base font-bold text-foreground mt-3 mb-1">{line.replace(/^#+\s/, "")}</p>
          }
          if (line.startsWith("## ")) {
            return <p key={i} className="text-sm font-semibold text-foreground/90 mt-2 mb-0.5">{line.replace(/^#+\s/, "")}</p>
          }
          if (line.startsWith("### ")) {
            return <p key={i} className="text-xs font-semibold text-foreground/80 mt-1.5">{line.replace(/^#+\s/, "")}</p>
          }
          if (line.startsWith("- ") || line.startsWith("* ")) {
            return <p key={i} className="pl-3">{line}</p>
          }
          if (line.trim() === "") {
            return <div key={i} className="h-1.5" />
          }
          return <p key={i}>{line.replace(/\*\*/g, "").replace(/\*/g, "")}</p>
        })}
      </div>
      <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-background to-transparent" />
    </div>
  )
}

function PptxOutlinePreview({ report, query }: { report: string; query: string }) {
  const headings = report
    .split("\n")
    .filter((l) => l.startsWith("## ") || l.startsWith("# "))
    .slice(0, 6)
    .map((h) => h.replace(/^#+\s/, ""))

  return (
    <div className="bg-background rounded-lg border border-border h-[400px] overflow-hidden relative">
      <div className="absolute top-3 left-3 right-3 flex items-center justify-between gap-2 z-10">
        <div className="flex items-center gap-1.5 text-orange-400/80">
          <Presentation className="w-3.5 h-3.5" />
          <span className="font-mono text-[10px] uppercase tracking-wider">Slide outline</span>
        </div>
      </div>
      <p className="absolute top-9 left-3 right-3 text-[10px] text-muted-foreground z-10">
        Browsers cannot display .pptx slides. Download the file to view the full presentation.
      </p>
      <div className="mt-16 p-4 flex flex-col gap-3 h-full overflow-hidden">
        {/* Title slide */}
        <div className="bg-primary/10 border border-primary/20 rounded-lg p-4 flex-shrink-0">
          <p className="text-sm font-bold text-foreground truncate">{query}</p>
          <p className="text-[10px] text-muted-foreground font-mono mt-1">Deep Research Report</p>
        </div>
        {/* Content slides */}
        <div className="grid grid-cols-2 gap-2 flex-1 overflow-hidden">
          {headings.map((heading, i) => (
            <div
              key={i}
              className="bg-secondary/50 border border-border rounded-lg p-3 flex flex-col gap-1.5"
            >
              <p className="text-[10px] font-semibold text-foreground truncate">{heading}</p>
              <div className="flex flex-col gap-1">
                {[1, 2, 3].map((j) => (
                  <div
                    key={j}
                    className="h-1 rounded-full bg-muted-foreground/15"
                    style={{ width: `${80 - j * 15}%` }}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="absolute bottom-0 left-0 right-0 h-16 bg-gradient-to-t from-background to-transparent" />
    </div>
  )
}

function base64ToBlob(base64: string, mime: string): Blob {
  const bin = atob(base64)
  const arr = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i)
  return new Blob([arr], { type: mime })
}

export function DocumentPreview({ query, report, pdfBase64, pptxBase64 }: DocumentPreviewProps) {
  const [downloadingPdf, setDownloadingPdf] = useState(false)
  const [downloadingPptx, setDownloadingPptx] = useState(false)

  function handleDownload(type: "pdf" | "pptx") {
    const setter = type === "pdf" ? setDownloadingPdf : setDownloadingPptx
    const b64 = type === "pdf" ? pdfBase64 : pptxBase64
    if (!b64) return
    setter(true)
    try {
      const mime = type === "pdf" ? "application/pdf" : "application/vnd.openxmlformats-officedocument.presentationml.presentation"
      const blob = base64ToBlob(b64, mime)
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `research-report.${type}`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      console.error("Download error:", err)
    } finally {
      setter(false)
    }
  }

  const pdfReady = !!pdfBase64
  const pptxReady = !!pptxBase64
  const pdfDataUrl = pdfBase64 ? `data:application/pdf;base64,${pdfBase64}` : null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center gap-3">
        <FileDown className="w-5 h-5 text-primary" />
        <h3 className="text-sm font-semibold text-foreground">Export Documents</h3>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="flex flex-col gap-3">
          {pdfDataUrl ? (
            <div className="bg-background rounded-lg border border-border overflow-hidden h-[400px]">
              <div className="flex items-center gap-1.5 text-red-400/80 px-3 py-2 border-b border-border">
                <FileText className="w-3.5 h-3.5" />
                <span className="font-mono text-[10px] uppercase tracking-wider">PDF Preview</span>
              </div>
              <iframe
                src={pdfDataUrl}
                title="PDF report"
                className="w-full h-[calc(400px-2.5rem)] border-0"
              />
            </div>
          ) : (
            <PdfPreview report={report} />
          )}
          <button
            onClick={() => handleDownload("pdf")}
            disabled={!pdfReady || downloadingPdf}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {downloadingPdf ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Download PDF
          </button>
        </div>

        <div className="flex flex-col gap-3">
          <PptxOutlinePreview report={report} query={query} />
          <button
            onClick={() => handleDownload("pptx")}
            disabled={!pptxReady || downloadingPptx}
            className="flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-orange-500/10 border border-orange-500/20 text-orange-400 hover:bg-orange-500/20 transition-all text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed w-full"
          >
            {downloadingPptx ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Download className="w-4 h-4" />
            )}
            Download PPTX
          </button>
        </div>
      </div>
    </div>
  )
}
