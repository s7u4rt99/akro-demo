"""URL fetch + main-content extraction to ground synthesis in full pages (reduce snippet hallucination)."""

from __future__ import annotations

import concurrent.futures
from urllib.parse import urlparse

import httpx
from trafilatura import extract

from akro_agent.models import EvidenceChunk, ResearchEvidence

FETCH_TIMEOUT_SEC = 10
FETCH_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; AkroResearch/1.0)"}
MAX_CONCURRENT_FETCHES = 5
MAX_URLS_TO_FETCH = 15
MAX_CHARS_PER_PAGE = 14_000


def _is_safe_url(url: str) -> bool:
    try:
        p = urlparse(url)
        return bool(p.scheme in ("http", "https") and p.netloc)
    except Exception:
        return False


def _fetch_and_extract(url: str) -> str | None:
    """Fetch URL with httpx (controlled timeout), then extract main content with trafilatura."""
    if not _is_safe_url(url):
        return None
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT_SEC, follow_redirects=True) as client:
            resp = client.get(url, headers=FETCH_HEADERS)
            resp.raise_for_status()
            html = resp.text
        if not html or len(html) < 100:
            return None
        text = extract(html)
        if not text or not text.strip():
            return None
        return text.strip()[:MAX_CHARS_PER_PAGE]
    except Exception:
        return None


def enrich_evidence(
    evidence_list: list[ResearchEvidence],
    *,
    max_urls: int = MAX_URLS_TO_FETCH,
    max_concurrent: int = MAX_CONCURRENT_FETCHES,
) -> list[ResearchEvidence]:
    """
    After search, fetch each unique URL and replace chunk content with full-page
    text when available. Reduces snippet hallucination by grounding synthesis
    in actual page content.
    """
    # Collect unique URLs (order: first seen across chunks)
    seen: set[str] = set()
    urls_in_order: list[str] = []
    for ev in evidence_list:
        for c in ev.chunks:
            u = (c.source or "").strip()
            if u and _is_safe_url(u) and u not in seen:
                seen.add(u)
                urls_in_order.append(u)
    print(f"fetching URLS {len(urls_in_order)} < {max_urls}\n")
    to_fetch = urls_in_order[:max_urls]

    # Fetch in parallel
    url_to_content: dict[str, str] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as ex:
        fut_to_url = {ex.submit(_fetch_and_extract, u): u for u in to_fetch}
        for fut in concurrent.futures.as_completed(fut_to_url):
            url = fut_to_url[fut]
            try:
                content = fut.result()
                if content:
                    url_to_content[url] = content
            except Exception:
                pass

    # Build new evidence list: replace chunk content when we have fetched content
    result: list[ResearchEvidence] = []
    for ev in evidence_list:
        new_chunks: list[EvidenceChunk] = []
        for c in ev.chunks:
            url = (c.source or "").strip()
            if url in url_to_content:
                new_chunks.append(
                    EvidenceChunk(
                        content=url_to_content[url],
                        source=c.source,
                        sub_query=c.sub_query,
                    )
                )
            else:
                # Keep original snippet; optionally mark as snippet-only
                new_chunks.append(
                    EvidenceChunk(
                        content=c.content + "\n\n[Full page not fetched; above is search snippet only.]",
                        source=c.source,
                        sub_query=c.sub_query,
                    )
                )
        result.append(ResearchEvidence(sub_query=ev.sub_query, chunks=new_chunks))
    return result
