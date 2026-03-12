"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DISCORD_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_CHANNEL_ID: str = os.getenv("GEMINI_CHANNEL_ID", "")
DISCORD_GUILD_ID: str | None = os.getenv("DISCORD_GUILD_ID")


def validate_config() -> None:
    """Validate that all required environment variables are set.

    Raises:
        SystemExit: If any required variable is missing.
    """
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN environment variable not set.")
        exit(1)

    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set.")
        exit(1)

    if not GEMINI_CHANNEL_ID:
        print("Error: GEMINI_CHANNEL_ID environment variable not set.")
        print("Please specify at least one channel ID where the bot should respond.")
        exit(1)
