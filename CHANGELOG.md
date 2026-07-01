# Changelog

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

[1.0.0]: https://github.com/derekgallardo01/outlook-copilot-sorter/releases/tag/v1.0.0
