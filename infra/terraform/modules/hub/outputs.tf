output "resource_group_name" {
  value = azurerm_resource_group.hub.name
}

output "vnet_id" {
  value = azurerm_virtual_network.hub.id
}

output "vnet_name" {
  value = azurerm_virtual_network.hub.name
}

output "private_dns_zone_ids" {
  value = { for k, z in azurerm_private_dns_zone.zone : k => z.id }
}

output "private_dns_zone_names" {
  value = { for k, z in azurerm_private_dns_zone.zone : k => z.name }
}

output "log_analytics_workspace_id" {
  value = azurerm_log_analytics_workspace.hub.id
}

output "aks_oidc_issuer_url" {
  value = var.aks_oidc_issuer_url
}
