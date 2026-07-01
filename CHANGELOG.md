# Changelog

## [1.1.0] - 2026-07-01

### Added
- **Graph subscription lifecycle manager** (`graph_subscription_manager.py`) — `list_subscriptions` / `plan_renewals` / `create_subscription` / `renew_subscription` / `refresh_all` for keeping Graph webhook subscriptions alive past their 70-hour max lifetime. `refresh_all()` is the one call an hourly scheduled Azure Function / cron job makes: creates missing, renews near-expiry (default threshold 4 hours), replaces expired.
- **Learn-from-moves feedback loop** (`learn_from_moves.py`) — `LabelCorrection` capture + `analyze_corrections()` produces a `CatalogUpdate` with three suggestion types: sender-rule suggestions (`sender_locals` to add per label), keyword weight changes (add to right label / remove from wrong), and confidence-threshold tuning (raise threshold when model is confidently wrong). Deliberately does NOT auto-apply — the delivery lead reviews weekly.
- Two new CLI subcommands: `refresh-subscriptions` and `analyze-feedback`
- 22 new tests (11 subscription manager + 11 feedback loop) - now 55 total
- Restructured `evals/golden.json` to add `module_cases` section with 5 new cases (13 assertions) alongside the existing 10 classification cases; total 32 eval assertions now (up from 19)
- Extended all 6 docs to cover both new modules
- Extended live Pages demo to show both new module summaries

## [1.0.0] - 2026-07-01

### Added
- Two delivery modes: server-side Microsoft Graph webhook AND client-side Outlook rules XML generator
- 6-label default catalog (support_ticket, sales_opportunity, billing, newsletter, notification, internal_hr) with confidence-thresholded routing
- Copilot-style reply drafter with substitution + Graph Copilot backends, tone tags (warm/professional/concise)
- Graph webhook validation handshake + clientState shared-secret check
- Mock Graph client with 12-message fixture inbox spanning all 6 classes + 2 ambiguous cases
- Flask receiver sample app (`examples/graph_webhook_server.py`) with health + graph-webhook endpoints
- Outlook client-side rules XML generator for tenants without Entra app-reg access
- CLI: `classify-inbox / webhook-smoke / emit-outlook-rules / list-labels / demo` with `--json` on classify
- 34 unit tests + 10 golden classification cases (19 assertions, 100% pass) + CI + Pages + screenshots + portfolio workflows

[1.1.0]: https://github.com/derekgallardo01/outlook-copilot-sorter/releases/tag/v1.1.0
[1.0.0]: https://github.com/derekgallardo01/outlook-copilot-sorter/releases/tag/v1.0.0
