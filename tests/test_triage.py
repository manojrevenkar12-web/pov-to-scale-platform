from pts import triage

METRICS = """
gateway_requests_total{code="200",engagement="auto-parts-pricing-pov",model="gpt-4o-mini"} 900
gateway_upstream_errors_total{code="429",engagement="auto-parts-pricing-pov",model="gpt-4o"} 140
gateway_fallbacks_total{engagement="auto-parts-pricing-pov",model="gpt-4o"} 120
gateway_refused_total{engagement="auto-parts-pricing-pov",reason="budget-exhausted"} 35
gateway_budget_used_ratio{engagement="auto-parts-pricing-pov"} 0.97
gateway_requests_total{code="200",engagement="other",model="gpt-4o"} 10
"""

ALERT = {"labels": {"alertname": "SLOAvailabilityBurn1h", "engagement": "auto-parts-pricing-pov", "severity": "page"}}


def test_triage_names_causes_runbook_and_read_only_checks():
    note = triage.triage(ALERT, METRICS)
    text = note.markdown()
    assert note.runbook == "runbooks/slo-availability.md"
    assert any("budget" in c and "97%" in c for c in note.causes)
    assert any("throttled 140" in c and "120 served by the fallback" in c for c in note.causes)
    assert len(note.steps) == 5 and "pts triage" in note.steps[0]
    assert all(c.split()[0] in ("kubectl", "az") for c in note.commands)
    assert not any(v in " ".join(note.commands) for v in ("delete", "apply", "scale", "rollout restart", "patch"))
    assert "Nothing was changed" in text


def test_quiet_gateway_points_at_the_service():
    note = triage.triage({"labels": {"alertname": "SLOLatencyBurn6h", "engagement": "other"}}, METRICS)
    assert note.causes == ["the gateway sees no errors of its own: look at the engagement's service (pods, latency)"]
    assert note.runbook == "runbooks/slo-latency.md"


def test_unknown_alert_still_gets_a_note():
    note = triage.triage({"labels": {"alertname": "Mystery", "engagement": "x"}})
    assert note.runbook == "" and note.commands
