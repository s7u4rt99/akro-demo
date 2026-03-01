"use client"

import { useState } from "react"
import { useRouter } from "next/navigation"
import { Search, ArrowRight, Sparkles } from "lucide-react"

const SUGGESTIONS = [
  "The impact of quantum computing on cryptography",
  "How mRNA technology is reshaping medicine",
  "The economics of space exploration in 2026",
  "Climate change adaptation strategies for coastal cities",
]

export function LandingHero() {
  const [query, setQuery] = useState("")
  const [isFocused, setIsFocused] = useState(false)
  const router = useRouter()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim()) return
    const encoded = encodeURIComponent(query.trim())
    router.push(`/research?q=${encoded}`)
  }

  function handleSuggestion(suggestion: string) {
    const encoded = encodeURIComponent(suggestion)
    router.push(`/research?q=${encoded}`)
  }

  return (
    <div className="relative z-10 flex flex-col items-center gap-8 px-4 max-w-3xl w-full">
      <div className="flex items-center gap-2 text-primary/80 font-mono text-sm tracking-wider uppercase">
        <Sparkles className="w-4 h-4" />
        <span>Deep Research Agent</span>
      </div>

      <h1 className="text-4xl md:text-6xl font-bold text-center text-foreground leading-tight text-balance">
        Research any topic
        <br />
        <span className="text-muted-foreground">in depth.</span>
      </h1>

      <p className="text-muted-foreground text-center text-lg max-w-xl leading-relaxed">
        Ask a question and get a comprehensive research report with downloadable documents, powered by AI.
      </p>

      <form
        onSubmit={handleSubmit}
        className="w-full max-w-2xl relative group"
      >
        <div
          className={`
            relative flex items-center gap-3 rounded-xl border bg-card px-4 py-3
            transition-all duration-300
            ${isFocused
              ? "border-primary/50 shadow-[0_0_30px_-5px] shadow-primary/20"
              : "border-border hover:border-border/80"
            }
          `}
        >
          <Search className="w-5 h-5 text-muted-foreground shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => setIsFocused(true)}
            onBlur={() => setIsFocused(false)}
            placeholder="What would you like to research?"
            className="flex-1 bg-transparent text-foreground placeholder:text-muted-foreground text-base outline-none"
          />
          <button
            type="submit"
            disabled={!query.trim()}
            className="shrink-0 flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium transition-all hover:opacity-90 disabled:opacity-30 disabled:cursor-not-allowed"
          >
            <span className="hidden sm:inline">Research</span>
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </form>

      <div className="flex flex-col items-center gap-3 w-full max-w-2xl">
        <span className="text-xs text-muted-foreground font-mono uppercase tracking-widest">Try these</span>
        <div className="flex flex-wrap justify-center gap-2">
          {SUGGESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => handleSuggestion(suggestion)}
              className="text-sm px-3 py-1.5 rounded-lg border border-border bg-secondary/50 text-muted-foreground hover:text-foreground hover:border-primary/30 hover:bg-secondary transition-all duration-200"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8 flex items-center gap-6 text-xs text-muted-foreground font-mono">
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
          <span>AI Powered</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-primary" />
          <span>PDF + PPTX Export</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-1.5 h-1.5 rounded-full bg-primary/60" />
          <span>Interactive Chat</span>
        </div>
      </div>
    </div>
  )
}
