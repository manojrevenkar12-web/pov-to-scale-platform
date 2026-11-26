# AGENTS.md

Rules for anyone changing this repository, people and coding agents alike.

## Invariants

1. **Code decides, the model reads.** The provisioning agent may use a model to turn a request into
   fields. Validation, policy, address allocation and rendering are code (`src/pts`). A model's output
   never reaches Terraform without `policy.check` passing.
2. **Nothing is applied without a merged pull request.** The agent writes `engagements/<id>.yaml`; a person
   approves; CI runs the policy check, `terraform validate`/`plan` and Checkov. Changes made in the portal
   are drift and get reverted.
3. **One engagement, one environment.** Each engagement has its own resource group, network range,
   Azure OpenAI account, Key Vault, identity and budget. No cross-client sharing, no API keys
   (`local_auth_enabled = false`), no public endpoints.
4. **Client data stays in the EU**, and fine-tuning on confidential or client-restricted data needs the
   client's written consent (`config/platform.yaml`).
5. **Budgets are enforced at the gateway**: owner told at 80%, new requests refused at 100%. Raising a budget
   is a one-line pull request.
6. **Promotion needs evidence.** pilot and scaled syncs run the promotion gate; missing metrics fail closed.
7. **Generated files are generated.** `infra/ipam.json`, `infra/terraform/envs/lab/engagements.auto.tfvars.json`,
   `deploy/argocd/engagements.json`, `deploy/prometheus/slo-rules.yaml`, the README results block,
   `reports/RESULTS.md` and `dashboard/public/data/results.json`. CI fails if any is stale.
8. **The held-out lab split runs once.** `results/HELDOUT.lock` exists afterwards; `pts lab report` refuses
   if the settings changed later.
9. **Address ranges never move.** `pts render-all` keeps existing allocations and only releases ranges of
   engagements that were removed.

## Commands

```bash
pip install -e ".[dev]"
pytest -q && ruff check src tests && ruff format --check src tests
pts check                 # policy on every engagement + static Terraform checks
pts render-all --check    # generated Terraform variables, address ranges, Argo CD apps are current
pts slo-rules --check
promtool test rules tests/prometheus/slo-rules-test.yaml
pts lab sim --split dev && pts lab report
cd dashboard && npm ci && npm test && npm run build
```

## Conventions

- Python 3.11+, typed, `ruff` clean. Settings in `config/*.yaml`, never constants in code.
- Every change to `src/pts/policy.py`, `budget.py`, `gate.py` or `infra/terraform` comes with a test.
- Commit trailers: `AI-Assisted: yes` when an assistant wrote part of the change; `Reviewed-by:` once a person
  reviewed it.
- Terraform: `terraform fmt`; every taggable resource carries the engagement tags; Checkov skips need a reason
  on the same line.
