import logging

from src.config import get_secret

logger = logging.getLogger(__name__)


class ResearchError(Exception):
    pass


def research_topic(topic: str, max_results: int = 5) -> list:
    """Fetch recent, relevant sources for a topic via Tavily.

    Raises ResearchError on any failure so the caller can fall back to
    "no research context" mode with a visible warning, per FR2.
    """
    api_key = get_secret("TAVILY_API_KEY")
    if not api_key:
        raise ResearchError("TAVILY_API_KEY not configured")

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(query=topic, max_results=max_results, search_depth="basic")
    except Exception as e:
        raise ResearchError(f"Tavily search failed: {e}")

    results = []
    for r in (response.get("results") or [])[:max_results]:
        results.append(
            {
                "title": r.get("title", "").strip(),
                "url": r.get("url", "").strip(),
                "snippet": (r.get("content", "") or "").strip(),
            }
        )

    if not results:
        raise ResearchError("Tavily returned no results for this topic")

    return results


def format_research_context(results: list) -> str:
    if not results:
        return ""
    lines = ["Recent research context (use for facts/angles, not verbatim copying):"]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']} — {r['snippet']} (source: {r['url']})")
    return "\n".join(lines)
