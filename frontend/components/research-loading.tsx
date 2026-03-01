"use client"

import { useEffect, useState } from "react"
import { Brain, Search, Layers, FileText, Check } from "lucide-react"

type Phase = "analyzing" | "searching" | "synthesizing" | "generating" | "complete"

const PHASE_CONFIG: Record<Phase, { icon: typeof Brain; label: string; description: string }> = {
  analyzing: {
    icon: Brain,
    label: "Analyzing Query",
    description: "Breaking down your research question into sub-topics...",
  },
  searching: {
    icon: Search,
    label: "Searching Sources",
    description: "Gathering information from multiple knowledge sources...",
  },
  synthesizing: {
    icon: Layers,
    label: "Synthesizing Data",
    description: "Cross-referencing findings and building connections...",
  },
  generating: {
    icon: FileText,
    label: "Generating Report",
    description: "Composing a comprehensive research document...",
  },
  complete: {
    icon: Check,
    label: "Complete",
    description: "Your research report is ready.",
  },
}

const PHASES: Phase[] = ["analyzing", "searching", "synthesizing", "generating"]

export function ResearchLoading({
  phase,
  query,
  progress = 0,
}: {
  phase: Phase
  query: string
  progress?: number
}) {
  const [dots, setDots] = useState("")

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((d) => (d.length >= 3 ? "" : d + "."))
    }, 500)
    return () => clearInterval(interval)
  }, [])

  const currentConfig = PHASE_CONFIG[phase]
  const CurrentIcon = currentConfig.icon
  const currentPhaseIndex = PHASES.indexOf(phase as Phase)

  return (
    <div className="flex flex-col items-center gap-8 max-w-lg w-full">
      <div className="relative">
        <div className="w-20 h-20 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center">
          <CurrentIcon className="w-8 h-8 text-primary animate-pulse" />
        </div>
        <div className="absolute -inset-2 rounded-3xl border border-primary/10 animate-ping opacity-20" />
      </div>

      <div className="text-center flex flex-col gap-2">
        <h2 className="text-xl font-semibold text-foreground">
          {currentConfig.label}{dots}
        </h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {currentConfig.description}
        </p>
      </div>

      <div className="w-full flex flex-col gap-3">
        {PHASES.map((p, index) => {
          const config = PHASE_CONFIG[p]
          const Icon = config.icon
          const isActive = p === phase
          const isDone = currentPhaseIndex > index || phase === "complete"

          return (
            <div
              key={p}
              className={`
                flex items-center gap-3 px-4 py-3 rounded-lg border transition-all duration-500
                ${isActive
                  ? "border-primary/30 bg-primary/5"
                  : isDone
                    ? "border-border/50 bg-secondary/30"
                    : "border-transparent opacity-40"
                }
              `}
            >
              <div className={`
                w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-500
                ${isActive
                  ? "bg-primary/20 text-primary"
                  : isDone
                    ? "bg-green-500/10 text-green-500"
                    : "bg-secondary text-muted-foreground"
                }
              `}>
                {isDone ? (
                  <Check className="w-4 h-4" />
                ) : (
                  <Icon className={`w-4 h-4 ${isActive ? "animate-pulse" : ""}`} />
                )}
              </div>
              <div className="flex-1">
                <span className={`text-sm font-medium ${isActive ? "text-foreground" : isDone ? "text-muted-foreground" : "text-muted-foreground"}`}>
                  {config.label}
                </span>
              </div>
              {isActive && (
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="w-1.5 h-1.5 rounded-full bg-primary"
                      style={{
                        animation: `typing-dot 1.4s ease-in-out ${i * 0.2}s infinite`,
                      }}
                    />
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>

      <div className="w-full flex flex-col gap-2">
        <div className="flex justify-between text-xs font-mono text-muted-foreground">
          <span>Progress</span>
          <span>{Math.round(progress)}%</span>
        </div>
        <div className="w-full h-2 rounded-full bg-secondary overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
            style={{ width: `${Math.min(100, progress)}%` }}
          />
        </div>
      </div>

      <div className="animate-shimmer w-full h-px" />

      <p className="text-xs font-mono text-muted-foreground text-center">
        Researching: <span className="text-foreground/70">{query}</span>
      </p>
    </div>
  )
}
