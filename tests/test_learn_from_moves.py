from datetime import datetime, timezone

from outlook_copilot_sorter.learn_from_moves import (
    LabelCorrection,
    MIN_CORRECTIONS_FOR_KEYWORD,
    MIN_CORRECTIONS_FOR_SENDER,
    MIN_CORRECTIONS_FOR_THRESHOLD,
    analyze_corrections,
)


NOW = datetime(2026, 7, 1, tzinfo=timezone.utc)


def _correction(email_id: str, predicted: str, corrected: str,
                sender: str, subject: str, confidence: float = 0.6) -> LabelCorrection:
    return LabelCorrection(
        email_id=email_id, predicted_label=predicted, predicted_confidence=confidence,
        corrected_to=corrected, corrected_at=NOW,
        sender_email=sender, subject=subject,
    )


def test_empty_corrections_returns_empty_update():
    update = analyze_corrections([])
    assert update.total_corrections == 0
    assert update.sender_rules == []
    assert update.keyword_changes == []
    assert update.threshold_changes == []


def test_sender_rule_suggested_when_dominant():
    """Threshold: 3+ corrections + 80% dominance."""
    corrections = [
        _correction(f"m-{i}", "newsletter", "sales_opportunity",
                    "sales@bigco.com", "renewal terms")
        for i in range(MIN_CORRECTIONS_FOR_SENDER)
    ]
    update = analyze_corrections(corrections)
    assert update.sender_rules
    assert update.sender_rules[0].label == "sales_opportunity"
    assert update.sender_rules[0].sender_local == "sales"


def test_sender_rule_not_suggested_below_threshold():
    corrections = [
        _correction(f"m-{i}", "newsletter", "sales_opportunity",
                    "sales@bigco.com", "quote request")
        for i in range(MIN_CORRECTIONS_FOR_SENDER - 1)
    ]
    update = analyze_corrections(corrections)
    assert update.sender_rules == []


def test_sender_rule_not_suggested_when_split():
    """If corrections go to different labels for the same sender, no dominance."""
    corrections = []
    for i in range(3):
        corrections.append(_correction(f"m-a-{i}", "newsletter", "sales_opportunity",
                                       "cs@bigco.com", "a"))
    for i in range(3):
        corrections.append(_correction(f"m-b-{i}", "newsletter", "support_ticket",
                                       "cs@bigco.com", "b"))
    update = analyze_corrections(corrections)
    # 3/6 = 50% dominance, below 80% threshold
    assert not any(s.sender_local == "cs" for s in update.sender_rules)


def test_keyword_suggested_when_repeated():
    corrections = [
        _correction(f"m-{i}", "newsletter", "sales_opportunity",
                    f"sender{i}@x.com", "renewal proposal quote follow-up")
        for i in range(MIN_CORRECTIONS_FOR_KEYWORD)
    ]
    update = analyze_corrections(corrections)
    assert update.keyword_changes
    # Should suggest adding "renewal" to sales and removing from newsletter
    add_kws = [k for k in update.keyword_changes if k.direction == "add"]
    remove_kws = [k for k in update.keyword_changes if k.direction == "remove"]
    assert add_kws and remove_kws
    assert any(k.keyword == "renewal" for k in add_kws)


def test_keyword_ignores_stopwords():
    corrections = [
        _correction(f"m-{i}", "newsletter", "sales_opportunity",
                    f"sender{i}@x.com", "the a of for with and")
        for i in range(MIN_CORRECTIONS_FOR_KEYWORD)
    ]
    update = analyze_corrections(corrections)
    kws = {k.keyword for k in update.keyword_changes}
    assert not (kws & {"the", "a", "of", "for", "with", "and"})


def test_threshold_raise_when_high_confidence_corrections():
    """If corrections cluster at HIGH confidence, model is confidently wrong."""
    corrections = [
        _correction(f"m-{i}", "notification", "billing",
                    "aws@amazon.com", "invoice available", confidence=0.85)
        for i in range(MIN_CORRECTIONS_FOR_THRESHOLD)
    ]
    update = analyze_corrections(corrections, current_thresholds={"notification": 0.55})
    assert update.threshold_changes
    t = update.threshold_changes[0]
    assert t.label == "notification"
    assert t.suggested_threshold > t.current_threshold


def test_no_threshold_change_when_low_confidence_corrections():
    """Low-confidence corrections already caught by review threshold."""
    corrections = [
        _correction(f"m-{i}", "notification", "billing",
                    "aws@amazon.com", "invoice available", confidence=0.30)
        for i in range(MIN_CORRECTIONS_FOR_THRESHOLD)
    ]
    update = analyze_corrections(corrections, current_thresholds={"notification": 0.55})
    assert not update.threshold_changes


def test_summary_line_reports_all_categories():
    corrections = [
        _correction(f"m-a-{i}", "newsletter", "sales_opportunity",
                    "sales@x.com", "renewal proposal")
        for i in range(6)
    ]
    update = analyze_corrections(corrections)
    s = update.summary()
    assert "corrections" in s
    assert "sender-rule" in s
    assert "keyword" in s
    assert "threshold" in s


def test_keyword_candidates_strips_re_prefix():
    corrections = [
        _correction(f"m-{i}", "newsletter", "sales_opportunity",
                    f"s{i}@x.com", "Re: renewal proposal quote")
        for i in range(MIN_CORRECTIONS_FOR_KEYWORD)
    ]
    update = analyze_corrections(corrections)
    # "re:" should be stripped so it doesn't appear as a keyword
    kws = {k.keyword for k in update.keyword_changes}
    assert "re:" not in kws
