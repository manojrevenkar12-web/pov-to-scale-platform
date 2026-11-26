from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from pts import ROOT, policy
from pts.engagement import Stage
from pts.ipam import IpamError, allocate, overlaps

from .conftest import TODAY, make


def rules(findings):
    return sorted({f.rule for f in policy.errors(findings)})


def test_sample_engagements_pass(samples):
    for e in samples:
        others = [o for o in samples if o is not e]
        assert policy.errors(policy.check(e, others, today=TODAY)) == [], e.id


def test_region_and_model_availability():
    assert rules(policy.check(make(region="eastus"), today=TODAY)) == ["PTS001", "PTS003"]
    assert rules(policy.check(make(region="eastus", classification="public"), today=TODAY)) == ["PTS001"]
    assert rules(policy.check(make(models=[{"model": "gpt-4.1", "tokens_per_minute": 1000}]), today=TODAY)) == [
        "PTS002"
    ]


def test_duration_budget_and_expiry():
    assert "PTS004" in rules(policy.check(make(expires=date(2027, 6, 1)), today=TODAY))
    assert "PTS005" in rules(policy.check(make(budget_eur=90000), today=TODAY))
    assert "PTS007" in rules(policy.check(make(start=date(2026, 9, 1), expires=date(2026, 11, 1)), today=TODAY))
    pilot = make(stage="pilot", budget_eur=70000, expires=date(2027, 5, 1))
    assert policy.errors(policy.check(pilot, today=TODAY)) == []


def test_fine_tuning_needs_consent_for_client_data():
    e = make(
        classification="client-restricted",
        region="swedencentral",
        fine_tuning=True,
        models=[{"model": "gpt-4.1-mini", "tokens_per_minute": 10000}],
    )
    assert rules(policy.check(e, today=TODAY)) == ["PTS006"]
    ok = e.model_copy(update={"client_consent_fine_tuning": True})
    assert policy.errors(policy.check(ok, today=TODAY)) == []


def test_duplicate_id_and_quota_warning():
    e = make()
    assert "PTS008" in rules(policy.check(e, [make()], today=TODAY))
    burner = make(budget_eur=500, models=[{"model": "gpt-4o", "tokens_per_minute": 900000}])
    assert any(f.rule == "PTS010" for f in policy.check(burner, today=TODAY))


def test_request_validation():
    with pytest.raises(ValidationError):
        make(id="Bad ID")
    with pytest.raises(ValidationError):
        make(owner="not-an-email")
    assert Stage.pov.next == Stage.pilot and Stage.scaled.next is None


def test_terraform_sources_are_clean():
    findings = policy.check_terraform(ROOT / "infra" / "terraform")
    assert findings == [], "\n".join(map(str, findings))


def test_terraform_static_rules_catch_mistakes(tmp_path: Path):
    (tmp_path / "main.tf").write_text(
        'resource "azurerm_cognitive_account" "x" {\n'
        "  public_network_access_enabled = true\n"
        "  local_auth_enabled = true\n"
        "}\n"
        'resource "azurerm_key_vault" "kv" {\n  purge_protection_enabled = false\n  tags = {}\n}\n'
    )
    assert sorted({f.rule for f in policy.check_terraform(tmp_path)}) == ["TF001", "TF002", "TF005", "TF007"]


def test_ipam_gives_every_engagement_its_own_range():
    got = allocate({}, ["a", "b", "c"], "10.64.0.0/12", ["10.64.0.0/22"], 22)
    assert got == {"a": "10.64.4.0/22", "b": "10.64.8.0/22", "c": "10.64.12.0/22"}
    again = allocate(got, ["a", "b", "c", "d"], "10.64.0.0/12", ["10.64.0.0/22"], 22)
    assert {k: again[k] for k in got} == got and again["d"] == "10.64.16.0/22"
    assert overlaps(list(again.values()) + ["10.64.0.0/22"]) == []
    assert overlaps(["10.64.4.0/22", "10.64.6.0/24"]) == [("10.64.4.0/22", "10.64.6.0/24")]
    with pytest.raises(IpamError):
        allocate({"x": "10.64.4.0/23", "y": "10.64.5.0/24"}, [], "10.64.0.0/12", [], 22)
    with pytest.raises(IpamError):
        allocate({}, [str(i) for i in range(5)], "10.64.0.0/20", ["10.64.0.0/22"], 22)
