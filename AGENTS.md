# AGENTS.md

This file contains guidelines for AI coding agents.

## Important Rules

**Do not commit unless explicitly instructed. The user needs to verify the changes first.**

## Project Overview

A Discord bot that enables AI conversations using the Gemini API with Google Calendar/Tasks integration.

## Tech Stack

- Python 3.13+
- discord.py (Discord Bot framework)
- google-genai (Gemini API client)
- google-api-python-client (Google Calendar/Tasks API)
- google-auth-oauthlib (OAuth 2.0 flow)
- uv (Package manager)

## Project Structure

```
gem-bot/                    # Repository root
├── bot.py                  # Entry point, GeminiBot class, event handlers
├── cogs/
│   ├── __init__.py         # Cog package marker
│   └── commands.py         # Discord commands
├── history_manager.py      # Git-based history management
├── i18n.py                 # Internationalization
├── calendar_manager.py     # Google Calendar/Tasks OAuth & API
├── calendar_tools.py       # Gemini Calendar function declarations
├── tasks_tools.py          # Gemini Tasks function declarations
├── locales/
│   ├── ja.json             # Japanese translations
│   └── en.json             # English translations
├── history/                # Conversation data (git-ignored)
│   ├── config.json         # Global settings (language, per-channel model/config)
│   ├── tokens/             # Google OAuth tokens per user
│   └── {channel_id}/       # Per-channel Git repository
│       ├── .git/
│       ├── conversation.json
│       ├── GEMINI.md       # System prompt
│       └── files/          # Image attachments
├── credentials.json        # Google OAuth credentials (git-ignored)
├── .env                    # Environment variables (git-ignored)
└── .env.example            # Environment variables template
```

## Architecture

### GeminiBot Class (bot.py)

A custom class extending `commands.Bot`. It holds the following state:

- `gemini_client`: Gemini API client
- `default_model`: Default model name (used when no channel-specific setting exists)
- `pending_model_selections`: Interactive model selection state
- `pending_delete_confirmations`: Delete confirmation state
- `conversation_history`: Per-channel conversation history
- `history_manager`: Git-based history and settings manager
- `i18n`: Internationalization manager
- `calendar_auth`: Google Calendar OAuth manager
- `calendar_tool_handler`: Calendar tool handler
- `tasks_tool_handler`: Tasks tool handler
- `channel_tool_mode`: Per-channel tool mode (default/calendar/todo)

Model and generation config settings are managed per-channel in `history/config.json`.

### Cog (cogs/commands.py)

Commands are separated using discord.py's Cog feature.

**Command Groups:**
- `!model` - Model management (list, set)
- `!history` - Conversation history (list, delete, clear, export)
- `!branch` - Branch management (create, list, switch, delete, merge)
- `!prompt` - System prompt (show, set, append, clear, download)
- `!config` - Generation config (show, set, reset)
- `!mode` - Tool mode (default, calendar, todo)
- `!google` - Google integration (link, unlink, status)
- `!image` - Image generation

### Calendar Manager (calendar_manager.py)

Handles Google OAuth 2.0 flow and API calls:

- `CalendarAuthManager`: OAuth flow, credential storage, API service creation
- `OAuthCallbackHandler`: HTTP handler for OAuth redirect
- Calendar API: list_events, create_event, update_event, delete_event
- Tasks API: list_task_lists, list_tasks, create_task, update_task, complete_task, delete_task

### Tool Handlers (calendar_tools.py, tasks_tools.py)

Declare Gemini function tools and handle function calls:

- `get_calendar_tools()`: Returns Gemini Tool objects for calendar
- `get_tasks_tools()`: Returns Gemini Tool objects for tasks
- `CalendarToolHandler`: Routes calendar function calls to API
- `TasksToolHandler`: Routes tasks function calls to API

### History Manager (history_manager.py)

Git-based conversation persistence:

- Per-channel Git repositories
- Branch/merge operations
- Image file storage with MIME type handling
- System prompt storage (GEMINI.md)
- Global config management

### i18n (i18n.py)

Internationalization support:

- Auto-detects languages from `locales/` directory
- JSON-based translation files
- `t(key, **kwargs)` for formatted translations

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

For command groups (subcommands):

```python
@commands.group(name="mygroup", invoke_without_command=True)
async def mygroup(self, ctx: commands.Context):
    """Group description"""
    if ctx.invoked_subcommand is None:
        await ctx.send(self.t("mygroup_help"))

@mygroup.command(name="subcommand")
async def mygroup_subcommand(self, ctx: commands.Context, arg: str):
    """Subcommand description"""
    pass
```

### Accessing Shared State

Access shared state from Cog via `self.bot`:

- `self.bot.get_model(channel_id)`: Get model for channel
- `self.bot.set_model(channel_id, model)`: Set model for channel
- `self.bot.get_tool_mode(channel_id)`: Get tool mode for channel
- `self.bot.set_tool_mode(channel_id, mode)`: Set tool mode for channel
- `self.bot.default_model`: Default model
- `self.bot.gemini_client`: Gemini API client
- `self.bot.conversation_history`: Per-channel conversation history dict
- `self.bot.pending_model_selections`: Model selection state
- `self.bot.pending_delete_confirmations`: Delete confirmation state
- `self.bot.history_manager`: Git-based history manager
- `self.bot.i18n`: Internationalization manager
- `self.bot.calendar_auth`: Google Calendar auth manager
- `self.bot.calendar_tool_handler`: Calendar tool handler
- `self.bot.tasks_tool_handler`: Tasks tool handler

### Translation

Use `self.t(key, **kwargs)` in Cog for translated messages:

```python
await ctx.send(self.t("some_message_key", param=value))
```

Note: Avoid using `key` as a kwarg name since `t()` uses it as the first parameter.

### Adding Tool Functions

To add new Gemini function tools:

1. Define the tool in a `*_tools.py` file using `types.Tool` and `types.FunctionDeclaration`
2. Create a handler class with `handle_function_call()` method
3. Register in `bot.py`:
   - Add handler to GeminiBot
   - Update `_get_tools_for_mode()` to return tools
   - Update `_execute_single_function()` to route calls

## Development Commands

```bash
# Install dependencies
uv sync

# Start the bot
uv run python bot.py

# Syntax check
python -m py_compile bot.py cogs/commands.py history_manager.py i18n.py calendar_manager.py calendar_tools.py tasks_tools.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Discord Bot token |
| `GEMINI_API_KEY` | Yes | Gemini API key |
| `GEMINI_CHANNEL_ID` | Yes | Auto-response channel IDs (comma-separated) |

## Optional Files

| File | Description |
|------|-------------|
| `credentials.json` | Google OAuth credentials for Calendar/Tasks integration |

## Notes

- `.env` file is git-ignored. Never commit API keys or tokens.
- `credentials.json` is git-ignored. Required for Google integration.
- Discord messages have a 2000 character limit. `send_response` handles automatic splitting.
- Conversation history is persisted via Git in `history/{channel_id}/`.
- Each channel has its own Git repository for branch/merge support.
- Global settings (language, per-channel model/config) are stored in `history/config.json`.
- Google OAuth tokens are stored per-user in `history/tokens/`.
- Image attachments are stored in `history/{channel_id}/files/`.
