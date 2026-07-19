"""Single-page FastAPI UI for warrant-mini.

    uv run warrant-mini serve            # then open http://127.0.0.1:8000
    # or: uv run uvicorn warrant_mini.web:app --reload

The page is a textarea + results panel; it POSTs to /api/review, which runs the
exact same `checker.review()` the CLI uses. Input is routed through
`load_input`, so pasting a URL fetches and reviews the page too.
"""

from __future__ import annotations

import html
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from . import checker
from .input_loader import load_input
from .models import ReviewResult

app = FastAPI(title="warrant-mini", docs_url="/api/docs")

_EXAMPLE_DIR = Path(__file__).resolve().parent.parent / "examples"
_EXAMPLE_FILES = {
    "fintech": "fintech_landing.md",
    "influencer": "influencer_post.txt",
    "clean": "clean_newsletter.md",
}
_SEV_LABEL = {"P1": "P1 · critical", "P2": "P2 · high", "P3": "P3 · moderate", "P4": "P4 · review suggested"}


class ReviewRequest(BaseModel):
    text: str
    model: str = checker.DEFAULT_MODEL


def _example_text(name: str | None) -> str:
    """Return an example file's text, or '' if the name is unknown."""
    fname = _EXAMPLE_FILES.get(name or "")
    if not fname:
        return ""
    path = _EXAMPLE_DIR / fname
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def _render_results_html(result: ReviewResult) -> tuple[str, str]:
    """Server-side render (summary_html, cards_html) — mirrors the client renderer.

    Used for /?run=<example> deep-links so a result page works without JS.
    """
    esc = html.escape
    f = result.findings
    meta = f'<span class="hint"> · {result.char_count} chars · {esc(result.model)}</span>'
    if not f:
        return (f'<span class="clean">✓ No compliance issues found</span>{meta}', "")
    counts = result.counts
    pills = "".join(
        f'<span class="pill {s}">{counts[s]}× {s}</span>' for s in ("P1", "P2", "P3", "P4") if counts[s]
    )
    summary = f"<b>{len(f)} finding(s):</b> {pills}{meta}"
    cards = "\n".join(
        f'<div class="card {x.severity}">'
        f'<h3><span class="pill {x.severity}">{_SEV_LABEL[x.severity]}</span> {esc(x.rule_name)}</h3>'
        f'<div class="reg">{esc(x.regulation)}</div>'
        f'<div class="field"><div class="label">offending text</div>'
        f'<div class="quote">“{esc(x.quote)}”</div></div>'
        f'<div class="field"><div class="label">why it\'s a problem</div><div>{esc(x.reasoning)}</div></div>'
        f'<div class="field"><div class="label">suggested fix</div>'
        f'<div class="fix">{esc(x.suggested_rewrite)}</div></div>'
        f"</div>"
        for x in f
    )
    return summary, cards


@app.get("/", response_class=HTMLResponse)
def index(example: str | None = None, run: str | None = None) -> str:
    prefill, summary_html, results_html = "", "", ""
    summary_style = "display:none"

    if run:  # server-side render a full result (works without JS)
        text = _example_text(run)
        if text:
            prefill = text
            result = checker.review(text, source=f"example: {run}", model=checker.DEFAULT_MODEL)
            summary_html, results_html = _render_results_html(result)
            summary_style = "display:block"
    elif example:  # just prefill the textarea
        prefill = _example_text(example)

    return (
        _PAGE.replace("__PREFILL__", html.escape(prefill))
        .replace("__SUMMARY_STYLE__", summary_style)
        .replace("__SUMMARY__", summary_html)
        .replace("__RESULTS__", results_html)
    )


@app.post("/api/review")
def api_review(req: ReviewRequest) -> JSONResponse:
    # Sync endpoint → FastAPI runs it in a threadpool, so the blocking
    # per-group API calls don't stall the event loop.
    if not req.text.strip():
        return JSONResponse({"error": "Please paste some marketing copy to review."}, status_code=400)
    try:
        loaded = load_input(req.text)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"Could not load input: {exc}"}, status_code=400)
    try:
        result = checker.review(loaded.text, source=loaded.source_label, model=req.model)
    except checker.MissingAPIKey as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"error": f"Review failed: {exc}"}, status_code=500)
    return JSONResponse(result.model_dump())


_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>warrant-mini — marketing compliance checker</title>
<style>
  :root {
    --bg: #0f1115; --panel: #171a21; --panel-2: #1e222b; --border: #2a2f3a;
    --text: #e6e8ec; --muted: #9aa1ad; --accent: #5b8cff;
    --p1: #ff4d4d; --p2: #ff8a3d; --p3: #ffca3a; --p4: #38bdf8; --ok: #34d399;
  }
  @media (prefers-color-scheme: light) {
    :root {
      --bg: #f6f7f9; --panel: #ffffff; --panel-2: #f0f2f5; --border: #e2e6ec;
      --text: #1a1d23; --muted: #5b626e; --accent: #2f6bff;
    }
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--text);
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  header { padding: 28px 24px 8px; max-width: 900px; margin: 0 auto; }
  h1 { margin: 0; font-size: 22px; letter-spacing: -0.01em; }
  h1 .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--accent); }
  .sub { color: var(--muted); margin-top: 4px; font-size: 14px; }
  main { max-width: 900px; margin: 0 auto; padding: 16px 24px 60px; }
  textarea {
    width: 100%; min-height: 200px; resize: vertical; padding: 14px 16px;
    background: var(--panel); color: var(--text); border: 1px solid var(--border);
    border-radius: 12px; font: 14px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  textarea:focus { outline: none; border-color: var(--accent); }
  .row { display: flex; gap: 12px; align-items: center; margin-top: 12px; flex-wrap: wrap; }
  button {
    background: var(--accent); color: #fff; border: 0; padding: 11px 20px;
    border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer;
  }
  button:disabled { opacity: .55; cursor: default; }
  .hint { color: var(--muted); font-size: 13px; }
  .examples { color: var(--muted); font-size: 13px; margin-left: auto; }
  .examples a { color: var(--accent); text-decoration: none; cursor: pointer; }
  .examples a:hover { text-decoration: underline; }
  #summary { margin: 22px 0 6px; font-size: 15px; display: none; }
  .pill {
    display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px;
    font-weight: 700; margin-right: 6px; color: #0b0d10;
  }
  .pill.P1 { background: var(--p1); color: #fff; } .pill.P2 { background: var(--p2); }
  .pill.P3 { background: var(--p3); } .pill.P4 { background: var(--p4); color: #06263a; }
  .clean { color: var(--ok); font-weight: 700; }
  .card {
    background: var(--panel); border: 1px solid var(--border); border-left-width: 4px;
    border-radius: 12px; padding: 14px 16px; margin: 12px 0;
  }
  .card.P1 { border-left-color: var(--p1); } .card.P2 { border-left-color: var(--p2); }
  .card.P3 { border-left-color: var(--p3); } .card.P4 { border-left-color: var(--p4); }
  .card h3 { margin: 0 0 4px; font-size: 15px; display: flex; align-items: center; gap: 8px; }
  .card .reg { color: var(--muted); font-size: 12.5px; margin-bottom: 10px; }
  .field { margin: 7px 0; }
  .label { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: .04em; }
  .quote { font-style: italic; background: var(--panel-2); padding: 8px 10px; border-radius: 8px; }
  .fix { color: var(--ok); }
  .err { background: var(--panel); border: 1px solid var(--p1); border-radius: 10px; padding: 12px 14px; color: var(--p1); }
  .spinner { display: inline-block; width: 15px; height: 15px; border: 2px solid var(--muted);
    border-top-color: transparent; border-radius: 50%; animation: spin .7s linear infinite; vertical-align: -2px; }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<header>
  <h1><span class="mono">warrant-mini</span> · marketing compliance checker</h1>
  <div class="sub">Paste marketing copy (or a URL). It's reviewed against a library of real
    FTC / FINRA / Reg&nbsp;DD / FDIC rules — risk-tiered, with reasoning and suggested fixes.</div>
</header>
<main>
  <textarea id="copy" placeholder="Paste marketing copy here — e.g. a landing page, an email, an influencer post — or a URL to fetch…">__PREFILL__</textarea>
  <div class="row">
    <button id="go">Review copy</button>
    <span class="hint" id="status"></span>
    <span class="examples">try:
      <a data-ex="fintech">fintech landing</a> ·
      <a data-ex="influencer">influencer post</a> ·
      <a data-ex="clean">clean newsletter</a>
    </span>
  </div>
  <div id="summary" style="__SUMMARY_STYLE__">__SUMMARY__</div>
  <div id="results">__RESULTS__</div>
</main>
<script>
// Examples as line arrays (joined at click time) — avoids escaping newlines.
const EXAMPLES = {
  fintech: [
    "The #1 savings app in the world. Earn 5% on your savings — that's 10x the national average.*",
    "Your balance is FDIC insured, so your crypto and your cash are protected against any loss.",
    "Our Growth Portfolio delivers guaranteed 12% annual returns with zero risk. Our fund has never had a down year.",
    "Start your FREE trial today! Buy the Premium plan for 5x more chances to win a Tesla."
  ],
  influencer: [
    "Okay I need to talk about this serum because my skin has literally never looked better",
    "I've been using the GlowLab Vitamin C serum every morning for 3 weeks and the difference is INSANE.",
    "They set me up with a code so you can try it too — use LUNA20 for 20% off at glowlab. this is the best serum I've ever used and it works instantly.",
    "#skincare #glowup"
  ],
  clean: [
    "Hi friends, thanks for reading. This week we shipped a redesigned trip planner and fixed the sync bug several of you reported.",
    "Offline maps now download in the background. We think the new planner is genuinely nicer to use, and we hope you do too.",
    "You're receiving this because you signed up. Unsubscribe any time below."
  ]
};
const SEV_LABEL = { P1: "P1 · critical", P2: "P2 · high", P3: "P3 · moderate", P4: "P4 · review suggested" };
const $ = s => document.querySelector(s);
const esc = s => s.replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function loadExample(name) { if (EXAMPLES[name]) $('#copy').value = EXAMPLES[name].join("\\n"); }
document.querySelectorAll('.examples a').forEach(a => a.onclick = () => loadExample(a.dataset.ex));
// Deep-link: /?example=fintech prefills the textarea (handy for demos/sharing).
// (/?run=fintech is rendered server-side, so no client action is needed for it.)
loadExample(new URLSearchParams(location.search).get('example'));

$('#go').onclick = async () => {
  const text = $('#copy').value.trim();
  const results = $('#results'), summary = $('#summary');
  results.innerHTML = ''; summary.style.display = 'none';
  if (!text) { results.innerHTML = '<div class="err">Please paste some copy to review.</div>'; return; }
  $('#go').disabled = true;
  $('#status').innerHTML = '<span class="spinner"></span> reviewing…';
  try {
    const r = await fetch('/api/review', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ text })
    });
    const data = await r.json();
    if (!r.ok) { results.innerHTML = `<div class="err">${esc(data.error || 'Review failed.')}</div>`; return; }
    render(data);
  } catch (e) {
    results.innerHTML = `<div class="err">${esc(String(e))}</div>`;
  } finally {
    $('#go').disabled = false; $('#status').textContent = '';
  }
};

function render(data) {
  const summary = $('#summary'), results = $('#results');
  summary.style.display = 'block';
  const f = data.findings || [];
  if (!f.length) {
    summary.innerHTML = `<span class="clean">✓ No compliance issues found</span>
      <span class="hint"> · ${data.char_count} chars · ${esc(data.model)}</span>`;
    results.innerHTML = ''; return;
  }
  const counts = { P1:0, P2:0, P3:0, P4:0 };
  f.forEach(x => counts[x.severity]++);
  const pills = ['P1','P2','P3','P4'].filter(s => counts[s])
    .map(s => `<span class="pill ${s}">${counts[s]}× ${s}</span>`).join('');
  summary.innerHTML = `<b>${f.length} finding(s):</b> ${pills}
    <span class="hint"> · ${data.char_count} chars · ${esc(data.model)}</span>`;
  results.innerHTML = f.map(x => `
    <div class="card ${x.severity}">
      <h3><span class="pill ${x.severity}">${SEV_LABEL[x.severity]}</span> ${esc(x.rule_name)}</h3>
      <div class="reg">${esc(x.regulation)}</div>
      <div class="field"><div class="label">offending text</div><div class="quote">“${esc(x.quote)}”</div></div>
      <div class="field"><div class="label">why it's a problem</div><div>${esc(x.reasoning)}</div></div>
      <div class="field"><div class="label">suggested fix</div><div class="fix">${esc(x.suggested_rewrite)}</div></div>
    </div>`).join('');
}
</script>
</body>
</html>"""
