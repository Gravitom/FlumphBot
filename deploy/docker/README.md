# Self-Hosted Docker Deployment

This directory contains Docker configuration for self-hosted FlumphBot deployments.

## Quick Start

1. Copy the environment template:
   ```bash
   cp ../../.env.example .env
   ```

2. Edit `.env` with your configuration:
   - `DISCORD_BOT_TOKEN`: Your Discord bot token
   - `DISCORD_GUILD_ID`: Your Discord server ID
   - `DISCORD_CHANNEL_ID`: Channel for polls and notifications
   - `GOOGLE_CREDENTIALS_JSON`: Base64-encoded Google service account JSON
   - `GOOGLE_CALENDAR_ID`: Your shared calendar ID

3. Build and run:
   ```bash
   docker-compose up -d
   ```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | - | Discord bot token |
| `DISCORD_GUILD_ID` | Yes | - | Discord server ID |
| `DISCORD_CHANNEL_ID` | Yes | - | Notification channel ID |
| `GOOGLE_CREDENTIALS_JSON` | Yes | - | Service account credentials (base64) |
| `GOOGLE_CALENDAR_ID` | Yes | - | Shared calendar ID |
| `POLL_DAY` | No | Monday | Day to post polls |
| `POLL_TIME` | No | 09:00 | Time to post polls |
| `POLL_DURATION_HOURS` | No | 48 | How long polls stay open |
| `DND_SESSION_KEYWORD` | No | D&D | Keyword for session detection |
| `TIMEZONE` | No | America/New_York | Timezone for scheduling |

### Google Credentials

To create base64-encoded credentials:

```bash
cat your-service-account.json | base64 -w 0
```

On macOS:
```bash
cat your-service-account.json | base64
```

### Data Persistence

The SQLite database is stored in a Docker volume (`flumphbot_data`).
To backup your data:

```bash
docker run --rm -v flumphbot_data:/data -v $(pwd):/backup alpine \
    cp /data/flumphbot.db /backup/
```

## Commands

```bash
# View logs
docker-compose logs -f

# Restart
docker-compose restart

# Stop
docker-compose down

# Update to latest
docker-compose pull
docker-compose up -d
```

## Updating

1. Pull the latest code
2. Rebuild and restart:
   ```bash
   docker-compose build
   docker-compose up -d
   ```
