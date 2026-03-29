"""
Web Fetcher — extract text from URLs and search queries.

Supports:
  - Direct URL fetch: scrapes the page and extracts readable text
  - Search query: searches DuckDuckGo, fetches top results
"""

import re
import time
from typing import List, Dict, Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from ..utils.logger import get_logger

logger = get_logger('mirofish.web_fetcher')

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

FETCH_TIMEOUT = 20
MAX_TEXT_LENGTH = 80_000  # per page


def fetch_url(url: str) -> Dict[str, str]:
    """
    Fetch a URL and extract readable text.

    Returns:
        {"url": str, "title": str, "text": str, "error": str|None}
    """
    try:
        logger.info("Fetching URL: %s", url)
        resp = requests.get(url, headers=HEADERS, timeout=FETCH_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return {"url": url, "title": "", "text": "", "error": f"Unsupported content type: {content_type}"}

        if "text/plain" in content_type:
            text = resp.text[:MAX_TEXT_LENGTH]
            return {"url": url, "title": url.split("/")[-1], "text": text, "error": None}

        soup = BeautifulSoup(resp.text, "lxml")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside",
                         "iframe", "noscript", "svg", "form", "button"]):
            tag.decompose()

        title = soup.title.string.strip() if soup.title and soup.title.string else url

        # Try <article> first, then <main>, then <body>
        content_el = soup.find("article") or soup.find("main") or soup.find("body")
        if content_el is None:
            content_el = soup

        # Extract text from paragraphs, headings, lists
        blocks = []
        for el in content_el.find_all(["p", "h1", "h2", "h3", "h4", "li", "blockquote", "pre", "td", "th"]):
            text = el.get_text(separator=" ", strip=True)
            if len(text) > 20:
                blocks.append(text)

        full_text = "\n\n".join(blocks)

        # Fallback: if structured extraction got very little, use get_text
        if len(full_text) < 200:
            full_text = content_el.get_text(separator="\n", strip=True)

        # Clean up
        full_text = re.sub(r'\n{3,}', '\n\n', full_text)
        full_text = full_text[:MAX_TEXT_LENGTH]

        logger.info("Fetched %s: %d chars, title=%s", url, len(full_text), title[:60])
        return {"url": url, "title": title, "text": full_text, "error": None}

    except requests.exceptions.Timeout:
        logger.warning("Timeout fetching %s", url)
        return {"url": url, "title": "", "text": "", "error": "Request timed out"}
    except requests.exceptions.RequestException as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return {"url": url, "title": "", "text": "", "error": str(exc)}
    except Exception as exc:
        logger.warning("Error processing %s: %s", url, exc)
        return {"url": url, "title": "", "text": "", "error": str(exc)}


def fetch_urls(urls: List[str], max_workers: int = 5) -> List[Dict[str, str]]:
    """Fetch multiple URLs in parallel using ThreadPoolExecutor."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    clean_urls = []
    for url in urls:
        url = url.strip()
        if not url:
            continue
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        clean_urls.append(url)

    if not clean_urls:
        return []

    results = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(clean_urls))) as executor:
        future_to_url = {executor.submit(fetch_url, url): url for url in clean_urls}
        for future in as_completed(future_to_url):
            try:
                results.append(future.result())
            except Exception as exc:
                url = future_to_url[future]
                logger.warning("Parallel fetch failed for %s: %s", url, exc)
                results.append({"url": url, "title": "", "text": "", "error": str(exc)})

    return results


def search_and_fetch(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search DuckDuckGo for a query and fetch the top results.

    Returns list of {"url", "title", "text", "error"} dicts.
    """
    logger.info("Searching: %s (max %d results)", query, max_results)
    urls = _search_duckduckgo(query, max_results)

    if not urls:
        logger.warning("No search results for: %s", query)
        return []

    results = []
    for url in urls:
        result = fetch_url(url)
        if result["text"] and not result["error"]:
            results.append(result)
        if len(results) >= max_results:
            break
        time.sleep(0.5)  # be polite

    logger.info("Search '%s' returned %d usable results", query, len(results))
    return results


def _search_duckduckgo(query: str, max_results: int = 5) -> List[str]:
    """Get URLs from DuckDuckGo HTML search."""
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        urls = []
        for link in soup.select("a.result__a"):
            href = link.get("href", "")
            if href and href.startswith("http") and "duckduckgo.com" not in href:
                urls.append(href)
                if len(urls) >= max_results:
                    break

        return urls
    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)
        return []
