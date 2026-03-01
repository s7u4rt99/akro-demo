import { Suspense } from "react"
import { ResearchView } from "@/components/research-view"

export default function ResearchPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-background" />}>
      <ResearchView />
    </Suspense>
  )
}
