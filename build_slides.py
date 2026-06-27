# Builds a professionally designed slide deck (HTML) and renders PRESENTATION.pdf
# via the bundled headless Chromium. No Node/Marp required.
import os
from playwright.sync_api import sync_playwright

SHOT = lambda n: "file:///" + os.path.abspath(f"working_dir/screenshots/{n}").replace("\\", "/")
GH = "https://github.com/novoha/rootiq"
APP = "https://rootiq.streamlit.app/"

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
:root{--navy:#0D1B2A;--teal:#0D9488;--teal2:#14b8a6;--ink:#1f2937;--muted:#64748b;
  --soft:#f1f5f9;--line:#e2e8f0;--ok:#166534;--okbg:#dcfce7;--warn:#854d0e;--warnbg:#fef9c3}
body{font-family:'Segoe UI',system-ui,-apple-system,Arial,sans-serif;color:var(--ink)}
@page{size:1280px 720px;margin:0}
.slide{width:1280px;height:720px;padding:56px 72px;position:relative;overflow:hidden;
  page-break-after:always;background:#fff}
.slide:last-child{page-break-after:auto}
.kicker{font-size:15px;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--teal);margin-bottom:10px}
h1.title{font-size:44px;font-weight:800;color:var(--navy);line-height:1.1;margin-bottom:8px}
.sub{font-size:20px;color:var(--muted);margin-bottom:22px;max-width:1050px}
.foot{position:absolute;left:72px;right:72px;bottom:26px;display:flex;justify-content:space-between;
  align-items:center;font-size:13px;color:#94a3b8;border-top:1px solid var(--line);padding-top:12px}
.foot b{color:var(--teal)}
ul.clean{list-style:none}
ul.clean li{position:relative;padding-left:30px;margin:13px 0;font-size:21px;line-height:1.4}
ul.clean li:before{content:'';position:absolute;left:4px;top:9px;width:11px;height:11px;border-radius:3px;
  background:var(--teal)}
.grid{display:grid;gap:18px}
.card{background:#fff;border:1px solid var(--line);border-radius:16px;padding:22px 24px;
  box-shadow:0 6px 20px rgba(13,27,42,.06)}
.card .ic{font-size:30px;line-height:1}
.card h3{font-size:20px;color:var(--navy);margin:10px 0 6px}
.card p{font-size:16px;color:var(--muted);line-height:1.4}
.pill{display:inline-flex;align-items:center;gap:8px;background:var(--soft);border:1px solid var(--line);
  border-radius:999px;padding:8px 16px;font-size:16px;font-weight:600;color:var(--navy)}
.badge{display:inline-block;border-radius:999px;padding:4px 12px;font-size:14px;font-weight:700}
.b-ok{background:var(--okbg);color:var(--ok)}
.b-warn{background:var(--warnbg);color:var(--warn)}
.frame{border-radius:14px;overflow:hidden;border:1px solid var(--line);box-shadow:0 12px 34px rgba(13,27,42,.18)}
.frame img{display:block;width:100%}
.barbox{display:flex;align-items:center;gap:10px}
.step{flex:1;background:#fff;border:1px solid var(--line);border-radius:14px;padding:14px 10px;text-align:center;
  box-shadow:0 4px 14px rgba(13,27,42,.05)}
.step .ic{font-size:26px}.step .t{font-size:16px;font-weight:700;color:var(--navy);margin-top:4px}
.step .d{font-size:12.5px;color:var(--muted);margin-top:2px}
.arrow{color:var(--teal);font-size:24px;font-weight:800}
.secbar{margin-top:20px;background:linear-gradient(90deg,#7f1d1d,#b91c1c);color:#fff;border-radius:12px;
  padding:14px 20px;font-size:17px;font-weight:600;display:flex;align-items:center;gap:12px}
.mono{font-family:'Cascadia Code',Consolas,monospace}
.term{background:var(--navy);border-radius:12px;padding:18px 20px;color:#e2e8f0;font-size:15.5px;
  font-family:'Cascadia Code',Consolas,monospace;line-height:1.7}
.term .g{color:#4ade80}.term .c{color:#94a3b8}.term .y{color:#fbbf24}
.two{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.lead-x{height:100%;display:flex;flex-direction:column;justify-content:center}
.linkpill{display:inline-flex;align-items:center;gap:9px;background:rgba(255,255,255,.12);
  border:1px solid rgba(255,255,255,.3);border-radius:999px;padding:11px 20px;font-size:18px;color:#fff;
  text-decoration:none;font-weight:600}
.tbl{width:100%;border-collapse:collapse;font-size:16.5px}
.tbl th{background:var(--navy);color:#fff;text-align:left;padding:9px 14px}
.tbl td{border-bottom:1px solid var(--line);padding:9px 14px;vertical-align:middle}
.tbl tr:nth-child(even) td{background:#f8fafc}
.note{background:#f8fafc;border-left:4px solid var(--teal);border-radius:0 10px 10px 0;padding:12px 18px;
  font-size:16px;color:#475569;margin-top:8px}
"""


def foot(n):
    return (f"<div class='foot'><div>RootIQ &middot; <b>PLC Error Intelligence</b></div>"
            f"<div>rootiq.streamlit.app &nbsp;&middot;&nbsp; {n} / TOTAL</div></div>")


def head(kick, title, sub=""):
    s = f"<div class='kicker'>{kick}</div><h1 class='title'>{title}</h1>"
    if sub:
        s += f"<div class='sub'>{sub}</div>"
    return s


def cap(ic, t, p):
    return f"<div class='card'><div class='ic'>{ic}</div><h3>{t}</h3><p>{p}</p></div>"


def step(ic, t, d):
    return f"<div class='step'><div class='ic'>{ic}</div><div class='t'>{t}</div><div class='d'>{d}</div></div>"


def layer(n, t, d):
    return ("<div class='card' style='display:flex;gap:16px;align-items:center;padding:16px 22px'>"
            f"<div style='font-size:26px;font-weight:800;color:var(--teal);min-width:34px'>{n}</div>"
            f"<div><h3 style='margin:0'>{t}</h3><p>{d}</p></div></div>")


def row(tool, risk, verd, cls):
    return f"<tr><td><b>{tool}</b></td><td>{risk}</td><td><span class='badge {cls}'>{verd}</span></td></tr>"


def dlv(t, d):
    return f"<div class='card'><div style='font-size:22px'>&#9989; <b>{t}</b></div><p style='margin-top:6px'>{d}</p></div>"


ar = "<div class='arrow'>&rarr;</div>"
S = []

# 1 — COVER
S.append(f"""
<div class='slide' style="background:radial-gradient(1200px 700px at 78% -10%,#14b8a6 0%,#0D1B2A 46%,#081320 100%);color:#fff">
  <div class='lead-x'>
    <div style="font-size:21px;font-weight:700;letter-spacing:.16em;color:#5eead4;text-transform:uppercase">Industrial AI &middot; 2026</div>
    <div style="font-size:96px;font-weight:800;margin:8px 0 2px">&#128295;&#129504; RootIQ</div>
    <div style="font-size:32px;font-weight:600;color:#e2e8f0">PLC Error Intelligence &mdash; a secure agent harness</div>
    <div style="font-size:20px;color:#94a3b8;margin-top:18px;max-width:980px">
      Reads a fault log, reuses past fixes, mines the IQAN forum, and synthesises a
      <b style="color:#fff">cited</b> solution &mdash; behind a security interlock that screens every action.</div>
    <div style="margin-top:30px;font-size:22px;font-weight:700">Victor Otu Hayford</div>
    <div style="display:flex;gap:14px;margin-top:22px">
      <a class='linkpill' href="{GH}">&#128025; github.com/novoha/rootiq</a>
      <a class='linkpill' href="{APP}">&#128640; rootiq.streamlit.app</a>
    </div>
  </div>
</div>""")

# 2 — PROBLEM
S.append(f"""
<div class='slide'>
  {head("The problem", "A cryptic fault &mdash; and the fix is buried in a forum")}
  <div class='two' style="margin-top:6px">
    <div class='term'>
      <span class='c'># IQAN controller system log</span><br>
      XC44 ; <span class='y'>No contact</span><br>
      COUT-Suction hose 1 (C1:43/59) ; <span class='y'>Open load</span><br>
      VIN-Joystick (C1:26) ; <span class='y'>Low error</span><br>
      MC43FS[0] ; <span class='y'>No contact</span>
    </div>
    <ul class='clean'>
      <li>The answer lives across forum threads &amp; comments &mdash; slow to find by hand</li>
      <li>The <b>same faults recur</b>, yet nothing is captured or reused</li>
      <li>Sensitive sites want it to run <b>offline &mdash; no cloud, no API key</b></li>
    </ul>
  </div>
  <div class='note' style="margin-top:26px"><b>RootIQ</b> turns that moment into a guided, cited fix &mdash; and remembers it for next time.</div>
  {foot(2)}
</div>""")

# 3 — WHAT IT IS
S.append(f"""
<div class='slide'>
  {head("What RootIQ is", "Not just an app &mdash; a reusable, secure agent harness")}
  <div class='grid' style="grid-template-columns:repeat(3,1fr);margin-top:8px">
    {cap("&#128229;", "Intake", "Upload PDF/image, type a code, or drop a whole CSV export")}
    {cap("&#128190;", "Reuse", "Instant history cache hit &mdash; no LLM, no network")}
    {cap("&#127760;", "Retrieve", "Offline forum index &rarr; scrape threads + comments")}
    {cap("&#129302;", "Synthesise", "LLM reasons across sources &rarr; a cited JSON fix")}
    {cap("&#128506;&#65039;", "Remember", "Auto-saved &rarr; a knowledge map of related faults")}
    {cap("&#128274;", "Guard", "security_check() screens every tool call first")}
  </div>
  <div style="margin-top:24px;display:flex;gap:12px">
    <span class='pill'>&#128268; Offline &mdash; local Ollama</span>
    <span class='pill'>&#9729;&#65039; Online &mdash; any OpenAI-compatible API</span>
    <span class='pill'>One sidebar toggle</span>
  </div>
  {foot(3)}
</div>""")

# 4 — WHY IT MATTERS
S.append(f"""
<div class='slide'>
  {head("Why it matters", "A daily bridge between PLC programming and software")}
  <div class='two' style="margin-top:6px">
    <div class='card'><div class='ic'>&#129504;</div><h3>Known faults &rarr; instant reuse</h3>
      <p style="font-size:17px">The history cache turns a recurring fault into a zero-effort, no-LLM,
      no-network answer. The same faults come back &mdash; now solved on sight. <b>This saves the most time.</b></p></div>
    <div class='card'><div class='ic'>&#128269;</div><h3>New faults &rarr; reason + search</h3>
      <p style="font-size:17px">Unseen faults are searched against the forum index, scraped with community
      comments, and reasoned into a cited fix &mdash; then <b>remembered</b>, so tomorrow they are "known" too.</p></div>
  </div>
  <div class='note' style="margin-top:24px">&#128200; <b>The knowledge compounds</b> &mdash; every diagnosis grows the cache and the map, so the tool gets faster and smarter the more it is used.</div>
  {foot(4)}
</div>""")

# 5 — PIPELINE
S.append(f"""
<div class='slide'>
  {head("How it works", "An orchestrated pipeline &mdash; the harness routes, the LLM only synthesises")}
  <div class='barbox' style="margin-top:30px">
    {step("&#128229;", "Intake", "upload &middot; type &middot; CSV")}{ar}
    {step("&#128190;", "History", "instant reuse")}{ar}
    {step("&#128465;&#65039;", "Search", "offline index")}{ar}
    {step("&#127760;", "Scrape", "threads + comments")}{ar}
    {step("&#129302;", "Synthesise", "cited JSON")}{ar}
    {step("&#128506;&#65039;", "Remember", "map + history")}
  </div>
  <div class='secbar' style="margin-top:34px">&#128274; security_check() runs <b>before every tool</b> &middot; every rejection logged to rejection_log.jsonl</div>
  <div class='note' style="margin-top:20px">Known faults short-circuit at <b>History</b> &mdash; instant, no LLM, no network. Only new faults reach scrape + synthesis.</div>
  {foot(5)}
</div>""")

# 6 — DEMO BATCH
S.append(f"""
<div class='slide'>
  {head("Demo &middot; three ways in", "Upload a log &middot; type a code &middot; or batch a whole CSV")}
  <div style="display:grid;grid-template-columns:1.35fr 1fr;gap:30px;align-items:center;margin-top:4px">
    <div class='frame'><img src="{SHOT('05_batch.png')}"></div>
    <div>
      <ul class='clean'>
        <li>A real IQAN system log &mdash; <b>semicolon-delimited, BOM</b> &mdash; parsed cleanly</li>
        <li>De-duplicated to <b>9 unique faults</b> across the log</li>
        <li>One click: known faults instant, new ones scraped &amp; reasoned</li>
      </ul>
      <div class='note'>Routine rows (System started, App changed&hellip;) are filtered out automatically.</div>
    </div>
  </div>
  {foot(6)}
</div>""")

# 7 — DEMO cited answer
S.append(f"""
<div class='slide'>
  {head("Demo &middot; a cited answer", "Reasoned across multiple threads &mdash; never one")}
  <div class='two' style="margin-top:6px">
    <div class='card' style="border-top:5px solid var(--teal)">
      <div style="display:flex;justify-content:space-between;align-items:center">
        <h3 style="font-size:22px;margin:0">XC44 &mdash; No contact</h3><span class='badge b-ok'>High confidence</span></div>
      <p style="font-size:16px;margin:10px 0"><b>Root cause:</b> expansion module lost CAN communication &mdash; usually termination or wiring <b>[1]</b>.</p>
      <p style="font-size:16px;margin:6px 0">1 &middot; Verify 120 &#937; termination at both ends <b>[1]</b></p>
      <p style="font-size:16px;margin:6px 0">2 &middot; Inspect CAN_H/CAN_L for opens/shorts <b>[1][2]</b></p>
      <p style="font-size:14px;color:var(--muted);margin-top:10px">&#128279; Sources: No contact &amp; critical CAN error &middot; CAN bus-off / termination</p>
    </div>
    <ul class='clean'>
      <li><b>Inline citations</b> [1][2] on every step + all source links</li>
      <li>Weighs <b>higher-voted, answered</b> community comments</li>
      <li>Output is parsed <b>only as JSON</b> &mdash; the model is never wired to a file/command tool</li>
    </ul>
  </div>
  {foot(7)}
</div>""")

# 8 — DEMO map
S.append(f"""
<div class='slide'>
  {head("Demo &middot; the knowledge map", "Related faults connect through shared forum threads")}
  <div style="display:grid;grid-template-columns:1fr 1.5fr;gap:30px;align-items:center;margin-top:4px">
    <ul class='clean'>
      <li>Each <b>unique error</b> is one node, sized by occurrence</li>
      <li>Linked to its <b>fix</b> and the <b>forum threads</b> it cited</li>
      <li><b>Shared threads converge</b> &rarr; related faults visibly connect</li>
    </ul>
    <div class='frame'><img src="{SHOT('06_map.png')}"></div>
  </div>
  {foot(8)}
</div>""")

# 9 — HARNESS
S.append(f"""
<div class='slide'>
  {head("The harness", "Sandboxed tools &middot; drop-in skills &middot; editable config")}
  <div class='grid' style="grid-template-columns:repeat(3,1fr);margin-top:8px">
    <div class='card'><div class='ic'>&#129520;</div><h3>Sandboxed tools</h3>
      <p>read &middot; write &middot; create &middot; list &middot; <b>transform_markdown</b> (md&rarr;HTML) &middot; run_command &mdash; every path through <span class='mono'>_safe_path()</span>.</p></div>
    <div class='card'><div class='ic'>&#129513;</div><h3>Drop-in skills</h3>
      <p>Any <span class='mono'>skills/*.py</span> with a SKILL dict is auto-discovered. <b>Drop one in &mdash; it appears.</b> No harness edit.</p></div>
    <div class='card'><div class='ic'>&#9881;&#65039;</div><h3>Editable config</h3>
      <p><span class='mono'>mcp.json</span> sets the LLM provider, forums, and scraping limits &mdash; no code change.</p></div>
  </div>
  <div class='note' style="margin-top:22px">The loaded extension: <b>extract_log</b> (problem log &rarr; text + codes), plus lookup_history, save_solution, phase1_crawl, phase2_scrape.</div>
  {foot(9)}
</div>""")

# 10 — SECURITY layers
S.append(f"""
<div class='slide'>
  {head("Security &middot; defense in depth", "A wide attack surface, guarded in four layers")}
  <div class='grid' style="grid-template-columns:1fr 1fr;margin-top:8px">
    {layer("1", "security_check(tool, args)", "Regex + command screen before every tool call")}
    {layer("2", "_safe_path()", "Authoritative sandbox &mdash; resolve() + is_relative_to")}
    {layer("3", "check_url()", "Scheme check + domain allowlist before any HTTP")}
    {layer("4", "rejection_log.jsonl", "Every block recorded and shown in Settings")}
  </div>
  <div class='term' style="margin-top:22px">
    security_check("run_command", {{"command":"rm -rf /"}})  <span class='c'>&rarr; (False, 'Blocked command: rm')</span><br>
    _safe_path("../../etc/passwd")  <span class='c'>&rarr; raises SandboxError</span>
  </div>
  {foot(10)}
</div>""")

# 11 — SECURITY per-tool
S.append(f"""
<div class='slide'>
  {head("Security &middot; per-tool verdicts", "Each risk: blocked, mitigated, or honestly accepted")}
  <table class='tbl' style="margin-top:6px">
    <tr><th style="width:27%">Tool / surface</th><th>Risk</th><th style="width:24%">Verdict</th></tr>
    {row("File ops", "path traversal out of the sandbox", "&#128274; Blocked", "b-ok")}
    {row("run_command", "shell injection from tool output", "&#128274; Mitigated", "b-ok")}
    {row("transform_markdown", "HTML / script injection", "&#128274; Mitigated", "b-ok")}
    {row("Outbound HTTP", "SSRF / scraping abuse", "&#128274; Mitigated", "b-ok")}
    {row("Prompt injection", "scraped / file text as instructions", "&#128274; By design", "b-ok")}
    {row("Secrets", "API key leakage", "&#128274; Mitigated", "b-ok")}
    {row("Skills in skills/", "arbitrary import-time code", "&#9888;&#65039; Accepted", "b-warn")}
  </table>
  <div class='note' style="margin-top:16px">Honest acceptance of a risk you understand &mdash; not pretending it isn't there.</div>
  {foot(11)}
</div>""")

# 12 — DELIVERABLES
S.append(f"""
<div class='slide'>
  {head("How it maps to the assignment", "All four deliverables, in the repo")}
  <div class='grid' style="grid-template-columns:1fr 1fr;margin-top:8px">
    {dlv("The harness", "Working code; app runs headless with zero exceptions")}
    {dlv("A loaded extension", "Five drop-in skills &mdash; headline extract_log")}
    {dlv("README + security", "Per-tool risks &rarr; blocked / mitigated / accepted + diagrams")}
    {dlv("Presentation", "This deck + live app screenshots")}
  </div>
  <div style="margin-top:22px;display:flex;gap:10px;flex-wrap:wrap">
    <span class='pill'>Offline (Ollama)</span><span class='pill'>Safety interlock + log</span>
    <span class='pill'>Eval / retry loop</span><span class='pill'>Context caps</span><span class='pill'>Staged multi-agent roles</span>
  </div>
  {foot(12)}
</div>""")

# 13 — HONESTY
S.append(f"""
<div class='slide'>
  {head("Honesty notes", "Stated plainly &mdash; the brief rewards this")}
  <ul class='clean' style="font-size:19px">
    <li><b>mcp.json is config, not a literal MCP server</b> &mdash; the real extension mechanism is the drop-in skills/ loader</li>
    <li><b>Skills are not sandboxed</b> &mdash; trusted first-party code; importing one equals editing the app</li>
    <li><b>python is allow-listed</b> for run_command (capable) &mdash; accepted convenience</li>
    <li><b>No robots.txt parsing</b> &mdash; we rate-limit, identify our UA, read only public threads</li>
    <li><b>Hosted history is ephemeral</b> &mdash; Streamlit Cloud resets on reboot; persistence needs a database</li>
  </ul>
  {foot(13)}
</div>""")

# 14 — TRY IT
S.append(f"""
<div class='slide' style="background:linear-gradient(135deg,#0D1B2A 0%,#0f766e 100%);color:#fff">
  <div class='kicker' style="color:#5eead4">Try it yourself</div>
  <h1 class='title' style="color:#fff">Run RootIQ in two ways</h1>
  <div class='two' style="margin-top:14px">
    <div class='term' style="background:rgba(0,0,0,.35)">
      <span class='c'># Offline &mdash; local, no key</span><br>
      ollama serve &amp;&amp; ollama pull phi3<br>
      streamlit run app.py  <span class='c'># toggle &#127760; OFF</span>
    </div>
    <div class='term' style="background:rgba(0,0,0,.35)">
      <span class='c'># Online &mdash; hosted LLM</span><br>
      export OPENAI_API_KEY=sk-...<br>
      streamlit run app.py  <span class='c'># toggle &#127760; ON</span>
    </div>
  </div>
  <div style="display:flex;gap:14px;margin-top:30px">
    <a class='linkpill' href="{GH}">&#128025; github.com/novoha/rootiq</a>
    <a class='linkpill' href="{APP}">&#128640; rootiq.streamlit.app</a>
  </div>
</div>""")

# 15 — THANK YOU
S.append(f"""
<div class='slide' style="background:radial-gradient(1200px 700px at 22% 110%,#14b8a6 0%,#0D1B2A 50%,#081320 100%);color:#fff">
  <div class='lead-x' style="align-items:flex-start">
    <div style="font-size:84px;font-weight:800">Thank you &#128591;</div>
    <div style="font-size:30px;color:#e2e8f0;margin-top:6px">RootIQ &mdash; diagnose faster, fix smarter. Securely.</div>
    <div style="font-size:22px;font-weight:700;margin-top:26px">Victor Otu Hayford <span style="color:#5eead4">&middot; Industrial AI, 2026</span></div>
    <div style="display:flex;gap:14px;margin-top:26px">
      <a class='linkpill' href="{GH}">&#128025; github.com/novoha/rootiq</a>
      <a class='linkpill' href="{APP}">&#128640; rootiq.streamlit.app</a>
    </div>
  </div>
</div>""")

TOTAL = len(S)
html = "<!doctype html><html><head><meta charset='utf-8'><style>" + CSS + "</style></head><body>"
html += "".join(S).replace("TOTAL", str(TOTAL))
html += "</body></html>"
open("_deck.html", "w", encoding="utf-8").write(html)

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1280, "height": 720})
    pg.goto("file:///" + os.path.abspath("_deck.html").replace("\\", "/"))
    pg.wait_for_timeout(1800)
    pg.emulate_media(media="print")
    pg.pdf(path="_render.pdf", prefer_css_page_size=True, print_background=True)
    b.close()

try:
    os.replace("_render.pdf", "PRESENTATION.pdf")
    print(f"OK -> PRESENTATION.pdf ({TOTAL} slides)")
except PermissionError:
    print(f"OK -> _render.pdf ({TOTAL} slides) — PRESENTATION.pdf is open/locked; "
          "close it, then rename _render.pdf to PRESENTATION.pdf")
