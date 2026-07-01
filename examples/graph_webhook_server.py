"""Production-shaped Flask receiver for Microsoft Graph webhooks.

Wraps the transport-agnostic `GraphWebhook` class in a Flask app so it
can be deployed to Azure App Service, Azure Functions (with a Flask
adapter), or a container.

Run:
    pip install -e ".[webhook]"
    python examples/graph_webhook_server.py

Then in a separate terminal, POST a Graph-style notification:

    curl -X POST http://localhost:5000/graph-webhook \\
        -H 'Content-Type: application/json' \\
        -d '{
              "value": [{
                "clientState": "demo-secret",
                "resourceData": {"id": "m-01"}
              }]
            }'

Production wiring: create a Graph subscription against
`/users/{userId}/mailFolders('Inbox')/messages` pointing at
https://<your-app>/graph-webhook with the same `clientState` shared
secret. See docs/customization.md.
"""
from __future__ import annotations

import json
import sys

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("This example needs Flask. Install with: pip install -e '.[webhook]'")
    sys.exit(1)

from outlook_copilot_sorter.backend import MockGraphClient
from outlook_copilot_sorter.classifier import Classifier
from outlook_copilot_sorter.copilot_drafter import CopilotDrafter
from outlook_copilot_sorter.graph_webhook import GraphWebhook


CLIENT_STATE_SECRET = "demo-secret"

app = Flask(__name__)

# Wire the pipeline once at startup - the classifier catalog + drafter templates
# are shared across every request.
_graph_client = MockGraphClient()
_classifier = Classifier()
_drafter = CopilotDrafter()
_webhook = GraphWebhook(
    client=_graph_client,
    classifier=_classifier,
    drafter=_drafter,
    client_state_secret=CLIENT_STATE_SECRET,
)


@app.route("/graph-webhook", methods=["POST"])
def graph_webhook():
    # Graph subscription validation handshake:
    # first request has a validationToken query param and expects the token
    # back as text/plain within 10 seconds.
    validation_token = request.args.get("validationToken")
    if validation_token:
        return validation_token, 200, {"Content-Type": "text/plain"}

    payload = request.get_json(force=True, silent=True) or {}
    batch = _webhook.parse_notification(payload, query_params=dict(request.args))

    try:
        processed = _webhook.process_batch(batch)
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 401

    return jsonify({
        "processed_count": len(processed),
        "results": [
            {
                "id": p.email.id,
                "action": p.action_taken,
                "label": p.decision.label,
                "confidence": p.decision.review_reason == "" or p.decision.review_reason,
                "folder": p.decision.folder,
                "queue": p.decision.queue,
                "drafted_reply": bool(p.draft and not p.draft.error),
            }
            for p in processed
        ],
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "labels": [c.label for c in _classifier.catalog]})


def main() -> int:
    print("Graph webhook receiver on http://localhost:5000/graph-webhook")
    print(f"clientState secret is: {CLIENT_STATE_SECRET}")
    print()
    print("To smoke-test, POST any of these ids from the mock inbox:")
    for e in _graph_client.list_inbox()[:6]:
        print(f"  {e.id}   {e.subject}")
    print()
    app.run(host="0.0.0.0", port=5000, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
