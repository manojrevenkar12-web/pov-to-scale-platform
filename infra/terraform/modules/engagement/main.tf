# One isolated environment per client engagement: its own resource group, network, Azure OpenAI
# account, Key Vault, identity and budget. Nothing in here is shared with another client.

locals {
  short = substr(replace(var.engagement_id, "-", ""), 0, 18)
  ns    = "eng-${var.engagement_id}"
}

resource "azurerm_resource_group" "eng" {
  name     = "rg-eng-${var.engagement_id}"
  location = var.location
  tags     = var.tags
}

resource "azurerm_virtual_network" "spoke" {
  name                = "vnet-eng-${var.engagement_id}"
  location            = var.location
  resource_group_name = azurerm_resource_group.eng.name
  address_space       = [var.address_space]
  tags                = var.tags
}

resource "azurerm_subnet" "endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = azurerm_resource_group.eng.name
  virtual_network_name = azurerm_virtual_network.spoke.name
  address_prefixes     = [cidrsubnet(var.address_space, 2, 0)]
}

# Only the hub (gateway, AKS) may reach this engagement's private endpoints; other spokes may not.
resource "azurerm_network_security_group" "endpoints" {
  name                = "nsg-eng-${var.engagement_id}"
  location            = var.location
  resource_group_name = azurerm_resource_group.eng.name

  security_rule {
    name                       = "allow-hub-https"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = var.hub_address_space
    destination_address_prefix = "*"
  }

  security_rule {
    name                       = "deny-all-inbound"
    priority                   = 4000
    direction                  = "Inbound"
    access                     = "Deny"
    protocol                   = "*"
    source_port_range          = "*"
    destination_port_range     = "*"
    source_address_prefix      = "*"
    destination_address_prefix = "*"
  }

  tags = var.tags
}

resource "azurerm_subnet_network_security_group_association" "endpoints" {
  subnet_id                 = azurerm_subnet.endpoints.id
  network_security_group_id = azurerm_network_security_group.endpoints.id
}

resource "azurerm_virtual_network_peering" "to_hub" {
  name                      = "peer-to-hub"
  resource_group_name       = azurerm_resource_group.eng.name
  virtual_network_name      = azurerm_virtual_network.spoke.name
  remote_virtual_network_id = var.hub.vnet_id
  allow_forwarded_traffic   = false
}

resource "azurerm_virtual_network_peering" "from_hub" {
  name                      = "peer-${var.engagement_id}"
  resource_group_name       = var.hub.resource_group_name
  virtual_network_name      = var.hub.vnet_name
  remote_virtual_network_id = azurerm_virtual_network.spoke.id
  allow_forwarded_traffic   = false
}

resource "azurerm_cognitive_account" "openai" {
  #checkov:skip=CKV2_AZURE_22:Microsoft-managed keys for PoVs; customer-managed keys are a scaled-stage option (docs/adr/0003)
  #checkov:skip=CKV_AZURE_247:outbound is restricted with an empty allow-list, which is stricter than the check expects
  name                          = "aoai-${local.short}"
  location                      = var.location
  resource_group_name           = azurerm_resource_group.eng.name
  kind                          = "OpenAI"
  sku_name                      = "S0"
  custom_subdomain_name         = "aoai-${local.short}"
  public_network_access_enabled = false
  local_auth_enabled            = false # Entra ID only, no keys to leak or reuse across clients
  # data loss prevention: the account may not call out to anything (no data sources, no web)
  outbound_network_access_restricted = true
  fqdns                              = []

  network_acls {
    default_action = "Deny"
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_cognitive_deployment" "model" {
  for_each             = { for d in var.model_deployments : d.name => d }
  name                 = each.value.name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format = "OpenAI"
    name   = each.value.model
  }

  sku {
    name     = "Standard"
    capacity = each.value.capacity
  }
}

resource "azurerm_private_endpoint" "openai" {
  name                = "pe-aoai-${var.engagement_id}"
  location            = var.location
  resource_group_name = azurerm_resource_group.eng.name
  subnet_id           = azurerm_subnet.endpoints.id

  private_service_connection {
    name                           = "aoai"
    private_connection_resource_id = azurerm_cognitive_account.openai.id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "openai"
    private_dns_zone_ids = [var.hub.private_dns_zone_ids["openai"]]
  }

  tags = var.tags
}

resource "azurerm_key_vault" "eng" {
  count                         = var.dedicated_key_vault ? 1 : 0
  name                          = "kv-${local.short}"
  location                      = var.location
  resource_group_name           = azurerm_resource_group.eng.name
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  enable_rbac_authorization     = true
  purge_protection_enabled      = true
  soft_delete_retention_days    = 30
  public_network_access_enabled = false

  network_acls {
    bypass         = "None"
    default_action = "Deny"
  }

  tags = var.tags
}

resource "azurerm_private_endpoint" "vault" {
  count               = var.dedicated_key_vault ? 1 : 0
  name                = "pe-kv-${var.engagement_id}"
  location            = var.location
  resource_group_name = azurerm_resource_group.eng.name
  subnet_id           = azurerm_subnet.endpoints.id

  private_service_connection {
    name                           = "vault"
    private_connection_resource_id = azurerm_key_vault.eng[0].id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "vault"
    private_dns_zone_ids = [var.hub.private_dns_zone_ids["vault"]]
  }

  tags = var.tags
}

resource "azurerm_storage_account" "finetune" {
  #checkov:skip=CKV_AZURE_206:ZRS on purpose; geo-replication would copy client data to a second region
  #checkov:skip=CKV_AZURE_33:queue service is not used; blob only
  #checkov:skip=CKV2_AZURE_1:Microsoft-managed keys for PoVs; customer-managed keys are a scaled-stage option
  count                           = var.fine_tuning_storage ? 1 : 0
  name                            = "stft${local.short}"
  location                        = var.location
  resource_group_name             = azurerm_resource_group.eng.name
  account_tier                    = "Standard"
  account_replication_type        = "ZRS"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  allow_nested_items_to_be_public = false
  shared_access_key_enabled       = false

  blob_properties {
    delete_retention_policy {
      days = 14
    }
    container_delete_retention_policy {
      days = 14
    }
  }

  tags = var.tags
}

resource "azurerm_private_endpoint" "finetune" {
  count               = var.fine_tuning_storage ? 1 : 0
  name                = "pe-st-${var.engagement_id}"
  location            = var.location
  resource_group_name = azurerm_resource_group.eng.name
  subnet_id           = azurerm_subnet.endpoints.id

  private_service_connection {
    name                           = "blob"
    private_connection_resource_id = azurerm_storage_account.finetune[0].id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "blob"
    private_dns_zone_ids = [var.hub.private_dns_zone_ids["blob"]]
  }

  tags = var.tags
}

# The engagement's service runs in its own AKS namespace and gets a token for this identity only;
# the identity may call this engagement's Azure OpenAI account and nothing else.
resource "azurerm_user_assigned_identity" "service" {
  name                = "id-${var.engagement_id}"
  location            = var.location
  resource_group_name = azurerm_resource_group.eng.name
  tags                = var.tags
}

resource "azurerm_federated_identity_credential" "aks" {
  name                = "aks-${local.ns}"
  resource_group_name = azurerm_resource_group.eng.name
  parent_id           = azurerm_user_assigned_identity.service.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = var.hub.aks_oidc_issuer_url
  subject             = "system:serviceaccount:${local.ns}:agent-service"
}

resource "azurerm_role_assignment" "openai_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.service.principal_id
}

resource "azurerm_role_assignment" "secrets_user" {
  count                = var.dedicated_key_vault ? 1 : 0
  scope                = azurerm_key_vault.eng[0].id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.service.principal_id
}

resource "azurerm_role_assignment" "finetune_data" {
  count                = var.fine_tuning_storage ? 1 : 0
  scope                = azurerm_storage_account.finetune[0].id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.service.principal_id
}

resource "azurerm_consumption_budget_resource_group" "eng" {
  name              = "budget-${var.engagement_id}"
  resource_group_id = azurerm_resource_group.eng.id
  amount            = var.budget_eur
  time_grain        = "Annually"

  time_period {
    start_date = var.budget_start_date
    end_date   = var.budget_end_date
  }

  dynamic "notification" {
    for_each = var.budget_alert_thresholds
    content {
      enabled        = true
      threshold      = notification.value
      operator       = "GreaterThanOrEqualTo"
      threshold_type = "Actual"
      contact_emails = [var.owner_email]
    }
  }

  notification {
    enabled        = true
    threshold      = 100
    operator       = "GreaterThanOrEqualTo"
    threshold_type = "Forecasted"
    contact_emails = [var.owner_email]
  }
}

resource "azurerm_monitor_diagnostic_setting" "openai" {
  name                       = "to-log-analytics"
  target_resource_id         = azurerm_cognitive_account.openai.id
  log_analytics_workspace_id = var.hub.log_analytics_workspace_id

  enabled_log {
    category = "Audit"
  }

  metric {
    category = "AllMetrics"
  }
}
