"""Outlook client-side rules generator.

When a client tenant will NOT grant you app-registration + Graph
subscription rights (common for small orgs on shared M365 plans),
you fall back to Outlook desktop's built-in rules engine.

This module emits an Outlook Rules XML export that a user can
import via Outlook -> File -> Manage Rules -> Options -> Import Rules.

Trade-offs vs the Graph webhook:

|                   | Graph webhook | Outlook rules |
|-------------------|:-------------:|:-------------:|
| Server-side       | yes           | no (client)   |
| Requires app reg  | yes           | no            |
| LLM-classified    | yes           | no (keywords) |
| Draft replies     | yes           | no            |
| Works offline     | no            | yes           |
| Works on OWA/web  | yes           | yes*          |
| Works on mobile   | yes           | partial       |

Both modes ship in this kit; the classifier catalog is shared so the
label -> folder mapping is identical.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from outlook_copilot_sorter.classifier import LabelConfig, ROUTING


@dataclass
class OutlookRule:
    name: str
    when_subject_contains: list[str] = field(default_factory=list)
    when_body_contains: list[str] = field(default_factory=list)
    when_from_local_matches: list[str] = field(default_factory=list)
    move_to_folder: str = "Inbox"
    stop_processing: bool = True


def build_rules_from_catalog(catalog: Iterable[LabelConfig]) -> list[OutlookRule]:
    """Translate a classifier catalog into Outlook rule definitions."""
    rules: list[OutlookRule] = []
    for cfg in catalog:
        folder, _queue, _sla, _drafts = ROUTING.get(cfg.label, ROUTING["unknown"])
        rules.append(OutlookRule(
            name=f"Sort - {cfg.display_name}",
            when_subject_contains=[kw for kw in cfg.keywords if len(kw) >= 4][:8],
            when_from_local_matches=list(cfg.sender_locals),
            move_to_folder=folder,
            stop_processing=True,
        ))
    return rules


def generate_outlook_rules_xml(rules: list[OutlookRule]) -> str:
    """Emit an Outlook-importable XML rules file.

    Uses a simplified rules-format subset that Outlook 2019+ imports
    cleanly. The real format is defined in [MS-OXORULE]; this generator
    covers the subset most SMB tenants need.
    """
    lines: list[str] = []
    lines.append("<?xml version='1.0' encoding='utf-8'?>")
    lines.append("<Rules xmlns='http://schemas.microsoft.com/mailrules/2011'>")
    for r in rules:
        lines.append(f"  <Rule Name='{_esc(r.name)}' Enabled='true'>")
        lines.append("    <Conditions Any='true'>")
        for kw in r.when_subject_contains:
            lines.append(f"      <SubjectContains>{_esc(kw)}</SubjectContains>")
        for kw in r.when_body_contains:
            lines.append(f"      <BodyContains>{_esc(kw)}</BodyContains>")
        for local in r.when_from_local_matches:
            lines.append(f"      <FromAddressContains>{_esc(local)}</FromAddressContains>")
        lines.append("    </Conditions>")
        lines.append("    <Actions>")
        lines.append(f"      <MoveToFolder>{_esc(r.move_to_folder)}</MoveToFolder>")
        if r.stop_processing:
            lines.append("      <StopProcessing/>")
        lines.append("    </Actions>")
        lines.append("  </Rule>")
    lines.append("</Rules>")
    return "\n".join(lines)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;")
             .replace(">", "&gt;").replace("'", "&apos;"))
