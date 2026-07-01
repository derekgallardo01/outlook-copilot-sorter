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
    elif args.cmd == "demo":
        _demo()
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
