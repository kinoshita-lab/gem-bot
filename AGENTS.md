# AGENTS.md

This file contains guidelines for AI coding agents.

## Important Rules

**Do not commit unless explicitly instructed. The user needs to verify the changes first.**

## Project Overview

A Discord bot that enables AI conversations using the Gemini API.

## Tech Stack

- Python 3.13+
- discord.py (Discord Bot framework)
- google-genai (Gemini API client)
- uv (Package manager)

## Project Structure

```
gem-bot/                # Repository root
├── bot.py              # Entry point, GeminiBot class, event handlers
├── cogs/
│   ├── __init__.py     # Cog package marker
│   └── commands.py     # Discord commands
├── history_manager.py  # Git-based history management
├── i18n.py             # Internationalization
├── locales/
│   ├── ja.json         # Japanese translations
│   └── en.json         # English translations
├── history/            # Conversation data (git-ignored)
│   ├── config.json     # Global settings (language, per-channel model/config)
│   └── {channel_id}/   # Per-channel Git repository
│       ├── .git/
│       ├── conversation.json
│       └── GEMINI.md   # System prompt
├── .env                # Environment variables (git-ignored)
└── .env.example        # Environment variables template
```

## Architecture

### GeminiBot Class (bot.py)

A custom class extending `commands.Bot`. It holds the following state:

- `gemini_client`: Gemini API client
- `default_model`: Default model name (used when no channel-specific setting exists)
- `pending_model_selections`: Interactive model selection state
- `conversation_history`: Per-channel conversation history
- `history_manager`: Git-based history and settings manager
- `i18n`: Internationalization manager

Model and generation config settings are managed per-channel in `history/config.json`.

### Cog (cogs/commands.py)

Commands are separated using discord.py's Cog feature. Add new commands to this file.

## Coding Guidelines

### Async Processing

- Always use the **async version** of Gemini API calls (`client.aio.models.xxx`)
- Using sync version blocks Discord's heartbeat and causes disconnection

```python
# Good
response = await self.gemini_client.aio.models.generate_content(...)

# Bad - blocks the event loop
response = self.gemini_client.models.generate_content(...)
```

### Adding Commands

Add new commands to the `Commands` class in `cogs/commands.py`:

```python
@commands.command(name="newcommand")
async def newcommand(self, ctx: commands.Context):
    """Command description"""
    # Access GeminiBot instance via self.bot
    pass
```

### Accessing Shared State

Access shared state from Cog via `self.bot`:

- `self.bot.get_model(channel_id)`: Get model for channel
- `self.bot.set_model(channel_id, model)`: Set model for channel
- `self.bot.default_model`: Default model
- `self.bot.gemini_client`
- `self.bot.conversation_history`
- `self.bot.pending_model_selections`
- `self.bot.history_manager`
- `self.bot.i18n`

### Translation

Use `self.t(key, **kwargs)` in Cog for translated messages:

```python
await ctx.send(self.t("some_message_key", param=value))
```

Note: Avoid using `key` as a kwarg name since `t()` uses it as the first parameter.

## Development Commands

```bash
# Install dependencies
uv sync

# Start the bot
uv run python bot.py

# Syntax check
python -m py_compile bot.py cogs/commands.py history_manager.py i18n.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Discord Bot token |
| `GEMINI_API_KEY` | Yes | Gemini API key |
| `GEMINI_CHANNEL_ID` | Yes | Auto-response channel IDs (comma-separated) |

## Notes

- `.env` file is git-ignored. Never commit API keys or tokens.
- Discord messages have a 2000 character limit. `send_response` handles automatic splitting.
- Conversation history is persisted via Git in `history/{channel_id}/`.
- Each channel has its own Git repository for branch/merge support.
- Global settings (language, per-channel model/config) are stored in `history/config.json`.
