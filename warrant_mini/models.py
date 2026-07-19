"""Typed data models for warrant-mini.

Two layers:
  * `Rule` — one entry from the compliance rule library (rules.yaml).
  * `Finding` / `ReviewResult` — the output of a review, including the raw
    schema the LLM judge is constrained to return.

The judge is never allowed to free-form its output: `_JudgeFinding` is the
Pydantic schema handed to `messages.parse()`, so every finding is validated
before it ever reaches the CLI.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# Severity is a fixed ladder. P4 is the deliberate low-confidence escape hatch:
# when the judge isn't sure a violation is real, it must land here rather than
# inventing a confident higher tier.
Severity = Literal["P1", "P2", "P3", "P4"]

SEVERITY_ORDER = {"P1": 0, "P2": 1, "P3": 2, "P4": 3}


class RuleGroup(str, Enum):
    FINANCIAL = "financial"
    CLAIMS = "claims"
    DISCLOSURE = "disclosure"


class Rule(BaseModel):
    """One compliance rule from the library."""

    id: str
    name: str
    regulation: str  # the real citation, e.g. "FTC 16 CFR Part 255"
    group: RuleGroup
    severity_default: Severity
    description: str
    violation_examples: list[str] = Field(default_factory=list)


class _JudgeFinding(BaseModel):
    """The exact shape the LLM judge is constrained to emit per finding.

    `rule_id` is validated against the rule set that was actually sent to the
    judge (see checker.py) — a finding citing a rule outside the group is
    dropped, which structurally prevents the model from inventing regulations.
    """

    rule_id: str = Field(description="ID of the violated rule. Must be one of the rule IDs provided.")
    severity: Severity = Field(
        description="P1 critical, P2 high, P3 moderate, P4 review-suggested. "
        "Use P4 whenever you are not confident the violation is real."
    )
    quote: str = Field(
        description="The exact substring of the marketing copy that violates the rule. "
        "Copy it verbatim — do not paraphrase."
    )
    reasoning: str = Field(description="Why this specific text violates the cited rule.")
    suggested_rewrite: str = Field(
        description="A compliant rewrite of the quoted text, or a concrete fix (e.g. an added disclosure)."
    )


class _JudgeResponse(BaseModel):
    """Top-level object the judge returns for one rule-group pass."""

    findings: list[_JudgeFinding] = Field(
        default_factory=list,
        description="All violations found for the provided rules. Empty list if the copy is compliant.",
    )


class Finding(BaseModel):
    """A validated finding, enriched with rule metadata for display."""

    rule_id: str
    rule_name: str
    regulation: str
    severity: Severity
    quote: str
    reasoning: str
    suggested_rewrite: str

    @property
    def sort_key(self) -> int:
        return SEVERITY_ORDER[self.severity]


class ReviewResult(BaseModel):
    """The full result of reviewing one piece of marketing copy."""

    source: str  # human-readable description of what was reviewed
    model: str
    char_count: int
    findings: list[Finding] = Field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        out = {"P1": 0, "P2": 0, "P3": 0, "P4": 0}
        for f in self.findings:
            out[f.severity] += 1
        return out
