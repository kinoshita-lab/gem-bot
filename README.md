# Gemini Discord Bot

Discord上でGemini APIを使用してAIと会話できるボットです。

## セットアップ

### 1. 環境変数の設定

`.env.example`を`.env`にコピーして、必要な値を設定します：

```bash
cp .env.example .env
```

| 環境変数 | 必須 | 説明 |
|---------|------|------|
| `GEMINI_API_KEY` | ✅ | Google AI Studio から取得したAPIキー |
| `DISCORD_BOT_TOKEN` | ✅ | Discord Developer Portal から取得したボットトークン |
| `GEMINI_MODEL` | ❌ | 使用するGeminiモデル（デフォルト: `gemini-2.5-flash`） |
| `GEMINI_CHANNEL_ID` | ❌ | 自動応答を有効にするチャンネルID（カンマ区切りで複数指定可） |

### 2. 依存関係のインストール

```bash
uv sync
```

### 3. ボットの起動

```bash
uv run python bot.py
```

## 使い方

### `!ask` コマンド

どのチャンネルでも `!ask` コマンドを使ってGeminiに質問できます：

```
!ask Pythonのリスト内包表記について教えてください
```

### 自動応答モード

`GEMINI_CHANNEL_ID` を設定すると、指定したチャンネルでは `!ask` コマンドなしで、メッセージを送信するとGeminiが自動的に応答します。

```bash
# 単一チャンネル
GEMINI_CHANNEL_ID=123456789012345678

# 複数チャンネル（カンマ区切り）
GEMINI_CHANNEL_ID=123456789012345678,987654321098765432
```

### チャンネルIDの取得方法

1. Discordの設定 > 詳細設定 > 「開発者モード」を有効化
2. チャンネルを右クリック > 「IDをコピー」

## システムプロンプト

`GEMINI.md` ファイルにシステムプロンプトを記載することで、Geminiの振る舞いをカスタマイズできます。

## 会話履歴

各チャンネルごとに会話履歴が保持されます（ボット再起動でリセット）。
