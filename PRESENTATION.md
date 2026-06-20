# RootIQ — Presentation

**PLC Error Intelligence — Diagnose faster, fix smarter.**

RootIQ is a fully local agent harness for PLC engineers. Upload an error log,
and it identifies the fault, reuses past fixes when it can, and otherwise mines
the IQAN community forum and a local LLM to produce a structured, actionable
solution — all without touching the cloud.

---

## What it does, end to end

1. **Upload** a PLC error log (PDF or image) on the Analyse page.
2. The **`extract_log` skill** pulls the raw text and auto-detects error codes
   (e.g. `COUT_OVERCURRENT`, `CAN01`, `E-205`).
3. The **agent** runs its pipeline:
   - **`lookup_history`** — if this code was solved before, return instantly (no LLM, no network).
   - On a miss, **`phase1_crawl.search_index`** finds the most relevant forum topics in the *local* offline index.
   - **`phase2_scrape`** fetches those threads (requests + BeautifulSoup), gated by a domain allowlist.
   - **Ollama** (local LLM) reads the scraped, clearly-delimited *untrusted* content and returns a structured JSON solution.
4. The **solution card** shows the root cause, numbered fix steps, source, and a
   confidence badge. Download it as Markdown or save it to history.
5. **`save_solution`** persists it (append/update, never delete) so the next
   occurrence is an instant history hit.

Every tool call passes through the **security interlock** first; every rejection
is logged.

---

## Screens (working as intended)

### Analyse page
The entry point: dark sidebar with live **Ollama status** and **index status**,
an uploader accepting PDF/PNG/JPG/TIFF/BMP, and the agent run panel.

![Analyse page](working_dir/screenshots/01_analyse.png)

> Here Ollama shows **offline** — RootIQ degrades gracefully to history-only
> instead of crashing (constraint #8). The index shows **6 topics indexed**.

### Solution History
Every saved diagnosis, searchable, with metric cards (total saved, history
re-uses, most common code), a table, and a full-record inspector.

![History page](working_dir/screenshots/02_history.png)

### Reports & Analytics
Metric cards plus Plotly charts: top error codes, source breakdown
(history vs forum), and solutions over time.

![Reports page](working_dir/screenshots/03_reports.png)

### Settings
Ollama config + connection test, **Phase 1 index** build/refresh, editable
**forum config (mcp.json)**, the **Security** panel (blocked patterns, blocked
commands, allowlisted domains, recent rejections), and maintenance/backup.

![Settings page](working_dir/screenshots/04_settings.png)

---

## How it maps to the assignment

| Requirement | In RootIQ |
|---|---|
| Agent loop talking to an LLM | `agent.py` — pipeline + local Ollama caller, JSON output with one strict retry |
| Read/write/create files in a working dir | `tools.py` — all confined to `working_dir/` via `_safe_path()` |
| A transform tool | `tools.transform_markdown` — markdown → standalone HTML |
| Config editable without touching the harness | `mcp.json` (Ollama, forums, scraping limits) via `config.py` |
| Drop-in skills | `skills/*.py` with a `SKILL` dict, auto-discovered by `agent.load_skills()` |
| Run commands securely | `tools.run_command` — `shell=False`, allow+deny lists, sandbox cwd, timeout |
| Security interlock + rejection log | `security.py` — runs before every tool; logs to `rejection_log.jsonl` |
| Offline / no cloud / no keys | Local Ollama + local index; nothing leaves the machine |

See **README.md** for the full per-tool security discussion (path traversal,
shell injection, SSRF, prompt injection, untrusted skills, secret leakage) and
the explicitly **accepted** residual risks.

---

## Verification done

- All modules compile; sandbox traversal, command allow/deny, and URL allowlist
  verified by smoke test.
- All four Streamlit pages execute headlessly with **zero exceptions**
  (`streamlit.testing` AppTest), and serve a healthy endpoint.
- Screenshots above were captured from the live app.

## Try the security interlock yourself
```python
from security import security_check, check_url
security_check("run_command", {"command": "rm -rf /"})      # -> (False, 'Blocked by pattern ...')
check_url("https://evil.com/x")                              # -> (False, 'Domain not in allowlist ...')

from tools import _safe_path
_safe_path("../../etc/passwd")                              # -> raises SandboxError
```
