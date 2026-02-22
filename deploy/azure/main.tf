# FlumphBot Azure Infrastructure
# This Terraform configuration deploys the FlumphBot Discord bot to Azure

terraform {
  required_version = ">= 1.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy = true
    }
  }
}

# Data source for current Azure client
data "azurerm_client_config" "current" {}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.project_name}-${var.environment}"
  location = var.location

  tags = var.tags
}

# Log Analytics Workspace
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 30

  tags = var.tags
}

# Storage Account for Table Storage and Functions
resource "azurerm_storage_account" "main" {
  name                     = "${var.project_name}${var.environment}sa"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"

  tags = var.tags
}

# Key Vault for secrets
resource "azurerm_key_vault" "main" {
  name                       = "kv-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  tenant_id                  = data.azurerm_client_config.current.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 7
  purge_protection_enabled   = false

  access_policy {
    tenant_id = data.azurerm_client_config.current.tenant_id
    object_id = data.azurerm_client_config.current.object_id

    secret_permissions = [
      "Get", "List", "Set", "Delete", "Purge"
    ]
  }

  tags = var.tags
}

# Store Discord bot token in Key Vault
resource "azurerm_key_vault_secret" "discord_token" {
  name         = "discord-bot-token"
  value        = var.discord_bot_token
  key_vault_id = azurerm_key_vault.main.id
}

# Store Google credentials in Key Vault
resource "azurerm_key_vault_secret" "google_credentials" {
  name         = "google-credentials-json"
  value        = var.google_credentials_json
  key_vault_id = azurerm_key_vault.main.id
}

# Container Registry
resource "azurerm_container_registry" "main" {
  name                = "${var.project_name}${var.environment}acr"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true

  tags = var.tags
}

# Container App Environment
resource "azurerm_container_app_environment" "main" {
  name                       = "cae-${var.project_name}-${var.environment}"
  location                   = azurerm_resource_group.main.location
  resource_group_name        = azurerm_resource_group.main.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  tags = var.tags
}

# User-assigned Managed Identity for Container App
resource "azurerm_user_assigned_identity" "container_app" {
  name                = "id-${var.project_name}-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  tags = var.tags
}

# Key Vault access policy for Container App
resource "azurerm_key_vault_access_policy" "container_app" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_user_assigned_identity.container_app.principal_id

  secret_permissions = ["Get", "List"]
}

# Container App for the Discord Bot
resource "azurerm_container_app" "bot" {
  name                         = "ca-${var.project_name}-${var.environment}"
  container_app_environment_id = azurerm_container_app_environment.main.id
  resource_group_name          = azurerm_resource_group.main.name
  revision_mode                = "Single"

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_app.id]
  }

  registry {
    server               = azurerm_container_registry.main.login_server
    username             = azurerm_container_registry.main.admin_username
    password_secret_name = "acr-password"
  }

  secret {
    name  = "acr-password"
    value = azurerm_container_registry.main.admin_password
  }

  secret {
    name  = "discord-token"
    value = var.discord_bot_token
  }

  secret {
    name  = "google-credentials"
    value = var.google_credentials_json
  }

  secret {
    name  = "storage-connection"
    value = azurerm_storage_account.main.primary_connection_string
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "flumphbot"
      image  = "${azurerm_container_registry.main.login_server}/flumphbot:latest"
      cpu    = 0.25
      memory = "0.5Gi"

      env {
        name        = "DISCORD_BOT_TOKEN"
        secret_name = "discord-token"
      }

      env {
        name  = "DISCORD_GUILD_ID"
        value = var.discord_guild_id
      }

      env {
        name  = "DISCORD_CHANNEL_ID"
        value = var.discord_channel_id
      }

      env {
        name        = "GOOGLE_CREDENTIALS_JSON"
        secret_name = "google-credentials"
      }

      env {
        name  = "GOOGLE_CALENDAR_ID"
        value = var.google_calendar_id
      }

      env {
        name        = "AZURE_STORAGE_CONNECTION_STRING"
        secret_name = "storage-connection"
      }

      env {
        name  = "STORAGE_BACKEND"
        value = "azure"
      }

      env {
        name  = "POLL_DAY"
        value = var.poll_day
      }

      env {
        name  = "POLL_TIME"
        value = var.poll_time
      }

      env {
        name  = "DND_SESSION_KEYWORD"
        value = var.dnd_session_keyword
      }

      env {
        name  = "TIMEZONE"
        value = var.timezone
      }
    }
  }

  tags = var.tags
}

# App Service Plan for Azure Functions (Consumption)
resource "azurerm_service_plan" "functions" {
  name                = "asp-${var.project_name}-func-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "Y1"

  tags = var.tags
}

# Azure Function App (for scheduled tasks as alternative to APScheduler)
resource "azurerm_linux_function_app" "scheduler" {
  name                       = "func-${var.project_name}-${var.environment}"
  resource_group_name        = azurerm_resource_group.main.name
  location                   = azurerm_resource_group.main.location
  storage_account_name       = azurerm_storage_account.main.name
  storage_account_access_key = azurerm_storage_account.main.primary_access_key
  service_plan_id            = azurerm_service_plan.functions.id

  site_config {
    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    "FUNCTIONS_WORKER_RUNTIME"       = "python"
    "AzureWebJobsFeatureFlags"       = "EnableWorkerIndexing"
    "DISCORD_BOT_TOKEN"              = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=discord-bot-token)"
    "DISCORD_GUILD_ID"               = var.discord_guild_id
    "DISCORD_CHANNEL_ID"             = var.discord_channel_id
    "GOOGLE_CREDENTIALS_JSON"        = "@Microsoft.KeyVault(VaultName=${azurerm_key_vault.main.name};SecretName=google-credentials-json)"
    "GOOGLE_CALENDAR_ID"             = var.google_calendar_id
    "AZURE_STORAGE_CONNECTION_STRING" = azurerm_storage_account.main.primary_connection_string
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.container_app.id]
  }

  tags = var.tags
}
