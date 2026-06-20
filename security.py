"""
security.py — Security Interlock
Called before EVERY tool and skill execution.
Logs all rejections to working_dir/rejection_log.jsonl

Defense layers:
  1. security_check()  — pattern + command screening on tool arguments
  2. check_url()       — domain allowlist for any outbound HTTP request
  3. tools._safe_path()— resolved-path sandbox (the real filesystem boundary)

The regex patterns are a cheap first screen, NOT the primary boundary. The
authoritative filesystem boundary is _safe_path() in tools.py (resolve() +
is_relative_to(WORKING_DIR)), which is OS-correct on Windows and Unix alike.
"""
import re
import json
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REJECT_LOG = ROOT / "working_dir" / "rejection_log.jsonl"
WORKING_DIR = (ROOT / "working_dir").resolve()

# First-screen patterns. Applied to a json.dumps() of the tool args.
BLOCKED_PATTERNS = [
    r"\.\.[/\\]",                              # path traversal
    r"(?<![:\w])[;`]",                         # shell statement separators / backticks
    r"\brm\s+-[rf]",                           # destructive deletion
    r"(password|secret|token|api_key)\s*=",    # secret assignment leaking into args
]

# Commands the run_command tool will never execute (first token match).
BLOCKED_COMMANDS = {
    "rm", "rmdir", "del", "dd", "mkfs", "format", "shutdown", "reboot",
    "curl", "wget", "nc", "ncat", "bash", "sh", "zsh", "powershell", "cmd",
    "sudo", "su", "chmod", "chown", "icacls",
}

# URL allowlist — only fetch URLs from these domains.
ALLOWED_SCRAPE_DOMAINS = {
    "forum.iqan.se",
}


def security_check(tool_name: str, args: dict) -> tuple[bool, str]:
    """Screen a tool call before it runs. Returns (allowed, reason)."""
    payload = json.dumps(args, default=str)

    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, payload, re.IGNORECASE):
            reason = f"Blocked by pattern: {pattern}"
            _log_rejection(tool_name, args, reason)
            return False, reason

    if tool_name == "run_command":
        raw = (args.get("command") or "").strip()
        first = raw.split()[0] if raw.split() else ""
        # Strip any path prefix (e.g. /usr/bin/rm -> rm)
        first = first.replace("\\", "/").split("/")[-1].lower()
        if first in BLOCKED_COMMANDS:
            reason = f"Blocked command: {first}"
            _log_rejection(tool_name, args, reason)
            return False, reason

    return True, "ok"


def check_url(url: str) -> tuple[bool, str]:
    """Validate a URL is in the scraping allowlist before fetching."""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            reason = f"Disallowed URL scheme: {parsed.scheme}"
            _log_rejection("scrape_url", {"url": url}, reason)
            return False, reason
        domain = parsed.netloc.lower().split(":")[0]
        if not any(domain == d or domain.endswith("." + d) for d in ALLOWED_SCRAPE_DOMAINS):
            reason = f"Domain not in allowlist: {domain}"
            _log_rejection("scrape_url", {"url": url}, reason)
            return False, reason
        return True, "ok"
    except Exception as e:  # noqa: BLE001 — never let a parse error open the gate
        _log_rejection("scrape_url", {"url": url}, str(e))
        return False, str(e)


def _log_rejection(tool_name, args, reason):
    entry = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tool": tool_name,
        "args": args,
        "reason": reason,
    }
    REJECT_LOG.parent.mkdir(exist_ok=True)
    with open(REJECT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, default=str) + "\n")
    print(f"[SECURITY BLOCK] [{tool_name}] - {reason}")
