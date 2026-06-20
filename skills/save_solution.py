"""
save_solution skill — append or update a solution in solutions.json.

Rules (from spec): never delete, never duplicate. If the error_code already
exists, UPDATE in place (increment scrape_count, refresh date_saved, keep the
best confidence). All writes go through tools._safe_path via write_file.
"""
import json
import uuid
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOLUTIONS = ROOT / "working_dir" / "solutions.json"

SKILL = {
    "name": "save_solution",
    "description": "Persist a solution to history, updating on duplicate error codes.",
}

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _load() -> list[dict]:
    if not SOLUTIONS.exists():
        return []
    try:
        return json.loads(SOLUTIONS.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _norm(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def _best_confidence(a: str, b: str) -> str:
    ra = _CONFIDENCE_RANK.get((a or "").lower(), 0)
    rb = _CONFIDENCE_RANK.get((b or "").lower(), 0)
    return a if ra >= rb else b


def run(solution: dict) -> dict:
    """
    Save `solution`. Returns the stored record (with id/date assigned).
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    data = _load()
    target = _norm(solution.get("error_code", ""))

    for entry in data:
        if target and _norm(entry.get("error_code", "")) == target:
            entry["scrape_count"] = int(entry.get("scrape_count", 1)) + 1
            entry["date_saved"] = now
            entry["confidence"] = _best_confidence(
                entry.get("confidence", "Low"), solution.get("confidence", "Low")
            )
            # Prefer richer fields if the new record has them
            for k in ("device", "root_cause", "fix_steps", "source_url",
                      "source_type", "notes", "model_used", "raw_text_snippet"):
                if solution.get(k):
                    entry[k] = solution[k]
            _write(data)
            return entry

    record = {
        "id": str(uuid.uuid4()),
        "error_code": solution.get("error_code", "UNKNOWN"),
        "device": solution.get("device"),
        "root_cause": solution.get("root_cause", ""),
        "fix_steps": solution.get("fix_steps", []),
        "source_url": solution.get("source_url", ""),
        "source_type": solution.get("source_type", "forum"),
        "confidence": solution.get("confidence", "Low"),
        "notes": solution.get("notes", ""),
        "raw_text_snippet": (solution.get("raw_text_snippet", "") or "")[:300],
        "date_saved": now,
        "scrape_count": 1,
        "model_used": solution.get("model_used", ""),
    }
    data.append(record)
    _write(data)
    return record


def _write(data: list[dict]) -> None:
    # Routed through the sandbox boundary for consistency with the harness rules.
    from tools import write_file
    write_file("solutions.json", json.dumps(data, indent=2))
