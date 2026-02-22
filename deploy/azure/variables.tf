# FlumphBot Azure Variables

variable "project_name" {
  description = "Project name used for resource naming (lowercase, no special characters)"
  type        = string
  default     = "flumphbot"

  validation {
    condition     = can(regex("^[a-z0-9]+$", var.project_name))
    error_message = "Project name must be lowercase alphanumeric characters only."
  }
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "location" {
  description = "Azure region for resources"
  type        = string
  default     = "eastus"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    project   = "FlumphBot"
    managedBy = "terraform"
  }
}

# Discord Configuration
variable "discord_bot_token" {
  description = "Discord bot token"
  type        = string
  sensitive   = true
}

variable "discord_guild_id" {
  description = "Discord server (guild) ID"
  type        = string
}

variable "discord_channel_id" {
  description = "Discord channel ID for polls and notifications"
  type        = string
}

# Google Calendar Configuration
variable "google_credentials_json" {
  description = "Google service account credentials JSON (base64 encoded)"
  type        = string
  sensitive   = true
}

variable "google_calendar_id" {
  description = "Google Calendar ID to use"
  type        = string
}

# Scheduling Configuration
variable "poll_day" {
  description = "Day of week to post polls"
  type        = string
  default     = "Monday"
}

variable "poll_time" {
  description = "Time to post polls (HH:MM)"
  type        = string
  default     = "09:00"
}

variable "dnd_session_keyword" {
  description = "Keyword to identify D&D session events"
  type        = string
  default     = "D&D"
}

variable "timezone" {
  description = "Timezone for scheduling"
  type        = string
  default     = "America/New_York"
}
