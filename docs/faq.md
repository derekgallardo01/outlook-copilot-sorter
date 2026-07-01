# FAQ

**Q: Why two delivery modes? Can't I just use one?**

Yes and no. If your client has admin access to their tenant + is
willing to grant an Entra app registration, use the Graph webhook —
it's LLM-classifiable, works on every device, and can draft replies.
If the client won't grant app reg (very common for small SMB tenants
on shared M365 Business plans), you fall back to Outlook rules. Both
modes share the same catalog + folder map so migration between them
is zero-drift.

---

**Q: What's the difference between this and email-triage-automation?**

`email-triage-automation` is a general-purpose triage kit (IMAP-based,
non-Outlook-specific, four-format parser). Use it if the client's
inbox is on Gmail or a random IMAP server.

This kit is **Outlook + Copilot specific**: it wires to Microsoft
Graph webhooks, uses the Copilot draft-reply endpoint, and ships the
Outlook client-side rules fallback. Use it specifically for M365
tenants.

---

**Q: How accurate is the rule-based classifier?**

Against the bundled 12-message fixture, 10 of 12 messages classify
with 0.85+ confidence and 2 fall to `unknown` → REVIEW queue (correct
behavior for ambiguous mail). In real client engagements, expect
70-85% correct label with first-week keyword tuning — a good LLM
classifier (via `OUTLOOK_SORTER_LLM=claude`) pushes that to 92-96%.

---

**Q: How do I keep the Copilot drafter from hallucinating reply
   content?**

Two techniques:

1. Keep the drafter deterministic (default template backend) for the
   first month; wire real Copilot only once you have keyword-tuned
   the classifier
2. When you do wire Copilot, use short, tone-tagged prompts
   (see the `_draft_copilot` sketch in `docs/customization.md`) and
   add a post-check that the draft doesn't contain placeholder
   patterns like `[name]` or `[company]`

---

**Q: Does Outlook support importing rules XML that this tool
   generates?**

Outlook 2019+ desktop, yes — the file goes to **File → Manage Rules &
Alerts → Options → Import Rules**. OWA does not have direct import,
but rules imported on desktop sync to OWA automatically. Mobile
Outlook has limited rule support — some rules run, others don't. This
is Outlook's limitation, not the kit's.

---

**Q: How do I keep the Graph subscription alive? Doesn't it expire?**

Yes. Graph subscriptions for `/messages` have a max lifetime of 4230
minutes (~70 hours). The kit does not renew for you. In production,
add a scheduled task that calls `subscriptions.by_subscription_id(id).patch(
{"expirationDateTime": now + 4200min})` every 60 hours.

---

**Q: How do I know if my subscription cron is actually running?**

Two signals: `RefreshReport.summary()` should show at least 1
`healthy` per cron run against a live tenant. If it shows `0 healthy`
and `N created`, either the subscriptions expired unnoticed or the
cron didn't fire the previous hour. Log the summary line + alert on
`report.errors`.

The kit does NOT include a "subscriptions health dashboard" — that's
a separate observability layer. Pair with
[llm-observability-kit](https://github.com/derekgallardo01/llm-observability-kit)
if you want fired-alert semantics.

---

**Q: The learn-from-moves suggestions look aggressive. How do I filter
noise?**

Bump the `MIN_CORRECTIONS_FOR_*` constants in `learn_from_moves.py`.
Defaults (3 / 4 / 5) are tuned for a first month of calibration.
After the classifier stabilizes, raise to 6 / 8 / 10 so only strong
signals produce suggestions.

If you see the same keyword suggested to add AND remove for related
labels, that's usually because the classifier has an over-broad
keyword shared between two labels. Manually merge the labels or add
a `weight` adjustment before applying the suggestion.

---

**Q: Do you offer this as a delivered engagement?**

Yes. See my Upwork profile at
[upwork.com/freelancers/~derekgallardo](https://www.upwork.com/freelancers/~derekgallardo)
or email derekgallardo01@gmail.com. Typical scope: USD 400 - 800
fixed for client-side rules install; USD 1,800 - 3,500 for the
Graph-webhook build with Copilot drafter + your first month of
keyword tuning; USD 250/mo retainer for subscription-cron + weekly
feedback-loop review.
