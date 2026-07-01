"""Eval harness for the classification golden set.

Runs each case's expected label against the classifier + router,
reports pass/fail, and exits non-zero on any regression.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from outlook_copilot_sorter.backend import MockGraphClient
from outlook_copilot_sorter.classifier import Classifier, route


HERE = Path(__file__).parent


def _run() -> int:
    golden = json.loads((HERE / "golden.json").read_text())
    client = MockGraphClient()
    inbox = {e.id: e for e in client.list_inbox()}
    clf = Classifier()

    total = 0
    passed = 0

    print(f"Running {len(golden['cases'])} classification cases...\n")
    for case in golden["cases"]:
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

    print(f"\nResult: {passed}/{total} assertions passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(_run())
