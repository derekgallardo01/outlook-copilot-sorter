# Architecture

## Layers

```
Delivery mode 1: Server-side (Graph webhook)
  Graph subscription --notification--> Flask receiver
                                        --> parse_notification()
                                        --> process_batch()
                                              --> Classifier
                                              --> route()
                                              --> CopilotDrafter (when drafts_reply=True)
                                              --> client.move_to_folder() OR client.flag()

Delivery mode 2: Client-side (Outlook rules)
  build_rules_from_catalog(DEFAULT_CATALOG)
    --> generate_outlook_rules_xml()
    --> Outlook Import Rules
```

Both modes share the **same catalog** and **same folder mapping**, so a
tenant can migrate between them without re-training.

## Modules

| Module | Responsibility |
|---|---|
| `classifier.py` | 6-label catalog + rule/keyword classifier + `route()` for folder/queue/SLA/drafts_reply |
| `copilot_drafter.py` | Substitution templates by default; Graph-Copilot backend behind an env var |
| `graph_webhook.py` | Parse Graph POST body + validate `clientState` + dispatch to classifier/drafter/client |
| `graph_subscription_manager.py` | Subscription lifecycle: `list_subscriptions` / `plan_renewals` / `refresh_all` for scheduled cron |
| `learn_from_moves.py` | Ingest `LabelCorrection` events + emit `CatalogUpdate` suggestions (sender rules, keyword changes, threshold tuning) |
| `outlook_rules.py` | Translate the catalog into Outlook-importable XML |
| `backend.py` | `MockGraphClient` + 12-message fixture inbox for tests + demo |
| `cli.py` | The `outlook-sorter` script's subcommand dispatch |

## The classifier

`Classifier.classify(email)` returns a `ClassificationResult` with:

- `label` — primary label
- `confidence` — [0.0, 1.0], normalized against total raw score
- `candidates` — every label with its normalized score, sorted desc
- `signals` — which keyword / sender / subject-pattern matches fired

The classifier is deterministic (rule + keyword) by default. Setting
`OUTLOOK_SORTER_LLM=claude` swaps to an LLM classifier (not yet
implemented — see `docs/customization.md`).

## The router

`route(result, catalog)` maps a label to:

- **folder** where the message should land
- **queue** the human owner watches
- **sla_hours** for support/sales/HR queues
- **drafts_reply** — whether Copilot should draft a response

Low-confidence results (below `REVIEW_THRESHOLD = 0.55`) get flagged
for human review instead of being auto-routed. `unknown` label always
flags for review.

## The drafter

`CopilotDrafter.draft(email, label)` returns a `Draft` with subject +
body + tone, or `None` if the label doesn't have a template. Setting
`OUTLOOK_SORTER_DRAFTER=copilot` swaps to real Microsoft Graph Copilot
reply-suggestions (sketch in `docs/customization.md`).

Only three of the six labels get templates (support/sales/hr). Billing
+ newsletter + notification get sorted without a reply because those
categories rarely need one.

## The Graph webhook

`GraphWebhook.parse_notification(payload, query_params)` handles both:

- **Validation handshake** — when Graph creates the subscription, it
  sends a `validationToken` query parameter. The receiver echoes it
  back as text/plain within 10 seconds. Otherwise the subscription
  fails.
- **Real notifications** — the POST body has `value: [{clientState,
  resourceData, ...}]`. The receiver validates the shared secret and
  extracts message ids.

`GraphWebhook.process_batch(batch)` classifies each message, routes
it, optionally drafts a reply, and moves it to the target folder (or
flags it for review).

The webhook module is **transport-agnostic** — the Flask receiver in
`examples/` is one integration; you can also call this from Azure
Functions or an AWS Lambda.

## The Outlook rules fallback

`build_rules_from_catalog(catalog)` translates the classifier catalog
into `OutlookRule` objects (name + condition list + move target).
`generate_outlook_rules_xml(rules)` serializes them to Outlook's
importable rules format.

The subset supported: `SubjectContains`, `BodyContains`,
`FromAddressContains`, `MoveToFolder`, `StopProcessing`. Outlook 2019+
imports these cleanly. Delegated LLM classification is not possible in
this mode — Outlook rules are keyword-only. That's why the two modes
share a catalog but the LLM upgrade path is server-side only.

## The Graph subscription manager

Graph subscriptions for `/messages` have a max lifetime of 4230 minutes
(~70 hours). If a subscription expires without renewal, notifications
stop and the classifier goes silent — the delivery lead usually finds
out from an angry client 8 hours later.

`refresh_all(client, notification_url, client_state, desired_resources)`
is the one call a scheduled Azure Function / cron job makes every hour:

- **Every desired resource without an active subscription** → create
  one at max lifetime
- **Every subscription with less than `DEFAULT_RENEW_THRESHOLD_HOURS`
  remaining** → renew to max lifetime
- **Every expired subscription** → delete + replace with a fresh one
- **Every healthy subscription** → leave alone

The report has `renewed / created / healthy / expired_removed / errors`
counts + IDs, so the cron job can log a one-line status per hour and
alert only on errors.

## The learn-from-moves feedback loop

When a user manually moves a message from `Sales/Inbox` to
`Support/Inbox`, that's a labeled correction: the classifier said
`sales_opportunity` but the correct label was `support_ticket`.

`record_correction(email, predicted_label, predicted_confidence,
corrected_to, at)` captures the event. Over 100+ corrections,
`analyze_corrections(corrections, current_thresholds)` produces a
`CatalogUpdate` with three kinds of suggestions:

- **Sender-rule suggestions** — if a sender_local consistently gets
  corrected to the same label (>= 3 corrections + >= 80% dominance),
  add it to that label's `sender_locals`
- **Keyword change suggestions** — if a specific keyword appears in
  many corrections between the same (wrong, right) label pair
  (>= 4 corrections), add to the right label + remove from the wrong
- **Threshold change suggestions** — if corrections cluster at HIGH
  confidence for a label (avg confidence >= current threshold with
  >= 5 corrections), the model is confidently wrong — raise the
  threshold to force human review

The kit deliberately does NOT auto-apply changes to the catalog. A
classifier that mutates itself is impossible to debug. The delivery
lead reviews the update weekly and applies the safe subset.

The `MIN_CORRECTIONS_FOR_*` constants tune noise-vs-signal trade-off
per suggestion type.
