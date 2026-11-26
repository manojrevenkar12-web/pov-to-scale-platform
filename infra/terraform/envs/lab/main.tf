data "azurerm_client_config" "current" {}

locals {
  platform_tags = {
    engagement     = "platform"
    client         = "roland-berger-internal"
    owner          = var.apim_publisher_email
    stage          = "scaled"
    classification = "internal"
    expires        = "never"
    cost-center    = "RB-AILAB-001"
  }
}

module "hub" {
  source               = "../../modules/hub"
  name                 = "ailab"
  location             = var.location
  address_space        = var.hub_address_space
  apim_publisher_email = var.apim_publisher_email
  aks_oidc_issuer_url  = var.aks_oidc_issuer_url
  tags                 = local.platform_tags
}

module "engagement" {
  source   = "../../modules/engagement"
  for_each = var.engagements

  engagement_id           = each.value.engagement_id
  resource_suffix         = each.value.resource_suffix
  client                  = each.value.client
  location                = each.value.location
  stage                   = each.value.stage
  address_space           = each.value.address_space
  budget_eur              = each.value.budget_eur
  budget_alert_thresholds = each.value.budget_alert_thresholds
  budget_start_date       = each.value.budget_start_date
  budget_end_date         = each.value.budget_end_date
  owner_email             = each.value.owner_email
  model_deployments       = each.value.model_deployments
  dedicated_key_vault     = each.value.dedicated_key_vault
  fine_tuning_storage     = each.value.fine_tuning_storage
  replicas                = each.value.replicas
  tags                    = each.value.tags
  tenant_id               = data.azurerm_client_config.current.tenant_id
  hub_address_space       = var.hub_address_space

  hub = {
    resource_group_name        = module.hub.resource_group_name
    vnet_id                    = module.hub.vnet_id
    vnet_name                  = module.hub.vnet_name
    private_dns_zone_ids       = module.hub.private_dns_zone_ids
    log_analytics_workspace_id = module.hub.log_analytics_workspace_id
    aks_oidc_issuer_url        = module.hub.aks_oidc_issuer_url
  }
}

output "engagements" {
  value = { for k, m in module.engagement : k => {
    resource_group = m.resource_group_name
    endpoint       = m.openai_endpoint
    namespace      = m.namespace
  } }
}
