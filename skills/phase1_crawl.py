"""
Phase 1 Crawler — IQAN Forum Topic Index Builder
Runs Playwright headless browser to crawl topic list pages (JS-rendered).
Output: working_dir/topic_index.json
Run manually (python skills/phase1_crawl.py) or from the Settings page.
"""
import json
import time
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "working_dir" / "topic_index.json"

COMMUNITIES = [
    ("software", "https://forum.iqan.se/communities/1-software/topics"),
    ("hardware", "https://forum.iqan.se/communities/5-hardware/topics"),
]
SCROLL_PAUSE = 1.5   # seconds between scrolls
MAX_SCROLLS = 80     # safety cap (~2500 topics at ~30 per scroll)

SKILL = {
    "name": "phase1_crawl",
    "description": "Crawl IQAN forum topic-list pages with a headless browser to build a URL index.",
}


def crawl_community(page, name, url, progress=None):
    """Scroll the topic list to load all JS-rendered topics, extract URLs."""
    page.goto(url, wait_until="networkidle", timeout=30000)

    topics = []
    seen = set()
    prev_count = 0
    no_change = 0

    for scroll_n in range(MAX_SCROLLS):
        links = page.query_selector_all("a[href*='/topics/']")
        for link in links:
            href = link.get_attribute("href") or ""
            if href.startswith("/"):
                href = "https://forum.iqan.se" + href
            if re.search(r"/topics/\d+-", href) and href not in seen:
                seen.add(href)
                title = (link.inner_text() or "").strip()
                topics.append({
                    "url": href,
                    "title": title,
                    "community": name,
                    "topic_id": re.search(r"/topics/(\d+)-", href).group(1),
                })

        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(SCROLL_PAUSE)

        if len(topics) == prev_count:
            no_change += 1
            if no_change >= 3:
                break
        else:
            no_change = 0
        prev_count = len(topics)
        if progress:
            progress(name, scroll_n + 1, len(topics))

    return topics


def run_phase1(progress=None) -> int:
    """Crawl all communities and merge into topic_index.json. Returns total count."""
    from playwright.sync_api import sync_playwright

    all_topics = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (compatible; RootIQ/1.0; research bot)"
        )
        page.set_default_timeout(30000)
        for name, url in COMMUNITIES:
            all_topics.extend(crawl_community(page, name, url, progress))
            time.sleep(2)  # polite delay between communities
        browser.close()

    OUTPUT.parent.mkdir(exist_ok=True)
    existing = []
    if OUTPUT.exists():
        try:
            existing = json.loads(OUTPUT.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = []

    existing_ids = {t["topic_id"]: i for i, t in enumerate(existing)}
    for t in all_topics:
        if t["topic_id"] in existing_ids:
            existing[existing_ids[t["topic_id"]]].update(t)
        else:
            existing.append(t)

    OUTPUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return len(existing)


def search_index(query: str, top_n: int = 5) -> list[dict]:
    """Keyword-match topic titles in the index. Empty list if not built yet."""
    if not OUTPUT.exists():
        return []
    try:
        topics = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    query_lower = (query or "").lower()
    query_words = [w for w in re.split(r"[\s_\-]+", query_lower) if w]

    scored = []
    for t in topics:
        title = t.get("title", "").lower()
        if query_lower and query_lower in title:
            score = 100
        else:
            score = sum(10 for w in query_words if w and w in title)
        if score > 0:
            scored.append((score, t))

    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored[:top_n]]


def index_stats() -> dict:
    """Summary for the Settings page."""
    if not OUTPUT.exists():
        return {"exists": False, "count": 0}
    try:
        topics = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"exists": True, "count": 0}
    return {
        "exists": True,
        "count": len(topics),
        "last_modified": OUTPUT.stat().st_mtime,
        "recent": topics[-5:][::-1],
    }


if __name__ == "__main__":
    n = run_phase1(progress=lambda c, s, t: print(f"  [{c}] scroll {s}: {t} topics"))
    print(f"Phase 1 complete. {n} topics indexed -> {OUTPUT}")
