import pytest

from outlook_copilot_sorter.backend import MockGraphClient
from outlook_copilot_sorter.classifier import Classifier
from outlook_copilot_sorter.copilot_drafter import CopilotDrafter
from outlook_copilot_sorter.graph_webhook import GraphWebhook


@pytest.fixture
def wh():
    client = MockGraphClient()
    clf = Classifier()
    drafter = CopilotDrafter()
    return GraphWebhook(client=client, classifier=clf, drafter=drafter,
                        client_state_secret="test-secret"), client


def test_validation_token_handshake(wh):
    hook, _client = wh
    batch = hook.parse_notification({}, query_params={"validationToken": "abc123"})
    assert batch.validation_token == "abc123"
    assert not batch.message_ids


def test_process_batch_returns_empty_for_validation(wh):
    hook, _client = wh
    batch = hook.parse_notification({}, query_params={"validationToken": "abc"})
    assert hook.process_batch(batch) == []


def test_invalid_client_state_refuses_processing(wh):
    hook, _client = wh
    payload = {"value": [{"clientState": "wrong-secret", "resourceData": {"id": "m-01"}}]}
    batch = hook.parse_notification(payload)
    assert batch.invalid_client_state
    with pytest.raises(PermissionError):
        hook.process_batch(batch)


def test_valid_batch_moves_messages(wh):
    hook, client = wh
    payload = {"value": [
        {"clientState": "test-secret", "resourceData": {"id": e.id}}
        for e in client.list_inbox()
    ]}
    batch = hook.parse_notification(payload)
    processed = hook.process_batch(batch)

    assert len(processed) == 12
    # Every non-unknown should trigger a folder move
    moves = {mid for mid, _ in client.moves()}
    unknowns = {p.email.id for p in processed if p.decision.label == "unknown"}
    all_ids = {e.id for e in client.list_inbox()}
    # Every message that's not unknown should be in the moves set
    assert (all_ids - unknowns).issubset(moves)


def test_low_confidence_flagged_not_moved(wh):
    hook, client = wh
    payload = {"value": [
        {"clientState": "test-secret", "resourceData": {"id": e.id}}
        for e in client.list_inbox()
    ]}
    batch = hook.parse_notification(payload)
    processed = hook.process_batch(batch)

    # unknowns should be flagged for review, not moved
    unknowns = [p for p in processed if p.decision.label == "unknown"]
    assert unknowns
    flagged_ids = {mid for mid, _ in client.flags()}
    assert all(p.email.id in flagged_ids for p in unknowns)


def test_missing_message_ids_are_ignored(wh):
    hook, _client = wh
    payload = {"value": [
        {"clientState": "test-secret", "resourceData": {"id": "does-not-exist"}}
    ]}
    batch = hook.parse_notification(payload)
    processed = hook.process_batch(batch)
    assert processed == []
