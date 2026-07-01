# Walkthrough: graph_webhook_server.py

## What it does

A Flask receiver for Microsoft Graph change notifications. Every time a
new message arrives in the monitored mailbox, Graph POSTs to this
endpoint, and the receiver:

1. Handles the Graph subscription validation handshake
2. Validates the `clientState` shared secret
3. Fetches the message from the (mock) Graph client
4. Classifies it against the 6-label catalog
5. Routes it to the right folder OR flags for human review
6. Drafts a reply if the label warrants it (support / sales / HR)

## Run

```bash
pip install -e ".[webhook]"
python examples/graph_webhook_server.py
```

## Test-drive with curl

```bash
curl -X POST http://localhost:5000/graph-webhook \
    -H 'Content-Type: application/json' \
    -d '{
          "value": [{
            "clientState": "demo-secret",
            "resourceData": {"id": "m-01"}
          }]
        }'
```

You should see a JSON response with `processed_count: 1` and a
`results` array containing the label + folder + queue + reply-drafted
flag.

## Wire to a real M365 tenant

1. Create an app registration in Entra with `Mail.Read`,
   `MailboxSettings.Read`, and `Mail.ReadWrite` (delegated or
   application, depending on scope).
2. Deploy this receiver to a public HTTPS URL. Azure App Service or
   Azure Functions with Flask adapter both work.
3. Create a Graph subscription:

   ```python
   graph_client.subscriptions.post({
       "changeType": "created",
       "notificationUrl": "https://your-app.example.com/graph-webhook",
       "resource": "/users/user@tenant.onmicrosoft.com/mailFolders('Inbox')/messages",
       "expirationDateTime": "2026-07-04T00:00:00Z",
       "clientState": "your-shared-secret",
   })
   ```

4. Swap `MockGraphClient` in this file for a real `GraphClient` using
   `msgraph-sdk` + `msal`. See `docs/customization.md`.

## Fallback path for tenants without app-reg access

Not every SMB tenant will grant you the Entra app registration. For
those, generate an Outlook client-side rules XML file instead:

```bash
outlook-sorter emit-outlook-rules --out my-rules.xml
```

Then walk the client through: Outlook -> File -> Manage Rules and
Alerts -> Options -> Import Rules -> select `my-rules.xml`. The label
-> folder mapping is identical to the Graph-webhook path.
