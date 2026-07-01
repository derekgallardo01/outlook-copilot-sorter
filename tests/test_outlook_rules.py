from outlook_copilot_sorter.classifier import DEFAULT_CATALOG
from outlook_copilot_sorter.outlook_rules import (
    build_rules_from_catalog,
    generate_outlook_rules_xml,
)


def test_rules_generated_for_every_label():
    rules = build_rules_from_catalog(DEFAULT_CATALOG)
    assert len(rules) == 6


def test_each_rule_has_at_least_one_condition():
    rules = build_rules_from_catalog(DEFAULT_CATALOG)
    for r in rules:
        has_cond = r.when_subject_contains or r.when_from_local_matches
        assert has_cond, f"Rule {r.name} has no conditions"


def test_each_rule_has_folder_target():
    rules = build_rules_from_catalog(DEFAULT_CATALOG)
    for r in rules:
        assert r.move_to_folder
        assert r.move_to_folder != ""


def test_xml_is_well_formed_and_contains_rules():
    rules = build_rules_from_catalog(DEFAULT_CATALOG)
    xml = generate_outlook_rules_xml(rules)
    assert xml.startswith("<?xml")
    assert "<Rules " in xml
    assert xml.rstrip().endswith("</Rules>")
    for r in rules:
        assert r.name in xml
        assert r.move_to_folder in xml


def test_xml_escapes_special_chars():
    from outlook_copilot_sorter.outlook_rules import OutlookRule
    rule = OutlookRule(
        name="Rule with <special> & 'chars'",
        when_subject_contains=["<script>"],
        move_to_folder="Inbox",
    )
    xml = generate_outlook_rules_xml([rule])
    assert "<special>" not in xml.replace("&lt;special&gt;", "")
    assert "&amp;" in xml
    assert "&apos;" in xml


def test_subject_contains_truncated_to_8_keywords_max():
    from outlook_copilot_sorter.classifier import LabelConfig
    cfg = LabelConfig(
        label="test",
        display_name="Test",
        keywords=[f"keyword-{i}" for i in range(30)],
    )
    rules = build_rules_from_catalog([cfg])
    assert len(rules[0].when_subject_contains) <= 8
