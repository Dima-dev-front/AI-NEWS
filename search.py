import logging
import os
from typing import List

import requests

logger = logging.getLogger(__name__)


def discover_urls(query: str, locale: str = "en", country: str = "US", num_results: int = 20, timeout_sec: int = 12) -> List[str]:
    """
    Discover fresh news/article URLs via a web search API. Currently supports SerpAPI (Google News).

    Env:
    - SEARCH_PROVIDER=serpapi
    - SERPAPI_API_KEY
    """
    provider = os.getenv("SEARCH_PROVIDER", "serpapi").strip().lower()
    if provider == "serpapi":
        return _discover_urls_serpapi(query=query, locale=locale, country=country, num_results=num_results, timeout_sec=timeout_sec)
    logger.warning("Unknown SEARCH_PROVIDER '%s' — returning empty list", provider)
    return []


def _discover_urls_serpapi(query: str, locale: str, country: str, num_results: int, timeout_sec: int) -> List[str]:
    api_key = os.getenv("SERPAPI_API_KEY", "").strip()
    if not api_key:
        logger.error("SERPAPI_API_KEY not set; cannot perform discovery")
        return []

    params = {
        "engine": "google_news",
        "q": query,
        "hl": locale,
        "gl": country,
        "num": max(10, min(100, num_results)),
        "api_key": api_key,
    }
    try:
        resp = requests.get("https://serpapi.com/search.json", params=params, timeout=timeout_sec)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("SerpAPI request failed: %s", exc)
        return []

    urls: List[str] = []
    # Prefer news_results
    for entry in (data.get("news_results") or []):
        link = (entry.get("link") or "").strip()
        if link and link.startswith("http"):
            urls.append(link)
    # Fallback: organic_results
    if not urls:
        for entry in (data.get("organic_results") or []):
            link = (entry.get("link") or "").strip()
            if link and link.startswith("http"):
                urls.append(link)
    # De-dup while preserving order
    seen = set()
    uniq = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq[:num_results]


