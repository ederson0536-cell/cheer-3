"""
RSS Source for EvoClaw - Fetches and processes RSS feeds
"""
import feedparser
import json
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

from evoclaw.sqlite_memory import SQLiteMemoryStore

WORKSPACE = resolve_workspace(__file__)
CONFIG_PATH = WORKSPACE / "evoclaw" / "config.json"
MEMORY_DB_PATH = WORKSPACE / "memory" / "memory.db"
EXPERIENCES_PATH = WORKSPACE / "memory" / "experiences"
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
        for entry in feed.entries[:10]:  # Top 10 items
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
    
    # Keywords that indicate important/Notable content
    notable_keywords = [
        "ai", "gpt", "chatgpt", "claude", "gemini",  # AI
        "breakthrough", "revolution", "launch", "release",  # Big events
        "government", "policy", "regulation", "law",  # Policy
        "stock", "market", "economy", "recession",  # Finance
        "security", "privacy", "hack", "breach",  # Security
        "new", "first", "best", "top",  # Positive
        "warning", "risk", "danger", "crisis"  # Negative
    ]
    
    # Check for notable keywords
    for kw in notable_keywords:
        if kw in text:
            return "notable"
    
    return "routine"

def poll_rss_sources():
    """Main function to poll all RSS sources"""
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
    
    # Log as experiences
    date_str = datetime.now().strftime("%Y-%m-%d")
    exp_file = EXPERIENCES_PATH / f"{date_str}.jsonl"
    EXPERIENCES_PATH.mkdir(parents=True, exist_ok=True)
    
    for entry in all_entries:
        exp_record = {
            "timestamp": entry["fetched_at"],
            "type": "rss",
            "significance": "routine",
            "source": entry["source"],
            "title": entry["title"],
            "summary": entry["summary"],
            "link": entry["link"]
        }
        with open(exp_file, "a") as f:
            f.write(json.dumps(exp_record, ensure_ascii=False) + "\n")
    
    # Update state
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
