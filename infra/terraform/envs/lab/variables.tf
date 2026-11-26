variable "location" {
  type    = string
  default = "germanywestcentral"
}

variable "hub_address_space" {
  type    = string
  default = "10.64.0.0/22"
}

variable "apim_publisher_email" {
  type    = string
  default = "ai-lab-platform@example.com"
}

variable "aks_oidc_issuer_url" {
  type    = string
  default = "https://germanywestcentral.oic.prod-aks.azure.com/00000000-0000-0000-0000-000000000000/00000000-0000-0000-0000-000000000000/"
}

variable "engagements" {
  description = "Rendered by `pts render-all` into engagements.auto.tfvars.json"
  type = map(object({
    engagement_id           = string
    client                  = string
    location                = string
    stage                   = string
    address_space           = string
    budget_eur              = number
    budget_alert_thresholds = list(number)
    budget_start_date       = string
    budget_end_date         = string
    owner_email             = string
    model_deployments = list(object({
      name     = string
      model    = string
      capacity = number
    }))
    dedicated_key_vault = bool
    fine_tuning_storage = bool
    replicas            = number
    tags                = map(string)
  }))
}
