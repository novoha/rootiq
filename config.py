"""
config.py — central config loader for RootIQ.
Loads mcp.json (Ollama settings, forum list, scraping params) once and
exposes helpers. Editing mcp.json never requires touching the harness code.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MCP_PATH = ROOT / "mcp.json"
WORKING_DIR = ROOT / "working_dir"

_DEFAULTS = {
    "ollama": {"url": "http://localhost:11434", "model": "phi3", "timeout": 120},
    "forums": [],
    "scraping": {
        "request_delay_seconds": 1.5,
        "max_threads_per_query": 3,
        "max_scroll_pages": 80,
        "scroll_pause_seconds": 1.5,
    },
}


def load_config() -> dict:
    """Read mcp.json, falling back to defaults if absent or malformed."""
    if not MCP_PATH.exists():
        return dict(_DEFAULTS)
    try:
        cfg = json.loads(MCP_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)
    # Merge missing top-level keys from defaults
    for k, v in _DEFAULTS.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg: dict) -> None:
    """Persist config back to mcp.json."""
    MCP_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def ollama_settings() -> dict:
    return load_config().get("ollama", _DEFAULTS["ollama"])


def scraping_settings() -> dict:
    return load_config().get("scraping", _DEFAULTS["scraping"])


def enabled_forums() -> list[dict]:
    return [f for f in load_config().get("forums", []) if f.get("enabled", True)]
