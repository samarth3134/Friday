import html
import re

from duckduckgo_search import DDGS


SEARCH_FAILED = "Search failed, answering from memory."


def _clean_text(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _format_results(results, heading):
    formatted = []
    for index, result in enumerate(results[:5], start=1):
        title = _clean_text(result.get("title"))
        snippet = _clean_text(result.get("body") or result.get("snippet") or result.get("excerpt"))
        url = _clean_text(result.get("href") or result.get("url"))

        parts = [part for part in (title, snippet, url) if part]
        if parts:
            formatted.append(f"{index}. " + " - ".join(parts))

    if not formatted:
        return SEARCH_FAILED

    return f"{heading}:\n" + "\n".join(formatted)


def web_search(query):
    """Return the top five DuckDuckGo web results as Ollama-ready context."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        return _format_results(results, "Web search results")
    except Exception:
        return SEARCH_FAILED


def news_search(query):
    """Return the top five DuckDuckGo news results as Ollama-ready context."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=5))
        return _format_results(results, "News search results")
    except Exception:
        return SEARCH_FAILED
