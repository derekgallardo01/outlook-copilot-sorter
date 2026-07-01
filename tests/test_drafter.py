from outlook_copilot_sorter.backend import DEFAULT_INBOX
from outlook_copilot_sorter.copilot_drafter import CopilotDrafter


def test_support_draft_includes_sender_first_name():
    drafter = CopilotDrafter()
    d = drafter.draft(DEFAULT_INBOX[0], "support_ticket")
    assert d is not None
    assert "Acme" in d.body  # first name of "Acme Support"


def test_sales_draft_has_professional_tone():
    drafter = CopilotDrafter()
    d = drafter.draft(DEFAULT_INBOX[1], "sales_opportunity")
    assert d is not None
    assert d.tone == "professional"


def test_hr_draft_is_concise():
    drafter = CopilotDrafter()
    d = drafter.draft(DEFAULT_INBOX[4], "internal_hr")
    assert d is not None
    assert d.tone == "concise"


def test_billing_no_draft():
    """Billing has no template, so drafter returns None (billing routes without a reply)."""
    drafter = CopilotDrafter()
    d = drafter.draft(DEFAULT_INBOX[9], "billing")
    assert d is None


def test_notification_no_draft():
    drafter = CopilotDrafter()
    d = drafter.draft(DEFAULT_INBOX[2], "notification")
    assert d is None


def test_draft_subject_prefixes_re():
    drafter = CopilotDrafter()
    e = DEFAULT_INBOX[0]
    d = drafter.draft(e, "support_ticket")
    assert d is not None
    assert d.subject.startswith("Re:")
    assert e.subject in d.subject


def test_copilot_backend_stub_error():
    import os
    os.environ["OUTLOOK_SORTER_DRAFTER"] = "copilot"
    try:
        drafter = CopilotDrafter()
        d = drafter.draft(DEFAULT_INBOX[0], "support_ticket")
        assert d is not None
        assert d.error
    finally:
        del os.environ["OUTLOOK_SORTER_DRAFTER"]
