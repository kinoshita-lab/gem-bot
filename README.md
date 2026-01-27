# Gemini Discord Bot

A Discord bot that enables AI conversations using the Gemini API.

Discord上でGemini APIを使用してAIと会話できるボットです。

---

## Features

- **Channel-based conversation** - Responds to all messages in specified channels
- **Model switching** - Change Gemini models at runtime with recommended models shown first
- **Image generation** - Generate images from text prompts using Gemini
- **Conversation history** - Git-based persistent history with branch/merge support
- **Channel-specific system prompts** - Customize AI behavior per channel via Discord commands
- **Generation config** - Customize temperature, top_p, and other parameters per channel
- **i18n support** - Multi-language support (Japanese/English by default, extensible)

## 機能

- **チャンネルベースの会話** - 指定したチャンネルの全メッセージに応答
- **モデル切り替え** - おすすめモデルを先頭に表示し、実行時に変更可能
- **画像生成** - テキストプロンプトから画像を生成
- **会話履歴** - Gitベースの永続化、ブランチ・マージ対応
- **チャンネル別システムプロンプト** - Discordコマンドでチャンネルごとにカスタマイズ
- **生成設定** - temperature、top_p などのパラメータをチャンネルごとに設定
- **多言語対応** - 日本語/英語（拡張可能）

---

## Setup

### 1. Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | API key from Google AI Studio |
| `DISCORD_BOT_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `GEMINI_CHANNEL_ID` | Yes | Channel IDs for bot responses (comma-separated) |

### 2. Install Dependencies

```bash
uv sync
```

### 3. Start the Bot

```bash
uv run python bot.py
```

## セットアップ

### 1. 環境変数の設定

`.env.example`を`.env`にコピーして設定:

```bash
cp .env.example .env
```

| 変数 | 必須 | 説明 |
|------|------|------|
| `GEMINI_API_KEY` | Yes | Google AI Studio の API キー |
| `DISCORD_BOT_TOKEN` | Yes | Discord Developer Portal の Bot トークン |
| `GEMINI_CHANNEL_ID` | Yes | ボットが応答するチャンネルID（カンマ区切り） |

### 2. 依存関係のインストール

```bash
uv sync
```

### 3. ボットの起動

```bash
uv run python bot.py
```

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

System prompts are stored in `history/{channel_id}/GEMINI.md`.

## システムプロンプト

各チャンネルは独自のシステムプロンプトを持てます。Discordコマンドで設定できます:

```
!prompt set あなたは親切なアシスタントです。
!prompt show
!prompt clear
```

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

## プロジェクト構造

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
