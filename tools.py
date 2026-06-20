"""
tools.py — Sandboxed file tools for RootIQ.

Every path passed by a skill or the agent goes through _safe_path(), which
resolves the path and verifies it stays inside working_dir/. This is the
authoritative filesystem boundary (OS-correct on Windows and Unix), backing
up the cheaper regex screen in security.py.

Tools exposed:
  read_file(path)              -> str
  write_file(path, content)    -> str   (creates parent dirs inside sandbox)
  create_markdown(name, body)  -> str   (convenience for .md files)
  list_files(subdir="")        -> list[str]
  transform_markdown(path)     -> str   (md file -> standalone .html file)
  run_command(command)         -> str   (allowlisted, sandbox cwd)
"""
import subprocess
from pathlib import Path

from security import security_check

ROOT = Path(__file__).resolve().parent
WORKING_DIR = (ROOT / "working_dir").resolve()

# Commands explicitly permitted for run_command (the agent cannot run others).
ALLOWED_COMMANDS = {"python", "marp", "echo", "type", "dir", "ls"}


class SandboxError(Exception):
    """Raised when a path escapes the working directory."""


def _safe_path(path: str) -> Path:
    """
    Resolve `path` relative to working_dir and guarantee it does not escape.
    Absolute paths are accepted only if they already live inside the sandbox.
    """
    WORKING_DIR.mkdir(exist_ok=True)
    p = Path(path)
    candidate = p if p.is_absolute() else (WORKING_DIR / p)
    resolved = candidate.resolve()
    if not resolved.is_relative_to(WORKING_DIR):
        raise SandboxError(f"Path escapes working_dir: {path}")
    return resolved


def read_file(path: str) -> str:
    target = _safe_path(path)
    if not target.exists():
        return f"[error] file not found: {path}"
    return target.read_text(encoding="utf-8", errors="replace")


def write_file(path: str, content: str) -> str:
    ok, reason = security_check("write_file", {"path": path, "content": content})
    if not ok:
        return f"[blocked] {reason}"
    target = _safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"[ok] wrote {len(content)} chars to {target.relative_to(WORKING_DIR)}"


def create_markdown(name: str, body: str) -> str:
    if not name.endswith(".md"):
        name += ".md"
    return write_file(name, body)


def list_files(subdir: str = "") -> list[str]:
    base = _safe_path(subdir) if subdir else WORKING_DIR
    if not base.exists():
        return []
    return [str(p.relative_to(WORKING_DIR)) for p in base.rglob("*") if p.is_file()]


def transform_markdown(path: str) -> str:
    """
    Transform a markdown file in the sandbox into a standalone HTML file.
    This is the harness's 'turn files into something else' tool. It performs a
    minimal, dependency-free markdown->HTML conversion (headings, lists, code,
    bold/italic) and writes <name>.html next to the source.
    """
    src = _safe_path(path)
    if not src.exists():
        return f"[error] file not found: {path}"
    html_body = _md_to_html(src.read_text(encoding="utf-8", errors="replace"))
    doc = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{src.stem}</title>"
        "<style>body{font-family:system-ui,Segoe UI,Arial,sans-serif;"
        "max-width:760px;margin:2rem auto;padding:0 1rem;line-height:1.5;}"
        "code{background:#f4f4f4;padding:2px 5px;border-radius:4px;}"
        "pre{background:#f4f4f4;padding:1rem;border-radius:8px;overflow:auto;}"
        "h1{color:#0D9488;}</style></head><body>"
        f"{html_body}</body></html>"
    )
    out = src.with_suffix(".html")
    out.write_text(doc, encoding="utf-8")
    return f"[ok] transformed {src.name} -> {out.name}"


def _md_to_html(md: str) -> str:
    """Tiny, safe markdown subset -> HTML (no external deps)."""
    import html as _html
    import re

    lines = md.splitlines()
    out: list[str] = []
    in_code = False
    in_list = False
    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                out.append("</pre>")
                in_code = False
            else:
                out.append("<pre>")
                in_code = True
            continue
        if in_code:
            out.append(_html.escape(line))
            continue

        esc = _html.escape(line)
        # inline bold / italic / code
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        esc = re.sub(r"\*(.+?)\*", r"<em>\1</em>", esc)
        esc = re.sub(r"`(.+?)`", r"<code>\1</code>", esc)

        heading = re.match(r"(#{1,6})\s+(.*)", line)
        if heading:
            if in_list:
                out.append("</ul>")
                in_list = False
            level = len(heading.group(1))
            out.append(f"<h{level}>{_html.escape(heading.group(2))}</h{level}>")
        elif re.match(r"\s*[-*]\s+", line):
            if not in_list:
                out.append("<ul>")
                in_list = True
            item = re.sub(r"\s*[-*]\s+", "", esc, count=1)
            out.append(f"<li>{item}</li>")
        elif line.strip() == "":
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append("")
        else:
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(f"<p>{esc}</p>")
    if in_list:
        out.append("</ul>")
    if in_code:
        out.append("</pre>")
    return "\n".join(out)


def run_command(command: str) -> str:
    """
    Run an allowlisted command with cwd pinned to the sandbox.
    Goes through security_check() first; only ALLOWED_COMMANDS may execute.
    """
    ok, reason = security_check("run_command", {"command": command})
    if not ok:
        return f"[blocked] {reason}"

    parts = command.split()
    if not parts:
        return "[error] empty command"
    first = parts[0].replace("\\", "/").split("/")[-1].lower()
    if first not in ALLOWED_COMMANDS:
        return f"[blocked] command not in allowlist: {first}"

    try:
        proc = subprocess.run(
            parts,
            cwd=str(WORKING_DIR),
            capture_output=True,
            text=True,
            timeout=60,
            shell=False,  # never invoke a shell — avoids metacharacter injection
        )
    except subprocess.TimeoutExpired:
        return "[error] command timed out after 60s"
    except FileNotFoundError:
        return f"[error] executable not found: {first}"
    out = (proc.stdout or "") + (proc.stderr or "")
    return out.strip() or f"[ok] exit {proc.returncode}"
