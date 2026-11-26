# SKILLS.md

| Task | Files | Done when |
|---|---|---|
| New engagement environment | `pts agent "<request>" --owner … --cost-center … --write`, then `pts render-all` | PR shows the policy result, address range and budget; CI green |
| Promote an engagement | `engagements/<id>.yaml` (`stage`, budget, expiry), `pts render-all` | policy passes for the new stage; Argo CD syncs only after the promotion gate passes |
| Add a model or region | `config/platform.yaml` (`regions.models`), tests in `tests/test_policy.py` | `pts check` and tests pass |
| Change a promotion threshold | `config/promotion.yaml` | `tests/test_gate.py` updated; dev lab rerun and reports regenerated |
| Change an SLO | `config/slo.yaml`, `pts slo-rules`, `tests/prometheus/slo-rules-test.yaml` | `promtool test rules` passes |
| Triage a page | `pts triage alert.json --metrics gateway.prom` | note posted to the incident channel; postmortem from `runbooks/postmortem-template.md` |
| Change a lab assumption | `config/lab.yaml` | dev split rerun; never after the held-out lock without saying so in the README |
