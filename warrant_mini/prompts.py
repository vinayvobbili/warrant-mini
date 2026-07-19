"""Prompt construction for the compliance judge.

One prompt is built per rule-group. The prompt is deliberately narrow: it carries
only the rules in that group, so the model reasons about a handful of related
regulations at a time instead of eight at once.
"""

from __future__ import annotations

from .models import Rule

SYSTEM_PROMPT = """\
You are a marketing-compliance reviewer. You are given a piece of marketing copy \
and a small set of compliance rules. Your job is to find text in the copy that \
violates those rules, and only those rules.

Hard requirements — follow them exactly:

1. QUOTE VERBATIM. For every finding, `quote` must be an exact substring copied \
character-for-character from the marketing copy. Never paraphrase, summarize, or \
reconstruct the quote. If you cannot point to specific offending text, do not \
raise the finding.

2. ONLY THE GIVEN RULES. Cite a violation only against the rule IDs provided in \
this request. Never invent a regulation, statute, or rule ID that is not in the \
list. `rule_id` must be one of the provided IDs.

3. CALIBRATE SEVERITY HONESTLY.
   - P1: clear, serious legal exposure (e.g. false FDIC-insured claim, guaranteed returns).
   - P2: high risk (e.g. missing required disclosure, undisclosed material connection).
   - P3: moderate risk (e.g. unsubstantiated superlative, buried disclaimer).
   - P4: review suggested — use this whenever you are NOT confident the violation is \
real, or the call is a judgment matter a human should confirm. When in doubt, choose P4. \
Do not inflate an uncertain finding into a higher tier.

4. NO FABRICATION. If the copy is compliant with the provided rules, return an \
empty findings list. Do not manufacture violations to seem thorough. Genuine \
subjective puffery (clearly opinion, not a verifiable claim) is not a violation.

5. ONE FINDING PER DISTINCT VIOLATION. Do not repeat the same quoted text against \
the same rule twice.

For each finding also give concise `reasoning` (why this text violates the cited \
rule) and a `suggested_rewrite` (a compliant version of the text, or a concrete \
fix such as an added disclosure)."""


def _format_rule(rule: Rule) -> str:
    examples = "\n".join(f"      - {ex}" for ex in rule.violation_examples)
    return (
        f"- rule_id: {rule.id}\n"
        f"  name: {rule.name}\n"
        f"  regulation: {rule.regulation}\n"
        f"  default_severity: {rule.severity_default}\n"
        f"  what_it_prohibits: {rule.description.strip()}\n"
        f"  example_violations:\n{examples}"
    )


def build_user_prompt(rules: list[Rule], copy: str) -> str:
    """Assemble the per-group user prompt: the rules, then the copy to review."""
    rules_block = "\n".join(_format_rule(r) for r in rules)
    return (
        "RULES TO CHECK AGAINST (cite only these rule_ids):\n\n"
        f"{rules_block}\n\n"
        "----------\n"
        "MARKETING COPY TO REVIEW (quote exact substrings from between the markers):\n"
        "<<<COPY\n"
        f"{copy}\n"
        "COPY\n\n"
        "Return every violation of the rules above. If there are none, return an empty list."
    )
