"""Generated files must match their sources; CI runs the same checks."""

from pts.cli import main


def test_render_and_slo_rules_are_current():
    assert main(["render-all", "--check"]) == 0
    assert main(["slo-rules", "--check"]) == 0


def test_policy_check_passes_on_the_repository():
    assert main(["check", "--today", "2026-11-26"]) == 0
