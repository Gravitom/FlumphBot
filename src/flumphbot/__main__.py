"""Entry point for FlumphBot."""

import asyncio
import logging

from flumphbot.bot.client import FlumphBot
from flumphbot.config import load_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main entry point."""
    config = load_config()

    if not config.discord.bot_token:
        logger.error("DISCORD_BOT_TOKEN not set. Please configure your environment.")
        return

    bot = FlumphBot(config)
    asyncio.run(bot.start(config.discord.bot_token))


if __name__ == "__main__":
    main()
