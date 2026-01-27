# Gemini Discord Bot

A Discord bot that enables AI conversations using the Gemini API.

Discord上でGemini APIを使用してAIと会話できるボットです。

---

## Features

- **Git-powered conversation branching** - Branch, merge, and fork conversations just like code.
- **Channel-based conversation** - Responds to all messages in specified channels
- **Model switching** - Change Gemini models at runtime with recommended models shown first
- **Image generation** - Generate images from text prompts using Gemini
- **Persistent history** - Conversation history is stored in Git repositories, surviving restarts and enabling version control
- **Channel-specific system prompts** - Customize AI behavior per channel via Discord commands
- **Generation config** - Customize temperature, top_p, and other parameters per channel
- **Export to Markdown** - Export conversation history as Markdown files for documentation or sharing
- **i18n support** - Multi-language support (Japanese/English by default, extensible)

## 機能

- **Git による会話の分岐** - コードのように会話をブランチ、マージ、フォーク可能。
- **チャンネルベースの会話** - 指定したチャンネルの全メッセージに応答
- **モデル切り替え** - おすすめモデルを先頭に表示し、実行時に変更可能
- **画像生成** - テキストプロンプトから画像を生成
- **永続的な履歴** - 会話履歴は Git リポジトリに保存され、再起動後も保持、バージョン管理が可能
- **チャンネル別システムプロンプト** - Discordコマンドでチャンネルごとにカスタマイズ
- **生成設定** - temperature、top_p などのパラメータをチャンネルごとに設定
- **Markdownエクスポート** - 会話履歴をMarkdownファイルとしてエクスポート、ドキュメント化や共有に便利
- **多言語対応** - 日本語/英語（拡張可能）

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
cd gemini_discord
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
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | API key from Google AI Studio |
| `DISCORD_BOT_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `GEMINI_CHANNEL_ID` | Yes | Channel IDs for bot responses (comma-separated) |

### 3. Start the Bot

```bash
uv run python bot.py
```

The bot will send a message to the configured channels when it comes online.

---

## 前提条件

### uv（パッケージマネージャー）のインストール

このプロジェクトはパッケージマネージャーとして [uv](https://docs.astral.sh/uv/) を使用しています。

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Git のインストール

会話履歴の管理に Git が必要です。

**Windows:**
[git-scm.com](https://git-scm.com/download/win) からダウンロードしてインストール

**macOS:**
```bash
xcode-select --install
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt install git
```

インストール後、ユーザー情報を設定:
```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Gemini API キーの取得

1. [Google AI Studio API Keys](https://aistudio.google.com/apikey) にアクセス
2. Google アカウントでログイン
3. 「Create API Key」をクリック
4. API キーをコピー

### Discord Bot の作成

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. 「New Application」をクリック
3. アプリケーション名を入力
   - **重要:** ボット名に「gemini」を含めないでください。Discordは「gemini」を予約語としてブロックします。
   - 「gem-bot」「ai-assistant」などの代替名を使用してください。
4. 左サイドバーの「Bot」に移動
5. 「Reset Token」をクリックしてボットトークンをコピー
6. 以下の Privileged Gateway Intents を有効化:
   - Message Content Intent（メッセージ読み取りに必須）
7. 「OAuth2」>「URL Generator」に移動
8. スコープを選択: `bot`
9. ボット権限を選択: `Send Messages`, `Read Message History`, `Attach Files`
10. 生成された URL をコピーして開き、ボットをサーバーに招待

---

## セットアップ

### 1. クローンとインストール

```bash
git clone <repository-url>
cd gemini_discord
uv sync
```

### 2. 環境変数の設定

`.env.example`を`.env`にコピーして設定:

```bash
cp .env.example .env
```

`.env` を編集して認証情報を設定:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
GEMINI_CHANNEL_ID=123456789012345678
```

| 変数 | 必須 | 説明 |
|------|------|------|
| `GEMINI_API_KEY` | Yes | Google AI Studio の API キー |
| `DISCORD_BOT_TOKEN` | Yes | Discord Developer Portal の Bot トークン |
| `GEMINI_CHANNEL_ID` | Yes | ボットが応答するチャンネルID（カンマ区切り） |

### 3. ボットの起動

```bash
uv run python bot.py
```

ボットがオンラインになると、設定されたチャンネルにメッセージが送信されます。

---

## Commands

### General

| Command | Description |
|---------|-------------|
| `!help` | Show help message |
| `!info` | Show bot information |
| `!lang [code]` | Change display language |

### Model

| Command | Description |
|---------|-------------|
| `!model list` | List available Gemini models |
| `!model set` | Interactively change the model |

### Image Generation

| Command | Description |
|---------|-------------|
| `!image <prompt>` | Generate an image from text |

### System Prompt

| Command | Description |
|---------|-------------|
| `!prompt show` | Show current system prompt |
| `!prompt set <content>` | Set system prompt |
| `!prompt clear` | Clear system prompt |
| `!prompt download` | Download system prompt as file |
| Upload `GEMINI.md` | Upload file to set system prompt |

### Generation Config

| Command | Description |
|---------|-------------|
| `!config show` | Show current generation settings |
| `!config set <key> <value>` | Set a generation parameter |
| `!config reset [key]` | Reset settings to default |

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
| `!history clear` | Clear all conversation history |
| `!history export [filename]` | Export history as Markdown |

### Branch Management

| Command | Description |
|---------|-------------|
| `!branch list` | List all branches |
| `!branch create <name>` | Create and switch to new branch |
| `!branch switch <name>` | Switch to a branch |
| `!branch merge <name>` | Merge a branch into current |
| `!branch delete <name>` | Delete a branch |

## コマンド

### 一般

| コマンド | 説明 |
|---------|------|
| `!help` | ヘルプを表示 |
| `!info` | ボット情報を表示 |
| `!lang [code]` | 表示言語を変更 |

### モデル

| コマンド | 説明 |
|---------|------|
| `!model list` | 利用可能なモデル一覧 |
| `!model set` | モデルを対話的に変更 |

### 画像生成

| コマンド | 説明 |
|---------|------|
| `!image <プロンプト>` | テキストから画像を生成 |

### システムプロンプト

| コマンド | 説明 |
|---------|------|
| `!prompt show` | 現在のシステムプロンプトを表示 |
| `!prompt set <内容>` | システムプロンプトを設定 |
| `!prompt clear` | システムプロンプトを削除 |
| `!prompt download` | システムプロンプトをファイルでダウンロード |
| `GEMINI.md` をアップロード | ファイルをアップロードしてプロンプトを設定 |

### 生成設定

| コマンド | 説明 |
|---------|------|
| `!config show` | 現在の生成設定を表示 |
| `!config set <キー> <値>` | 生成パラメータを設定 |
| `!config reset [キー]` | 設定をリセット |

設定可能なパラメータ:
- `temperature` (0.0-2.0) - ランダム性
- `top_p` (0.0-1.0) - トークン選択閾値
- `top_k` (1-100) - 候補トークン数
- `max_output_tokens` (1-65536) - 最大出力長
- `presence_penalty` (-2.0-2.0) - 存在ペナルティ
- `frequency_penalty` (-2.0-2.0) - 頻度ペナルティ

### 会話履歴

| コマンド | 説明 |
|---------|------|
| `!history clear` | 会話履歴を全て削除 |
| `!history export [ファイル名]` | 履歴をMarkdownでエクスポート |

### ブランチ管理

| コマンド | 説明 |
|---------|------|
| `!branch list` | ブランチ一覧を表示 |
| `!branch create <名前>` | 新しいブランチを作成して切り替え |
| `!branch switch <名前>` | 指定したブランチに切り替え |
| `!branch merge <名前>` | ブランチをマージ |
| `!branch delete <名前>` | ブランチを削除 |

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

## チャンネル設定

ボットは`GEMINI_CHANNEL_ID`で指定されたチャンネルの全メッセージに応答します。
この設定はボットの動作に必須です。

```bash
# 単一チャンネル
GEMINI_CHANNEL_ID=123456789012345678

# 複数チャンネル
GEMINI_CHANNEL_ID=123456789012345678,987654321098765432
```

### チャンネルIDの取得方法

1. Discordの設定 > 詳細設定 > 「開発者モード」を有効化
2. チャンネルを右クリック > 「IDをコピー」

---

## System Prompts

Each channel can have its own system prompt. You can set it via Discord commands:

```
!prompt set You are a helpful assistant.
!prompt show
!prompt clear
```

### Download / Upload

You can also download and upload system prompts as files:

- **Download**: Use `!prompt download` to download the current system prompt as `GEMINI.md`
- **Upload**: Simply upload a file named `GEMINI.md` to the channel, and the bot will automatically update the system prompt

This is useful for editing long prompts in your favorite text editor.

System prompts are stored in `history/{channel_id}/GEMINI.md`.

## システムプロンプト

各チャンネルは独自のシステムプロンプトを持てます。Discordコマンドで設定できます:

```
!prompt set あなたは親切なアシスタントです。
!prompt show
!prompt clear
```

### ダウンロード / アップロード

システムプロンプトはファイルとしてダウンロード・アップロードすることもできます:

- **ダウンロード**: `!prompt download` で現在のシステムプロンプトを `GEMINI.md` としてダウンロード
- **アップロード**: `GEMINI.md` という名前のファイルをチャンネルにアップロードすると、ボットが自動的にシステムプロンプトを更新

長いプロンプトをお気に入りのテキストエディタで編集したい場合に便利です。

システムプロンプトは`history/{channel_id}/GEMINI.md`に保存されます。

---

## Conversation History

Conversation history is persisted per channel using Git in the `history/` directory.

- Each channel has its own Git repository
- History survives bot restarts
- Branch/merge support for conversation forking
- Export to Markdown with `!history export`

## 会話履歴

会話履歴は`history/`ディレクトリにGitで永続化されます。

- 各チャンネルが独自のGitリポジトリを持つ
- 再起動後も履歴が保持される
- ブランチ・マージで会話を分岐可能
- `!history export`でMarkdownにエクスポート

---

## i18n

The bot supports multiple languages. Default languages are Japanese (`ja`) and English (`en`).

### Change Language

```
!lang ja    # Japanese
!lang en    # English
```

### Add New Language

Create a new JSON file in `locales/` directory (e.g., `locales/de.json`).
The bot will automatically detect and enable the new language.

Language settings are stored in `history/config.json`.

## 多言語対応

ボットは多言語に対応しています。デフォルトは日本語（`ja`）と英語（`en`）です。

### 言語変更

```
!lang ja    # 日本語
!lang en    # English
```

### 新しい言語の追加

`locales/`ディレクトリに新しいJSONファイル（例: `locales/de.json`）を作成してください。
ボットは自動的に新しい言語を検出して有効化します。

言語設定は`history/config.json`に保存されます。

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
```

## 設定ファイル

グローバル設定は`history/config.json`に保存されます:

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
```

---

## Project Structure

```
gemini_discord/
├── bot.py              # Main entry point
├── cogs/
│   └── commands.py     # Discord commands
├── history_manager.py  # Git-based history management
├── i18n.py             # Internationalization
├── locales/
│   ├── ja.json         # Japanese translations
│   └── en.json         # English translations
├── history/            # Conversation data (git-ignored)
│   ├── config.json     # Global settings
│   └── {channel_id}/   # Per-channel data
│       ├── .git/       # Git repository
│       ├── conversation.json  # Conversation history
│       └── GEMINI.md   # System prompt
└── .env                # Environment variables (git-ignored)
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
WorkingDirectory=/path/to/gemini_discord
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

## systemd サービスとして実行

Linux でバックグラウンドサービスとしてボットを実行するには、systemd ユニットファイルを作成します。

### 1. サービスファイルの作成

```bash
sudo nano /etc/systemd/system/gem-bot.service
```

以下の内容を追加（パスとユーザー名は環境に合わせて変更）:

```ini
[Unit]
Description=Gemini Discord Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/gemini_discord
ExecStart=/home/your_username/.local/bin/uv run python bot.py
Restart=always
RestartSec=10
Environment=PATH=/home/your_username/.local/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
```

### 2. サービスの有効化と起動

```bash
# systemd をリロード
sudo systemctl daemon-reload

# 起動時に自動起動
sudo systemctl enable gem-bot

# サービスを開始
sudo systemctl start gem-bot

# 状態を確認
sudo systemctl status gem-bot
```

### 3. ログの確認

```bash
# 最近のログを表示
sudo journalctl -u gem-bot -n 50

# リアルタイムでログを追跡
sudo journalctl -u gem-bot -f
```

### 4. サービスの管理

```bash
# 停止
sudo systemctl stop gem-bot

# 再起動
sudo systemctl restart gem-bot

# 自動起動を無効化
sudo systemctl disable gem-bot
```

---

## Project Structure

```
gemini_discord/
├── bot.py              # エントリーポイント
├── cogs/
│   └── commands.py     # コマンド定義
├── history_manager.py  # 履歴管理
├── i18n.py             # 多言語対応
├── locales/
│   ├── ja.json         # 日本語
│   └── en.json         # 英語
├── history/            # 会話データ（git管理外）
│   ├── config.json     # グローバル設定
│   └── {channel_id}/   # チャンネル別データ
│       ├── .git/       # Gitリポジトリ
│       ├── conversation.json  # 会話履歴
│       └── GEMINI.md   # システムプロンプト
└── .env                # 環境変数（git管理外）
```
