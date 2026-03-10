"""
RSS Source for EvoClaw - Fetches and processes RSS feeds
"""
import feedparser
import json
from hashlib import sha1
from datetime import datetime

from evoclaw.workspace_resolver import resolve_workspace
from evoclaw.sqlite_memory import SQLiteMemoryStore

WORKSPACE = resolve_workspace(__file__)
CONFIG_PATH = WORKSPACE / "evoclaw" / "config.json"
MEMORY_DB_PATH = WORKSPACE / "memory" / "memory.db"
STATE_KEY = "evoclaw_state"

_MEMORY_STORE = None


def _get_memory_store():
    global _MEMORY_STORE
    if _MEMORY_STORE is None:
        store = SQLiteMemoryStore(MEMORY_DB_PATH)
        store.init_schema()
        _MEMORY_STORE = store
    return _MEMORY_STORE


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_state():
    default_state = {"rss_last_fetched": None, "source_last_polled": {}}
    state = _get_memory_store().get_state(STATE_KEY, default_state)
    if not isinstance(state, dict):
        return dict(default_state)
    normalized = dict(default_state)
    normalized.update(state)
    if not isinstance(normalized.get("source_last_polled"), dict):
        normalized["source_last_polled"] = {}
    return normalized


def save_state(state):
    _get_memory_store().upsert_state(STATE_KEY, state, datetime.now().isoformat())


def fetch_feed(url):
    """Fetch a single RSS feed"""
    try:
        feed = feedparser.parse(url)
        entries = []
        for entry in feed.entries[:10]:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", "")[:500],
                "published": entry.get("published", "")
            })
        return entries
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return []


def classify_significance(title, summary):
    """Auto-classify significance based on keywords"""
    text = (title + " " + summary).lower()

    notable_keywords = [
        "ai", "gpt", "chatgpt", "claude", "gemini",
        "breakthrough", "revolution", "launch", "release",
        "government", "policy", "regulation", "law",
        "stock", "market", "economy", "recession",
        "security", "privacy", "hack", "breach",
        "new", "first", "best", "top",
        "warning", "risk", "danger", "crisis"
    ]

    for kw in notable_keywords:
        if kw in text:
            return "notable"

    return "routine"


def poll_rss_sources():
    """Main function to poll all RSS sources and persist to memory.db only."""
    config = load_config()
    state = load_state()

    rss_config = config.get("sources", {}).get("rss", {})
    if not rss_config.get("enabled", False):
        return []

    feeds = rss_config.get("feeds", [])
    all_entries = []

    for feed_url in feeds:
        entries = fetch_feed(feed_url)
        for entry in entries:
            entry["source"] = feed_url
            entry["fetched_at"] = datetime.now().isoformat()
            all_entries.append(entry)

    store = _get_memory_store()
    for entry in all_entries:
        fetched_at = entry["fetched_at"]
        significance = classify_significance(entry.get("title", ""), entry.get("summary", ""))
        exp_record = {
            "id": "rss-" + sha1((entry.get("link") or entry.get("title") or fetched_at).encode("utf-8")).hexdigest()[:16],
            "timestamp": fetched_at,
            "created_at": fetched_at,
            "updated_at": fetched_at,
            "type": "rss_active",
            "significance": significance,
            "source": entry["source"],
            "title": entry.get("title", ""),
            "summary": entry.get("summary", ""),
            "content": (entry.get("title", "") + "\n" + entry.get("summary", "")).strip(),
            "metadata": {
                "link": entry.get("link", ""),
                "published": entry.get("published", ""),
            },
        }
        store.upsert_experience(exp_record)

    now_iso = datetime.now().isoformat()
    state["rss_last_fetched"] = now_iso
    source_last_polled = state.get("source_last_polled", {})
    if not isinstance(source_last_polled, dict):
        source_last_polled = {}
    source_last_polled["rss"] = now_iso
    state["source_last_polled"] = source_last_polled
    save_state(state)

    print(f"Fetched {len(all_entries)} RSS entries from {len(feeds)} feeds")
    return all_entries


if __name__ == "__main__":
    poll_rss_sources()
