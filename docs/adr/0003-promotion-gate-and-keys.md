# ADR 0003: promotion gate on evidence; customer-managed keys at scale

Status: accepted

## Decision

- A release moves to pilot or scaled only if its observation window in Prometheus passes
  `config/promotion.yaml`: traffic, p95 latency, error rate, offline eval score, no eval regression against
  the running release, cost per 1,000 requests and (for scaled) remaining error budget. Missing data fails
  closed. The gate runs as an Argo CD PreSync hook, in CI and in the lab.
- PoVs use Microsoft-managed encryption keys. Customer-managed keys in the engagement's Key Vault are switched
  on for scaled client-restricted work (Checkov CKV2_AZURE_22 / CKV2_AZURE_1 skips say so).

## Consequences

About one in three promotions is sent back in the lab; each costs roughly a week. In exchange regressed
releases almost never reach production.
