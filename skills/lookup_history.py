"""
lookup_history skill — search working_dir/solutions.json by error code.

Read-only. Returns the stored solution dict if a matching error_code exists,
else None. Matching is case-insensitive and also tries a normalised form.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = ROOT / "working_dir" / "solutions.json"

SKILL = {
    "name": "lookup_history",
    "description": "Look up a previously saved solution by error code.",
}


def _load() -> list[dict]:
    if not SOLUTIONS.exists():
        return []
    try:
        return json.loads(SOLUTIONS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _norm(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def run(error_code: str) -> dict | None:
    """Return the stored solution for error_code, or None on a miss."""
    if not error_code:
        return None
    target = _norm(error_code)
    for entry in _load():
        if _norm(entry.get("error_code", "")) == target:
            return entry
    return None


def all_solutions() -> list[dict]:
    """Expose the full history (used by History/Reports pages)."""
    return _load()
