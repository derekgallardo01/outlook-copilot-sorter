# Security

## Reporting a vulnerability

If you find a security issue in this project, please email
derekgallardo01@gmail.com with the details.

## Notes on the Graph webhook receiver

- The receiver validates the `clientState` shared secret on every
  notification. Rotating the secret invalidates all outstanding
  notifications until the subscription is renewed.
- Graph subscriptions expire (max 4230 minutes for messages). Renew via
  a scheduled task; the kit does not renew for you.
- The Flask sample uses `debug=False` and runs on `0.0.0.0:5000`;
  deploy behind a reverse proxy with TLS terminated at the proxy.
- The Copilot drafter never logs the full message body. Only the
  message id, subject, and first-name are logged for debugging.

## Dependencies

- Runtime default: stdlib only.
- `flask` (webhook extra) for the sample receiver.
- `msgraph-sdk` + `msal` (graph extra) for production Graph client.
- `anthropic` (llm extra) for a Claude-backed classifier / drafter.

Dependabot is enabled.
