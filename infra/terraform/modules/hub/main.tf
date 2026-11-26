# Shared hub: network, private DNS for the services spokes use, logs, and API Management as the
# AI gateway front door (Entra ID token validation, then the gateway service in AKS).

resource "azurerm_resource_group" "hub" {
  name     = "rg-${var.name}-hub"
  location = var.location
  tags     = var.tags
}

resource "azurerm_virtual_network" "hub" {
  name                = "vnet-${var.name}-hub"
  location            = var.location
  resource_group_name = azurerm_resource_group.hub.name
  address_space       = [var.address_space]
  tags                = var.tags
}

resource "azurerm_subnet" "apim" {
  name                 = "snet-apim"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [cidrsubnet(var.address_space, 2, 0)]
}

resource "azurerm_subnet" "endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = azurerm_resource_group.hub.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = [cidrsubnet(var.address_space, 2, 1)]
}

# API Management in internal VNet mode needs its management and load-balancer probes allowed.
resource "azurerm_network_security_group" "apim" {
  name                = "nsg-${var.name}-apim"
  location            = var.location
  resource_group_name = azurerm_resource_group.hub.name

  security_rule {
    name                       = "apim-management"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "3443"
    source_address_prefix      = "ApiManagement"
    destination_address_prefix = "VirtualNetwork"
  }

  security_rule {
    name                       = "load-balancer"
    priority                   = 110
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "6390"
    source_address_prefix      = "AzureLoadBalancer"
    destination_address_prefix = "VirtualNetwork"
  }

  security_rule {
    name                       = "https-from-vnet"
    priority                   = 120
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
  }

  tags = var.tags
}

resource "azurerm_subnet_network_security_group_association" "apim" {
  subnet_id                 = azurerm_subnet.apim.id
  network_security_group_id = azurerm_network_security_group.apim.id
}

resource "azurerm_network_security_group" "endpoints" {
  name                = "nsg-${var.name}-endpoints"
  location            = var.location
  resource_group_name = azurerm_resource_group.hub.name

  security_rule {
    name                       = "https-from-vnet"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "443"
    source_address_prefix      = "VirtualNetwork"
    destination_address_prefix = "VirtualNetwork"
  }

  tags = var.tags
}

resource "azurerm_subnet_network_security_group_association" "endpoints" {
  subnet_id                 = azurerm_subnet.endpoints.id
  network_security_group_id = azurerm_network_security_group.endpoints.id
}

resource "azurerm_log_analytics_workspace" "hub" {
  name                = "log-${var.name}"
  location            = var.location
  resource_group_name = azurerm_resource_group.hub.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
  tags                = var.tags
}

locals {
  private_zones = {
    openai = "privatelink.openai.azure.com"
    vault  = "privatelink.vaultcore.azure.net"
    blob   = "privatelink.blob.core.windows.net"
  }
}

resource "azurerm_private_dns_zone" "zone" {
  for_each            = local.private_zones
  name                = each.value
  resource_group_name = azurerm_resource_group.hub.name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "hub" {
  for_each              = local.private_zones
  name                  = "link-hub-${each.key}"
  resource_group_name   = azurerm_resource_group.hub.name
  private_dns_zone_name = azurerm_private_dns_zone.zone[each.key].name
  virtual_network_id    = azurerm_virtual_network.hub.id
  registration_enabled  = false
  tags                  = var.tags
}

resource "azurerm_api_management" "gateway" {
  #checkov:skip=CKV_AZURE_174:Internal VNet mode already keeps the gateway private; Azure refuses public_network_access_enabled = false at creation
  name                 = "apim-${var.name}"
  location             = var.location
  resource_group_name  = azurerm_resource_group.hub.name
  publisher_name       = "AI Lab platform"
  publisher_email      = var.apim_publisher_email
  sku_name             = var.apim_sku
  virtual_network_type = "Internal"
  min_api_version      = "2021-08-01"

  virtual_network_configuration {
    subnet_id = azurerm_subnet.apim.id
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_monitor_diagnostic_setting" "apim" {
  name                       = "to-log-analytics"
  target_resource_id         = azurerm_api_management.gateway.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.hub.id

  enabled_log {
    category = "GatewayLogs"
  }

  metric {
    category = "AllMetrics"
  }
}
