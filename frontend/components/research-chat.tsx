"use client"

import { useState, useRef, useEffect } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Send, Bot, User, Loader2, MessageSquare, FileText, X } from "lucide-react"
import type { ReportData } from "@/components/research-view"

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000"

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result as string
      resolve((result?.split(",")[1]) ?? "")
    }
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}

export type ChatMessage = {
  id: string
  role: "user" | "assistant"
  text: string
  attachmentName?: string
}

interface ResearchChatProps {
  query: string
  report: string
  reportData: ReportData | null
  onReportUpdating?: () => void
  onReportUpdated?: (report: ReportData, pdfBase64: string, pptxBase64: string, diff?: string) => void
  onReportUpdateFailed?: () => void
  messages: ChatMessage[]
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>
}

export function ResearchChat({
  query,
  report,
  reportData,
  onReportUpdating,
  onReportUpdated,
  onReportUpdateFailed,
  messages,
  setMessages,
}: ResearchChatProps) {
  const [input, setInput] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [attachment, setAttachment] = useState<{ name: string; base64: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const [isDragOverChat, setIsDragOverChat] = useState(false)

  async function handleChatDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOverChat(false)
    const file = e.dataTransfer.files[0]
    if (file?.type === "application/pdf") {
      const base64 = await fileToBase64(file)
      setAttachment({ name: file.name, base64 })
    }
  }

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages])

  async function sendMessage(
    userText: string,
    attachmentBase64?: string | null,
    attachmentName?: string | null
  ) {
    if (!userText.trim() || isLoading) return

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text: userText.trim(),
      ...(attachmentName ? { attachmentName } : {}),
    }
    const assistantId = `a-${Date.now()}`
    setMessages((prev) => [...prev, userMsg, { id: assistantId, role: "assistant", text: "" }])
    setIsLoading(true)
    setAttachment(null)

    try {
      const apiMessages = [...messages, userMsg].map((m) => ({ role: m.role, content: m.text }))
      const response = await fetch(`${BACKEND_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          messages: apiMessages,
          context: {
            query,
            report: report.slice(0, 4000),
            ...(reportData ? { report_full: reportData } : {}),
          },
          ...(attachmentBase64 ? { attachment_base64: attachmentBase64 } : {}),
          ...(attachmentName ? { attachment_filename: attachmentName } : {}),
        }),
      })
      if (!response.ok || !response.body) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, text: "Sorry, the chat request failed." } : m
          )
        )
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let full = ""
      let currentEvent = "message"

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split("\n")
        for (const line of lines) {
          if (line.startsWith("event:")) {
            currentEvent = line.slice(6).trim()
            continue
          }
          if (line.startsWith("data:")) {
            const data = line.slice(5).trim()
            if (!data) continue
            try {
              const parsed = JSON.parse(data)
              if (currentEvent === "report_updating") {
                onReportUpdating?.()
              } else if (currentEvent === "error") {
                onReportUpdateFailed?.()
              } else if (currentEvent === "report_updated" && onReportUpdated) {
                if (parsed.report && parsed.pdf_base64 != null && parsed.pptx_base64 != null) {
                  onReportUpdated(
                    parsed.report,
                    parsed.pdf_base64,
                    parsed.pptx_base64,
                    parsed.diff ?? undefined
                  )
                }
              } else if (parsed.content) {
                full += parsed.content
                setMessages((prev) =>
                  prev.map((m) => (m.id === assistantId ? { ...m, text: full } : m))
                )
              }
            } catch {
              // skip
            }
          }
        }
      }
      onReportUpdateFailed?.()
    } catch (err) {
      console.error("Chat error:", err)
      onReportUpdateFailed?.()
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, text: "Sorry, something went wrong." } : m
        )
      )
    } finally {
      setIsLoading(false)
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim()) return
    const text = input.trim()
    setInput("")
    sendMessage(text, attachment?.base64 ?? null, attachment?.name ?? null)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <MessageSquare className="w-4 h-4 text-primary" />
        <span className="text-sm font-semibold text-foreground">Chat with Research</span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
        {messages.length === 0 && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-center py-12">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
              <Bot className="w-6 h-6 text-primary" />
            </div>
            <div className="flex flex-col gap-1">
              <p className="text-sm font-medium text-foreground">Ask about this research</p>
              <p className="text-xs text-muted-foreground max-w-[250px] leading-relaxed">
                I can clarify findings, dive deeper into sections, or revise the report (e.g. improve a section, add limitations).
              </p>
            </div>
            <div className="flex flex-col gap-2 mt-2 w-full max-w-[280px]">
              {[
                "Summarize the key findings",
                "What are the main implications?",
                "Improve the methodology section",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => sendMessage(suggestion, attachment?.base64 ?? null, attachment?.name ?? null)}
                  disabled={isLoading}
                  className="text-xs text-left px-3 py-2 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-secondary transition-all disabled:opacity-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => {
          const isUser = message.role === "user"
          return (
            <div key={message.id} className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                  isUser ? "bg-primary/20" : "bg-secondary"
                }`}
              >
                {isUser ? (
                  <User className="w-3.5 h-3.5 text-primary" />
                ) : (
                  <Bot className="w-3.5 h-3.5 text-muted-foreground" />
                )}
              </div>
              <div className={`flex-1 max-w-[85%] ${isUser ? "text-right" : ""}`}>
                <div
                  className={`
                  inline-block text-sm leading-relaxed px-3 py-2 rounded-xl max-w-full overflow-hidden
                  ${isUser ? "whitespace-pre-wrap" : ""}
                  ${
                    isUser
                      ? "bg-primary text-primary-foreground rounded-tr-sm"
                      : "bg-secondary text-foreground rounded-tl-sm"
                  }
                `}
                >
                  {isUser ? (
                    <>
                      {message.attachmentName && (
                        <div className="flex items-center gap-1.5 text-xs opacity-90 mb-2 pb-1.5 border-b border-primary-foreground/20">
                          <FileText className="w-3.5 h-3.5 shrink-0" />
                          <span className="truncate">{message.attachmentName}</span>
                        </div>
                      )}
                      {message.text}
                    </>
                  ) : (
                    <div className="chat-markdown [&_p]:my-1 first:[&_p]:mt-0 last:[&_p]:mb-0 [&_ul]:my-2 [&_ol]:my-2 [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:my-0.5 [&_code]:bg-muted/80 [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_pre]:my-2 [&_pre]:p-2.5 [&_pre]:rounded-lg [&_pre]:bg-muted/80 [&_pre]:overflow-x-auto [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_strong]:font-semibold [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm [&_h1]:font-bold [&_h2]:font-bold [&_h3]:font-semibold [&_h1]:mt-2 [&_h2]:mt-2 [&_h3]:mt-1.5 [&_blockquote]:border-l-2 [&_blockquote]:border-primary/30 [&_blockquote]:pl-3 [&_blockquote]:italic [&_blockquote]:text-muted-foreground">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {message.text}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        })}

        {isLoading && messages.length > 0 && messages[messages.length - 1].role === "user" && (
          <div className="flex gap-3">
            <div className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 bg-secondary">
              <Bot className="w-3.5 h-3.5 text-muted-foreground" />
            </div>
            <div className="flex items-center gap-1 px-3 py-2">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-primary/60"
                  style={{
                    animation: `typing-dot 1.4s ease-in-out ${i * 0.2}s infinite`,
                  }}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className={`p-3 border-t border-border transition-colors ${isDragOverChat ? "bg-primary/5" : ""}`}
        onDrop={handleChatDrop}
        onDragOver={(e) => { e.preventDefault(); setIsDragOverChat(true) }}
        onDragLeave={() => setIsDragOverChat(false)}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf"
          className="hidden"
          onChange={async (e) => {
            const file = e.target.files?.[0]
            if (file?.type === "application/pdf") {
              const base64 = await fileToBase64(file)
              setAttachment({ name: file.name, base64 })
            }
            e.target.value = ""
          }}
        />
        {attachment && (
          <div className="flex items-center gap-2 mb-2 px-1">
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <FileText className="w-3.5 h-3.5" />
              {attachment.name}
            </span>
            <button
              type="button"
              onClick={() => setAttachment(null)}
              className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-secondary"
              aria-label="Remove attachment"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}
        <div className="flex items-end gap-2 bg-secondary/50 rounded-xl px-3 py-2 border border-border focus-within:border-primary/30 transition-colors">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="shrink-0 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
            title="Attach PDF"
          >
            <FileText className="w-4 h-4" />
          </button>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault()
                if (input.trim()) {
                  const text = input.trim()
                  setInput("")
                  sendMessage(text, attachment?.base64 ?? null, attachment?.name ?? null)
                }
              }
            }}
            placeholder="Ask a follow-up... or attach a PDF (Shift+Enter for new line)"
            rows={1}
            className="flex-1 min-h-[40px] max-h-[120px] py-2 bg-transparent text-sm text-foreground placeholder:text-muted-foreground outline-none resize-none"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="shrink-0 w-8 h-8 rounded-lg bg-primary text-primary-foreground flex items-center justify-center disabled:opacity-30 disabled:cursor-not-allowed hover:opacity-90 transition-opacity"
          >
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Send className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </form>
    </div>
  )
}
