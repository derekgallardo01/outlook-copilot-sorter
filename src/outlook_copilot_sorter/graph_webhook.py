"""Microsoft Graph change-notification receiver.

Graph sends a POST to your subscription URL every time a new message
arrives in the monitored mailbox. The payload contains a list of
`value` items each with a `resourceData.id` pointing at the message.

This module:
1. Validates the `clientState` shared secret from the notification.
2. Handles the Graph subscription validation handshake (returns
   `validationToken` on first call).
3. Batches the notifications and dispatches each message to the
   classifier + drafter + folder-move pipeline.

The Flask/HTTP wrapping is left to the caller (`examples/graph_webhook_server.py`
shows a Flask app). This module is transport-agnostic so it can also be
called from Azure Functions or an AWS Lambda.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from outlook_copilot_sorter.backend import Email, MockGraphClient
from outlook_copilot_sorter.classifier import Classifier, Decision, route
from outlook_copilot_sorter.copilot_drafter import CopilotDrafter, Draft


@dataclass
class NotificationBatch:
    """One HTTP request's worth of Graph change notifications."""

    validation_token: str | None = None
    message_ids: list[str] = field(default_factory=list)
    invalid_client_state: bool = False


@dataclass
class ProcessedMessage:
    email: Email
    decision: Decision
    draft: Draft | None
    action_taken: str  # "moved", "flagged_for_review", "drafted_reply", "no_op"


class GraphWebhook:
    """Wraps a mock or real Graph client + classifier + drafter."""

    def __init__(
        self,
        client: MockGraphClient | Any,
        classifier: Classifier,
        drafter: CopilotDrafter | None = None,
        client_state_secret: str = "changeme-in-prod",
    ) -> None:
        self.client = client
        self.classifier = classifier
        self.drafter = drafter or CopilotDrafter()
        self.client_state_secret = client_state_secret

    def parse_notification(self, payload: dict, query_params: dict[str, str] | None = None) -> NotificationBatch:
        """Interpret a Graph POST body + query string.

        - On subscription validation, Graph sends a `validationToken`
          query parameter. Echo it back within 10 seconds.
        - On real notifications, the body has `value: [{resourceData, clientState, ...}]`.
        """
        query_params = query_params or {}
        if "validationToken" in query_params:
            return NotificationBatch(validation_token=query_params["validationToken"])

        batch = NotificationBatch()
        for item in payload.get("value", []):
            if item.get("clientState") != self.client_state_secret:
                batch.invalid_client_state = True
                continue
            resource = item.get("resourceData") or {}
            msg_id = resource.get("id")
            if msg_id:
                batch.message_ids.append(msg_id)

        return batch

    def process_batch(self, batch: NotificationBatch) -> list[ProcessedMessage]:
        if batch.validation_token:
            return []
        if batch.invalid_client_state:
            raise PermissionError(
                "Notification carried an invalid clientState. Refusing to process."
            )

        results: list[ProcessedMessage] = []
        inbox = {e.id: e for e in self.client.list_inbox()}

        for msg_id in batch.message_ids:
            email = inbox.get(msg_id)
            if email is None:
                continue
            result = self.classifier.classify(email)
            decision = route(result, self.classifier.catalog)

            if decision.review_required:
                self.client.flag(email.id, "human_review")
                action = "flagged_for_review"
                draft = None
            else:
                self.client.move_to_folder(email.id, decision.folder)
                draft = None
                if decision.drafts_reply:
                    draft = self.drafter.draft(email, decision.label)
                action = "drafted_reply" if draft and not draft.error else "moved"

            results.append(ProcessedMessage(
                email=email,
                decision=decision,
                draft=draft,
                action_taken=action,
            ))

        return results
