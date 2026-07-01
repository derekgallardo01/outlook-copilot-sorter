"""AI-powered Outlook email sorter with two delivery modes."""
from outlook_copilot_sorter.classifier import Classifier, ClassificationResult, Decision, route
from outlook_copilot_sorter.copilot_drafter import CopilotDrafter, Draft
from outlook_copilot_sorter.graph_subscription_manager import (
    MockSubscriptionClient,
    RefreshReport,
    RenewalPlan,
    Subscription,
    create_subscription,
    plan_renewals,
    refresh_all,
    renew_subscription,
)
from outlook_copilot_sorter.graph_webhook import GraphWebhook, NotificationBatch
from outlook_copilot_sorter.learn_from_moves import (
    CatalogUpdate,
    KeywordWeightSuggestion,
    LabelCorrection,
    SenderRuleSuggestion,
    ThresholdSuggestion,
    analyze_corrections,
    record_correction,
)
from outlook_copilot_sorter.outlook_rules import OutlookRule, generate_outlook_rules_xml
from outlook_copilot_sorter.backend import MockGraphClient, Email

__all__ = [
    "Classifier",
    "ClassificationResult",
    "Decision",
    "route",
    "CopilotDrafter",
    "Draft",
    "GraphWebhook",
    "NotificationBatch",
    "OutlookRule",
    "generate_outlook_rules_xml",
    "MockGraphClient",
    "Email",
    "MockSubscriptionClient",
    "RefreshReport",
    "RenewalPlan",
    "Subscription",
    "create_subscription",
    "plan_renewals",
    "refresh_all",
    "renew_subscription",
    "CatalogUpdate",
    "KeywordWeightSuggestion",
    "LabelCorrection",
    "SenderRuleSuggestion",
    "ThresholdSuggestion",
    "analyze_corrections",
    "record_correction",
]
