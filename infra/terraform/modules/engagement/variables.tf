# Inputs are rendered from engagements/<id>.yaml by `pts render`; do not hand-write them.

variable "engagement_id" {
  type = string
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}[a-z0-9]$", var.engagement_id))
    error_message = "engagement_id must be a lowercase slug."
  }
}

variable "client" {
  type = string
}

variable "location" {
  type = string
}

variable "stage" {
  type = string
  validation {
    condition     = contains(["pov", "pilot", "scaled"], var.stage)
    error_message = "stage is pov, pilot or scaled."
  }
}

variable "address_space" {
  description = "This engagement's own /22, allocated by `pts ipam`"
  type        = string
}

variable "budget_eur" {
  type = number
}

variable "budget_alert_thresholds" {
  description = "Percentages; the owner is mailed at each"
  type        = list(number)
}

variable "budget_start_date" {
  description = "First day of the month the engagement starts, RFC 3339"
  type        = string
}

variable "budget_end_date" {
  description = "Expiry; the budget ends and the teardown job removes the resource group"
  type        = string
}

variable "owner_email" {
  type = string
}

variable "model_deployments" {
  description = "Azure OpenAI deployments; capacity is in units of 1,000 tokens per minute"
  type = list(object({
    name     = string
    model    = string
    capacity = number
  }))
}

variable "dedicated_key_vault" {
  type    = bool
  default = true
}

variable "fine_tuning_storage" {
  description = "Storage for fine-tuning data; created only when policy allowed fine-tuning"
  type        = bool
  default     = false
}

variable "replicas" {
  type    = number
  default = 1
}

variable "tags" {
  type = map(string)
}

variable "hub" {
  description = "Outputs of the hub module"
  type = object({
    resource_group_name        = string
    vnet_id                    = string
    vnet_name                  = string
    private_dns_zone_ids       = map(string)
    log_analytics_workspace_id = string
    aks_oidc_issuer_url        = string
  })
}

variable "hub_address_space" {
  description = "Hub network allowed to reach this engagement's private endpoints"
  type        = string
}

variable "tenant_id" {
  type = string
}
