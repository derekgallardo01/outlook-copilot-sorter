"""Copilot-style reply drafter.

Ships two backends:
- `template` (default) - deterministic substitution templates per label.
  CI-friendly; runs in tests without an API key.
- `copilot`             - Microsoft Graph Copilot reply-suggestions.
  Requires app-registration + Copilot license. Sketch in docs/customization.md.

Only labels routed as `drafts_reply=True` in `classifier.ROUTING` get a
draft. Everything else returns None.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from outlook_copilot_sorter.backend import Email


@dataclass
class Draft:
    subject: str
    body: str
    tone: str = "professional"  # or "warm" / "concise"
    error: str = ""


DEFAULT_TEMPLATES: dict[str, tuple[str, str, str]] = {
    "support_ticket": (
        "Re: {subject}",
        ("Hi {sender_first},\n\n"
         "Thanks for reaching out. I've received your ticket and "
         "escalated it to the on-call engineer. Someone will follow "
         "up within our support SLA (4 business hours).\n\n"
         "For faster diagnosis, could you share:\n"
         "- The time (with timezone) when the issue started\n"
         "- Your account email / tenant ID\n"
         "- A screenshot of the error if possible\n\n"
         "We'll get you unblocked.\n\n"
         "Thanks,\n"
         "Support Team"),
        "warm",
    ),
    "sales_opportunity": (
        "Re: {subject}",
        ("Hi {sender_first},\n\n"
         "Thanks for sharing the proposal. I've flagged this for our "
         "review team and will get you a response within 24 hours.\n\n"
         "One quick question so we can move fast: do you have an "
         "internal deadline we should be aware of?\n\n"
         "Best,\n"
         "Sales Team"),
        "professional",
    ),
    "internal_hr": (
        "Re: {subject}",
        ("Hi,\n\n"
         "Received - I'll review and follow up if I have questions "
         "before the deadline.\n\n"
         "Thanks,"),
        "concise",
    ),
}


class CopilotDrafter:
    """Substitution drafter by default; swap to Copilot via env var."""

    def __init__(self, templates: dict[str, tuple[str, str, str]] | None = None) -> None:
        self.templates = templates if templates is not None else DEFAULT_TEMPLATES
        self._backend = os.environ.get("OUTLOOK_SORTER_DRAFTER", "template").lower()

    def draft(self, email: Email, label: str) -> Draft | None:
        if label not in self.templates:
            return None

        if self._backend == "copilot":
            return self._draft_copilot(email, label)

        subject_tmpl, body_tmpl, tone = self.templates[label]
        sender_first = email.sender_name.split()[0] if email.sender_name else "there"
        return Draft(
            subject=subject_tmpl.format(subject=email.subject),
            body=body_tmpl.format(subject=email.subject,
                                  sender_first=sender_first,
                                  sender_name=email.sender_name),
            tone=tone,
        )

    def _draft_copilot(self, email: Email, label: str) -> Draft:
        """Placeholder for Microsoft Graph Copilot reply-suggestions.

        See docs/customization.md for the Graph endpoint + prompt sketch.
        """
        return Draft(
            subject="",
            body="",
            tone="",
            error=("OUTLOOK_SORTER_DRAFTER=copilot requires implementing "
                   "_draft_copilot. See docs/customization.md."),
        )
