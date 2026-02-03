# AGENTS.md

Guidelines for AI coding agents working in this repository.

## Critical Rules - MUST FOLLOW

### Git Operations - ABSOLUTELY PROHIBITED

**The following commands are STRICTLY FORBIDDEN unless the user explicitly uses the words "commit" or "push":**

- `git commit` - PROHIBITED
- `git push` - PROHIBITED
- `git add . && git commit` - PROHIBITED
- `gh pr create` - PROHIBITED

**The following phrases are NOT permission to commit or push:**

- "complete this", "finish", "done"
- "apply changes", "save changes"
- "build", "fix", "update"
- "make this work", "implement this"
- Any instruction that does not explicitly contain "commit" or "push"

**Required behavior after making changes:**

1. Report a summary of what was changed
2. Ask the user: "Would you like me to commit these changes?"
3. Wait for explicit permission before running any git commit/push commands

**User needs to verify all changes before any commit is made.**

## Project Overview

A Discord bot enabling AI conversations using the Gemini API with Google Calendar/Tasks integration.

**Tech Stack:** Python 3.13+, discord.py (app_commands), google-genai, google-api-python-client, uv

## Build/Lint/Test Commands

```bash
# Install dependencies
uv sync

# Run the bot
uv run python bot.py

# Syntax check all Python files
python -m py_compile bot.py cogs/commands.py history_manager.py i18n.py latex_renderer.py calendar_manager.py calendar_tools.py tasks_tools.py

# Type checking (if mypy is added)
uv run mypy bot.py

# Run a single file syntax check
python -m py_compile <filename.py>
```

**Note:** No test framework is currently configured. Tests would be added with pytest.

## Project Structure

```
gem-bot/
├── bot.py                  # Entry point, GeminiBot class, event handlers
├── cogs/
│   ├── __init__.py
│   └── commands.py         # Discord commands (Cog)
├── history_manager.py      # Git-based history management
├── i18n.py                 # Internationalization
├── latex_renderer.py       # LaTeX formula rendering to PNG
├── calendar_manager.py     # Google Calendar/Tasks OAuth & API
├── calendar_tools.py       # Gemini Calendar function declarations
├── tasks_tools.py          # Gemini Tasks function declarations
├── locales/{en,ja}.json    # Translation files
└── history/                # Runtime data (git-ignored)
```

## Code Style Guidelines

### Import Order

Group imports in this order, separated by blank lines:
1. Standard library (`json`, `os`, `subprocess`, `datetime`)
2. Third-party packages (`discord`, `google.genai`)
3. Local modules (`history_manager`, `i18n`, `calendar_manager`)

```python
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord.ext import commands
from google.genai import types

from history_manager import HistoryManager
from i18n import I18nManager
```

### Type Annotations

- Use Python 3.10+ union syntax: `str | None` instead of `Optional[str]`
- Use lowercase generics: `list[str]`, `dict[str, Any]` instead of `List`, `Dict`
- Annotate all function parameters and return types
- Use `TYPE_CHECKING` for import-only type hints to avoid circular imports

```python
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from i18n import I18nManager

def get_model(self, channel_id: int) -> str:
    ...

def load_conversation(self, channel_id: int) -> dict[str, Any] | None:
    ...
```

### Naming Conventions

- **Classes:** PascalCase (`GeminiBot`, `HistoryManager`, `CalendarToolHandler`)
- **Functions/methods:** snake_case (`load_conversation`, `_ensure_repo`)
- **Constants:** UPPER_SNAKE_CASE (`DEFAULT_LANGUAGE`, `MIME_TO_EXT`)
- **Private methods:** prefix with underscore (`_get_repo_path`, `_load_config`)

### Docstrings

Use Google-style docstrings for all public functions and classes:

```python
def save_conversation(
    self,
    channel_id: int,
    messages: list[dict[str, Any]],
    model: str,
    auto_commit: bool = True,
) -> None:
    """Save conversation history to file.

    Args:
        channel_id: Discord channel ID.
        messages: List of message dictionaries with role, content, timestamp.
        model: Model name used for the conversation.
        auto_commit: Whether to automatically commit changes.
    """
```

### Async/Await

**Critical:** Always use async Gemini API calls to avoid blocking Discord's event loop:

```python
# Correct - non-blocking
response = await self.gemini_client.aio.models.generate_content(...)

# Wrong - blocks event loop, causes disconnection
response = self.gemini_client.models.generate_content(...)
```

### Error Handling

- Catch specific exceptions, not bare `except:`
- Re-raise or handle appropriately; avoid silent failures
- Use translated error messages via `self.t()` for user-facing errors

```python
try:
    self.bot.history_manager.create_branch(channel_id, branch_name)
except RuntimeError as e:
    await ctx.send(self.t("branch_error", error=e))
except Exception as e:
    await ctx.send(self.t("branch_error", error=e))
```

### String Formatting

- Use f-strings for simple formatting: `f"Channel {channel_id}"`
- Use `.format()` only for i18n: `self.t("key", param=value)`
- JSON: Always use `ensure_ascii=False, indent=2` for readability

### Class Constants

Define class-level constants as class attributes:

```python
class HistoryManager:
    MIME_TO_EXT: dict[str, str] = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }
```

### Discord Commands

Commands live in `cogs/commands.py`. Use slash commands with `app_commands`:

```python
# Root command group
gem_group = app_commands.Group(name="gem", description="Gemini Bot Commands")

@gem_group.command(name="info")
async def info(self, interaction: discord.Interaction):
    """Displays information about the bot."""
    ...

# Subgroups
model_group = app_commands.Group(name="model", parent=gem_group, description="Model management")

@model_group.command(name="list")
async def model_list(self, interaction: discord.Interaction):
    """Lists all available Gemini models."""
    ...
```

### Translation Helper

All classes with user-facing messages should have a `t()` shortcut:

```python
def t(self, key: str, **kwargs) -> str:
    """Shortcut for translation."""
    return self.bot.i18n.t(key, **kwargs)
```

## Key Patterns

- **Early returns:** Prefer early returns to reduce nesting
- **Frozensets for constants:** Use `frozenset` for immutable sets of function names
- **Path objects:** Use `pathlib.Path` instead of `os.path`
- **Context managers:** Use `async with ctx.typing():` for long operations

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Discord Bot token |
| `GEMINI_API_KEY` | Yes | Gemini API key |
| `GEMINI_CHANNEL_ID` | Yes | Auto-response channel IDs (comma-separated) |
| `DISCORD_GUILD_ID` | No | Guild ID for instant slash command sync (Development) |

## External Dependencies

### LaTeX (Optional)

LaTeX is required for rendering mathematical formulas as images. The bot uses `latex` and `dvipng` commands.

**Installation:**

**Windows:**
- Install [MiKTeX](https://miktex.org/download)
- Enable "Install missing packages on-the-fly"

**macOS:**
```bash
brew install --cask mactex-no-gui
# Or for smaller install:
brew install --cask basictex && sudo tlmgr install standalone preview dvipng
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install texlive-latex-extra dvipng
```

**Linux (Fedora/RHEL):**
```bash
sudo dnf install texlive-standalone texlive-preview dvipng
```

**Linux (Arch):**
```bash
sudo pacman -S texlive-latexextra
```

If LaTeX is not installed, the bot will still work but formulas will only be displayed as text without rendered images.
