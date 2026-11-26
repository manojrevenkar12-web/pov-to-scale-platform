# Task: change the engagement module

Read AGENTS.md first; invariants 2, 3 and 4 apply.

1. Edit `infra/terraform/modules/engagement`. Keep `public_network_access_enabled = false`,
   `local_auth_enabled = false`, private endpoints and tags on every taggable resource.
2. `terraform fmt -recursive infra/terraform`; `pytest -q tests/test_policy.py` (static rules TF001-TF007);
   `checkov -d infra/terraform --framework terraform`. A new Checkov skip needs a reason on the same line.
3. CI runs `terraform init -backend=false && terraform validate` against the pinned provider.

Stop and ask if the change touches network isolation, identity or role assignments: those need a named reviewer.
