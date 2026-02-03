# Gemini Discord Bot

Discord上でGemini APIを使用してAIと会話できるボットです。


---

## 機能

- **Git による会話の分岐** - コードのように会話をブランチ、マージ、フォーク可能。
- **チャンネルベースの会話** - 指定したチャンネルの全メッセージに応答
- **モデル切り替え** - おすすめモデルを先頭に表示し、実行時に変更可能
- **画像生成** - テキストプロンプトから画像を生成
- **画像分析** - メッセージと一緒に画像をアップロードしてAI分析
- **永続的な履歴** - 会話履歴は Git リポジトリに保存され、再起動後も保持、バージョン管理が可能
- **2階層システムプロンプト** - グローバルマスター指示書 + チャンネルごとのカスタマイズで柔軟なAI動作
- **生成設定** - temperature、top_p などのパラメータをチャンネルごとに設定
- **Markdownエクスポート** - 会話履歴をMarkdownファイルと画像をZIPでエクスポート
- **多言語対応** - 日本語/英語（拡張可能）
- **Googleカレンダー連携** - 自然言語でカレンダーイベントを管理
- **Google Tasks連携** - 自然言語でTODOリストを管理
- **LaTeX数式レンダリング** - 数式を自動的に画像としてレンダリング


---

## システムプロンプト

ボットは2階層のプロンプトシステムを使用し、柔軟にAIの動作をカスタマイズできます:

### マスター指示書（全体共通）

マスター指示書は**全チャンネル**に適用され、ボットの基本的な性格と動作を定義します。

**保存場所**: `history/project/GEMINI.md`（別Gitリポジトリで管理）

**管理方法**:
- **表示**: `/gem system-prompt show` - 現在のマスター指示書を表示
- **ダウンロード**: `/gem system-prompt download` - `GEMINI.md` ファイルとしてダウンロードして編集
- **編集**: `GEMINI.md` という名前のファイルを任意のチャンネルにアップロードして更新（自動コミット）

**記述例**:
```
あなたはソフトウェア開発に特化した、親切でプロフェッショナルなAIアシスタントです。

ガイドライン:
- 常に明確でコメント付きのコード例を提供してください
- 技術的な概念をわかりやすく説明してください
- 簡潔かつ徹底的に答えてください
- 読みやすさのためにマークダウン形式を使用してください
```

**使用例**:
- ボットの基本的な性格を定義（例: 「あなたは親切なプログラミングアシスタントです」）
- 組織全体のガイドラインやポリシーを設定
- デフォルトの応答スタイルとトーンを設定

**Git管理**: `history/project` リポジトリに自動コミットされます。

### チャンネル個別指示

各チャンネルは、マスター指示書を**拡張**する独自の追加指示を持つことができます。

**保存場所**: `history/{channel_id}/channel_instruction.md`（チャンネルごとにGit管理）

**管理方法**:
- **表示**: `/gem channel-prompt show` - 現在のチャンネル指示書を表示
- **ダウンロード**: `/gem channel-prompt download` - `channel_instruction.md` としてダウンロード
- **編集**: `channel_instruction.md` という名前のファイルをチャンネルにアップロード
- **削除**: `/gem channel-prompt clear` - チャンネル指示書を削除

**記述例**（Pythonチャンネル向け）:
```
このチャンネルはPythonプログラミングの議論専用です。

追加ガイドライン:
- Python 3.10+ の機能とベストプラクティスに焦点を当ててください
- 型ヒントと適切なドキュメントを推奨してください
- テスト例には pytest を提案してください
- PEP 8 スタイルガイドラインに従ってください
```

**使用例**:
- チャンネル固有のコンテキストを追加（例: 「このチャンネルはPythonの議論専用です」）
- 特定の用途向けに動作を上書きまたは拡張
- 一時的なプロジェクト固有の指示を設定

**Git管理**: 変更のたびに自動コミット。詳細は [Git バージョン管理](#git-バージョン管理) を参照。

### プロンプトの結合方法

Geminiに送信される最終的なプロンプトは以下のように構成されます:

```
[マスター指示書]

[チャンネル指示書]

[ユーザーメッセージ]
```

**例**:
- **マスター**: 「あなたは親切なアシスタントです。常に簡潔に答えてください。」
- **チャンネル**（#python-helpチャンネル）: 「Pythonのベストプラクティスに焦点を当て、コード例を提供してください。」
- **結果**: #python-helpチャンネルでは、ボットは簡潔で親切、かつPythonに特化したコード例を含む応答をします。

**注意**: チャンネル指示書が設定されていない場合は、マスター指示書のみが使用されます。


---

## Git バージョン管理

### Git で管理されるもの

ボットは**チャンネル固有のデータのみ**を自動的にGitでバージョン管理します。各チャンネルは独立したGitリポジトリを持ちます。

#### Git管理対象ファイル（チャンネルごと）

`history/{channel_id}/` に配置:

- **`conversation.json`** - 完全な会話履歴
  - メッセージ交換の後に毎回コミット
  - 会話の分岐と履歴追跡を可能にする
  
- **`channel_instruction.md`** - チャンネル固有の指示書
  - ファイルアップロードまたは `/gem channel-prompt clear` で更新時にコミット
  - ブランチを通じて以前の指示書に戻すことが可能
  
- **`files/`** - 画像添付ファイル
  - 会話内で画像がアップロードされた際にコミット
  - ブランチ間で保持される

#### プロジェクトデータ（グローバルGitリポジトリ）

`history/project/` に配置:

- **`GEMINI.md`** - マスター指示書
  - ファイルアップロードで更新時に自動コミット
  - チャンネル履歴とは別のGitリポジトリで管理

#### Git管理対象外ファイル

- **`history/config.json`** - グローバルボット設定
  - チャンネルのモデルと生成設定を含む
  - ボットコマンド（`/gem model`, `/gem config`）で管理

- **`history/tokens/`** - Google OAuth トークン
  - セキュリティ: バージョン管理すべきではない

- **`.env`** - 環境変数（APIキー、トークン）
  - セキュリティ: バージョン管理すべきではない

- **`credentials.json`** - Google OAuth 認証情報
  - セキュリティ: バージョン管理すべきではない

### この設計の理由

**チャンネル固有データ（Git管理）**:
- `/gem branch` コマンドで会話を分岐可能
- `/gem history` コマンドで完全な履歴追跡を提供
- 完全なコンテキスト付きで会話をエクスポート可能
- 各チャンネルが独立して動作

**プロジェクトデータ（Git管理）**:
- **`GEMINI.md`**: マスタープロンプトのバージョン管理のため `history/project` リポジトリで管理

**設定/機密情報（Git管理外）**:
- **設定/機密情報**: セキュリティのベストプラクティス - 認証情報はコミットしない
- **グローバル設定**: 全チャンネルでボットが自動管理

### 自動 Git 操作

ボットは以下の変更を自動的にコミットします:

1. **会話の更新**
   - ユーザーメッセージとボット応答の後
   - コミットメッセージ: `"Update conversation"`

2. **チャンネル指示書の変更**
   - `channel_instruction.md` をアップロードした時
   - `/gem channel-prompt clear` を使用した時
   - コミットメッセージ: `"Update channel instruction"`, `"Initialize empty channel instruction"`

3. **マスター指示書の変更**
    - `GEMINI.md` をアップロードした時
    - コミットメッセージ: `"Update master instruction"`

4. **ブランチ操作**
   - 切り替え前の自動保存: `"Auto-save before branch switch"`
   - マージの記録: `"Merge branch 'ブランチ名'"`

### ブランチワークフロー

各チャンネルリポジトリは会話の分岐のためGitブランチをサポート:

**使用例**: 現在の会話を失わずに異なるアプローチを探索したい。

```
メイン会話（mainブランチ）
├─ 現在の議論を継続
└─ ブランチ "experiment" を作成 → 別のアプローチを試す
   ├─ 成功した場合 → mainにマージ
   └─ 成功しなかった場合 → mainに戻る（experimentは保持）
```

**利用可能なコマンド**:
- `/gem branch list` - すべてのブランチを表示
- `/gem branch create <名前>` - 会話をフォーク
- `/gem branch switch <名前>` - アクティブブランチを変更
- `/gem branch merge <名前>` - ブランチを結合
- `/gem branch delete <名前>` - ブランチを削除

### 保存構造

```
history/
├── config.json                      # グローバル設定（Git管理外）
├── tokens/                          # OAuth トークン（Git管理外）
├── project/                         # プロジェクトデータ（Gitリポジトリ）
│   ├── .git/
│   └── GEMINI.md                    # マスター指示書（Git管理）
└── {channel_id}/                    # チャンネルごと（Gitリポジトリ）
    ├── .git/                        # Git メタデータ
    ├── conversation.json            # 会話履歴（Git管理）
    ├── channel_instruction.md       # チャンネルプロンプト（Git管理）
    └── files/                       # 画像（Git管理）
        └── img_20240130_123456_001.png
```

### メリット

1. **会話のバージョン管理**: すべてのメッセージが完全な履歴とともに追跡される
2. **実験**: コンテキストを失わずにアイデアを試すためにブランチを作成
3. **ロールバック**: ブランチを切り替えて以前の会話状態に戻る
4. **エクスポート**: `/gem history export` でMarkdown形式でエクスポート
5. **独立性**: 各チャンネルの履歴は分離されている


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

### LaTeX のインストール（オプション - 数式レンダリング用）

数式を画像としてレンダリングするには LaTeX が必要です。インストールしなくてもボットは動作しますが、数式はテキストのみで表示されます。

**Windows:**
1. [MiKTeX](https://miktex.org/download) をダウンロードしてインストール
2. インストール中に「Install missing packages on-the-fly: Yes」を選択
3. インストール後、MiKTeX Console を開いて `standalone` パッケージをインストール

**macOS:**
```bash
# Homebrew を使用
brew install --cask mactex-no-gui

# または BasicTeX（小さい、約100MB）
brew install --cask basictex
# 必要なパッケージをインストール
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
cd gem-bot
uv sync
```

### 2. 環境変数の設定

`.env.example`を`.env`にコピーして設定:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
GEMINI_API_KEY=your_gemini_api_key_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
GEMINI_CHANNEL_ID=123456789012345678
DISCORD_GUILD_ID=your_guild_id_here
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

### LaTeX のインストール（オプション - 数式レンダリング用）

数式を画像としてレンダリングするには LaTeX が必要です。インストールしなくてもボットは動作しますが、数式はテキストのみで表示されます。

**Windows:**
1. [MiKTeX](https://miktex.org/download) をダウンロードしてインストール
2. インストール中に「Install missing packages on-the-fly: Yes」を選択
3. インストール後、MiKTeX Console を開いて `standalone` パッケージをインストール

**macOS:**
```bash
# Homebrew を使用
brew install --cask mactex-no-gui

# または BasicTeX（小さい、約100MB）
brew install --cask basictex
# 必要なパッケージをインストール
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
8. スコープを選択: `bot`, `applications.commands`
9. ボット権限を選択: `Send Messages`, `Read Message History`, `Attach Files`
10. 生成された URL をコピーして開き、ボットをサーバーに招待

---

## セットアップ

### 1. クローンとインストール

```bash
git clone <repository-url>
cd gem-bot
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
DISCORD_GUILD_ID=your_guild_id_here
```

| 変数 | 必須 | 説明 |
|------|------|------|
| `GEMINI_API_KEY` | Yes | Google AI Studio の API キー |
| `DISCORD_BOT_TOKEN` | Yes | Discord Developer Portal の Bot トークン |
| `GEMINI_CHANNEL_ID` | Yes | ボットが応答するチャンネルID（カンマ区切り） |
| `DISCORD_GUILD_ID` | No | スラッシュコマンドの即時同期用ギルドID（開発用） |

### 3. ボットの起動

```bash
uv run python bot.py
```

ボットがオンラインになると、設定されたチャンネルにメッセージが送信されます。


---

## コマンド

すべてのコマンドは `/gem` グループ配下のスラッシュコマンドです。

### 一般

| コマンド | 説明 |
|---------|------|
| `/gem info` | ボット情報を表示 |
| `/gem lang [code]` | 表示言語を変更 |

### モデル

| コマンド | 説明 |
|---------|------|
| `/gem model list` | 利用可能なモデル一覧 |
| `/gem model set` | モデルを選択肢から変更 |

### 画像生成

| コマンド | 説明 |
|---------|------|
| `/gem image <プロンプト>` | テキストから画像を生成 |

### 生成設定

| コマンド | 説明 |
|---------|------|
| `/gem config show` | 現在の生成設定を表示 |
| `/gem config set <キー> <値>` | 生成パラメータを設定 |
| `/gem config reset [キー]` | 設定をリセット |

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
| `/gem history list [開始] [件数]` | 履歴を番号付きで一覧表示 |
| `/gem history delete <番号>` | 指定した番号のメッセージを削除 |
| `/gem history clear` | 会話履歴を全て削除 |
| `/gem history export [ファイル名]` | 履歴をMarkdownでエクスポート（画像はZIP） |

### ブランチ管理

| コマンド | 説明 |
|---------|------|
| `/gem branch list` | ブランチ一覧を表示 |
| `/gem branch create <名前>` | 新しいブランチを作成して切り替え |
| `/gem branch switch <名前>` | 指定したブランチに切り替え |
| `/gem branch merge <名前>` | ブランチをマージ |
| `/gem branch delete <名前>` | ブランチを削除 |

### ツールモード

| コマンド | 説明 |
|---------|------|
| `/gem mode set [モード]` | ツールモードを変更（default/calendar/todo） |

### Google連携

| コマンド | 説明 |
|---------|------|
| `/gem google link` | Googleアカウントを連携 |
| `/gem google unlink` | Googleアカウントの連携を解除 |
| `/gem google status` | Google連携状態を確認 |

### プロンプト管理

| コマンド | 説明 |
|---------|------|
| `/gem system-prompt show` | マスター指示書を表示 |
| `/gem system-prompt download` | マスター指示書をダウンロード |
| `/gem channel-prompt show` | チャンネル指示書を表示 |
| `/gem channel-prompt download` | チャンネル指示書をダウンロード |
| `/gem channel-prompt clear` | チャンネル指示書を削除 |

---

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

## システムプロンプト (マスター)

マスター指示書は全チャンネルに適用されます。以下の方法で管理できます:

- **表示**: `/gem system-prompt show` で現在のマスター指示書を表示
- **ダウンロード**: `/gem system-prompt download` でファイルとしてダウンロード
- **編集**: `GEMINI.md` という名前のファイルを任意のチャンネルにアップロードして更新

### チャンネル個別指示

各チャンネルは独自の追加指示を持つことができます。

- **表示**: `/gem channel-prompt show` で現在のチャンネル指示書を表示
- **ダウンロード**: `/gem channel-prompt download` でファイルとしてダウンロード
- **編集**: `channel_instruction.md` という名前のファイルをチャンネルにアップロード
- **削除**: `/gem channel-prompt clear` でチャンネル指示書を削除

システムプロンプトは `[マスター指示書] + [チャンネル指示書]` の形で結合されます。

---

## 会話履歴

会話履歴は`history/`ディレクトリにGitでチャンネルごとに永続化されます。

- 各チャンネルが独自のGitリポジトリを持つ
- 再起動後も履歴が保持される
- ブランチ・マージで会話を分岐可能
- `/gem history export`でMarkdownにエクスポート
- 自動コミットによる完全なGit履歴

Git操作とバージョン管理の詳細については、[Git バージョン管理](#git-バージョン管理) を参照してください。

---

## Google連携（カレンダー / Tasks）

ボットは自然言語でGoogleカレンダーとGoogle Tasksを操作できます。

### Google連携のセットアップ

1. [Google Cloud Console](https://console.cloud.google.com/) でプロジェクトを作成
2. Google Calendar API と Google Tasks API を有効化
3. OAuth 2.0認証情報を作成（デスクトップアプリケーション）
4. 認証情報ファイルをダウンロードし、プロジェクトルートに `credentials.json` として保存
5. `/gem google link` でGoogleアカウントを連携

### カレンダーモードの使用

```
/gem mode set calendar
```

カレンダーモードでは以下が可能:
- 予定の一覧表示
- 新しい予定の作成
- 既存の予定の更新
- 予定の削除

例: 「明日の予定を教えて」

### TODOモードの使用

```
/gem mode set todo
```

TODOモードでは以下が可能:
- タスクリストの一覧表示
- 特定のリストのタスク一覧
- 新しいタスクの作成
- タスクの完了マーク
- タスクの削除

例: 「買い物リストに『牛乳を買う』を追加して」

---

## 多言語対応

ボットは多言語に対応しています。デフォルトは日本語（`ja`）と英語（`en`）です。

### 言語変更

```
/gem lang ja    # 日本語
/gem lang en    # English
```

### 新しい言語の追加

`locales/`ディレクトリに新しいJSONファイル（例: `locales/de.json`）を作成してください。
ボットは自動的に新しい言語を検出して有効化します。

言語設定は`history/config.json`に保存されます。

---

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

---

## プロジェクト構造

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
WorkingDirectory=/path/to/gem-bot
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
