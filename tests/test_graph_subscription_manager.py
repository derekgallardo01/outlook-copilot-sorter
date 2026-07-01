from datetime import datetime, timedelta, timezone

from outlook_copilot_sorter.graph_subscription_manager import (
    DEFAULT_RENEW_THRESHOLD_HOURS,
    MAX_SUBSCRIPTION_MINUTES,
    MockSubscriptionClient,
    Subscription,
    create_subscription,
    plan_renewals,
    refresh_all,
    renew_subscription,
)


NOW = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)


def _sub(sid: str, hours_from_now: float, resource: str = "/users/x@corp/messages") -> Subscription:
    return Subscription(
        id=sid,
        resource=resource,
        notification_url="https://x.example.com/graph-webhook",
        client_state="secret",
        expiration=NOW + timedelta(hours=hours_from_now),
    )


def test_hours_remaining_positive():
    s = _sub("s-1", 24.0)
    assert 23.9 <= s.hours_remaining(NOW) <= 24.1


def test_hours_remaining_zero_for_expired():
    s = _sub("s-1", -5.0)
    assert s.hours_remaining(NOW) == 0.0


def test_plan_renewals_classifies_correctly():
    subs = [
        _sub("healthy", 20.0),
        _sub("near-expiry", 2.0),
        _sub("expired", -1.0),
    ]
    plan = plan_renewals(NOW, subs)
    assert [s.id for s in plan.to_leave] == ["healthy"]
    assert [s.id for s in plan.to_renew] == ["near-expiry"]
    assert [s.id for s in plan.expired] == ["expired"]


def test_plan_renewals_respects_custom_threshold():
    subs = [_sub("mid", 10.0)]
    # With 12-hour threshold, mid becomes near-expiry
    plan = plan_renewals(NOW, subs, min_hours_remaining=12.0)
    assert plan.to_renew == subs
    assert plan.to_leave == []


def test_create_subscription_caps_lifetime():
    client = MockSubscriptionClient()
    created = create_subscription(
        client, resource="/users/x/messages", notification_url="https://x/webhook",
        client_state="s", now=NOW, lifetime_minutes=99999,  # over the cap
    )
    assert (created.expiration - NOW).total_seconds() / 60 == MAX_SUBSCRIPTION_MINUTES


def test_create_subscription_appended_to_client():
    client = MockSubscriptionClient()
    created = create_subscription(client, "/users/x/messages", "https://x/webhook", "s", now=NOW)
    assert client.list() == [created]
    assert client.creates() == [created]


def test_renew_subscription_updates_expiration():
    client = MockSubscriptionClient()
    created = create_subscription(client, "/users/x/messages", "https://x/webhook", "s", now=NOW)
    later = NOW + timedelta(hours=10)
    renewed = renew_subscription(client, created.id, now=later)
    expected = later + timedelta(minutes=MAX_SUBSCRIPTION_MINUTES)
    assert renewed.expiration == expected


def test_refresh_all_renews_near_expiry_creates_new():
    initial = [_sub("healthy", 50.0, "/users/a/messages"), _sub("near", 2.0, "/users/b/messages")]
    client = MockSubscriptionClient(initial=initial)
    report = refresh_all(
        client, notification_url="https://x/webhook", client_state="s",
        desired_resources=["/users/a/messages", "/users/b/messages", "/users/c/messages"],
        now=NOW,
    )
    assert len(report.renewed) == 1
    assert len(report.created) == 1
    assert len(report.healthy) == 1


def test_refresh_all_removes_and_replaces_expired():
    initial = [_sub("expired", -5.0, "/users/a/messages")]
    client = MockSubscriptionClient(initial=initial)
    report = refresh_all(
        client, notification_url="https://x/webhook", client_state="s",
        desired_resources=["/users/a/messages"], now=NOW,
    )
    assert len(report.expired_removed) == 1
    assert len(report.created) == 1


def test_refresh_all_reports_summary():
    initial = [_sub("healthy", 40.0, "/users/a/messages")]
    client = MockSubscriptionClient(initial=initial)
    report = refresh_all(
        client, notification_url="https://x/webhook", client_state="s",
        desired_resources=["/users/a/messages", "/users/b/messages"], now=NOW,
    )
    s = report.summary()
    assert "created" in s
    assert "renewed" in s
    assert "healthy" in s


def test_default_renew_threshold_is_reasonable():
    """4 hours is short enough that a 1-hour scheduled Function can catch it."""
    assert 1.0 <= DEFAULT_RENEW_THRESHOLD_HOURS <= 12.0
