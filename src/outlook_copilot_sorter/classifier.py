"""Rule + keyword classifier with a documented LLM swap point.

Ships 6 default categories that match how most inboxes actually get sorted:

- support_ticket   -> Support queue (SLA 4h)
- sales_opportunity -> Sales queue  (SLA 24h)
- billing          -> Finance queue (SLA 48h)
- newsletter       -> Read-later folder
- notification     -> Notifications folder (auto-archive after 7d)
- internal_hr      -> HR folder      (SLA 24h - deadlines are critical)

Each classification returns:
- primary label + confidence
- ranked candidate labels with per-label scores
- routing decision (folder / queue / SLA / whether Copilot should draft a reply)

Set OUTLOOK_SORTER_LLM=claude to swap to an LLM classifier.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable

from outlook_copilot_sorter.backend import Email


@dataclass
class LabelConfig:
    label: str
    display_name: str
    keywords: list[str] = field(default_factory=list)
    sender_domains: list[str] = field(default_factory=list)
    sender_locals: list[str] = field(default_factory=list)  # local parts before @
    subject_patterns: list[str] = field(default_factory=list)
    weight: float = 1.0


@dataclass
class ClassificationResult:
    label: str
    confidence: float
    candidates: list[tuple[str, float]] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)


@dataclass
class Decision:
    label: str
    folder: str
    queue: str
    sla_hours: int
    drafts_reply: bool
    review_required: bool = False
    review_reason: str = ""


DEFAULT_CATALOG: list[LabelConfig] = [
    LabelConfig(
        label="support_ticket",
        display_name="Support ticket",
        keywords=["cannot log in", "cannot access", "error", "broken", "down", "help asap",
                  "ticket #", "password reset", "500 error", "not working"],
        sender_locals=["tickets", "support", "help", "desk"],
        subject_patterns=[r"^ticket #?\d+", r"\bhelp\b", r"\berror\b"],
        weight=1.3,
    ),
    LabelConfig(
        label="sales_opportunity",
        display_name="Sales / renewal / deal",
        keywords=["proposal", "renewal", "terms", "pricing", "quote", "SOW",
                  "contract", "MSA", "purchase order", "legal has signed"],
        subject_patterns=[r"renewal", r"proposal", r"quote"],
        weight=1.2,
    ),
    LabelConfig(
        label="billing",
        display_name="Billing / invoice",
        keywords=["invoice", "payment due", "billing", "subscription renewed",
                  "receipt", "purchase confirmation", "total: usd", "auto-billed"],
        sender_locals=["billing", "invoices", "accounting", "no-reply-billing"],
        subject_patterns=[r"invoice", r"receipt", r"payment"],
        weight=1.2,
    ),
    LabelConfig(
        label="newsletter",
        display_name="Newsletter / marketing",
        keywords=["unsubscribe", "sale ends", "% off", "click here to shop",
                  "biggest sale", "featured this week", "editor's pick"],
        sender_locals=["deals", "newsletter", "marketing", "promo"],
        subject_patterns=[r"\*\*.*\*\*", r"\d+% off", r"weekly digest"],
        weight=0.9,
    ),
    LabelConfig(
        label="notification",
        display_name="Automated notification",
        keywords=["no-reply", "your recording", "google alert", "build failed",
                  "build succeeded", "notification from"],
        sender_locals=["no-reply", "noreply", "notifications", "ci"],
        subject_patterns=[r"^\[.*\]", r"google alert"],
        weight=0.8,
    ),
    LabelConfig(
        label="internal_hr",
        display_name="Internal HR / benefits / policies",
        keywords=["benefits enrollment", "open enrollment", "action required",
                  "workday", "handbook", "1:1 with", "pto policy", "holiday"],
        sender_locals=["hr", "people-ops", "benefits"],
        subject_patterns=[r"action required", r"benefits enrollment"],
        weight=1.1,
    ),
]


ROUTING = {
    "support_ticket":     ("Support/Inbox",       "support",      4,  True),
    "sales_opportunity":  ("Sales/Inbox",         "sales",        24, True),
    "billing":            ("Finance/Inbox",       "finance",      48, False),
    "newsletter":         ("Read-later",          "unattended",   0,  False),
    "notification":       ("Notifications",       "unattended",   0,  False),
    "internal_hr":        ("HR/Inbox",            "hr",           24, False),
    "unknown":            ("Inbox",               "human_review", 24, False),
}


REVIEW_THRESHOLD = 0.55


class Classifier:
    """Deterministic rule + keyword classifier. Swap to LLM via env var."""

    def __init__(self, catalog: list[LabelConfig] | None = None,
                 internal_domains: Iterable[str] = ()) -> None:
        self.catalog = catalog if catalog is not None else DEFAULT_CATALOG
        self.internal_domains = set(internal_domains)
        self._use_llm = os.environ.get("OUTLOOK_SORTER_LLM", "").lower() == "claude"

    def classify(self, email: Email) -> ClassificationResult:
        if self._use_llm:
            return self._classify_llm(email)

        scores: dict[str, float] = {}
        signals_by_label: dict[str, list[str]] = {}

        sender_local = (email.sender_email.split("@", 1)[0]).lower()
        sender_domain = (email.sender_email.split("@", 1)[1] if "@" in email.sender_email else "").lower()
        body_lower = email.body.lower()
        subject_lower = email.subject.lower()

        for cfg in self.catalog:
            score = 0.0
            signals: list[str] = []
            for kw in cfg.keywords:
                if kw.lower() in body_lower or kw.lower() in subject_lower:
                    score += 1.0
                    signals.append(f"keyword: {kw}")
            for sl in cfg.sender_locals:
                if sender_local == sl.lower() or sender_local.startswith(sl.lower() + "-") \
                        or sender_local.endswith("-" + sl.lower()) or sl.lower() in sender_local:
                    score += 1.5
                    signals.append(f"sender_local: {sl}")
            for sd in cfg.sender_domains:
                if sender_domain == sd.lower():
                    score += 1.5
                    signals.append(f"sender_domain: {sd}")
            for pat in cfg.subject_patterns:
                if re.search(pat, subject_lower):
                    score += 1.0
                    signals.append(f"subject_pattern: {pat}")

            score *= cfg.weight
            scores[cfg.label] = score
            signals_by_label[cfg.label] = signals

        ranked = sorted(scores.items(), key=lambda p: p[1], reverse=True)
        total = sum(v for _, v in ranked) or 1.0
        candidates = [(label, round(score / total, 3)) for label, score in ranked]

        if ranked and ranked[0][1] > 0:
            best_label, best_raw = ranked[0]
            confidence = round(best_raw / total, 3)
            return ClassificationResult(
                label=best_label,
                confidence=confidence,
                candidates=candidates,
                signals=signals_by_label[best_label],
            )

        return ClassificationResult(
            label="unknown",
            confidence=0.0,
            candidates=candidates,
            signals=[],
        )

    def _classify_llm(self, email: Email) -> ClassificationResult:
        """Placeholder for a Claude-backed classifier.

        In production, this issues one Claude call with a system prompt
        containing the label catalog and a JSON-schema-constrained tool
        result. See docs/customization.md.
        """
        raise NotImplementedError(
            "OUTLOOK_SORTER_LLM=claude requires implementing _classify_llm. "
            "See docs/customization.md for the ~30-line sketch."
        )


def route(result: ClassificationResult, catalog: list[LabelConfig]) -> Decision:
    label = result.label
    folder, queue, sla, drafts = ROUTING.get(label, ROUTING["unknown"])

    review_required = False
    review_reason = ""

    if result.confidence < REVIEW_THRESHOLD and label != "unknown":
        review_required = True
        review_reason = (f"confidence {result.confidence:.2f} below threshold "
                         f"{REVIEW_THRESHOLD}")

    if label == "unknown":
        review_required = True
        review_reason = "no matching classification signals"

    return Decision(
        label=label,
        folder=folder,
        queue=queue,
        sla_hours=sla,
        drafts_reply=drafts,
        review_required=review_required,
        review_reason=review_reason,
    )
