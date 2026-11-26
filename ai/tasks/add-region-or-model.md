# Task: make <model> available in <region>

Read AGENTS.md first.

1. Add the model to `regions.models.<region>` in `config/platform.yaml`. Check that Azure OpenAI actually offers
   it there (Microsoft's model availability table); do not guess.
2. Add a case to `tests/test_policy.py` that a request for it passes, and keep the case that a region without it
   fails with PTS002.
3. `pytest -q`, `pts check`. If the change alters lab results, rerun the dev split and `pts lab report`.

Out of scope: Terraform. Deployments are rendered from the engagement YAML.
Commit with `AI-Assisted: yes`; a person adds `Reviewed-by:`.
