"""Feedback loop: learn from user manual moves.

When the sorter routes a message to `Sales/Inbox` and the user then
manually moves it to `Support/Inbox`, that's a labeled correction:
the classifier said `sales_opportunity` but the correct label was
`support_ticket`. Over 100+ corrections, patterns emerge:

- Certain keywords consistently push messages to the wrong class
- Certain senders should override the classifier entirely
- The confidence threshold may be too low (or too high) for certain
  labels

This module ingests those corrections, aggregates them, and emits a
`CatalogUpdate` suggestion the delivery lead reviews weekly:

- **New sender_locals** to add to specific `LabelConfig`s (high-signal
  senders)
- **Keyword weight adjustments** (up-weight for the correct label,
  down-weight for the wrong one)
- **Per-label confidence-threshold recommendations**

The kit deliberately does NOT auto-apply changes to the catalog. A
classifier that mutates itself is impossible to debug. The delivery
lead reviews the `CatalogUpdate` and applies the safe subset.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from outlook_copilot_sorter.backend import Email


@dataclass
class LabelCorrection:
    email_id: str
    predicted_label: str
    predicted_confidence: float
    corrected_to: str
    corrected_at: datetime
    sender_email: str = ""
    subject: str = ""


@dataclass
class SenderRuleSuggestion:
    """Suggested new sender_local to add to a LabelConfig."""

    label: str
    sender_local: str
    correction_count: int
    reason: str = ""


@dataclass
class KeywordWeightSuggestion:
    """Suggested keyword to add or remove from a LabelConfig."""

    label: str
    keyword: str
    direction: str  # "add" | "remove"
    correction_count: int
    reason: str = ""


@dataclass
class ThresholdSuggestion:
    """Suggested per-label confidence threshold tuning."""

    label: str
    current_threshold: float
    suggested_threshold: float
    correction_count: int
    reason: str = ""


@dataclass
class CatalogUpdate:
    sender_rules: list[SenderRuleSuggestion] = field(default_factory=list)
    keyword_changes: list[KeywordWeightSuggestion] = field(default_factory=list)
    threshold_changes: list[ThresholdSuggestion] = field(default_factory=list)
    total_corrections: int = 0

    def summary(self) -> str:
        return (
            f"Catalog update from {self.total_corrections} corrections: "
            f"{len(self.sender_rules)} sender-rule suggestions, "
            f"{len(self.keyword_changes)} keyword changes, "
            f"{len(self.threshold_changes)} threshold changes"
        )


# Minimum correction count before we recommend a change (avoid noise).
MIN_CORRECTIONS_FOR_SENDER = 3
MIN_CORRECTIONS_FOR_KEYWORD = 4
MIN_CORRECTIONS_FOR_THRESHOLD = 5


def record_correction(email: Email, predicted_label: str, predicted_confidence: float,
                      corrected_to: str, at: datetime) -> LabelCorrection:
    """Convenience constructor from an email + classifier result."""
    return LabelCorrection(
        email_id=email.id,
        predicted_label=predicted_label,
        predicted_confidence=predicted_confidence,
        corrected_to=corrected_to,
        corrected_at=at,
        sender_email=email.sender_email,
        subject=email.subject,
    )


def analyze_corrections(
    corrections: list[LabelCorrection],
    current_thresholds: dict[str, float] | None = None,
) -> CatalogUpdate:
    """Aggregate corrections into an actionable CatalogUpdate.

    Only actionable at scale - we require MIN_CORRECTIONS_FOR_* per suggestion
    to filter noise.
    """
    current_thresholds = current_thresholds or {}
    update = CatalogUpdate(total_corrections=len(corrections))

    if not corrections:
        return update

    update.sender_rules = _suggest_sender_rules(corrections)
    update.keyword_changes = _suggest_keyword_changes(corrections)
    update.threshold_changes = _suggest_threshold_changes(corrections, current_thresholds)

    return update


def _suggest_sender_rules(corrections: list[LabelCorrection]) -> list[SenderRuleSuggestion]:
    """If a specific sender consistently gets corrected to the same label,
    add that sender to the label's sender_locals."""
    # sender_local -> (target_label -> count)
    by_sender: dict[str, Counter[str]] = defaultdict(Counter)
    for c in corrections:
        if "@" not in c.sender_email:
            continue
        local = c.sender_email.split("@", 1)[0].lower()
        by_sender[local][c.corrected_to] += 1

    suggestions: list[SenderRuleSuggestion] = []
    for local, target_counts in by_sender.items():
        target, count = target_counts.most_common(1)[0]
        if count >= MIN_CORRECTIONS_FOR_SENDER and _dominant_ratio(target_counts) >= 0.8:
            suggestions.append(SenderRuleSuggestion(
                label=target,
                sender_local=local,
                correction_count=count,
                reason=(
                    f"{count} corrections routed to {target!r} from sender_local {local!r} "
                    f"(dominance {_dominant_ratio(target_counts):.0%})"
                ),
            ))

    suggestions.sort(key=lambda s: -s.correction_count)
    return suggestions


def _suggest_keyword_changes(corrections: list[LabelCorrection]) -> list[KeywordWeightSuggestion]:
    """If a specific keyword appears in many corrections between the same
    (wrong, right) label pair, propose adding it to the right label's
    keywords and removing it from the wrong label's."""
    # (wrong_label, right_label, keyword) -> count
    triples: Counter[tuple[str, str, str]] = Counter()
    for c in corrections:
        subject_words = _keyword_candidates(c.subject)
        for kw in subject_words:
            triples[(c.predicted_label, c.corrected_to, kw)] += 1

    suggestions: list[KeywordWeightSuggestion] = []
    already_suggested_kw_for_label: set[tuple[str, str]] = set()

    for (wrong, right, kw), count in triples.most_common():
        if count < MIN_CORRECTIONS_FOR_KEYWORD:
            break
        # Add to right label
        if (right, kw) not in already_suggested_kw_for_label:
            suggestions.append(KeywordWeightSuggestion(
                label=right, keyword=kw, direction="add",
                correction_count=count,
                reason=f"{count} messages containing {kw!r} were corrected from {wrong!r} to {right!r}",
            ))
            already_suggested_kw_for_label.add((right, kw))
        # Remove from wrong label (only if the keyword was likely in that label's list)
        if (wrong, kw) not in already_suggested_kw_for_label:
            suggestions.append(KeywordWeightSuggestion(
                label=wrong, keyword=kw, direction="remove",
                correction_count=count,
                reason=f"{count} messages containing {kw!r} misrouted to {wrong!r}",
            ))
            already_suggested_kw_for_label.add((wrong, kw))

    return suggestions


def _suggest_threshold_changes(
    corrections: list[LabelCorrection],
    current_thresholds: dict[str, float],
) -> list[ThresholdSuggestion]:
    """If corrections cluster at low-confidence predictions for a label,
    raise its threshold. If corrections cluster at high-confidence, we
    have a systematic bias (unhelpful; return nothing)."""
    # label -> list of predicted confidences that got corrected
    low_conf: dict[str, list[float]] = defaultdict(list)
    for c in corrections:
        low_conf[c.predicted_label].append(c.predicted_confidence)

    suggestions: list[ThresholdSuggestion] = []
    for label, confs in low_conf.items():
        if len(confs) < MIN_CORRECTIONS_FOR_THRESHOLD:
            continue
        avg = sum(confs) / len(confs)
        current = current_thresholds.get(label, 0.55)
        if avg < current:
            # Corrections tend to be at LOW confidence -> threshold OK; no change
            continue
        # Corrections at HIGH confidence -> the model is confidently wrong.
        # Raise threshold to force more into human review.
        suggested = min(0.9, avg + 0.1)
        suggestions.append(ThresholdSuggestion(
            label=label,
            current_threshold=current,
            suggested_threshold=round(suggested, 2),
            correction_count=len(confs),
            reason=(
                f"{len(confs)} corrections with avg confidence {avg:.2f} "
                f">= current threshold {current:.2f} - raise to force review."
            ),
        ))

    return suggestions


def _dominant_ratio(counter: Counter[str]) -> float:
    total = sum(counter.values())
    if not total:
        return 0.0
    return counter.most_common(1)[0][1] / total


_STOPWORDS = {
    "re:", "fwd:", "the", "a", "an", "of", "for", "with", "and", "or",
    "to", "in", "on", "at", "by", "is", "are", "was", "were",
    "my", "your", "our", "us", "we", "you", "i", "me",
    "hi", "hello", "hey", "thanks", "please", "please.",
}


def _keyword_candidates(subject: str) -> list[str]:
    """Extract likely-meaningful keywords from a subject line."""
    if not subject:
        return []
    lower = subject.lower()
    # Strip common prefixes
    for prefix in ("re: ", "fwd: ", "[fwd] "):
        if lower.startswith(prefix):
            lower = lower[len(prefix):]
    words = [w.strip(".,!?:;()[]") for w in lower.split()]
    return [w for w in words if len(w) >= 4 and w not in _STOPWORDS]
