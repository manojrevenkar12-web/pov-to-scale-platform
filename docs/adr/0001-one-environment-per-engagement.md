# ADR 0001: one isolated environment per engagement

Status: accepted

## Context

The lab runs many client PoVs at once, for clients who may compete with each other. A shared Azure OpenAI
resource and shared indexes are quick to start but mix client data in prompts, caches and logs, and make
cost attribution guesswork. Hand-built subscriptions per project are isolated but take days through IT,
drift, and are forgotten after the PoV.

## Decision

Every engagement gets its own resource group, /22 network range, Azure OpenAI account (Entra ID only, private
endpoint), Key Vault, workload identity, budget and expiry, rendered from one YAML file and applied by
Terraform after a reviewed pull request. Shared parts are only the hub (network, private DNS, logs, API
Management) and the AKS cluster, where namespaces are isolated by NetworkPolicy and the Argo CD project.

## Consequences

- More Azure resources and quota requests per engagement; Azure OpenAI capacity is planned per account.
- Teardown is automatic at expiry; a PoV that wins is promoted, not rebuilt.
