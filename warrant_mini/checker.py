"""Orchestrate a compliance review: one LLM judge pass per rule-group.

The judge is constrained by a Pydantic schema (structured outputs), but we do not
trust it blindly. Every returned finding is verified against reality before it is
kept:

  * its `rule_id` must be one of the rules that were actually sent in that pass
    (blocks invented regulations), and
  * its `quote` must genuinely appear in the reviewed copy (blocks fabricated
    "offending text").

Findings that fail verification are dropped, not surfaced.
"""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor

import anthropic

from .models import Finding, ReviewResult, Rule, _JudgeResponse
from .prompts import SYSTEM_PROMPT, build_user_prompt
from .rules import rule_index, rules_by_group

DEFAULT_MODEL = "claude-sonnet-5"  # you asked for sonnet; swap to claude-opus-4-8 here for more depth
_MAX_TOKENS = 4096


class MissingAPIKey(RuntimeError):
    pass


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _quote_in_copy(quote: str, copy: str) -> str | None:
    """Return the verbatim span from `copy` if `quote` really occurs in it.

    Exact substring wins. Otherwise we allow a whitespace-insensitive match and
    return the actual span from the copy (so what we display is always real text).
    A quote that matches neither is treated as fabricated and rejected.
    """
    if quote in copy:
        return quote
    norm_copy = _normalize(copy)
    norm_quote = _normalize(quote)
    if norm_quote and norm_quote in norm_copy:
        # Recover the real span by walking the original copy for the same
        # normalized content.
        words = re.escape(quote.strip()).replace(r"\ ", r"\s+")
        m = re.search(words, copy, flags=re.IGNORECASE)
        if m:
            return m.group(0)
        return quote  # normalized match but span recovery failed; keep the quote
    return None


def _run_group(
    client: anthropic.Anthropic,
    model: str,
    rules: list[Rule],
    copy: str,
) -> list[Finding]:
    allowed_ids = {r.id for r in rules}
    idx = rule_index()

    response = client.messages.parse(
        model=model,
        max_tokens=_MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(rules, copy)}],
        output_format=_JudgeResponse,
    )
    parsed = response.parsed_output
    if parsed is None:
        return []

    findings: list[Finding] = []
    seen: set[tuple[str, str]] = set()
    for jf in parsed.findings:
        if jf.rule_id not in allowed_ids:
            continue  # invented / out-of-group rule id — drop it
        verified_quote = _quote_in_copy(jf.quote, copy)
        if verified_quote is None:
            continue  # quote not actually in the copy — drop it
        key = (jf.rule_id, _normalize(verified_quote))
        if key in seen:
            continue
        seen.add(key)
        rule = idx[jf.rule_id]
        findings.append(
            Finding(
                rule_id=rule.id,
                rule_name=rule.name,
                regulation=rule.regulation,
                severity=jf.severity,
                quote=verified_quote,
                reasoning=jf.reasoning.strip(),
                suggested_rewrite=jf.suggested_rewrite.strip(),
            )
        )
    return findings


def review(text: str, *, source: str = "input", model: str = DEFAULT_MODEL) -> ReviewResult:
    """Review `text` against the full rule library, one pass per rule-group."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise MissingAPIKey(
            "ANTHROPIC_API_KEY is not set. Export it, e.g.\n"
            "    export ANTHROPIC_API_KEY=sk-ant-..."
        )

    client = anthropic.Anthropic()
    groups = rules_by_group()

    all_findings: list[Finding] = []
    # Groups are independent — run them concurrently. Each pass is one API call.
    with ThreadPoolExecutor(max_workers=len(groups)) as pool:
        futures = [
            pool.submit(_run_group, client, model, rules, text)
            for rules in groups.values()
        ]
        for fut in futures:
            all_findings.extend(fut.result())

    all_findings.sort(key=lambda f: f.sort_key)
    return ReviewResult(
        source=source,
        model=model,
        char_count=len(text),
        findings=all_findings,
    )
