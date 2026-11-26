alerts: SLOAvailabilityBurn1h SLOAvailabilityBurn6h SLOAvailabilityBurn3d
owner: ai-lab-platform
---
# Engagement service is failing requests

The availability SLO (99.5% over 30 days) is burning its error budget too fast.

1. Check whether the gateway refuses requests (budget, rate limit) or the model errors (429, 5xx): `pts triage` reads the gateway counters.
2. If Azure OpenAI throttles: move traffic to the fallback deployment or raise the deployment's TPM quota in the engagement YAML (pull request, not the portal).
3. If the budget is exhausted: tell the owner; a raise is a one-line pull request to the engagement YAML.
4. If pods crash or are not ready: roll back with Argo CD to the previous synced revision.
5. Write the incident in the postmortem template within two working days if the page fired.

## Never
- Do not raise budgets or quotas in the portal; the next Terraform apply would undo it and no one would know why.
- Do not grant cross-engagement access to "borrow" quota from another client.
