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

# Pages to crawl. Communities hold "topics"; the knowledge base holds "articles".
COMMUNITIES = [
    ("software", "https://forum.iqan.se/communities/1-software/topics"),
    ("hardware", "https://forum.iqan.se/communities/5-hardware/topics"),
    ("knowledge-base", "https://forum.iqan.se/knowledge-bases/2-knowledge-base"),
]

# A topic OR a knowledge-base article both count as an indexable entry.
_ENTRY_RE = re.compile(r"/(?:topics|articles)/(\d+)-")
SCROLL_PAUSE = 1.2   # polite delay between page fetches
MAX_PAGES = 400      # safety cap on pagination depth per category
MAX_SCROLLS = MAX_PAGES  # back-compat alias (Settings progress bar reads this)

SKILL = {
    "name": "phase1_crawl",
    "description": "Crawl IQAN forum topic-list pages with a headless browser to build a URL index.",
}


def crawl_community(page, name, url, progress=None):
    """
    Walk the paginated topic/article list (?page=N) and collect every entry.
    The UserEcho list paginates server-side via ?page=, so we step pages until
    two consecutive pages add nothing new (or we hit MAX_PAGES).
    """
    topics = []
    seen = set()
    empty_streak = 0
    sep = "&" if "?" in url else "?"

    for page_n in range(1, MAX_PAGES + 1):
        page.goto(f"{url}{sep}page={page_n}",
                  wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector("a[href*='/topics/'], a[href*='/articles/']",
                                   timeout=8000)
        except Exception:
            pass
        time.sleep(SCROLL_PAUSE)

        new = 0
        for link in page.query_selector_all("a[href*='/topics/'], a[href*='/articles/']"):
            href = link.get_attribute("href") or ""
            if href.startswith("/"):
                href = "https://forum.iqan.se" + href
            m = _ENTRY_RE.search(href)
            if not m or href in seen:
                continue
            title = (link.inner_text() or "").strip()
            # Skip junk anchors whose text is just a raw URL (in-content links).
            if not title or title.lower().startswith("http"):
                continue
            seen.add(href)
            new += 1
            topics.append({
                "url": href,
                "title": title,
                "community": name,
                "topic_id": m.group(1),
            })

        if progress:
            progress(name, page_n, len(topics))
        print(f"  [{name}] page {page_n}: +{new} (total {len(topics)})")

        if new == 0:
            empty_streak += 1
            if empty_streak >= 2:
                break  # reached the end of this category
        else:
            empty_streak = 0

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

    # Key by URL (a topic and an article can share the same numeric id).
    existing_by_url = {t["url"]: i for i, t in enumerate(existing)}
    for t in all_topics:
        if t["url"] in existing_by_url:
            existing[existing_by_url[t["url"]]].update(t)
        else:
            existing.append(t)

    OUTPUT.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    return len(existing)


# Very common words that add noise rather than signal when title-matching.
_STOPWORDS = {"the", "and", "a", "of", "to", "is", "for", "with", "at", "on",
              "in", "an", "by", "or", "this", "that", "it", "as", "be"}


def search_index(query: str, top_n: int = 5) -> list[dict]:
    """
    Keyword-match topic/article titles in the index. Accepts a short error code
    OR a longer blob of OCR'd log text — it tokenises and scores on overlap, so
    'Chassis module No contact ...' will surface 'No contact and critical CAN
    bus error'. Empty list if the index isn't built yet.
    """
    if not OUTPUT.exists():
        return []
    try:
        topics = json.loads(OUTPUT.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    query_lower = (query or "").lower()
    # Tokenise on anything that isn't a letter/digit, keep meaningful words.
    raw_words = re.split(r"[^a-z0-9]+", query_lower)
    query_words = [w for w in raw_words if len(w) >= 2 and w not in _STOPWORDS]

    scored = []
    for t in topics:
        title = t.get("title", "").lower()
        title_words = set(re.split(r"[^a-z0-9]+", title))
        score = 0
        if query_lower and query_lower in title:
            score = 100  # exact phrase
        else:
            score = sum(10 for w in set(query_words) if w in title_words)
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
