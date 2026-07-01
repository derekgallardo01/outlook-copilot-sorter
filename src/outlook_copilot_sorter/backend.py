"""Mock inbox + mock Graph client.

Ships a realistic 12-message inbox that covers the 6 default label classes
plus a few edge cases (ambiguous multi-class, thread reply, low-confidence).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Email:
    id: str
    sender_name: str
    sender_email: str
    subject: str
    body: str
    received: datetime
    is_reply: bool = False
    thread_id: str = ""
    to_addresses: list[str] = field(default_factory=list)

    def preview(self, n: int = 200) -> str:
        return self.body[:n] + ("..." if len(self.body) > n else "")


def _now(day: int, hour: int) -> datetime:
    return datetime(2026, 7, day, hour, tzinfo=timezone.utc)


DEFAULT_INBOX: list[Email] = [
    Email(
        id="m-01",
        sender_name="Acme Support",
        sender_email="tickets@acme.com",
        subject="Ticket #4218: password reset",
        body=("Hi, I cannot log in. It says my password is expired. "
              "I have tried the forgot-password link three times and no "
              "email arrives. Can you help ASAP?"),
        received=_now(1, 9),
    ),
    Email(
        id="m-02",
        sender_name="Elena Torres",
        sender_email="elena@bigco.com",
        subject="Q3 renewal - proposal attached",
        body=("Attaching our proposed Q3 renewal terms as discussed on "
              "yesterday's call. Please review and let me know if the "
              "pricing works. Legal has already signed off on our end."),
        received=_now(1, 10),
    ),
    Email(
        id="m-03",
        sender_name="Zoom",
        sender_email="no-reply@zoom.us",
        subject="Your Zoom recording is ready",
        body=("Your recording for 'Q3 planning' is now available. Access "
              "it at your Zoom portal. Recordings older than 90 days are "
              "auto-deleted."),
        received=_now(1, 11),
    ),
    Email(
        id="m-04",
        sender_name="Dev Team CI",
        sender_email="ci@dev.acme.com",
        subject="[FAILED] main branch build #2318",
        body=("Build failed at step 'run-tests'. See logs at "
              "https://ci.acme.com/build/2318. First failing test: "
              "test_user_login_flow. This is a merge blocker."),
        received=_now(1, 12),
    ),
    Email(
        id="m-05",
        sender_name="HR Team",
        sender_email="hr@acme.com",
        subject="ACTION REQUIRED: Q3 benefits enrollment closes Friday",
        body=("Reminder that Q3 benefits enrollment closes this Friday at "
              "5pm PT. Log in to Workday and confirm your elections. If "
              "you miss the deadline you'll be defaulted to last quarter's "
              "elections."),
        received=_now(1, 13),
    ),
    Email(
        id="m-06",
        sender_name="Best Bargain Newsletter",
        sender_email="deals@bestbargainweekly.com",
        subject="** 70% OFF summer sale ends tonight! **",
        body=("Don't miss our biggest sale of the year. 70% off everything "
              "in the summer collection. Click here to shop now. Unsubscribe "
              "at bottom of email."),
        received=_now(1, 14),
    ),
    Email(
        id="m-07",
        sender_name="Sarah Kim",
        sender_email="sarah@bigco.com",
        subject="RE: Q3 renewal - proposal attached",
        body=("Thanks Elena, we reviewed the terms and have a few notes "
              "on section 4. Can we jump on a call Thursday morning to "
              "walk through them?"),
        received=_now(2, 8),
        is_reply=True,
        thread_id="t-renewal-q3",
    ),
    Email(
        id="m-08",
        sender_name="Random Sender",
        sender_email="hello@unknown.com",
        subject="Following up",
        body=("Hi, following up on my earlier message. Any thoughts?"),
        received=_now(2, 9),
    ),
    Email(
        id="m-09",
        sender_name="Google Alerts",
        sender_email="googlealerts-noreply@google.com",
        subject="Google Alert: your company name",
        body=("New results for your query 'Acme Corp':\n\n"
              "- TechCrunch: Acme raises Series C\n"
              "- Reddit: r/business discussion of Acme's growth\n"
              "\n\nSee all results in Google."),
        received=_now(2, 10),
    ),
    Email(
        id="m-10",
        sender_name="AWS Billing",
        sender_email="billing@aws.amazon.com",
        subject="Your AWS invoice for June 2026",
        body=("Your invoice for June 2026 is now available. Total: "
              "USD 4,218.44. Payment due July 15. See breakdown in your "
              "billing console."),
        received=_now(2, 11),
    ),
    Email(
        id="m-11",
        sender_name="Cust Success Team",
        sender_email="cs@saastool.com",
        subject="Quick check-in: how's onboarding going?",
        body=("Hey! Wanted to check in as you approach 90 days on our "
              "platform. Anything blocking you? Happy to jump on a 15-min "
              "call if useful."),
        received=_now(2, 12),
    ),
    Email(
        id="m-12",
        sender_name="Acme Support",
        sender_email="tickets@acme.com",
        subject="Ticket #4219: cannot access billing dashboard",
        body=("Getting 500 error when I click Billing. Has been broken all "
              "morning. Multiple people on my team are affected."),
        received=_now(2, 13),
    ),
]


class MockGraphClient:
    """In-memory stand-in for a Microsoft Graph client."""

    def __init__(self, inbox: list[Email] | None = None) -> None:
        self._inbox: list[Email] = list(inbox if inbox is not None else DEFAULT_INBOX)
        self._folder_moves: list[tuple[str, str]] = []
        self._flags: list[tuple[str, str]] = []

    def list_inbox(self) -> list[Email]:
        return list(self._inbox)

    def move_to_folder(self, message_id: str, folder: str) -> None:
        self._folder_moves.append((message_id, folder))

    def flag(self, message_id: str, category: str) -> None:
        self._flags.append((message_id, category))

    def moves(self) -> list[tuple[str, str]]:
        return list(self._folder_moves)

    def flags(self) -> list[tuple[str, str]]:
        return list(self._flags)

    def clear(self) -> None:
        self._folder_moves = []
        self._flags = []
