# Gemini Discord Bot

A Discord bot that enables AI conversations using the Gemini API.

> **Note:** The official repository is hosted at [https://git.kinoshita-lab.org/kazbo/gem-bot](https://git.kinoshita-lab.org/kazbo/gem-bot). Other locations are mirrors.

[日本語ドキュメント (Japanese)](README.ja.md)

---

## Features

- **Git-powered conversation branching** - Branch, merge, and fork conversations just like code.
- **Channel-based conversation** - Responds to all messages in specified channels
- **Model switching** - Change Gemini models at runtime with recommended models shown first
- **Image generation** - Generate images from text prompts using Gemini
- **Image analysis** - Upload images with messages for AI analysis
- **Persistent history** - Conversation history is stored in Git repositories, surviving restarts and enabling version control
- **Two-level system prompts** - Global master instruction + per-channel customization for flexible AI behavior
- **Generation config** - Customize temperature, top_p, and other parameters per channel
- **Export to Markdown** - Export conversation history as Markdown files with images as ZIP
- **i18n support** - Multi-language support (Japanese/English by default, extensible)
- **Google Calendar integration** - Manage calendar events through natural language
- **Google Tasks integration** - Manage TODO lists through natural language
- **LaTeX formula rendering** - Automatically render mathematical formulas as images

---

## System Prompts

The bot uses a two-level prompt system for flexible AI behavior customization:

### Master Instruction (Global)

The master instruction applies to **all channels** and defines the bot's base personality and behavior.

**Location**: `history/project/GEMINI.md` (managed in separate Git repository)

**Management**:
- **View**: `/gem system-prompt show` - Display the current master instruction
- **Download**: `/gem system-prompt download` - Download as `GEMINI.md` file for editing
- **Edit**: Upload a file named `GEMINI.md` to any channel to update (automatically committed)

**Example**:
```
You are a helpful and professional AI assistant specialized in software development.

Guidelines:
- Always provide clear, well-commented code examples
- Explain technical concepts in simple terms
- Be concise but thorough
- Use markdown formatting for better readability
```

**Use cases**:
- Define the bot's core personality (e.g., "You are a helpful coding assistant")
- Set organization-wide guidelines or policies
- Configure default response style and tone

**Git management**: Automatically committed to `history/project` repository.

### Channel Instruction (Per-channel)

Each channel can have its own additional instruction that **extends** the master instruction.

**Location**: `history/{channel_id}/channel_instruction.md` (git-managed per channel)

**Management**:
- **View**: `/gem channel-prompt show` - Display the current channel instruction
- **Download**: `/gem channel-prompt download` - Download as `channel_instruction.md`
- **Edit**: Upload a file named `channel_instruction.md` to the channel
- **Clear**: `/gem channel-prompt clear` - Remove the channel instruction

**Example** (for a Python-focused channel):
```
This channel is dedicated to Python programming discussions.

Additional guidelines:
- Focus on Python 3.10+ features and best practices
- Recommend type hints and proper documentation
- Suggest pytest for testing examples
- Follow PEP 8 style guidelines
```

**Use cases**:
- Add channel-specific context (e.g., "This channel is for Python discussions")
- Override or extend behavior for specific use cases
- Set temporary project-specific instructions

**Git management**: Automatically committed with each change. See [Git Version Control](#git-version-control) for details.

### How Prompts are Combined

The final prompt sent to Gemini is constructed as:

```
[Master Instruction]

[Channel Instruction]

[User Message]
```

**Example**:
- **Master**: "You are a helpful assistant. Always be concise."
- **Channel** (in #python-help): "Focus on Python best practices. Provide code examples."
- **Result**: The bot will be concise, helpful, and focus on Python with examples in the #python-help channel.

**Note**: If no channel instruction is set, only the master instruction is used.


---

## Git Version Control

### What is Managed by Git

The bot automatically uses Git to version control **channel-specific data only**. Each channel has its own independent Git repository.

#### Git-managed Files (Per Channel)

Located in `history/{channel_id}/`:

- **`conversation.json`** - Complete conversation history
  - Committed after each message exchange
  - Enables conversation branching and history tracking
  
- **`channel_instruction.md`** - Channel-specific instruction
  - Committed when updated via file upload or `/gem channel-prompt clear`
  - Allows reverting to previous instructions through branching
  
- **`files/`** - Image attachments
  - Committed when images are uploaded in conversations
  - Preserved across branches

#### Project Data (Global Git Repository)

Located in `history/project/`:

- **`GEMINI.md`** - Master instruction
  - Automatically committed when updated via file upload
  - Managed in a separate Git repository from channel histories

#### NOT Git-managed Files

- **`history/config.json`** - Global bot configuration
  - Contains channel models and generation settings
  - Managed by bot commands (`/gem model`, `/gem config`)

- **`history/tokens/`** - Google OAuth tokens
  - Security: Should never be version controlled

- **`.env`** - Environment variables (API keys, tokens)
  - Security: Should never be version controlled

- **`credentials.json`** - Google OAuth credentials
  - Security: Should never be version controlled

### Why This Design?

**Channel-specific data (Git-managed)**:
- Enables conversation branching with `/gem branch` commands
- Provides complete history tracking with `/gem history` commands
- Allows exporting conversations with full context
- Each channel operates independently

**Project data (Git-managed)**:
- **`GEMINI.md`**: Managed in `history/project` repository for version control of the master prompt.

**Configuration/secrets (NOT Git-managed)**:
- **Configuration/secrets**: Security best practice - never commit credentials
- **Global settings**: Automatically managed by the bot across all channels

### Automatic Git Operations

The bot automatically commits changes for:

1. **Conversation updates**
   - After each user message and bot response
   - Commit message: `"Update conversation"`

2. **Channel instruction changes**
   - When uploading `channel_instruction.md`
   - When using `/gem channel-prompt clear`
   - Commit messages: `"Update channel instruction"`, `"Initialize empty channel instruction"`

3. **Master instruction changes**
    - When uploading `GEMINI.md`
    - Commit message: `"Update master instruction"`

4. **Branch operations**
   - Auto-saves before switching: `"Auto-save before branch switch"`
   - Records merges: `"Merge branch 'branch-name'"`

### Branch Workflow

Each channel repository supports Git branching for conversation forking:

**Use case**: You want to explore different approaches without losing your current conversation.

```
Main conversation (main branch)
├─ Continue current discussion
└─ Create branch "experiment" → Try alternative approach
   ├─ If successful → Merge back to main
   └─ If not → Switch back to main (experiment preserved)
```

**Available commands**:
- `/gem branch list` - View all branches
- `/gem branch create <name>` - Fork conversation
- `/gem branch switch <name>` - Change active branch
- `/gem branch merge <name>` - Combine branches
- `/gem branch delete <name>` - Remove branch

### Storage Structure

```
history/
├── config.json                      # Global settings (NOT in Git)
├── tokens/                          # OAuth tokens (NOT in Git)
├── project/                         # Project data (Git repository)
│   ├── .git/
│   └── GEMINI.md                    # Master instruction (Git-managed)
└── {channel_id}/                    # Per-channel (Git repository)
    ├── .git/                        # Git metadata
    ├── conversation.json            # Conversation history (Git-managed)
    ├── channel_instruction.md       # Channel prompt (Git-managed)
    └── files/                       # Images (Git-managed)
        └── img_20240130_123456_001.png
```

### Benefits

1. **Conversation Versioning**: Every message is tracked with full history
2. **Experimentation**: Branch to try ideas without losing context
3. **Rollback**: Switch branches to return to earlier conversation states
4. **Export**: `/gem history export` to Markdown format
5. **Independence**: Each channel's history is isolated


---

## Prerequisites

### Install uv (Package Manager)

This project uses [uv](https://docs.astral.sh/uv/) as the package manager.

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install Git

Git is required for conversation history management.

**Windows:**
Download and install from [git-scm.com](https://git-scm.com/download/win)

**macOS:**
```bash
xcode-select --install
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install git
```

After installation, configure your identity:
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Install LaTeX (Optional - for formula rendering)

LaTeX is required for rendering mathematical formulas as images. If not installed, the bot will still work but formulas will only be shown as text.

**Windows:**
1. Download and install [MiKTeX](https://miktex.org/download)
2. During installation, select "Install missing packages on-the-fly: Yes"
3. After installation, open MiKTeX Console and install the `standalone` package

**macOS:**
```bash
# Using Homebrew
brew install --cask mactex-no-gui

# Or install BasicTeX (smaller, ~100MB)
brew install --cask basictex
# Then install required packages
sudo tlmgr update --self
sudo tlmgr install standalone preview dvipng
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

### Get Gemini API Key

1. Go to [Google AI Studio API Keys](https://aistudio.google.com/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the API key

### Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application"
3. Enter an application name
   - **Important:** Do NOT use "gemini" in the bot name. Discord blocks bot names containing "gemini" as it's a reserved term.
   - Use alternative names like "gem-bot", "ai-assistant", etc.
4. Go to "Bot" in the left sidebar
5. Click "Reset Token" and copy the bot token
6. Enable these Privileged Gateway Intents:
   - Message Content Intent (required for reading messages)
7. Go to "OAuth2" > "URL Generator"
8. Select scopes: `bot`
9. Select bot permissions: `Send Messages`, `Read Message History`, `Attach Files`
10. Copy the generated URL and open it to invite the bot to your server


---

## Setup

### 1. Clone and Install

```bash
git clone <repository-url>
cd gem-bot
uv sync
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
GEMINI_CHANNEL_ID=123456789012345678
DISCORD_GUILD_ID=your_guild_id_here  # Optional: For dev slash command sync
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | API key from Google AI Studio |
| `DISCORD_BOT_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `GEMINI_CHANNEL_ID` | Yes | Channel IDs for bot responses (comma-separated) |
| `DISCORD_GUILD_ID` | No | Guild ID for instant slash command sync (Development) |

### 3. Start the Bot

```bash
uv run python bot.py
```

The bot will send a message to the configured channels when it comes online.


---

## Commands

All commands are slash commands under the `/gem` group.

### General

| Command | Description |
|---------|-------------|
| `/gem info` | Show bot information |
| `/gem lang [code]` | Change display language |

### Model

| Command | Description |
|---------|-------------|
| `/gem model list` | List available Gemini models |
| `/gem model set` | Select a model from available options |

### Image Generation

| Command | Description |
|---------|-------------|
| `/gem image <prompt>` | Generate an image from text |

### Generation Config

| Command | Description |
|---------|-------------|
| `/gem config show` | Show current generation settings |
| `/gem config set <key> <value>` | Set a generation parameter |
| `/gem config reset [key]` | Reset settings to default |

Available parameters:
- `temperature` (0.0-2.0) - Randomness
- `top_p` (0.0-1.0) - Token selection threshold
- `top_k` (1-100) - Candidate token count
- `max_output_tokens` (1-65536) - Max output length
- `presence_penalty` (-2.0-2.0) - Presence penalty
- `frequency_penalty` (-2.0-2.0) - Frequency penalty

### Conversation History

| Command | Description |
|---------|-------------|
| `/gem history list [start] [count]` | List history with numbered messages |
| `/gem history delete <number>` | Delete a specific message by number |
| `/gem history clear` | Clear all conversation history |
| `/gem history export [filename]` | Export history as Markdown (ZIP with images) |

### Branch Management

| Command | Description |
|---------|-------------|
| `/gem branch list` | List all branches |
| `/gem branch create <name>` | Create and switch to new branch |
| `/gem branch switch <name>` | Switch to a branch |
| `/gem branch merge <name>` | Merge a branch into current |
| `/gem branch delete <name>` | Delete a branch |

### Tool Mode

| Command | Description |
|---------|-------------|
| `/gem mode set [mode]` | Switch tool mode (default/calendar/todo) |

### Google Integration

| Command | Description |
|---------|-------------|
| `/gem google link` | Link your Google account |
| `/gem google unlink` | Unlink your Google account |
| `/gem google status` | Check Google connection status |

### Prompt Management

| Command | Description |
|---------|-------------|
| `/gem system-prompt show` | Show master system prompt |
| `/gem system-prompt download` | Download master system prompt |
| `/gem channel-prompt show` | Show channel instruction |
| `/gem channel-prompt download` | Download channel instruction |
| `/gem channel-prompt clear` | Clear channel instruction |

---

## Channel Configuration

The bot responds to all messages in the channels specified by `GEMINI_CHANNEL_ID`.
This setting is required for the bot to function.

```bash
# Single channel
GEMINI_CHANNEL_ID=123456789012345678

# Multiple channels
GEMINI_CHANNEL_ID=123456789012345678,987654321098765432
```

### How to Get Channel ID

1. Enable Developer Mode in Discord Settings > Advanced
2. Right-click a channel > "Copy ID"


---

## System Prompt (Master)

The master system prompt applies to all channels. You can view and manage it:

- **View**: Use `/gem system-prompt show` to view the current master instruction
- **Download**: Use `/gem system-prompt download` to download as a file
- **Edit**: Upload a file named `GEMINI.md` to any channel to update the master instruction

### Channel Instruction (Per-channel)

Each channel can have its own additional instruction.

- **View**: Use `/gem channel-prompt show` to view the current channel instruction
- **Download**: Use `/gem channel-prompt download` to download as a file
- **Edit**: Upload a file named `channel_instruction.md` to the channel
- **Clear**: Use `/gem channel-prompt clear` to remove the channel instruction

System prompts are constructed as: `[Master Instruction] + [Channel Instruction]`.

---

## Conversation History

Conversation history is persisted per channel using Git in the `history/` directory.

- Each channel has its own Git repository
- History survives bot restarts
- Branch/merge support for conversation forking
- Export to Markdown with `/gem history export`
- Full Git history with automatic commits

For more details on Git operations and version control, see [Git Version Control](#git-version-control).

---

## Google Integration (Calendar / Tasks)

The bot supports Google Calendar and Google Tasks integration through natural language.

### Setup Google Integration

1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the Google Calendar API and Google Tasks API
3. Create OAuth 2.0 credentials (Desktop application)
4. Download the credentials file and save it as `credentials.json` in the project root
5. Use `/gem google link` to link your Google account

### Using Calendar Mode

```
/gem mode set calendar
```

In calendar mode, you can ask the bot to:
- List upcoming events
- Create new events
- Update existing events
- Delete events

Example: "What do I have scheduled for tomorrow?"

### Using Todo Mode

```
/gem mode set todo
```

In todo mode, you can ask the bot to:
- List your task lists
- List tasks in a specific list
- Create new tasks
- Mark tasks as complete
- Delete tasks

Example: "Add 'Buy groceries' to my shopping list"

---

## i18n

The bot supports multiple languages. Default languages are Japanese (`ja`) and English (`en`).

### Change Language

```
/gem lang en    # English
/gem lang ja    # Japanese
```

### Add New Language

Create a new JSON file in `locales/` directory (e.g., `locales/de.json`).
The bot will automatically detect and enable the new language.

Language settings are stored in `history/config.json`.

---

## Configuration File

Global settings are stored in `history/config.json`:

```json
{
  "language": "ja",
  "channels": {
    "123456789012345678": {
      "model": "gemini-flash-latest",
      "generation_config": {
        "temperature": 0.7,
        "top_p": 0.9
      }
    }
  }
}

---

## Project Structure

```
gem-bot/                    # Repository root
├── bot.py                  # Main entry point, GeminiBot class
├── cogs/
│   ├── __init__.py         # Cog package marker
│   └── commands.py         # Discord commands
├── history_manager.py      # Git-based history management
├── i18n.py                 # Internationalization
├── latex_renderer.py       # LaTeX formula rendering
├── calendar_manager.py     # Google Calendar/Tasks OAuth & API
├── calendar_tools.py       # Gemini Calendar function declarations
├── tasks_tools.py          # Gemini Tasks function declarations
├── locales/
│   ├── ja.json             # Japanese translations
│   └── en.json             # English translations
├── history/                # Conversation data
│   ├── config.json         # Global settings
│   ├── tokens/             # Google OAuth tokens (git-ignored)
│   ├── project/            # Project data (Git repository)
│   │   └── GEMINI.md       # Master instruction (Git-managed)
│   └── {channel_id}/       # Per-channel data
│       ├── .git/           # Git repository
│       ├── conversation.json  # Conversation history
│       ├── channel_instruction.md       # Channel-specific instruction
│       └── files/          # Image attachments
├── credentials.json        # Google OAuth credentials (git-ignored)
└── .env                    # Environment variables (git-ignored)
```

---

## Running as a systemd Service

To run the bot as a background service on Linux, create a systemd unit file.

### 1. Create the service file

```bash
sudo nano /etc/systemd/system/gem-bot.service
```

Add the following content (adjust paths and user as needed):

```ini
[Unit]
Description=Gemini Discord Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/gem-bot
ExecStart=/home/your_username/.local/bin/uv run python bot.py
Restart=always
RestartSec=10
Environment=PATH=/home/your_username/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
```

### 2. Enable and start the service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable on boot
sudo systemctl enable gem-bot

# Start the service
sudo systemctl start gem-bot

# Check status
sudo systemctl status gem-bot
```

### 3. View logs

```bash
# View recent logs
sudo journalctl -u gem-bot -n 50

# Follow logs in real-time
sudo journalctl -u gem-bot -f
```

### 4. Manage the service

```bash
# Stop
sudo systemctl stop gem-bot

# Restart
sudo systemctl restart gem-bot

# Disable from boot
sudo systemctl disable gem-bot
```
