output "resource_group_name" {
  value = azurerm_resource_group.eng.name
}

output "openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "service_identity_client_id" {
  value = azurerm_user_assigned_identity.service.client_id
}

output "namespace" {
  value = local.ns
}
