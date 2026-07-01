from outlook_copilot_sorter.backend import DEFAULT_INBOX, Email, MockGraphClient
from outlook_copilot_sorter.classifier import Classifier, route
from datetime import datetime, timezone


def test_default_catalog_has_six_labels():
    clf = Classifier()
    labels = {c.label for c in clf.catalog}
    assert labels == {"support_ticket", "sales_opportunity", "billing",
                      "newsletter", "notification", "internal_hr"}


def test_password_reset_is_support_ticket():
    clf = Classifier()
    e = DEFAULT_INBOX[0]  # ticket #4218
    r = clf.classify(e)
    assert r.label == "support_ticket"
    assert r.confidence >= 0.7


def test_renewal_proposal_is_sales_opportunity():
    clf = Classifier()
    e = DEFAULT_INBOX[1]  # Elena's Q3 renewal
    r = clf.classify(e)
    assert r.label == "sales_opportunity"


def test_zoom_recording_is_notification():
    clf = Classifier()
    e = DEFAULT_INBOX[2]
    r = clf.classify(e)
    assert r.label == "notification"


def test_hr_benefits_is_internal_hr():
    clf = Classifier()
    e = DEFAULT_INBOX[4]  # HR benefits enrollment
    r = clf.classify(e)
    assert r.label == "internal_hr"


def test_percent_off_is_newsletter():
    clf = Classifier()
    e = DEFAULT_INBOX[5]  # 70% off sale
    r = clf.classify(e)
    assert r.label == "newsletter"


def test_aws_invoice_is_billing():
    clf = Classifier()
    e = DEFAULT_INBOX[9]  # AWS invoice
    r = clf.classify(e)
    assert r.label == "billing"


def test_ambiguous_message_is_unknown():
    clf = Classifier()
    e = DEFAULT_INBOX[7]  # "Following up"
    r = clf.classify(e)
    assert r.label == "unknown"
    assert r.confidence == 0.0


def test_result_includes_candidates():
    clf = Classifier()
    e = DEFAULT_INBOX[0]
    r = clf.classify(e)
    assert r.candidates
    assert all(isinstance(c[0], str) and 0 <= c[1] <= 1 for c in r.candidates)


def test_result_includes_signals():
    clf = Classifier()
    e = DEFAULT_INBOX[0]
    r = clf.classify(e)
    assert r.signals


def test_llm_backend_not_implemented_by_default():
    import os
    os.environ["OUTLOOK_SORTER_LLM"] = "claude"
    try:
        clf = Classifier()
        with __import__("pytest").raises(NotImplementedError):
            clf.classify(DEFAULT_INBOX[0])
    finally:
        del os.environ["OUTLOOK_SORTER_LLM"]


def test_route_flags_low_confidence_for_review():
    clf = Classifier()
    result = clf.classify(DEFAULT_INBOX[7])  # unknown
    d = route(result, clf.catalog)
    assert d.review_required
    assert "matching classification" in d.review_reason.lower() or "confidence" in d.review_reason.lower()


def test_route_support_ticket_gets_drafted():
    clf = Classifier()
    result = clf.classify(DEFAULT_INBOX[0])
    d = route(result, clf.catalog)
    assert d.drafts_reply
    assert d.queue == "support"
    assert d.sla_hours == 4


def test_route_billing_does_not_get_drafted():
    clf = Classifier()
    result = clf.classify(DEFAULT_INBOX[9])
    d = route(result, clf.catalog)
    assert not d.drafts_reply


def test_route_newsletter_goes_to_read_later():
    clf = Classifier()
    result = clf.classify(DEFAULT_INBOX[5])
    d = route(result, clf.catalog)
    assert d.folder == "Read-later"
