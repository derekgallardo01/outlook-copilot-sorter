# Evaluation

## Two suites

1. **Unit tests** (`tests/`) — 34 pytest tests across classifier,
   drafter, Graph webhook, and Outlook rules generator.
2. **Golden classification evals** (`evals/golden.json`) — 10 cases
   with 19 assertions.

## What the classifier evals cover

Per-message expected label + expected `drafts_reply` + expected
`review_required`. The 10 cases span:

- **Every default label class** — support_ticket, sales_opportunity,
  billing, newsletter, notification, internal_hr (each covered)
- **Ambiguous cases** — "Following up" (unknown, review) and
  "Customer success check-in" (unknown, review)
- **Reply-thread continuation** — Sarah's RE to Elena stays labeled
  as sales_opportunity
- **Two variants of the same class** — Two support tickets to verify
  the classifier isn't overfitting to a single sample

Every case runs against the bundled 12-message mock inbox. CI fails
the build if any assertion regresses.

## What the pytest suite covers

**Classifier (14 tests):**

- Default catalog has 6 labels
- Each fixture message classifies to the expected label
- Ambiguous messages return `unknown` with confidence 0.0
- LLM backend errors cleanly when not implemented
- Router flags low-confidence for review
- Router assigns correct folder + queue + SLA + drafts_reply per label

**Drafter (7 tests):**

- Templates for support / sales / HR
- No template for billing / newsletter / notification
- Draft subject prefixes "Re:"
- Sender first-name substitution works
- Copilot backend returns error struct when not implemented

**Graph webhook (6 tests):**

- Validation handshake echoes the token
- Invalid `clientState` raises PermissionError
- Full batch classifies + moves + flags per rules
- Low-confidence messages get flagged, not moved
- Missing message ids are silently ignored

**Outlook rules (6 tests):**

- Rule generated per label
- Each rule has at least one condition
- Each rule has a folder target
- XML is well-formed and includes all rule names
- Special characters are XML-escaped
- Subject-contains truncated to 8 keywords max

## Adding a new eval case

Edit `evals/golden.json`. Each case must have `message_id` (matching
a fixture id from `backend.py::DEFAULT_INBOX`) plus at least one of
`expected_label`, `expected_drafts_reply`, `expected_review`.

## CI

`.github/workflows/ci.yml` runs both suites on every push across
Python 3.10, 3.11, 3.12 and smoke-tests the CLI.
