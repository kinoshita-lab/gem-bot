# Gemini Discord Bot

Discord上でGemini APIを使用してAIと会話できるボットです。

A Discord bot that enables AI conversations using the Gemini API.

---

## Features / 機能

- **Auto-response mode** - Automatically responds to messages in specified channels
- **Model switching** - Change Gemini models at runtime
- **Conversation history** - Git-based persistent history per channel
- **Channel-specific system prompts** - Customize AI behavior per channel
- **i18n support** - Multi-language support (Japanese/English by default, extensible)

---

## Setup / セットアップ

### 1. Environment Variables / 環境変数の設定

Copy `.env.example` to `.env` and configure:

`.env.example`を`.env`にコピーして設定:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | Yes | API key from Google AI Studio |
| `DISCORD_BOT_TOKEN` | Yes | Bot token from Discord Developer Portal |
| `GEMINI_MODEL` | No | Gemini model to use (default: `gemini-2.5-flash`) |
| `GEMINI_CHANNEL_ID` | No | Channel IDs for auto-response (comma-separated) |

### 2. Install Dependencies / 依存関係のインストール

```bash
uv sync
```

### 3. Start the Bot / ボットの起動

```bash
uv run python bot.py
```

---

## Commands / コマンド

| Command | Description |
|---------|-------------|
| `!help` | Show help message / ヘルプを表示 |
| `!info` | Show bot information / ボット情報を表示 |
| `!model list` | List available Gemini models / 利用可能なモデル一覧 |
| `!model set` | Interactively change the model / モデルを対話的に変更 |
| `!lang [code]` | Change display language / 表示言語を変更 |

---

## Auto-Response Mode / 自動応答モード

Set `GEMINI_CHANNEL_ID` to enable automatic responses in specified channels:

`GEMINI_CHANNEL_ID`を設定すると、指定チャンネルで自動応答が有効になります:

```bash
# Single channel / 単一チャンネル
GEMINI_CHANNEL_ID=123456789012345678

# Multiple channels / 複数チャンネル
GEMINI_CHANNEL_ID=123456789012345678,987654321098765432
```

### How to Get Channel ID / チャンネルIDの取得方法

1. Enable Developer Mode in Discord Settings > Advanced
2. Right-click a channel > "Copy ID"

---

## System Prompts / システムプロンプト

Each channel can have its own system prompt stored in `history/{channel_id}/GEMINI.md`.

各チャンネルは`history/{channel_id}/GEMINI.md`に独自のシステムプロンプトを持てます。

---

## Conversation History / 会話履歴

Conversation history is persisted per channel using Git in the `history/` directory.

会話履歴は`history/`ディレクトリにGitで永続化されます。

- Each channel has its own Git repository
- History survives bot restarts
- Stored in `history/{channel_id}/conversation.json`

---

## i18n / 多言語対応

The bot supports multiple languages. Default languages are Japanese (`ja`) and English (`en`).

ボットは多言語に対応しています。デフォルトは日本語（`ja`）と英語（`en`）です。

### Change Language / 言語変更

```
!lang ja    # 日本語
!lang en    # English
```

### Add New Language / 新しい言語の追加

Create a new JSON file in `locales/` directory (e.g., `locales/de.json`).
The bot will automatically detect and enable the new language.

`locales/`ディレクトリに新しいJSONファイル（例: `locales/de.json`）を作成してください。
ボットは自動的に新しい言語を検出して有効化します。

Language settings are stored in `history/config.json`.

言語設定は`history/config.json`に保存されます。

---

## Project Structure / プロジェクト構造

```
gemini_discord/
├── bot.py              # Main entry point / エントリーポイント
├── cogs/
│   └── commands.py     # Discord commands / コマンド定義
├── history_manager.py  # Git-based history management / 履歴管理
├── i18n.py             # Internationalization / 多言語対応
├── locales/
│   ├── ja.json         # Japanese translations / 日本語
│   └── en.json         # English translations / 英語
├── history/            # Conversation data (git-ignored) / 会話データ
└── .env                # Environment variables (git-ignored) / 環境変数
```
