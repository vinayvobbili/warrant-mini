# warrant-mini — Build Plan

A miniature AI marketing-compliance checker. Paste text / point at a `.txt`/`.md`
file / give a URL → get risk-tiered findings with reasoning traces and suggested
rewrites, judged against a small library of real compliance rules.

Inspired by what Warrant (hellowarrant.com) does. This is a one-evening portfolio
piece — **polish-per-hour beats completeness**. Target: working end-to-end in ~3h.

---

## Decisions locked in

| Decision | Choice | Rationale |
|---|---|---|
| Language / deps | Python 3.14, **uv** | Per spec. `uv` not installed yet → `brew install uv` (Step 0). |
| LLM | Anthropic API, **`claude-sonnet-5`** | You specified "claude-sonnet". Sonnet is the right cost/quality point for a per-rule judge. Model ID lives in one constant, trivially swappable to `claude-opus-4-8`. |
| API call shape | `client.messages.parse()` with a Pydantic schema | Structured outputs guarantee valid findings JSON — no regex-scraping the model's prose. Adaptive thinking on (`effort: "medium"`). |
| Judging strategy | **One LLM pass per rule-group**, not one giant prompt | Keeps each prompt short and focused (better recall, cleaner reasoning traces), lets rules run concurrently, and isolates a bad rule from poisoning the rest. |
| Location | `~/PycharmProjects/warrant-mini` (standalone, **not** inside IR) | Separate portfolio repo; own git history. |

**Anti-hallucination contract** (baked into the judge prompt + schema):
- The judge must quote the **exact offending substring** and cite the rule by `id`.
- It may only cite regulations from the rule library it's given — never invent a cite.
- If it's unsure a violation is real, it must return **P4 "review suggested"**, not a confident higher tier.
- A rule-group pass with no violations returns an empty list (no fabricated findings).

---

## Severity tiers

`P1` critical (clear legal exposure) · `P2` high · `P3` moderate · `P4` review suggested (low-confidence / judgment call).

---

## File layout

```
warrant-mini/
├── pyproject.toml            # uv-managed; deps: anthropic, pydantic, rich, typer, httpx, beautifulsoup4, pyyaml
├── README.md                 # first-class deliverable (built last)
├── PLAN.md                   # this file
├── .env.example              # ANTHROPIC_API_KEY=...
├── warrant_mini/
│   ├── __init__.py
│   ├── rules.yaml            # ~8 hardcoded rules (see below)
│   ├── rules.py              # load + validate rules.yaml into typed Rule objects; group them
│   ├── models.py             # Pydantic: Rule, Finding, ReviewResult
│   ├── input_loader.py       # resolve pasted text / file path / URL → clean plain text
│   ├── checker.py            # orchestrates: chunk → per-rule-group LLM pass → collect Findings
│   ├── prompts.py            # the judge system+user prompt template
│   └── cli.py                # `warrant-mini check <src>` with rich output; --json flag
├── examples/
│   ├── fintech_landing.md    # planted violations (APY, FDIC, "guaranteed", superlatives)
│   ├── clean_newsletter.md   # should surface ~zero findings
│   └── influencer_post.txt   # missing #ad / material-connection disclosure
└── tests/
    └── test_smoke.py         # rules.yaml loads, schema validates, input_loader handles 3 source types (no live API)
```

## Rule library (`rules.yaml`, ~8 rules)

Each rule: `id`, `name`, `regulation` (cite), `group`, `severity_default`, `description`, `violation_examples[]`.

1. `ftc-endorsement` — FTC 16 CFR Part 255: material connections must be disclosed
2. `ftc-free-negative-option` — FTC "free" claims + negative-option billing clarity
3. `finra-2210` — FINRA Rule 2210: no promissory/exaggerated claims; fair & balanced; risk disclosure
4. `reg-dd-apy` — APY/APR advertising accuracy (Reg DD / Truth in Savings)
5. `fdic-ncua-insured` — "FDIC insured" / "NCUA insured" claim accuracy
6. `sweepstakes-disclosure` — sweepstakes/contest disclosure basics
7. `superlative-substantiation` — "best" / "#1" / "guaranteed" require substantiation
8. `disclaimer-proximity` — required disclaimers can't be buried / far from the claim

**Grouping for LLM passes** (fewer passes = faster + cheaper, keeps related rules together):
- `financial` → finra-2210, reg-dd-apy, fdic-ncua-insured
- `claims` → superlative-substantiation, ftc-free-negative-option, disclaimer-proximity
- `disclosure` → ftc-endorsement, sweepstakes-disclosure

## Finding shape

`rule_id` · `rule_name` · `regulation` · `severity` (P1–P4) · `quote` (exact offending text) · `reasoning` (why it violates) · `suggested_rewrite`.

---

## Build sequence (~3h)

- **Step 0 (10m)** — `brew install uv`; `uv init`; add deps; `.env.example`. Confirm `ANTHROPIC_API_KEY` reachable.
- **Step 1 (25m)** — `models.py` + `rules.yaml` + `rules.py`. Author all 8 rules with real cites and 1–2 violation examples each. Smoke-load them.
- **Step 2 (20m)** — `input_loader.py`: text vs. file vs. URL (httpx + BeautifulSoup strip). Handle the 3 source types cleanly.
- **Step 3 (35m)** — `prompts.py` + `checker.py`: per-group judge pass via `messages.parse()`, concurrent groups, collect + sort findings by severity. This is the core; spend the polish here.
- **Step 4 (30m)** — `cli.py`: `warrant-mini check <src>` rich output (severity-colored panels, quote, reasoning, rewrite) + `--json`.
- **Step 5 (20m)** — 3 `examples/`. Tune fintech example so planted violations actually fire; verify clean one stays quiet.
- **Step 6 (10m)** — `tests/test_smoke.py` (no live API).
- **Step 7 (20m)** — `README.md`: what it does, 60-sec quickstart, architecture sketch, "How this was built" (AI-native workflow — you fill hours/details at the end).

---

## Open items needing you

1. **API key** — I need `ANTHROPIC_API_KEY` in the environment (or a `.env`) to run the live end-to-end test in Step 3/5. Without it I can build everything and validate structure, but can't prove a real review. How do you want to provide it? (paste-and-export, `.env` file, or you run the final `check` yourself.)
2. **`brew install uv`** — OK to install `uv` via Homebrew? (It's the spec'd tool; alternative is a plain `python -m venv` + `pip`, but then it's not uv.)
3. **Scope of optional FastAPI UI** — deferred to a stretch goal only if the ~3h core lands with time to spare. Not in the critical path. Fine to leave out?
