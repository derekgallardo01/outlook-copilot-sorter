"""CLI entrypoint: `outlook-sorter <subcommand>`."""
from __future__ import annotations

import argparse
import json
import sys

from outlook_copilot_sorter.backend import MockGraphClient
from outlook_copilot_sorter.classifier import Classifier, DEFAULT_CATALOG, route
from outlook_copilot_sorter.copilot_drafter import CopilotDrafter
from outlook_copilot_sorter.graph_webhook import GraphWebhook, NotificationBatch
from outlook_copilot_sorter.outlook_rules import build_rules_from_catalog, generate_outlook_rules_xml


def _classify_inbox(as_json: bool = False) -> None:
    client = MockGraphClient()
    clf = Classifier()
    drafter = CopilotDrafter()

    lines: list[dict] = []
    for email in client.list_inbox():
        r = clf.classify(email)
        d = route(r, clf.catalog)
        draft = drafter.draft(email, d.label) if d.drafts_reply else None
        lines.append({
            "id": email.id,
            "from": email.sender_email,
            "subject": email.subject,
            "label": r.label,
            "confidence": r.confidence,
            "folder": d.folder,
            "queue": d.queue,
            "review_required": d.review_required,
            "review_reason": d.review_reason,
            "drafted_reply": bool(draft and not draft.error),
        })

    if as_json:
        print(json.dumps(lines, indent=2))
        return

    print(f"{'id':6s} {'label':20s} {'conf':>5s} {'folder':22s} status")
    print("-" * 78)
    for r in lines:
        status = "REVIEW" if r["review_required"] else ("DRAFTED" if r["drafted_reply"] else "SORTED")
        print(f"{r['id']:6s} {r['label']:20s} {r['confidence']:5.2f} "
              f"{r['folder']:22s} {status}")


def _emit_outlook_rules(out_path: str | None = None) -> None:
    rules = build_rules_from_catalog(DEFAULT_CATALOG)
    xml = generate_outlook_rules_xml(rules)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(xml)
        print(f"Wrote {len(xml)} chars to {out_path}")
    else:
        print(xml)


def _webhook_smoke() -> None:
    """Simulate one Graph notification against the mock client."""
    client = MockGraphClient()
    clf = Classifier()
    drafter = CopilotDrafter()
    wh = GraphWebhook(client=client, classifier=clf, drafter=drafter,
                      client_state_secret="demo-secret")

    payload = {
        "value": [
            {"clientState": "demo-secret", "resourceData": {"id": e.id}}
            for e in client.list_inbox()
        ]
    }
    batch = wh.parse_notification(payload)
    processed = wh.process_batch(batch)

    print(f"Processed {len(processed)} notifications from Graph webhook.\n")
    for p in processed:
        marker = f"[{p.action_taken.upper()}]"
        print(f"  {marker:24s} {p.email.id}  {p.decision.label:20s} "
              f"-> {p.decision.folder}")
        if p.draft and not p.draft.error:
            print(f"  {'':24s} drafted subject: {p.draft.subject}")


def _demo() -> None:
    print("=" * 74)
    print("OUTLOOK COPILOT SORTER - end-to-end demo (mock inbox + mock Graph)")
    print("=" * 74)
    print()
    print("1) Classify + route every inbox item")
    print("-" * 74)
    _classify_inbox()
    print()
    print("2) Simulate a Graph webhook batch")
    print("-" * 74)
    _webhook_smoke()
    print()
    print("3) Show the fallback Outlook client-side rules")
    print("-" * 74)
    xml = generate_outlook_rules_xml(build_rules_from_catalog(DEFAULT_CATALOG))
    print(xml[:400] + "\n...\n(full XML is " + str(len(xml)) + " chars)")


def _list_labels() -> None:
    print(f"{'label':22s} {'display name':32s}")
    print("-" * 60)
    for cfg in DEFAULT_CATALOG:
        print(f"{cfg.label:22s} {cfg.display_name:32s}")


def _refresh_subscriptions() -> None:
    """Demo: create some subscriptions with different expirations, then run refresh_all."""
    from datetime import datetime, timedelta, timezone
    from outlook_copilot_sorter.graph_subscription_manager import (
        MockSubscriptionClient, Subscription, refresh_all,
    )

    now = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    initial = [
        # Healthy - lots of runway
        Subscription(id="sub-01",
                     resource="/users/alice@corp.onmicrosoft.com/mailFolders('Inbox')/messages",
                     notification_url="https://sorter.example.com/graph-webhook",
                     client_state="secret", expiration=now + timedelta(hours=50)),
        # Near expiry - should be renewed
        Subscription(id="sub-02",
                     resource="/users/bob@corp.onmicrosoft.com/mailFolders('Inbox')/messages",
                     notification_url="https://sorter.example.com/graph-webhook",
                     client_state="secret", expiration=now + timedelta(hours=2)),
        # Expired - should be removed + replaced
        Subscription(id="sub-03",
                     resource="/users/carol@corp.onmicrosoft.com/mailFolders('Inbox')/messages",
                     notification_url="https://sorter.example.com/graph-webhook",
                     client_state="secret", expiration=now - timedelta(hours=3)),
    ]
    client = MockSubscriptionClient(initial=initial)

    desired = [s.resource for s in initial] + [
        # New user - no subscription yet
        "/users/dan@corp.onmicrosoft.com/mailFolders('Inbox')/messages",
    ]

    report = refresh_all(
        client, notification_url="https://sorter.example.com/graph-webhook",
        client_state="secret", desired_resources=desired, now=now,
    )
    print(report.summary())
    print()
    for sid in report.created:
        print(f"  CREATED   {sid}")
    for sid in report.renewed:
        print(f"  RENEWED   {sid}")
    for sid in report.healthy:
        print(f"  HEALTHY   {sid}")
    for sid in report.expired_removed:
        print(f"  REMOVED   {sid}")


def _analyze_feedback() -> None:
    """Demo: analyze a fabricated set of label corrections."""
    from datetime import datetime, timezone

    from outlook_copilot_sorter.learn_from_moves import (
        LabelCorrection, analyze_corrections,
    )

    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    # Fabricate 30 corrections that would emerge over a first calibration week
    corrections: list[LabelCorrection] = []
    # 5 messages from cs@acme.com misclassified as newsletter -> should be sales
    for i in range(5):
        corrections.append(LabelCorrection(
            email_id=f"m-cs-{i}", predicted_label="newsletter", predicted_confidence=0.62,
            corrected_to="sales_opportunity", corrected_at=now,
            sender_email="cs@acme.com",
            subject=f"Renewal proposal for Q{i} - please review",
        ))
    # 4 messages with "renewal" in subject wrongly labeled newsletter
    for i in range(4):
        corrections.append(LabelCorrection(
            email_id=f"m-r-{i}", predicted_label="newsletter", predicted_confidence=0.58,
            corrected_to="sales_opportunity", corrected_at=now,
            sender_email=f"sales{i}@bigco.com",
            subject=f"renewal proposal quote follow-up",
        ))
    # 6 misclassifications from AWS invoice-adjacent addresses -> billing
    for i in range(6):
        corrections.append(LabelCorrection(
            email_id=f"m-aws-{i}", predicted_label="notification", predicted_confidence=0.71,
            corrected_to="billing", corrected_at=now,
            sender_email="aws-invoice-team@amazon.com",
            subject=f"Invoice available - AWS account xxxx-{i}",
        ))

    update = analyze_corrections(
        corrections,
        current_thresholds={"sales_opportunity": 0.55, "billing": 0.55, "newsletter": 0.55},
    )
    print(update.summary())
    print()
    if update.sender_rules:
        print("Sender-rule suggestions:")
        for s in update.sender_rules:
            print(f"  add sender_local {s.sender_local!r} to label {s.label!r}   "
                  f"({s.correction_count} corrections)")
            print(f"    reason: {s.reason}")
        print()
    if update.keyword_changes:
        print("Keyword changes:")
        for k in update.keyword_changes:
            print(f"  {k.direction:6s} {k.keyword!r:20s} for label {k.label!r}   "
                  f"({k.correction_count} corrections)")
        print()
    if update.threshold_changes:
        print("Threshold changes:")
        for t in update.threshold_changes:
            print(f"  {t.label!r}: {t.current_threshold:.2f} -> {t.suggested_threshold:.2f}   "
                  f"({t.correction_count} corrections)")
            print(f"    reason: {t.reason}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="outlook-sorter")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_c = sub.add_parser("classify-inbox", help="Classify every message in the mock inbox.")
    p_c.add_argument("--json", action="store_true")

    p_r = sub.add_parser("emit-outlook-rules",
                         help="Generate the fallback Outlook client-side rules XML.")
    p_r.add_argument("--out", type=str, default=None)

    sub.add_parser("webhook-smoke",
                   help="Simulate a Graph webhook batch against the mock client.")

    sub.add_parser("list-labels", help="Show the 6 default label classes.")

    sub.add_parser("refresh-subscriptions",
                   help="Simulate the hourly Graph subscription lifecycle refresh.")

    sub.add_parser("analyze-feedback",
                   help="Analyze user manual moves and suggest catalog updates.")

    sub.add_parser("demo", help="Run every subcommand end-to-end.")

    args = parser.parse_args(argv)

    if args.cmd == "classify-inbox":
        _classify_inbox(as_json=args.json)
    elif args.cmd == "emit-outlook-rules":
        _emit_outlook_rules(out_path=args.out)
    elif args.cmd == "webhook-smoke":
        _webhook_smoke()
    elif args.cmd == "list-labels":
        _list_labels()
    elif args.cmd == "refresh-subscriptions":
        _refresh_subscriptions()
    elif args.cmd == "analyze-feedback":
        _analyze_feedback()
    elif args.cmd == "demo":
        _demo()
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
