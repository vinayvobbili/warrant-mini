"""Load and group the compliance rule library."""

from __future__ import annotations

import importlib.resources
from functools import lru_cache

import yaml

from .models import Rule, RuleGroup


@lru_cache(maxsize=1)
def load_rules() -> list[Rule]:
    """Parse rules.yaml (packaged alongside this module) into validated Rules."""
    raw = importlib.resources.files("warrant_mini").joinpath("rules.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, list):
        raise ValueError("rules.yaml must be a YAML list of rule objects")
    rules = [Rule.model_validate(item) for item in data]

    ids = [r.id for r in rules]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"Duplicate rule ids in rules.yaml: {sorted(dupes)}")
    return rules


def rules_by_group() -> dict[RuleGroup, list[Rule]]:
    """Group rules for per-group LLM judge passes, in a stable order."""
    grouped: dict[RuleGroup, list[Rule]] = {g: [] for g in RuleGroup}
    for rule in load_rules():
        grouped[rule.group].append(rule)
    # Drop empty groups so we don't fire a pointless LLM pass.
    return {g: rs for g, rs in grouped.items() if rs}


def rule_index() -> dict[str, Rule]:
    """Map rule id -> Rule for enriching judge findings with metadata."""
    return {r.id: r for r in load_rules()}
