# FlumphBot - D&D Session Scheduler

A Discord bot that automates D&D session scheduling by integrating with Google Calendar. It posts weekly polls, manages calendar hygiene (fixing busy/free status), and alerts on personal events.

## Features

- **Weekly Scheduling Polls**: Automatically posts polls for available dates
- **Calendar Hygiene**: Auto-fixes events incorrectly marked as "Busy"
- **Personal Event Detection**: Alerts users when personal events are added to the D&D calendar
- **Vacation Confirmation**: Weekly reminders to confirm vacation dates
- **Session Reminders**: DM players before scheduled sessions
- **Poll Warnings**: Remind channel if poll has low votes before closing
- **Interactive Settings**: Configure all settings via Discord UI (buttons, modals, dropdowns)
- **@everyone Toggle**: Optional tagging for poll posts
- **Slash Commands**: Full control via Discord commands

## Quick Start

### Prerequisites

- Python 3.10+
- Discord bot token (see setup below)
- Google Calendar API credentials ([Setup guide](https://developers.google.com/calendar/api/quickstart/python))

### Discord Bot Setup

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click **New Application** → name it "FlumphBot"
3. Go to **Bot** tab:
   - Click **Reset Token** → copy and save it
   - Enable **Server Members Intent**
   - Enable **Message Content Intent**
4. Go to **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot Permissions: `Send Messages`, `Create Polls`, `Embed Links`, `Read Message History`, `Mention Everyone`, `Use External Emojis`
5. Copy the generated URL and open it to invite the bot to your server
6. Get your IDs (enable Developer Mode in Discord settings first):
   - Right-click your server → **Copy Server ID** (this is `DISCORD_GUILD_ID`)
   - Right-click your scheduling channel → **Copy Channel ID** (this is `DISCORD_CHANNEL_ID`)

### Installation

```bash
# Clone the repository
git clone https://github.com/Gravitom/FlumphBot.git
cd FlumphBot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e .
```

### Configuration

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your configuration:
   ```env
   DISCORD_BOT_TOKEN=your_token
   DISCORD_GUILD_ID=your_server_id
   DISCORD_CHANNEL_ID=your_channel_id
   GOOGLE_CREDENTIALS_JSON=base64_encoded_credentials
   GOOGLE_CALENDAR_ID=your_calendar@group.calendar.google.com
   ```

3. Run the bot:
   ```bash
   python -m flumphbot
   ```

## Slash Commands

### Core Commands

| Command | Description |
|---------|-------------|
| `/dnd pollnow <start_day> <days_ahead>` | Create a scheduling poll with custom date range |
| `/dnd status` | Show upcoming sessions/vacations with quick actions |
| `/dnd sync` | Force calendar sync and show issues |
| `/dnd config` | View environment config and @everyone status |
| `/vacation add` | Add vacation dates to the calendar |
| `/keywords` | Manage detection keywords (list/add/remove) |

### Settings Commands

| Command | Description |
|---------|-------------|
| `/dnd showsettings` | View current bot settings |
| `/dnd allsettings` | Interactive settings panel with buttons |
| `/dnd schedule` | Configure weekly auto-poll (day, hour, duration, timezone dropdowns) |
| `/dnd everyone <on\|off>` | Toggle @everyone tagging in poll posts |
| `/dnd reminder <hours>` | Configure session reminder DMs (0 = disabled) |
| `/dnd pollwarn <hours> <min_votes>` | Configure poll close warnings (0 = disabled) |

### Timezone Options

The `/dnd schedule` command provides these timezone choices:

| Timezone | Description |
|----------|-------------|
| `US/Eastern` | New York |
| `US/Central` | Chicago |
| `US/Mountain` | Denver |
| `US/Pacific` | Los Angeles |
| `America/Phoenix` | Arizona (no DST) |
| `UTC` | Coordinated Universal Time |
| `Europe/London` | UK |
| `Europe/Paris` | France |
| `Europe/Berlin` | Germany |
| `Asia/Tokyo` | Japan |
| `Australia/Sydney` | Australia |

### Settings Storage

Settings configured via commands persist in the database and override environment defaults:

| Setting | Default | Description |
|---------|---------|-------------|
| `schedule_day` | Monday | Day of week for auto-poll |
| `schedule_hour` | 9 | Hour (0-23) for auto-poll |
| `schedule_timezone` | America/New_York | Timezone for scheduling |
| `poll_duration_days` | 2 | Days poll stays active |
| `tag_everyone` | false | Tag @everyone in poll posts |
| `reminder_hours` | 0 | Hours before session to DM reminder |
| `pollwarn_hours` | 0 | Hours before close to warn |
| `pollwarn_min_votes` | 3 | Min votes before warning triggers |

## Deployment

### Docker (Self-Hosted)

```bash
cd deploy/docker
cp ../../.env.example .env
# Edit .env with your configuration
docker-compose up -d
```

### Azure

See [deploy/azure/README.md](deploy/azure/README.md) for Terraform deployment instructions.

## How It Works

### Weekly Poll Flow

1. **1 hour before poll**: Bot sends vacation confirmation DMs
2. **Poll time** (configurable): Bot fetches calendar events for the next 2 weeks
3. Bot identifies dates where everyone is available
4. Poll posted in configured channel (optionally with @everyone)
5. **Poll warning**: If enabled, warns when votes are low before closing
6. After configured duration, poll closes
7. Winning date gets a D&D session event (marked as **Busy**)
8. **Session reminder**: If enabled, DMs players before the session

### Calendar Hygiene Rules

- **D&D sessions**: Always marked as **Busy**
- **Everything else**: Auto-fixed to **Free** (vacations, away, etc.)

### Personal Event Detection

Events containing these keywords trigger a DM alert:
- doctor, dentist, appointment, interview, therapy
- medical, checkup, prescription, court, lawyer
- accountant, meeting, call with, date, wedding

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Code Quality

```bash
ruff check src/ tests/
mypy src/flumphbot
```

### Project Structure

```
FlumphBot/
├── src/flumphbot/
│   ├── bot/           # Discord bot client, commands, and UI views
│   │   ├── client.py  # Main bot client
│   │   ├── commands.py # Slash command definitions
│   │   ├── polls.py   # Poll creation and management
│   │   └── views.py   # Discord UI components (modals, buttons, selects)
│   ├── calendar/      # Google Calendar integration
│   ├── scheduler/     # Scheduled tasks (APScheduler)
│   │   ├── runner.py  # Job scheduler with dynamic reload
│   │   └── tasks.py   # Task definitions (polls, reminders, warnings)
│   └── storage/       # Storage backends (SQLite, Azure Tables)
├── tests/             # Unit tests
├── deploy/
│   ├── azure/         # Azure Terraform deployment
│   └── docker/        # Docker Compose deployment
└── .github/workflows/ # CI/CD
```

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

### Adding New Deployment Targets

To add support for AWS, GCP, or other providers:

1. Create `deploy/<provider>/` directory
2. Add deployment configuration (Terraform, CloudFormation, etc.)
3. Add a README with setup instructions
4. Submit a PR

## License

MIT License - see [LICENSE](LICENSE) for details.

## Why "Flumph"?

[Flumphs](https://forgottenrealms.fandom.com/wiki/Flumph) are friendly, lawful good aberrations in D&D that communicate through telepathy. They're helpful, non-threatening, and often overlooked - much like a good scheduling bot should be!
