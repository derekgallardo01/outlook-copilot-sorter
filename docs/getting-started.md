# Getting started

## Install

```bash
pip install -e .
```

For the Flask webhook receiver sample:

```bash
pip install -e ".[webhook]"
```

For the real Graph client (production wiring):

```bash
pip install -e ".[graph]"
```

## Run the demo

```bash
outlook-sorter demo
```

Walks all three modes end-to-end against the bundled 12-message mock inbox:

1. Classify + route every message
2. Simulate a Graph webhook batch (validation handshake + processing)
3. Show the fallback Outlook rules XML

## Classify one inbox

```bash
outlook-sorter classify-inbox              # table view
outlook-sorter classify-inbox --json       # for jq/pandas
```

## Simulate a Graph webhook

```bash
outlook-sorter webhook-smoke
```

## Emit the fallback client-side rules

```bash
outlook-sorter emit-outlook-rules --out my-rules.xml
```

Then in Outlook desktop: **File → Manage Rules & Alerts → Options →
Import Rules** → select `my-rules.xml`.

## Refresh Graph subscriptions

```bash
outlook-sorter refresh-subscriptions
```

Deploy this as an hourly scheduled task (Azure Function timer trigger,
or Windows Task Scheduler) — it renews subscriptions before their
70-hour expiry and replaces any that have already lapsed.

## Analyze user feedback (learn from moves)

```bash
outlook-sorter analyze-feedback
```

Reads a fabricated set of `LabelCorrection` events and emits a
`CatalogUpdate` with suggested sender rules, keyword changes, and
confidence-threshold tuning. In production, hook the correction
capture to your actual mailbox move events (via Graph webhook or
Outlook add-in).

## Run the Flask receiver

```bash
pip install -e ".[webhook]"
python examples/graph_webhook_server.py
```

Listens on http://localhost:5000. See
[examples/walkthrough.md](../examples/walkthrough.md) for the curl
smoke test + production deployment notes.

## Run tests + evals

```bash
python -m pytest -q     # 55 unit tests
python evals/run.py     # 10 classification + 5 module cases (32 assertions)
```

## Next

- [Architecture](architecture.md) — the two delivery modes + how they share a catalog
- [Customization](customization.md) — swap the mock for real Graph, wire Copilot
- [Evaluation](evaluation.md) — how the classifier evals work
- [Diagrams](diagrams.md) — flowchart + comparison matrix
- [FAQ](faq.md) — common questions
