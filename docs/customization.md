# Customization

## Swap the mock Graph client for real Microsoft Graph

The `MockGraphClient` class in `src/outlook_copilot_sorter/backend.py`
defines the surface. A production `GraphClient` is ~100 lines of
`msgraph-sdk` + `msal`:

```python
# src/outlook_copilot_sorter/backend_graph.py
import os
from datetime import datetime, timezone

from msgraph import GraphServiceClient
from msal import ConfidentialClientApplication


class GraphClient:
    def __init__(self, user_id: str) -> None:
        self.user_id = user_id
        self.app = ConfidentialClientApplication(
            client_id=os.environ["AZURE_CLIENT_ID"],
            client_credential=os.environ["AZURE_CLIENT_SECRET"],
            authority=f"https://login.microsoftonline.com/{os.environ['AZURE_TENANT_ID']}",
        )
        token = self.app.acquire_token_for_client(
            scopes=["https://graph.microsoft.com/.default"]
        )
        self.client = GraphServiceClient(credentials=token["access_token"])

    def list_inbox(self) -> list[Email]:
        response = self.client.users.by_user_id(self.user_id).messages.get()
        return [
            Email(
                id=m.id,
                sender_name=m.from_.email_address.name if m.from_ else "",
                sender_email=m.from_.email_address.address if m.from_ else "",
                subject=m.subject or "",
                body=m.body.content if m.body else "",
                received=m.received_date_time or datetime.now(timezone.utc),
                is_reply=False,  # can derive from conversationId
                thread_id=m.conversation_id or "",
                to_addresses=[r.email_address.address for r in (m.to_recipients or [])],
            )
            for m in (response.value or [])
        ]

    def move_to_folder(self, message_id: str, folder: str) -> None:
        # First look up the folder id by display name, then POST /move
        folder_id = self._folder_id_by_name(folder)
        self.client.users.by_user_id(self.user_id).messages.by_message_id(
            message_id
        ).move.post({"destinationId": folder_id})

    def flag(self, message_id: str, category: str) -> None:
        self.client.users.by_user_id(self.user_id).messages.by_message_id(
            message_id
        ).patch({"categories": [category]})

    def _folder_id_by_name(self, name: str) -> str:
        # Cache these; each Graph roundtrip is ~100ms
        ...
```

Wire it into the pipeline by replacing `MockGraphClient()` with
`GraphClient(user_id=...)` in the Flask receiver.

## Wire real Microsoft Graph Copilot for reply drafting

The template drafter is deterministic. To wire Microsoft Graph Copilot
reply-suggestions:

```python
def _draft_copilot(self, email: Email, label: str) -> Draft:
    from msgraph import GraphServiceClient
    from msal import ConfidentialClientApplication

    # Reuse the same app-reg + token as the Graph client
    # POST /users/{userId}/mailFolders/inbox/messages/{id}/replyAll
    # with a Copilot-generated body. The exact endpoint depends on
    # your M365 Copilot license tier - Business Chat vs M365 Copilot.

    tone_prompt = {"warm": "friendly and empathetic",
                   "professional": "respectful and direct",
                   "concise": "brief and to the point"}[self.templates[label][2]]

    system_prompt = (
        f"You are drafting a {tone_prompt} reply to an inbound email. "
        f"The email is classified as: {label}. "
        f"Preserve any specific requests from the sender. "
        f"Do not include placeholders like [name] - use the sender's actual name."
    )

    # ... Graph Copilot API call here ...
    # Return Draft(subject=..., body=..., tone=self.templates[label][2])
```

Enable with `OUTLOOK_SORTER_DRAFTER=copilot`.

## Add a new label class

1. Add a `LabelConfig` to `DEFAULT_CATALOG` in `classifier.py`
2. Add the folder / queue / SLA / drafts_reply tuple to `ROUTING`
3. If `drafts_reply=True`, add a `(subject_tmpl, body_tmpl, tone)`
   entry to `DEFAULT_TEMPLATES` in `copilot_drafter.py`
4. Add fixture messages to `DEFAULT_INBOX` in `backend.py`
5. Add golden cases to `evals/golden.json`
6. Add pytest cases

## Change the confidence threshold

`REVIEW_THRESHOLD = 0.55` in `classifier.py`. Lower → fewer
false-positive reviews but more mis-routings. Higher → safer routing
but more human-review load.

## Tune per-class weights

`LabelConfig.weight` scales the raw match score. Bump `weight=1.3` on
`support_ticket` (default) if support-ticket precision matters more
than throughput.

## Use a different set of keywords

Every `LabelConfig` has `keywords`, `sender_locals`, `sender_domains`,
`subject_patterns`. Tune per client's actual inbox patterns during
first-week calibration.
