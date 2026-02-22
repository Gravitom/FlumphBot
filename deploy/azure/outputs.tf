# FlumphBot Azure Outputs

output "resource_group_name" {
  description = "Name of the resource group"
  value       = azurerm_resource_group.main.name
}

output "container_registry_login_server" {
  description = "Container registry login server"
  value       = azurerm_container_registry.main.login_server
}

output "container_registry_admin_username" {
  description = "Container registry admin username"
  value       = azurerm_container_registry.main.admin_username
  sensitive   = true
}

output "container_app_url" {
  description = "URL of the container app (if ingress enabled)"
  value       = try(azurerm_container_app.bot.latest_revision_fqdn, "N/A - No ingress configured")
}

output "function_app_name" {
  description = "Name of the function app"
  value       = azurerm_linux_function_app.scheduler.name
}

output "key_vault_name" {
  description = "Name of the Key Vault"
  value       = azurerm_key_vault.main.name
}

output "storage_account_name" {
  description = "Name of the storage account"
  value       = azurerm_storage_account.main.name
}

output "log_analytics_workspace_id" {
  description = "ID of the Log Analytics workspace"
  value       = azurerm_log_analytics_workspace.main.id
}

# Instructions for deploying
output "deployment_instructions" {
  description = "Instructions for completing deployment"
  value       = <<-EOT
    Deployment completed. Next steps:

    1. Build and push the Docker image:
       docker build -t ${azurerm_container_registry.main.login_server}/flumphbot:latest .
       az acr login --name ${azurerm_container_registry.main.name}
       docker push ${azurerm_container_registry.main.login_server}/flumphbot:latest

    2. The Container App will automatically pull the new image.

    3. View logs:
       az containerapp logs show -n ca-${var.project_name}-${var.environment} -g ${azurerm_resource_group.main.name}

    4. Monitor in Azure Portal:
       https://portal.azure.com/#@/resource${azurerm_container_app.bot.id}/overview
  EOT
}
