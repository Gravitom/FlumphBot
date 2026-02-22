# FlumphBot - D&D Session Scheduler

A Discord bot that automates D&D session scheduling by integrating with Google Calendar. It posts weekly polls, manages calendar hygiene (fixing busy/free status), and alerts on personal events.

## Features

- **Weekly Scheduling Polls**: Automatically posts polls for available dates
- **Calendar Hygiene**: Auto-fixes events incorrectly marked as "Busy"
- **Personal Event Detection**: Alerts users when personal events are added to the D&D calendar
- **Vacation Confirmation**: Weekly reminders to confirm vacation dates
- **Slash Commands**: Manual control via Discord commands

## Quick Start

### Prerequisites

- Python 3.10+
- Discord bot token ([Create one here](https://discord.com/developers/applications))
- Google Calendar API credentials ([Setup guide](https://developers.google.com/calendar/api/quickstart/python))

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/FlumphBot.git
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

| Command | Description |
|---------|-------------|
| `/dnd schedule` | Manually trigger a scheduling poll |
| `/dnd status` | Show upcoming sessions and vacations |
| `/dnd sync` | Force calendar sync and show issues |
| `/dnd config` | View bot configuration |
| `/vacation add` | Add vacation dates to the calendar |

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

1. **Monday 8 AM**: Bot sends vacation confirmation DMs
2. **Monday 9 AM**: Bot fetches calendar events for the next 2 weeks
3. Bot identifies dates where everyone is available
4. Poll posted in configured channel with available dates
5. After 48 hours (or when all vote), poll closes
6. Winning date gets a D&D session event (marked as **Busy**)

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
│   ├── bot/           # Discord bot client and commands
│   ├── calendar/      # Google Calendar integration
│   ├── scheduler/     # Scheduled tasks (APScheduler)
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
