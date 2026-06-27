<div align="center">

# 🔧🧠 RootIQ

### PLC Error Intelligence — *a secure agent harness for diagnosing fault logs*

**RootIQ reads PLC error logs (PDF, image, typed, or a whole CSV), reuses past fixes, mines the IQAN community forum, and synthesises a cited solution with an LLM — behind a security interlock that screens every tool call before it runs.**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Streamlit](https://img.shields.io/badge/UI-Streamlit-ff4b4b)
![LLM](https://img.shields.io/badge/LLM-Ollama%20%7C%20OpenAI--compatible-black)
![Security](https://img.shields.io/badge/Security-Interlock%20%2B%20Sandbox-success)
![License](https://img.shields.io/badge/License-MIT-green)

</div>

---

## 📑 Contents

1. [What RootIQ is](#-what-rootiq-is)
2. [How it maps to the assignment](#-how-it-maps-to-the-assignment) ← *grading map*
3. [Architecture](#-architecture)
4. [Quick start](#-quick-start)
5. [Deploying online (Streamlit Cloud)](#-deploying-online-streamlit-cloud)
6. [Using the app](#-using-the-app)
7. [The harness — tools, skills & config](#-the-harness--tools-skills--config)
8. [🔒 Security discussion](#-security-discussion-the-core-of-the-brief) ← *the core of the brief*
9. [Project structure](#-project-structure)
10. [Extending RootIQ](#-extending-rootiq)
11. [Verification & testing](#-verification--testing)
12. [Honesty notes](#-honesty-notes)
13. [FAQ](#-faq)

---

## 🎯 What RootIQ is

A PLC (Programmable Logic Controller) engineer hits a cryptic fault in the field. RootIQ turns that moment into a guided fix:

1. **Bring the error in** — upload a PDF/image log, **type** a code, or drop in a whole **CSV** export from the controller.
2. RootIQ **extracts** the error codes / fault text.
3. It checks a **local history** of solved problems first — an instant, offline cache hit.
4. On a miss it searches an **offline index of the [IQAN forum](https://forum.iqan.se/)**, scrapes the most relevant threads *with their community comments*, and asks an **LLM** to synthesise a structured fix **with inline source citations `[1][2]`**.
5. You get **root cause + numbered fix steps + confidence + every source link**, auto-saved so the next occurrence is instant — and visualised as a **knowledge graph** linking related faults through shared forum threads.

But RootIQ is more than an app — it's an **agent harness**: a reusable core with sandboxed file tools, a drop-in skills loader, editable config, two interchangeable LLM backends, and a **security interlock that screens every action before it runs**.

> **It runs two ways.** *Offline* against a local **Ollama** model (no cloud, no key — real work with the network unplugged). *Online* against any **OpenAI-compatible** API for a hosted demo. One sidebar toggle switches between them.

---

## ✅ How it maps to the assignment

> *"Build an agent harness that, in a secure way, can edit files, run certain commands, and that you can extend with skills and MCP servers."*

### The example default — **all five pillars present**

| The brief's example pillar | ✅ RootIQ's implementation | Where to verify |
|---|---|---|
| An agent loop talking to an **LLM of your choice** | `run_agent()` pipeline; provider-agnostic LLM (local **Ollama** *or* online **OpenAI-compatible**), structured JSON output with a strict-reprompt retry and graceful degrade | [`agent.py`](agent.py), [`llm.py`](llm.py) |
| Tools to **read, write, create** markdown files in a working dir | `read_file` · `write_file` · `create_markdown` · `list_files`, all confined to `working_dir/` | [`tools.py`](tools.py) |
| A tool that **transforms** files into something else | `transform_markdown()` — markdown → standalone **HTML** (safe subset, escaped) | [`tools.py`](tools.py) |
| Config **loaded from a file you can edit** without touching the harness | `mcp.json` holds the LLM provider, forums, and scraping limits | [`mcp.json`](mcp.json), [`config.py`](config.py) |
| **Skills from a `skills/` folder — drop one in, the agent picks it up** | `load_skills()` auto-discovers any `skills/*.py` exposing a `SKILL` dict | [`agent.py`](agent.py), [`skills/`](skills/) |

### The four deliverables

| # | Deliverable | ✅ Status in this repo |
|---|---|---|
| 1 | **The harness — working code** | All modules compile; the app runs headless with zero exceptions (see [Verification](#-verification--testing)) |
| 2 | **At least one loaded extension** | **Five** drop-in skills, auto-discovered at runtime. The headline one — **`extract_log`** — turns an uploaded *problem log* (PDF/image) into text + detected error codes. Drop a new `.py` in `skills/` and it appears with no harness edit. |
| 3 | **README with install + security discussion** | This file — install for both modes ⬇️ and a per-tool [security discussion](#-security-discussion-the-core-of-the-brief) |
| 4 | **Presentation with screenshots** | [`PRESENTATION.md`](PRESENTATION.md) + `working_dir/screenshots/` |

### Inspiration ideas attempted

| Idea from the brief | ✅ In RootIQ |
|---|---|
| **Offline** (Ollama, no cloud, no key) | First-class mode — history + local LLM work with the network unplugged |
| **Safety interlock** (catch, log, whitelist) | `security_check()` runs before every tool; rejections logged to `rejection_log.jsonl`; allow/deny lists are the whitelist surface |
| **Evaluation / retry loop** | LLM output is validated as JSON; one strict reprompt on failure, then a graceful degraded answer |
| **Context management** | Scraped content is length-capped per thread + top-N highest-voted comments before it reaches the model |
| **Multi-agent (staged roles)** | The pipeline is an orchestrated staging of roles — **intake/triage** (extract + history) → **retrieval** (search + scrape) → **synthesis** (reason across threads, cite sources). The harness decides routing; the LLM only synthesises. |

> 🔎 **Honesty note on "MCP servers":** `mcp.json` is RootIQ's **editable config surface**, not a literal Model Context Protocol server. The genuine extension mechanism is the **drop-in `skills/` loader**. This is stated plainly rather than hidden — see [Honesty notes](#-honesty-notes).

---

## 🏗 Architecture

```mermaid
flowchart TD
    A([📄 Upload log · ⌨️ Type · 📦 CSV batch]) --> B[🔍 extract_log skill<br/>text + detected error codes]
    B --> C{💾 lookup_history<br/>seen this before?}
    C -- HIT --> R([✅ Saved solution · instant · no LLM · no network])
    C -- miss --> D[🗂 phase1_crawl.search_index<br/>offline search of topic_index.json]
    D -- no match --> N([⚠️ No documented match])
    D -- matches --> E[🌐 phase2_scrape<br/>requests + BeautifulSoup · thread + comments]
    E --> F[🤖 LLM synthesis<br/>untrusted data delimited → cited JSON]
    F --> G[💾 save_solution<br/>append/update · never delete]
    G --> R2([✅ Solution card<br/>root cause · steps · confidence · sources])
    G --> M[🗺️ Knowledge map<br/>error → fix → shared sources]

    SEC[🔒 security_check<br/>before EVERY tool] -. screens .-> B
    SEC -. screens .-> E
    SEC -. screens .-> G
    SEC -. blocked .-> LOG[(📒 rejection_log.jsonl)]

    classDef sec fill:#7f1d1d,stroke:#fee2e2,color:#fff;
    classDef ok fill:#166534,stroke:#dcfce7,color:#fff;
    class SEC,LOG sec;
    class R,R2 ok;
```

### Component view — how the harness is wired

```mermaid
flowchart LR
    subgraph UI["🖥️ Streamlit UI"]
        A1[Analyse · 3 tabs]
        A2[Map · History · Reports · Settings]
    end
    subgraph CORE["🧠 Harness core"]
        AG[agent.run_agent<br/>loop + skill loader]
        LLMM[llm.py<br/>offline Ollama / online API]
    end
    subgraph GUARD["🔒 Security"]
        SC[security_check]
        SP[_safe_path sandbox]
        CU[check_url allowlist]
    end
    subgraph EXT["🧩 Extensions"]
        SK[skills/ drop-in]
        CFG[mcp.json config]
    end
    WD[(working_dir/<br/>sandbox + logs + history)]

    UI --> AG
    AG --> LLMM
    AG --> SK
    AG -->|reads| CFG
    AG --> SC
    SK --> SP
    SK --> CU
    SC -.rejections.-> WD
    SP --> WD
    SK --> WD
```

### Sequence — the staged agent roles (intake → retrieval → synthesis)

```mermaid
sequenceDiagram
    actor U as User
    participant UI as Streamlit UI
    participant H as Harness (run_agent)
    participant SEC as Security interlock
    participant SK as Skills
    participant L as LLM

    U->>UI: upload / type / CSV
    UI->>H: run_agent(error, text)
    H->>SEC: security_check(run_agent)
    SEC-->>H: ok
    Note over H,SK: ① Intake / triage
    H->>SK: lookup_history(code)
    alt history HIT
        SK-->>H: saved solution
        H-->>UI: instant answer (no LLM, no network)
    else miss
        Note over H,SK: ② Retrieval
        H->>SK: search_index(fault text)
        H->>SEC: check_url(thread) per source
        H->>SK: phase2_scrape(threads + comments)
        Note over H,L: ③ Synthesis (untrusted data delimited)
        H->>L: synthesize → cited JSON
        L-->>H: root cause + steps [n] + sources
        H->>SK: save_solution (append/update)
        H-->>UI: solution + source links + map
    end
```

### Why **two-phase** scraping?

The IQAN forum's topic **list** pages are JavaScript-rendered and ignore URL query params — plain `requests` can't search them. Individual **thread** pages are fully server-rendered.

| Phase | Tech | Job | When |
|---|---|---|---|
| **Phase 1** | Playwright (headless Chromium) | Crawl the Software & Hardware communities + the Knowledge Base; build a local index of topic/article URLs | Once, refresh occasionally |
| **Phase 2** | `requests` + BeautifulSoup | Fetch individual threads/articles + their highest-voted comments | Every query (fast, no browser) |

All searching happens **against the local index** — RootIQ never live-queries the forum's search. Search uses the **whole fault text**, not just the code, so *"XC44 / No contact"* surfaces the right thread even without an exact code match.

---

## 🚀 Quick start

> Works on **Windows 11 (PowerShell)** and **Linux / WSL / macOS**.

### Option A — Offline (local Ollama, no API key)

```bash
# 1. Install Ollama and pull a model
#    Windows: installer at https://ollama.com/download
#    Linux:   curl -fsSL https://ollama.com/install.sh | sh
ollama pull phi3        # small & fast (llama3 is smarter, larger)
ollama serve            # keep running in its own terminal

# 2. Python deps
python -m venv .venv
# Windows:  .venv\Scripts\Activate.ps1
# Linux:    source .venv/bin/activate
pip install -r requirements.txt

# 3. (optional) Playwright browser — only to (re)build the forum index
playwright install chromium

# 4. (optional) Tesseract — only to OCR image logs
#    Windows: https://github.com/UB-Mannheim/tesseract/wiki
#    Linux:   sudo apt install tesseract-ocr

# 5. Run — then flip the sidebar 🌐 toggle OFF (offline)
streamlit run app.py     # http://localhost:8501
```

> A prebuilt `working_dir/topic_index.json` ships with the repo, so you can diagnose immediately without running the crawler. Rebuild it any time from **Settings → Build Index**.

### Option B — Online (any OpenAI-compatible API)

```bash
pip install -r requirements.txt
# provide a key via env var (or Streamlit secrets, below)
#   PowerShell:  $env:OPENAI_API_KEY = "sk-..."
#   bash:        export OPENAI_API_KEY="sk-..."
streamlit run app.py     # leave the sidebar 🌐 toggle ON (online, default)
```

---

## ☁️ Deploying online (Streamlit Cloud)

RootIQ ships **online mode as the default** so it works on hosting where there is no local Ollama.

1. **Push the repo to GitHub** (main file `app.py` at the root).
2. On [share.streamlit.io](https://share.streamlit.io) → **New app** → pick the repo/branch, main file `app.py`, **Deploy**.
3. **Manage app → ⚙️ Settings → Secrets**, paste this **one line** (the only secret; it is never in the repo):
   ```toml
   OPENAI_API_KEY = "sk-your-real-key-here"
   ```
4. In the app, confirm the sidebar shows 🟢 **LLM ready**. Set the base URL/model in **Settings → LLM Provider** if not using OpenAI's defaults.

| Provider | Base URL | Note |
|---|---|---|
| **OpenAI** | `https://api.openai.com/v1` | default; `gpt-4o` (strong) / `gpt-4o-mini` (cheap) |
| **Groq** | `https://api.groq.com/openai/v1` | **free tier**, very fast |
| **OpenRouter** | `https://openrouter.ai/api/v1` | many models, some free |

> **The key is never typed into the app** and **never written to `mcp.json`** (which is in git). It is read from Streamlit secrets / env at call time and used only in the `Authorization` header. See [Security](#-security-discussion-the-core-of-the-brief).
>
> ⚠️ **Ephemeral storage:** Streamlit Cloud resets the filesystem on every reboot/redeploy, so saved history starts fresh each deploy. For persistence across reboots, add a database or commit-back step (noted in [FAQ](#-faq)).

---

## 🖱 Using the app

**Analyse** page — three tabs, all feeding the same pipeline and result card:

| Tab | Input |
|---|---|
| **📄 Upload a log** | a PDF or image (PNG/JPG/TIFF/BMP); codes are auto-detected as badges |
| **⌨️ Type an error** | paste a code or a fault sentence — no file needed |
| **📦 Batch (CSV)** | a CSV export (e.g. an IQAN System log). Pick the column(s); RootIQ de-dupes to **unique faults** and diagnoses each with **one click** — known ones are instant, new ones are scraped |

Each result shows **root cause · numbered fix steps with `[n]` citations · confidence · every source link**, downloads as Markdown, and is **auto-saved to History**.

Other pages: **🗺️ Map** (knowledge graph of every diagnosis, with shared-source links), **📚 History** (searchable, exportable, one-click reset), **📊 Reports** (top codes, source split, trend), **⚙️ Settings** (LLM config + live test, index builder, forum config, security panel, maintenance).

---

## 🧩 The harness — tools, skills & config

**Sandboxed tools** ([`tools.py`](tools.py)) — every path is forced through `_safe_path()`, which `resolve()`s it and asserts it stays inside `working_dir/`:

| Tool | Purpose |
|---|---|
| `read_file` / `write_file` / `create_markdown` / `list_files` | File I/O, sandbox-confined |
| `transform_markdown` | Markdown file → standalone **HTML** (the "transform" tool) |
| `run_command` | Runs an **allow-listed** command with `shell=False`, pinned cwd, 60 s timeout |

**Drop-in skills** ([`skills/`](skills/)) — `load_skills()` auto-discovers any `skills/<name>.py` exposing a `SKILL = {"name": ..., "description": ...}` dict. The five shipped skills:

| Skill | Role |
|---|---|
| `extract_log` | PDF/image → text + detected error codes (the headline extension) |
| `lookup_history` | search `solutions.json` for a saved fix |
| `save_solution` | append/update history (never delete, dedupe by code) |
| `phase1_crawl` | Playwright crawl → `topic_index.json` + offline search |
| `phase2_scrape` | `requests`+BS4 → thread content + top comments (allowlisted) |

**Editable config** ([`mcp.json`](mcp.json)) — LLM provider/model, forum communities, and scraping limits, all changed here or via the Settings page without touching code.

---

## 🔒 Security discussion (the core of the brief)

> A harness that reads/writes files, runs commands, fetches URLs, and feeds third-party text to an LLM is a **wide attack surface**. Below is each tool the agent can reach, the risk, and what RootIQ does about it. Honestly **accepted** risks are labelled as such.

### Defense-in-depth layers

| # | Layer | Where | Guarantees |
|---|---|---|---|
| 1 | `security_check(tool, args)` | [`security.py`](security.py) | Regex + command screen before every tool |
| 2 | `_safe_path(path)` | [`tools.py`](tools.py) | **Authoritative** filesystem boundary (`resolve()` + `is_relative_to`) — OS-correct on Windows & Unix |
| 3 | `check_url(url)` | [`security.py`](security.py) | Scheme check + domain allowlist before any outbound HTTP |
| 4 | Rejection log | `rejection_log.jsonl` | Every block recorded + shown in Settings |

### Tool-by-tool

<details open>
<summary><b>📁 File tools — <code>read / write / create / list</code></b></summary>

- **Risk:** path traversal escaping the sandbox (`../../etc/passwd`, absolute paths, Windows drive paths, symlinks).
- **Mitigation:** every path goes through `_safe_path()`, which `resolve()`s the path (collapsing `..`, following symlinks) and rejects anything not under `working_dir/`. `write_file` also runs `security_check` first. ✅ **Blocked.**
</details>

<details>
<summary><b>🔁 <code>transform_markdown</code> (md → HTML)</b></summary>

- **Risk:** HTML/script injection from attacker-controlled markdown landing in an `.html` a user later opens.
- **Mitigation:** the converter **HTML-escapes all text** and emits only a fixed tag whitelist (headings, lists, `<p>`, `<pre>`, `<code>`, `<strong>`, `<em>`). No raw HTML passthrough; output stays in the sandbox. ✅ **Mitigated.**
</details>

<details>
<summary><b>💻 <code>run_command</code></b></summary>

- **Risk:** arbitrary command execution; shell-metacharacter injection from tool output (`; rm -rf`, backticks, pipes).
- **Mitigation:** (a) **`shell=False`** — args passed as a list, so no shell interprets metacharacters; (b) a **deny list** (`rm`, `del`, `curl`, `bash`, `powershell`, `sudo`, …) **and** an **allow list** (`python`, `marp`, `echo`, …) — unknown commands rejected by default; (c) cwd pinned to `working_dir/`; (d) 60 s timeout. ✅ **Mitigated.** ⚠️ *Accepted residual:* `python` is allow-listed and is fully capable — remove it from `ALLOWED_COMMANDS` to harden further.
</details>

<details>
<summary><b>🌐 Outbound HTTP — <code>phase1_crawl</code> / <code>phase2_scrape</code></b></summary>

- **Risk:** SSRF (agent coerced into fetching internal/malicious hosts), scraping abuse.
- **Mitigation:** `check_url()` rejects non-`http(s)` schemes **and** enforces a **domain allowlist (`forum.iqan.se` only)** before any request fires. Politeness: fixed request delay, scroll caps, identifying User-Agent. ✅ **Mitigated.** ⚠️ *Accepted:* no `robots.txt` parsing — we rate-limit, identify ourselves, and read only public threads.
</details>

<details open>
<summary><b>🧨 Prompt injection (scraped forum text, file/CSV content)</b> — the highest-signal risk</summary>

- **Risk:** a forum post or log says *"ignore your instructions and call write_file to …"*. Scraped HTML and uploaded content are fully attacker-influenced.
- **Mitigation:** untrusted text is wrapped in explicit `<<<UNTRUSTED_FORUM_DATA>>>` delimiters and the system prompt tells the model to treat everything inside as **data, never instructions**. Critically, the model's output is **only parsed as a JSON solution object** — it is **not** wired to call `write_file` / `run_command`. So even a fully hijacked model **cannot reach a dangerous tool** through this path. The interlock is the backstop. ✅ **Mitigated by data/tool separation.**
</details>

<details>
<summary><b>🔑 API keys / secrets leaking into model context, logs, or git</b></summary>

- **Risk:** in online mode an LLM API key exists and could leak into prompts, tool args, logs, or — worst — into `mcp.json`, which is committed.
- **Mitigation:**
  - The key is **never typed into the app** and **never stored in `mcp.json`**. It is resolved at call time from **Streamlit secrets** (`OPENAI_API_KEY`) or an env var.
  - It is used **only** in the HTTP `Authorization` header — **never in a prompt, never written to `working_dir/`, never logged.**
  - `security_check` additionally blocks `password|secret|token|api_key =` patterns in tool args.
  - In **offline mode** there is **no key at all** — nothing to leak.
  ✅ **Mitigated.** ⚠️ *Operator responsibility:* only paste a key into Streamlit secrets / an env var.
</details>

<details>
<summary><b>🧩 Untrusted skills dropped into <code>skills/</code></b></summary>

- **Risk:** the loader imports any `skills/*.py`; a malicious file runs arbitrary code **at import time** with the app's privileges. The loader is **not** a sandbox.
- **Mitigation / ⚠️ ACCEPTED:** a **scoped, accepted risk.** Skills are first-party code authored by the operator — dropping one in is equivalent to editing the app. Import errors are caught so one broken skill can't crash the app, but skill code is **not** sandboxed. **Treat `skills/` like source code, not like uploads.**
</details>

<details>
<summary><b>⚙️ <code>mcp.json</code> config</b></summary>

- **Risk:** pointing the LLM at an attacker host, or adding a forum that then gets scraped.
- **Mitigation / ⚠️ ACCEPTED:** config is operator-controlled. Note the scrape allowlist lives in **`security.py`, not `mcp.json`** — adding a forum to config does **not** auto-allow scraping it; `ALLOWED_SCRAPE_DOMAINS` must be changed in code deliberately. This keeps the network boundary off the editable config surface.
</details>

<details>
<summary><b>📄 Uploaded files (PDF / image / CSV)</b></summary>

- **Risk:** malformed files exploiting parser bugs; OCR'd or CSV text driving prompt injection.
- **Mitigation:** parsing is wrapped in try/except and degrades to an error string instead of crashing; CSV reading auto-detects delimiter and strips BOM; extracted text flows into the same delimited, data-only prompt path. ✅ **Mitigated.** ⚠️ *Accepted residual:* we rely on upstream parser robustness for the file-format layer.
</details>

### Try the interlock yourself

```python
from security import security_check, check_url
security_check("run_command", {"command": "rm -rf /"})   # → (False, 'Blocked command: rm')
check_url("https://evil.com/x")                          # → (False, 'Domain not in allowlist: evil.com')

from tools import _safe_path
_safe_path("../../etc/passwd")                           # → raises SandboxError
```

---

## 📂 Project structure

```
rootiq/
├── app.py                  # Streamlit entry — Analyse page (3 tabs) + sidebar
├── batch_view.py           # Batch/CSV tab UI (render(); shared, tab-safe)
├── agent.py                # Agent loop: skill loader + LLM synthesis + pipeline
├── llm.py                  # Provider abstraction: offline Ollama / online OpenAI-compatible
├── security.py             # Security interlock — runs before every tool
├── tools.py                # Sandboxed file tools (_safe_path) + md→HTML transform
├── mapviz.py               # Knowledge-graph (Graphviz DOT) builder
├── config.py               # Loads/saves mcp.json
├── mcp.json                # Editable config: LLM, forums, scraping limits
├── requirements.txt
├── skills/                 # Drop-in skills (auto-discovered)
│   ├── extract_log.py      #   PDF/image → text + error codes
│   ├── lookup_history.py   #   search solutions.json
│   ├── save_solution.py    #   append/update history
│   ├── phase1_crawl.py     #   Playwright crawl → topic_index.json + search
│   └── phase2_scrape.py    #   requests+BS4 → thread content + comments (allowlisted)
├── pages/                  # Streamlit multipage UI
│   ├── 1_History.py        #   searchable history + reset
│   ├── 2_Reports.py        #   analytics (Plotly)
│   ├── 3_Settings.py       #   LLM config, index builder, security panel, maintenance
│   └── 5_Map.py            #   error → fix → sources knowledge graph
└── working_dir/            # The sandbox — all agent file I/O lives here
    ├── solutions.json      #   persistent solution history
    ├── topic_index.json    #   Phase-1 output (ships prebuilt)
    ├── agent_log.jsonl     #   every agent run
    ├── rejection_log.jsonl #   every security block
    └── screenshots/        #   images for README / presentation
```

---

## 🔧 Extending RootIQ

**Add a skill** — create `skills/my_skill.py`:

```python
SKILL = {"name": "my_skill", "description": "What it does."}

def run(*args, **kwargs):
    ...
```

Restart the app; `load_skills()` discovers it automatically. No harness edit.

**Add a forum** — edit `mcp.json` (or the Settings page). Then **deliberately** add its domain to `ALLOWED_SCRAPE_DOMAINS` in `security.py` to permit scraping it.

**Change the LLM** — set `llm.online.model` (online) or `llm.ollama.model` (offline) in `mcp.json`, or use the Settings page.

---

## 🧪 Verification & testing

- All modules **byte-compile**; the core safety primitives are exercised by smoke tests:
  - sandbox traversal raises `SandboxError`,
  - `run_command` deny/allow lists reject `rm`/unknown commands,
  - `check_url` rejects off-allowlist domains and non-http schemes,
  - the CSV reader parses semicolon-delimited, BOM-prefixed IQAN logs with quoted commas,
  - the knowledge-graph builder correctly merges shared sources across errors.
- The Streamlit pages execute headlessly without exceptions, and the running app serves a healthy endpoint.

---

## 🧾 Honesty notes

The brief rewards honesty about scope and accepted risk:

- **`mcp.json` is config, not a literal MCP server.** It is named for familiarity; the real, working extension mechanism is the drop-in `skills/` loader. Stated here rather than hidden.
- **Skills are not sandboxed.** They are trusted first-party code; importing one is equivalent to editing the app. Accepted and documented above.
- **`python` is allow-listed for `run_command`** and is fully capable. Accepted convenience; remove it to harden.
- **No `robots.txt` parsing.** We rate-limit, identify our User-Agent, and read only public threads. Accepted.
- **Hosted history is ephemeral.** On Streamlit Cloud the filesystem resets on reboot; persistence would need external storage.

---

## ❓ FAQ

**Does it work with the network unplugged?**
Yes, in **offline mode** — history lookups and the local Ollama LLM work fully offline. Forum scraping needs the network; if unavailable, RootIQ degrades to history-only answers instead of crashing.

**Can I use a ChatGPT (OpenAI) key?**
Yes. Online mode, base URL `https://api.openai.com/v1`, key in **Streamlit secrets** as `OPENAI_API_KEY` (never in `mcp.json`). Free alternatives (Groq, OpenRouter) work by changing only the base URL.

**Why is `mcp.json` called that if it isn't an MCP server?**
It's the editable config surface, named for familiarity and documented honestly here. The extension mechanism is the `skills/` loader.

**Where does the agent write files?**
Only inside `working_dir/`. Any attempt to escape raises `SandboxError`.

**Why does my saved history disappear after a redeploy?**
Streamlit Cloud storage is ephemeral and resets to the repo on reboot. Add a database or a GitHub commit-back step to persist across reboots.

---

<div align="center">

Built as a secure, dual-mode (offline/online) agent harness. • MIT License

</div>
