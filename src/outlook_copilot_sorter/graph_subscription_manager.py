"""Microsoft Graph subscription lifecycle manager.

Graph subscriptions for `/messages` have a max lifetime of 4230 minutes
(70 hours). If a subscription expires without renewal, notifications
stop and the classifier goes silent. The delivery lead usually finds
out from an angry client 8 hours later.

This module gives you the tools to keep subscriptions alive without
babysitting them:

- `list_subscriptions(client)` -> everything currently subscribed
- `plan_renewals(now, subscriptions, min_hours_remaining)` -> which
  subscriptions to renew right now (default: renew when less than 4 hrs
  remain)
- `create_subscription(client, resource, notification_url, ...)` -> new
  subscription with sensible defaults
- `refresh_all(client, notification_url, resources)` -> the one call
  a scheduled Azure Function makes every hour

The kit ships a `MockSubscriptionClient` for tests. Set
`GRAPH_BACKEND=graph` and provide app-reg env vars to swap to real Graph.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


MAX_SUBSCRIPTION_MINUTES = 4230  # Graph max for /messages
DEFAULT_RENEW_THRESHOLD_HOURS = 4


@dataclass
class Subscription:
    id: str
    resource: str
    notification_url: str
    client_state: str
    expiration: datetime
    change_type: str = "created"

    def hours_remaining(self, now: datetime) -> float:
        return max(0.0, (self.expiration - now).total_seconds() / 3600.0)


@dataclass
class RenewalPlan:
    to_renew: list[Subscription] = field(default_factory=list)
    to_leave: list[Subscription] = field(default_factory=list)
    expired: list[Subscription] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Renewal plan: {len(self.to_renew)} to renew, "
            f"{len(self.to_leave)} healthy, {len(self.expired)} expired"
        )


class MockSubscriptionClient:
    """In-memory subscription store used by tests + demos."""

    def __init__(self, initial: list[Subscription] | None = None) -> None:
        self._subs: dict[str, Subscription] = {s.id: s for s in (initial or [])}
        self._create_log: list[Subscription] = []
        self._renew_log: list[tuple[str, datetime]] = []
        self._delete_log: list[str] = []

    def list(self) -> list[Subscription]:
        return list(self._subs.values())

    def create(self, sub: Subscription) -> Subscription:
        if sub.id in self._subs:
            raise ValueError(f"Subscription {sub.id!r} already exists")
        self._subs[sub.id] = sub
        self._create_log.append(sub)
        return sub

    def renew(self, subscription_id: str, new_expiration: datetime) -> Subscription:
        if subscription_id not in self._subs:
            raise KeyError(subscription_id)
        self._subs[subscription_id].expiration = new_expiration
        self._renew_log.append((subscription_id, new_expiration))
        return self._subs[subscription_id]

    def delete(self, subscription_id: str) -> None:
        if subscription_id in self._subs:
            del self._subs[subscription_id]
            self._delete_log.append(subscription_id)

    # Debug/inspection helpers - real Graph client won't have these
    def creates(self) -> list[Subscription]:
        return list(self._create_log)

    def renewals(self) -> list[tuple[str, datetime]]:
        return list(self._renew_log)

    def deletes(self) -> list[str]:
        return list(self._delete_log)


def list_subscriptions(client: MockSubscriptionClient) -> list[Subscription]:
    return client.list()


def plan_renewals(
    now: datetime,
    subscriptions: list[Subscription],
    min_hours_remaining: float = DEFAULT_RENEW_THRESHOLD_HOURS,
) -> RenewalPlan:
    plan = RenewalPlan()
    for s in subscriptions:
        remaining = s.hours_remaining(now)
        if remaining <= 0:
            plan.expired.append(s)
        elif remaining < min_hours_remaining:
            plan.to_renew.append(s)
        else:
            plan.to_leave.append(s)
    return plan


def create_subscription(
    client: MockSubscriptionClient,
    resource: str,
    notification_url: str,
    client_state: str,
    now: datetime | None = None,
    lifetime_minutes: int = MAX_SUBSCRIPTION_MINUTES,
) -> Subscription:
    now = now or datetime.now(timezone.utc)
    lifetime_minutes = min(lifetime_minutes, MAX_SUBSCRIPTION_MINUTES)
    sub = Subscription(
        id=str(uuid.uuid4()),
        resource=resource,
        notification_url=notification_url,
        client_state=client_state,
        expiration=now + timedelta(minutes=lifetime_minutes),
    )
    return client.create(sub)


def renew_subscription(
    client: MockSubscriptionClient,
    subscription_id: str,
    now: datetime | None = None,
    lifetime_minutes: int = MAX_SUBSCRIPTION_MINUTES,
) -> Subscription:
    now = now or datetime.now(timezone.utc)
    lifetime_minutes = min(lifetime_minutes, MAX_SUBSCRIPTION_MINUTES)
    new_expiration = now + timedelta(minutes=lifetime_minutes)
    return client.renew(subscription_id, new_expiration)


@dataclass
class RefreshReport:
    renewed: list[str] = field(default_factory=list)
    created: list[str] = field(default_factory=list)
    healthy: list[str] = field(default_factory=list)
    expired_removed: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"Refresh: {len(self.created)} created, "
            f"{len(self.renewed)} renewed, {len(self.healthy)} healthy, "
            f"{len(self.expired_removed)} expired-removed, "
            f"{len(self.errors)} errors"
        )


def refresh_all(
    client: MockSubscriptionClient,
    notification_url: str,
    client_state: str,
    desired_resources: list[str],
    now: datetime | None = None,
    min_hours_remaining: float = DEFAULT_RENEW_THRESHOLD_HOURS,
) -> RefreshReport:
    """One call the scheduled Azure Function makes every hour.

    Ensures every desired resource has an active subscription with at
    least `min_hours_remaining` before expiry. Renews near-expiry
    subscriptions. Removes fully-expired ones.
    """
    now = now or datetime.now(timezone.utc)
    report = RefreshReport()

    active = client.list()
    active_by_resource: dict[str, Subscription] = {s.resource: s for s in active}

    for resource in desired_resources:
        sub = active_by_resource.get(resource)
        if sub is None:
            try:
                created = create_subscription(client, resource, notification_url,
                                              client_state, now=now)
                report.created.append(created.id)
            except Exception as exc:
                report.errors.append((resource, str(exc)))
            continue

        remaining = sub.hours_remaining(now)
        if remaining <= 0:
            client.delete(sub.id)
            report.expired_removed.append(sub.id)
            try:
                created = create_subscription(client, resource, notification_url,
                                              client_state, now=now)
                report.created.append(created.id)
            except Exception as exc:
                report.errors.append((resource, str(exc)))
        elif remaining < min_hours_remaining:
            try:
                renew_subscription(client, sub.id, now=now)
                report.renewed.append(sub.id)
            except Exception as exc:
                report.errors.append((sub.id, str(exc)))
        else:
            report.healthy.append(sub.id)

    return report


def get_backend() -> MockSubscriptionClient:
    """Swap seam for real Graph subscriptions client."""
    if os.environ.get("GRAPH_BACKEND", "mock").lower() == "graph":
        raise NotImplementedError(
            "GRAPH_BACKEND=graph requires wiring the real "
            "msgraph_core.subscriptions client. See docs/customization.md."
        )
    return MockSubscriptionClient()
