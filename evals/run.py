"""Eval harness for the classification golden set + module-level golden cases.

Runs each classification case's expected label against the classifier + router,
plus module-level assertions against the subscription manager and the
learn-from-moves feedback loop. Exits non-zero on any regression.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from outlook_copilot_sorter.backend import MockGraphClient
from outlook_copilot_sorter.classifier import Classifier, route
from outlook_copilot_sorter.graph_subscription_manager import (
    MockSubscriptionClient,
    Subscription,
    refresh_all,
)
from outlook_copilot_sorter.learn_from_moves import LabelCorrection, analyze_corrections


HERE = Path(__file__).parent
NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _run_classification_cases(cases: list[dict]) -> tuple[int, int]:
    client = MockGraphClient()
    inbox = {e.id: e for e in client.list_inbox()}
    clf = Classifier()
    total = 0
    passed = 0

    print(f"Running {len(cases)} classification cases...\n")
    for case in cases:
        msg_id = case["message_id"]
        email = inbox.get(msg_id)
        if email is None:
            print(f"  [FAIL] {case['name']} :: message {msg_id!r} not in mock inbox")
            total += 1
            continue

        result = clf.classify(email)
        decision = route(result, clf.catalog)

        case_ok = True

        if "expected_label" in case:
            total += 1
            if result.label == case["expected_label"]:
                passed += 1
            else:
                case_ok = False
                print(f"  [FAIL] {case['name']} :: label={result.label!r} "
                      f"expected={case['expected_label']!r}")

        if "expected_drafts_reply" in case:
            total += 1
            if decision.drafts_reply == case["expected_drafts_reply"]:
                passed += 1
            else:
                case_ok = False
                print(f"  [FAIL] {case['name']} :: drafts_reply="
                      f"{decision.drafts_reply} expected={case['expected_drafts_reply']}")

        if "expected_review" in case:
            total += 1
            if decision.review_required == case["expected_review"]:
                passed += 1
            else:
                case_ok = False
                print(f"  [FAIL] {case['name']} :: review_required="
                      f"{decision.review_required} expected={case['expected_review']}")

        if case_ok:
            print(f"  [PASS] {case['name']} :: label={result.label} "
                  f"conf={result.confidence:.2f}")

    return passed, total


def _op_subscription_refresh_mixed() -> dict:
    initial = [
        Subscription(id="healthy", resource="/users/a/messages",
                     notification_url="https://x/webhook", client_state="s",
                     expiration=NOW + timedelta(hours=50)),
        Subscription(id="near", resource="/users/b/messages",
                     notification_url="https://x/webhook", client_state="s",
                     expiration=NOW + timedelta(hours=2)),
        Subscription(id="expired", resource="/users/c/messages",
                     notification_url="https://x/webhook", client_state="s",
                     expiration=NOW - timedelta(hours=1)),
    ]
    client = MockSubscriptionClient(initial=initial)
    r = refresh_all(client, notification_url="https://x/webhook", client_state="s",
                    desired_resources=["/users/a/messages", "/users/b/messages",
                                       "/users/c/messages", "/users/d/messages"],
                    now=NOW)
    return {
        "renewed_count": len(r.renewed),
        "created_count": len(r.created),
        "healthy_count": len(r.healthy),
        "expired_removed_count": len(r.expired_removed),
    }


def _op_subscription_refresh_healthy() -> dict:
    initial = [
        Subscription(id="healthy", resource="/users/a/messages",
                     notification_url="https://x/webhook", client_state="s",
                     expiration=NOW + timedelta(hours=50)),
    ]
    client = MockSubscriptionClient(initial=initial)
    r = refresh_all(client, notification_url="https://x/webhook", client_state="s",
                    desired_resources=["/users/a/messages"], now=NOW)
    return {
        "renewed_count": len(r.renewed),
        "created_count": len(r.created),
        "healthy_count": len(r.healthy),
    }


def _op_feedback_5_sender_corrections() -> dict:
    corrections = [
        LabelCorrection(email_id=f"m-{i}", predicted_label="newsletter",
                        predicted_confidence=0.6, corrected_to="sales_opportunity",
                        corrected_at=NOW, sender_email="cs@bigco.com",
                        subject="renewal follow-up call")
        for i in range(5)
    ]
    u = analyze_corrections(corrections)
    return {
        "sender_rule_count": len(u.sender_rules),
        "keyword_change_count": len(u.keyword_changes),
        "threshold_change_count": len(u.threshold_changes),
        "total_corrections": u.total_corrections,
    }


def _op_feedback_2_corrections() -> dict:
    corrections = [
        LabelCorrection(email_id=f"m-{i}", predicted_label="newsletter",
                        predicted_confidence=0.6, corrected_to="sales_opportunity",
                        corrected_at=NOW, sender_email="cs@bigco.com",
                        subject="renewal follow-up call")
        for i in range(2)
    ]
    u = analyze_corrections(corrections)
    return {
        "sender_rule_count": len(u.sender_rules),
        "keyword_change_count": len(u.keyword_changes),
        "threshold_change_count": len(u.threshold_changes),
    }


def _op_feedback_stopword_subjects() -> dict:
    stopwords = {"the", "a", "of", "for", "with", "and", "or", "to", "in", "on"}
    corrections = [
        LabelCorrection(email_id=f"m-{i}", predicted_label="newsletter",
                        predicted_confidence=0.6, corrected_to="sales_opportunity",
                        corrected_at=NOW, sender_email=f"x{i}@x.com",
                        subject="the a of for with and or")
        for i in range(6)
    ]
    u = analyze_corrections(corrections)
    stop_kw_count = sum(1 for k in u.keyword_changes if k.keyword in stopwords)
    return {"stopword_keyword_count": stop_kw_count}


OPS = {
    "subscription_refresh_mixed": _op_subscription_refresh_mixed,
    "subscription_refresh_healthy": _op_subscription_refresh_healthy,
    "feedback_5_sender_corrections": _op_feedback_5_sender_corrections,
    "feedback_2_corrections": _op_feedback_2_corrections,
    "feedback_stopword_subjects": _op_feedback_stopword_subjects,
}


def _check(result: dict, a: dict) -> tuple[bool, str]:
    value = result.get(a["path"])
    if "eq" in a:
        ok = value == a["eq"]
        return ok, f"{a['path']} = {value} (expected {a['eq']})"
    if "gte" in a:
        ok = value is not None and value >= a["gte"]
        return ok, f"{a['path']} = {value} (expected >= {a['gte']})"
    if "lte" in a:
        ok = value is not None and value <= a["lte"]
        return ok, f"{a['path']} = {value} (expected <= {a['lte']})"
    return False, "unknown assertion"


def _run_module_cases(cases: list[dict]) -> tuple[int, int]:
    total = 0
    passed = 0
    print(f"Running {len(cases)} module cases...\n")
    for case in cases:
        result = OPS[case["op"]]()
        case_ok = True
        for a in case["assertions"]:
            ok, msg = _check(result, a)
            marker = "PASS" if ok else "FAIL"
            print(f"  [{marker}] {case['name']} :: {msg}")
            total += 1
            if ok:
                passed += 1
            else:
                case_ok = False
        print()
    return passed, total


def _run() -> int:
    golden = json.loads((HERE / "golden.json").read_text())

    passed_c, total_c = _run_classification_cases(golden.get("cases", []))
    print()
    passed_m, total_m = _run_module_cases(golden.get("module_cases", []))

    passed = passed_c + passed_m
    total = total_c + total_m
    print(f"\nResult: {passed}/{total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(_run())
