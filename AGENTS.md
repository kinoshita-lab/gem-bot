# AGENTS.md

このファイルはAIコーディングエージェント向けのガイドラインです。

## 重要なルール

**明示的に指示があるまで、コミットすることを禁止します。ユーザーが動作を確認する必要があります。**

## プロジェクト概要

Discord上でGemini APIを使用してAIと会話できるボットです。

## 技術スタック

- Python 3.13+
- discord.py (Discord Bot フレームワーク)
- google-genai (Gemini API クライアント)
- uv (パッケージマネージャー)

## プロジェクト構造

```
gemini_discord/
├── bot.py              # エントリーポイント、GeminiBotクラス、イベントハンドラ
├── cogs/
│   ├── __init__.py
│   └── commands.py     # Discordコマンド (!ask, !info, !model)
├── GEMINI.md           # Geminiのシステムプロンプト
├── .env                # 環境変数 (git管理外)
└── .env.example        # 環境変数のテンプレート
```

## アーキテクチャ

### GeminiBotクラス (bot.py)

`commands.Bot`を継承したカスタムクラス。以下の状態を保持：

- `gemini_client`: Gemini APIクライアント
- `default_model`: デフォルトのモデル名（チャンネル設定がない場合に使用）
- `pending_model_selections`: モデル選択の対話状態
- `conversation_history`: チャンネルごとの会話履歴
- `history_manager`: Git管理された会話履歴・設定のマネージャー

モデル設定はチャンネルごとに `history/{channel_id}/config.json` で管理される。

### Cog (cogs/commands.py)

discord.pyのCog機能を使用してコマンドを分離。新しいコマンドを追加する場合はこのファイルに追加する。

## コーディング規約

### 非同期処理

- Gemini APIの呼び出しは必ず**非同期版** (`client.aio.models.xxx`) を使用する
- 同期版を使用するとDiscordのハートビートがブロックされ、接続が切断される

```python
# Good
response = await self.gemini_client.aio.models.generate_content(...)

# Bad - イベントループをブロックする
response = self.gemini_client.models.generate_content(...)
```

### コマンドの追加

新しいコマンドは `cogs/commands.py` の `Commands` クラスに追加する：

```python
@commands.command(name="newcommand")
async def newcommand(self, ctx: commands.Context):
    """コマンドの説明"""
    # self.bot でGeminiBotインスタンスにアクセス可能
    pass
```

### 共有状態へのアクセス

Cogからは `self.bot` を通じて共有状態にアクセスする：

- `self.bot.get_model(channel_id)`: チャンネルのモデルを取得
- `self.bot.set_model(channel_id, model)`: チャンネルのモデルを設定
- `self.bot.default_model`: デフォルトモデル
- `self.bot.gemini_client`
- `self.bot.conversation_history`
- `self.bot.pending_model_selections`

## 開発コマンド

```bash
# 依存関係のインストール
uv sync

# ボットの起動
uv run python bot.py

# 構文チェック
python -m py_compile bot.py cogs/commands.py
```

## 環境変数

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `DISCORD_BOT_TOKEN` | Yes | Discord Botトークン |
| `GEMINI_API_KEY` | Yes | Gemini APIキー |
| `GEMINI_MODEL` | No | デフォルトモデル (デフォルト: gemini-2.5-flash)。チャンネルごとの設定がない場合に使用される |
| `GEMINI_CHANNEL_ID` | No | 自動応答チャンネルID (カンマ区切りで複数可) |

## 注意事項

- `.env` ファイルはgit管理外。APIキーやトークンをコミットしないこと
- Discord メッセージは2000文字制限があるため、`send_response`で自動分割される
- 会話履歴はメモリ上に保持され、ボット再起動でリセットされる
