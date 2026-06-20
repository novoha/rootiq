"""
Phase 2 Scraper — IQAN Forum Thread Content Extractor
Uses plain requests + BeautifulSoup (no JS needed for individual threads).
Every fetch is gated by security.check_url() against the domain allowlist.
Input: topic URL from the phase1 index
Output: dict with title, body, replies, status, votes, url
"""
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from security import check_url

ROOT = Path(__file__).resolve().parent.parent

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; RootIQ/1.0; +https://github.com/rootiq research bot)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}
REQUEST_DELAY = 1.5   # seconds between fetches — be polite
TIMEOUT = 15

SKILL = {
    "name": "phase2_scrape",
    "description": "Fetch and parse a single IQAN forum thread into structured text.",
}


def scrape_topic(url: str) -> dict:
    """Fetch one IQAN topic page and extract structured content."""
    result = {"url": url, "title": "", "status": "", "votes": 0,
              "body": "", "replies": [], "error": None}

    # Security gate: domain allowlist before any network call.
    ok, reason = check_url(url)
    if not ok:
        result["error"] = f"blocked: {reason}"
        return result

    time.sleep(REQUEST_DELAY)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("title")
    if title_tag:
        raw = title_tag.get_text()
        cleaned = re.sub(r"\s*/\s*Software\s*/\s*IQAN.*$", "", raw).strip()
        cleaned = re.sub(r"\s*/\s*Hardware\s*/\s*IQAN.*$", "", cleaned).strip()
        result["title"] = cleaned

    for tag in soup.find_all(class_=re.compile(r"status|badge|label", re.I)):
        text = tag.get_text(strip=True)
        if text and len(text) < 40:
            result["status"] = text
            break

    for v in soup.find_all(string=re.compile(r"^\+?\d+$")):
        try:
            result["votes"] = int(v.strip().replace("+", ""))
            break
        except ValueError:
            pass

    body_selectors = [
        {"class": re.compile(r"topic.description|post.body|userecho-comment-body", re.I)},
        {"class": re.compile(r"description|content|body", re.I)},
    ]
    for sel in body_selectors:
        tag = soup.find(attrs=sel)
        if tag:
            result["body"] = tag.get_text(separator="\n", strip=True)
            if len(result["body"]) > 50:
                break

    reply_containers = soup.find_all(class_=re.compile(r"comment|reply", re.I))
    seen_texts = set()
    for container in reply_containers:
        body_div = container.find(class_=re.compile(r"body|content|text", re.I))
        if not body_div:
            continue
        text = body_div.get_text(separator="\n", strip=True)
        if not text or text in seen_texts or len(text) < 20:
            continue
        if text == result["body"]:
            continue
        seen_texts.add(text)

        author_tag = container.find(class_=re.compile(r"user.name|author|username", re.I))
        author = author_tag.get_text(strip=True) if author_tag else "Unknown"

        reply_vote = 0
        for v in container.find_all(string=re.compile(r"^\+?\d+$")):
            try:
                reply_vote = int(v.strip().replace("+", ""))
                break
            except ValueError:
                pass

        result["replies"].append({"author": author, "text": text, "votes": reply_vote})

    result["replies"].sort(key=lambda r: -r["votes"])
    return result


def scrape_multiple(urls: list[str], max_threads: int = 3) -> list[dict]:
    """Scrape up to max_threads topic URLs, respecting REQUEST_DELAY."""
    return [scrape_topic(u) for u in urls[:max_threads]]


def format_for_llm(scraped: dict) -> str:
    """Format a scraped thread as clean, length-capped text for the LLM."""
    parts = [f"SOURCE: {scraped['url']}", f"TITLE: {scraped['title']}"]
    if scraped["status"]:
        parts.append(f"STATUS: {scraped['status']}")
    if scraped["body"]:
        parts.append(f"ORIGINAL POST:\n{scraped['body'][:800]}")
    if scraped["replies"]:
        parts.append("TOP REPLIES:")
        for r in scraped["replies"][:4]:
            parts.append(f"  [{r['author']} | +{r['votes']} votes]\n  {r['text'][:500]}")
    return "\n\n".join(parts)
