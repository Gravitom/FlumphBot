# Azure Deployment for FlumphBot

This directory contains Terraform configuration to deploy FlumphBot to Azure.

## Architecture

- **Container App**: Runs the Discord bot
- **Azure Functions**: Optional scheduled tasks (alternative to APScheduler)
- **Table Storage**: Stores user mappings and poll history
- **Key Vault**: Securely stores Discord token and Google credentials
- **Container Registry**: Hosts the bot Docker image
- **Log Analytics**: Centralized logging

## Prerequisites

1. [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
2. [Terraform](https://www.terraform.io/downloads.html) >= 1.0
3. Azure subscription with appropriate permissions

## Quick Start

### 1. Login to Azure

```bash
az login
az account set --subscription "Your Subscription Name"
```

### 2. Create terraform.tfvars

```hcl
# Required
discord_bot_token       = "your-discord-bot-token"
discord_guild_id        = "your-discord-server-id"
discord_channel_id      = "your-channel-id"
google_credentials_json = "base64-encoded-service-account-json"
google_calendar_id      = "your-calendar@group.calendar.google.com"

# Optional
project_name        = "flumphbot"
environment         = "prod"
location            = "eastus"
poll_day            = "Monday"
poll_time           = "09:00"
dnd_session_keyword = "D&D"
timezone            = "America/New_York"
```

### 3. Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 4. Build and Push Docker Image

After Terraform completes:

```bash
# Get ACR name from output
ACR_NAME=$(terraform output -raw container_registry_login_server)

# Build and push
cd ../..
docker build -t $ACR_NAME/flumphbot:latest .
az acr login --name flumphbotprodacr
docker push $ACR_NAME/flumphbot:latest
```

## Configuration

### Required Variables

| Variable | Description |
|----------|-------------|
| `discord_bot_token` | Your Discord bot token |
| `discord_guild_id` | Discord server ID |
| `discord_channel_id` | Channel for polls/notifications |
| `google_credentials_json` | Base64-encoded service account JSON |
| `google_calendar_id` | Google Calendar ID |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `project_name` | flumphbot | Name for resources |
| `environment` | prod | Environment name |
| `location` | eastus | Azure region |
| `poll_day` | Monday | Day to post polls |
| `poll_time` | 09:00 | Time to post polls |
| `dnd_session_keyword` | D&D | Session detection keyword |
| `timezone` | America/New_York | Scheduling timezone |

## Cost Estimation

Approximate monthly costs (East US, as of 2024):

| Resource | SKU | Est. Cost |
|----------|-----|-----------|
| Container App | 0.25 vCPU, 0.5 GB | ~$5-10 |
| Container Registry | Basic | ~$5 |
| Storage Account | LRS | ~$1-2 |
| Key Vault | Standard | ~$0.03/10k ops |
| Log Analytics | Per GB | ~$2-3 |
| **Total** | | **~$15-25/month** |

## Monitoring

### View Logs

```bash
# Container App logs
az containerapp logs show \
  -n ca-flumphbot-prod \
  -g rg-flumphbot-prod \
  --follow

# Function App logs
func azure functionapp logstream func-flumphbot-prod
```

### Azure Portal

Navigate to the Container App in Azure Portal to view:
- Live logs
- Metrics (CPU, memory)
- Revision history

## Updating

1. Make code changes
2. Build new image:
   ```bash
   docker build -t $ACR_NAME/flumphbot:v1.1.0 .
   docker push $ACR_NAME/flumphbot:v1.1.0
   ```
3. Update Container App (it auto-pulls `latest`, or update tag in Terraform)

## Cleanup

```bash
terraform destroy
```

This removes all Azure resources. Data in Table Storage will be lost.

## Troubleshooting

### Container App won't start

1. Check logs: `az containerapp logs show ...`
2. Verify secrets are set correctly
3. Ensure image was pushed to ACR

### Bot not connecting to Discord

1. Verify `DISCORD_BOT_TOKEN` is correct
2. Check bot has proper intents enabled in Discord Developer Portal
3. Ensure bot is invited to the server with correct permissions

### Calendar not syncing

1. Verify `GOOGLE_CREDENTIALS_JSON` is valid base64
2. Check service account has access to the calendar
3. Verify calendar ID is correct
