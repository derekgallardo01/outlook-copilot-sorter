# Evaluation

## Two suites

1. **Unit tests** (`tests/`) — 55 pytest tests across classifier,
   drafter, Graph webhook, Outlook rules generator, subscription
   manager, and learn-from-moves feedback loop.
2. **Golden evals** (`evals/golden.json`) — 10 classification cases
   (19 assertions) + 5 module-level cases (13 assertions) = 32 total
   assertions.

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

## What the module evals cover

5 module-level cases exercising the extension modules:

1. `subscription_manager_refreshes_near_expiry` — mixed initial state
   (healthy + near-expiry + expired + missing) produces correct
   renewed / created / healthy / expired-removed counts
2. `subscription_manager_no_op_on_healthy_sub` — healthy subscription
   with plenty of runway triggers 0 renewals + 0 creates + 1 healthy
3. `feedback_produces_sender_rule_at_5_corrections` — 5 corrections
   from same sender to same label triggers 1 SenderRuleSuggestion
4. `feedback_produces_no_suggestion_below_threshold` — 2 corrections
   (below `MIN_CORRECTIONS_FOR_SENDER = 3`) produces zero suggestions
5. `feedback_ignores_stopwords_in_keyword_suggestions` — subjects made
   of stopwords produce zero keyword suggestions

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

**Graph subscription manager (11 tests):**

- `hours_remaining` correct for positive, zero, and expired
- `plan_renewals` correctly bins healthy / near-expiry / expired
- Custom threshold reclassifies subscriptions correctly
- `create_subscription` caps lifetime at 4230 minutes
- Created subscriptions appear in client list
- `renew_subscription` updates expiration correctly
- `refresh_all` handles mixed state (renew + create + healthy)
- Expired subscriptions get removed and recreated
- Summary line reports all categories
- `DEFAULT_RENEW_THRESHOLD_HOURS` is a reasonable value

**Learn from moves (11 tests):**

- Empty corrections returns empty update
- Sender rule suggested at 3+ corrections with 80%+ dominance
- Sender rule not suggested below threshold
- Sender rule not suggested when corrections are split across labels
- Keyword suggested when repeated across corrections
- Stopwords ignored in keyword suggestions
- Threshold raised when corrections cluster at HIGH confidence
- No threshold change when corrections cluster at LOW confidence
- Summary line reports all category counts
- "Re:" prefix stripped from keyword candidates

## Adding a new classification eval case

Edit `evals/golden.json` under `cases`. Each case must have `message_id`
(matching a fixture id from `backend.py::DEFAULT_INBOX`) plus at least
one of `expected_label`, `expected_drafts_reply`, `expected_review`.

## Adding a new module eval case

Edit `evals/golden.json` under `module_cases`. Each case has an `op`
(matching a function in `evals/run.py::OPS`) plus a list of
`assertions` with `path` + one of `eq` / `gte` / `lte`.

## CI

`.github/workflows/ci.yml` runs all suites on every push across
Python 3.10, 3.11, 3.12 and smoke-tests every CLI subcommand.
