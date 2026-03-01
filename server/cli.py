#!/usr/bin/env python3
"""CLI to run deep research from the command line."""

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root without pip install -e . or PYTHONPATH
_root = Path(__file__).resolve().parent
_src = _root / "src"
if _src.exists() and str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from akro_agent.orchestration import run_research
from akro_agent.export import export_to_pdf, export_to_pptx, export_to_pptx_ai, export_all


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-agent deep research")
    parser.add_argument("query", nargs="?", help="Research query (or pass via stdin)")
    parser.add_argument(
        "--no-critic",
        action="store_true",
        help="Skip the Critic agent",
    )
    parser.add_argument(
        "--no-enrichment",
        action="store_true",
        help="Skip URL fetch + full-page extraction (faster, but synthesis uses snippets only)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output full report as JSON",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Export report to PDF in --output-dir",
    )
    parser.add_argument(
        "--pptx",
        action="store_true",
        help="Export report to PPTX in --output-dir",
    )
    parser.add_argument(
        "--ai-slides",
        action="store_true",
        help="Use AI slide designer for PPTX (icons, layout, optional charts); use with --pptx or --pdf --pptx",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        metavar="DIR",
        help="Directory for PDF/PPTX exports (default: current directory)",
    )
    args = parser.parse_args()

    query = args.query
    if not query:
        query = sys.stdin.read().strip()
    if not query:
        parser.error("Provide a query as argument or via stdin")
        return

    try:
        report = run_research(
        query,
        use_critic=not args.no_critic,
        use_enrichment=not args.no_enrichment,
    )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print("#", report.query)
        print()
        print("## Summary")
        print(report.summary)
        print()
        for sec in report.sections:
            title = sec.get("title", "Section")
            content = sec.get("content", "")
            print(f"## {title}")
            print(content)
            print()
        if report.confidence_notes:
            print("## Confidence & limitations")
            print(report.confidence_notes)
            print()
        if report.sources:
            print("## Sources")
            for s in report.sources:
                print("-", s)

    # Export layer: PDF and/or PPTX
    if args.pdf or args.pptx:
        out_dir = Path(args.output_dir)
        use_ai = getattr(args, "ai_slides", False)
        if args.pdf and args.pptx:
            paths = export_all(report, out_dir, use_ai_slides=use_ai)
            print(file=sys.stderr)
            print(f"Exported PDF: {paths['pdf']}", file=sys.stderr)
            print(f"Exported PPTX: {paths['pptx']}" + (" (AI-designed)" if use_ai else ""), file=sys.stderr)
        elif args.pdf:
            p = export_to_pdf(report, out_dir / "research_report.pdf")
            print(file=sys.stderr)
            print(f"Exported PDF: {p}", file=sys.stderr)
        else:
            if use_ai:
                p = export_to_pptx_ai(report, out_dir / "research_report.pptx")
                print(file=sys.stderr)
                print(f"Exported PPTX (AI-designed): {p}", file=sys.stderr)
            else:
                p = export_to_pptx(report, out_dir / "research_report.pptx")
                print(file=sys.stderr)
                print(f"Exported PPTX: {p}", file=sys.stderr)


if __name__ == "__main__":
    main()
