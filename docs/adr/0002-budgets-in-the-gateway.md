# ADR 0002: enforce budgets in the AI gateway, not only in Azure Cost Management

Status: accepted

## Context

Azure budgets alert; they do not stop spending, and cost data arrives hours late. An agent stuck in a loop or a
leaked token can spend a PoV's whole budget overnight.

## Decision

The gateway prices every request before sending it (input estimate plus `max_tokens`), tells the owner once at
80%, and refuses requests at 100%. The Azure budget on the resource group stays as a second line and a
forecast alert.

## Consequences

Legitimate work can be stopped until the owner raises the budget: the lab counts these waiting days and reports
them as the platform's cost. Estimates are pessimistic, so a request that might overrun is refused while a
smaller one still fits.
