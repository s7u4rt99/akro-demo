"use client"

import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { FileText, Clock, BookOpen } from "lucide-react"

function estimateReadTime(text: string) {
  const words = text.split(/\s+/).length
  const minutes = Math.ceil(words / 200)
  return minutes
}

function countSections(text: string) {
  return (text.match(/^#{1,3}\s/gm) || []).length
}

export function ResearchReport({ content }: { content: string }) {
  const readTime = estimateReadTime(content)
  const sections = countSections(content)
  const wordCount = content.split(/\s+/).length

  return (
    <div className="animate-float-up">
      <div className="flex items-center gap-4 mb-6 pb-4 border-b border-border">
        <div className="flex items-center gap-2 text-primary">
          <FileText className="w-5 h-5" />
          <span className="text-sm font-semibold">Research Report</span>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground font-mono">
          <div className="flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5" />
            <span>{readTime} min read</span>
          </div>
          <div className="flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5" />
            <span>{sections} sections</span>
          </div>
          <span>{wordCount.toLocaleString()} words</span>
        </div>
      </div>

      <article className="prose-research">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </article>
    </div>
  )
}
