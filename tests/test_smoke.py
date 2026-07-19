"""Smoke tests — no live API calls.

Cover the parts that must be right before any review runs: the rule library
loads and is internally consistent, the judge schema validates, the quote
verifier rejects fabricated text, and the input loader handles all three source
shapes.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from warrant_mini import checker
from warrant_mini.input_loader import load_input
from warrant_mini.models import RuleGroup, _JudgeResponse
from warrant_mini.rules import load_rules, rule_index, rules_by_group

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_rules_load_and_are_consistent():
    rules = load_rules()
    assert len(rules) >= 8
    ids = [r.id for r in rules]
    assert len(ids) == len(set(ids)), "rule ids must be unique"
    for r in rules:
        assert r.regulation.strip()
        assert r.description.strip()
        assert r.violation_examples, f"{r.id} should carry at least one example"


def test_every_group_is_populated():
    grouped = rules_by_group()
    assert set(grouped) <= set(RuleGroup)
    assert sum(len(v) for v in grouped.values()) == len(load_rules())


def test_judge_schema_accepts_wellformed_and_empty():
    assert _JudgeResponse.model_validate({"findings": []}).findings == []
    one = _JudgeResponse.model_validate(
        {
            "findings": [
                {
                    "rule_id": "finra-2210",
                    "severity": "P1",
                    "quote": "guaranteed 12% annual returns",
                    "reasoning": "Promissory / guaranteed-return language.",
                    "suggested_rewrite": "Past performance does not guarantee future results.",
                }
            ]
        }
    )
    assert one.findings[0].rule_id == "finra-2210"


def test_quote_verifier_rejects_fabrication():
    copy = "Earn 5% on your savings today."
    assert checker._quote_in_copy("Earn 5% on your savings", copy) is not None
    # whitespace-insensitive match still verifies
    assert checker._quote_in_copy("Earn   5%\non your savings", copy) is not None
    # text that is simply not present is rejected
    assert checker._quote_in_copy("guaranteed 30% returns", copy) is None


def test_rule_index_covers_all_rules():
    idx = rule_index()
    assert set(idx) == {r.id for r in load_rules()}


@pytest.mark.parametrize("name", ["fintech_landing.md", "clean_newsletter.md", "influencer_post.txt"])
def test_input_loader_reads_example_files(name):
    loaded = load_input(str(EXAMPLES / name))
    assert loaded.text.strip()
    assert loaded.source_label.startswith("file:")


def test_input_loader_treats_short_string_as_pasted_text():
    loaded = load_input("Guaranteed 20% returns!")
    assert loaded.source_label == "pasted text"
    assert "Guaranteed" in loaded.text
