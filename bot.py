import os
from datetime import datetime

import discord
from discord.ext import commands
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_CHANNEL_ID = os.getenv("GEMINI_CHANNEL_ID")
# Current model (can be changed at runtime via !model set)
current_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Pending model selections: user_id -> list of model names
pending_model_selections: dict[int, list[str]] = {}

# Check for required environment variables
if not DISCORD_TOKEN:
    print("Error: DISCORD_BOT_TOKEN environment variable not set.")
    exit(1)

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    exit(1)

# Parse GEMINI_CHANNEL_ID (can be comma-separated for multiple channels)
gemini_channel_ids: set[int] = set()
if GEMINI_CHANNEL_ID:
    for channel_id_str in GEMINI_CHANNEL_ID.split(","):
        channel_id_str = channel_id_str.strip()
        if channel_id_str:
            try:
                gemini_channel_ids.add(int(channel_id_str))
            except ValueError:
                print(
                    f"Warning: Invalid channel ID '{channel_id_str}' in GEMINI_CHANNEL_ID"
                )

# Load system prompt from GEMINI.md
try:
    with open("GEMINI.md", "r", encoding="utf-8") as f:
        system_prompt = f.read()
except FileNotFoundError:
    print("Warning: GEMINI.md not found. Using empty system prompt.")
    system_prompt = ""

# Initialize Gemini Client with 5-minute timeout
client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(timeout=300000),  # 5 minutes in milliseconds
)

# Conversation history per channel
conversation_history: dict[int, list] = {}

# Initialize Discord Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    if gemini_channel_ids:
        print(f"Gemini auto-response enabled for channels: {gemini_channel_ids}")
    else:
        print("Gemini auto-response disabled (GEMINI_CHANNEL_ID not set)")


async def send_response(channel, response_text: str):
    """Send a response to a channel, splitting if necessary."""
    # Discord has a 2000 character limit per message.
    if len(response_text) > 2000:
        for i in range(0, len(response_text), 2000):
            await channel.send(response_text[i : i + 2000])
    else:
        await channel.send(
            response_text if response_text else "No response from Gemini."
        )


async def ask_gemini(channel_id: int, prompt: str) -> str:
    """Send a prompt to Gemini and return the response."""
    # Initialize conversation history for this channel if not exists
    if channel_id not in conversation_history:
        conversation_history[channel_id] = []

    # Add current time prefix to the prompt
    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
    prompt_with_time = f"今の時間は {current_time} です。\n{prompt}"

    # Add user's message to history
    conversation_history[channel_id].append(
        types.Content(role="user", parts=[types.Part.from_text(text=prompt_with_time)])
    )

    try:
        response = client.models.generate_content(
            model=current_model,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
            contents=conversation_history[channel_id],
        )
        response_text = response.text or ""

        # Add model's response to history
        conversation_history[channel_id].append(
            types.Content(
                role="model", parts=[types.Part.from_text(text=response_text)]
            )
        )

        return response_text
    except Exception as e:
        # Remove the last user message from history if an error occurred
        if conversation_history[channel_id]:
            conversation_history[channel_id].pop()
        raise e


@bot.event
async def on_message(message):
    """Handle incoming messages."""
    global current_model

    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    user_id = message.author.id

    # Check if this user has a pending model selection
    if user_id in pending_model_selections:
        content = message.content.strip().lower()

        # Handle cancel
        if content == "cancel":
            del pending_model_selections[user_id]
            await message.channel.send("モデル選択をキャンセルしました。")
            return

        # Handle number selection
        if content.isdigit():
            index = int(content) - 1
            model_names = pending_model_selections[user_id]

            if 0 <= index < len(model_names):
                current_model = model_names[index]
                del pending_model_selections[user_id]
                await message.channel.send(
                    f"モデルを **{current_model}** に変更しました。"
                )
                return
            else:
                await message.channel.send(
                    f"無効な番号です。1 から {len(model_names)} の数字を入力してください。\n`cancel` でキャンセルできます。"
                )
                return

        # Invalid input - prompt again
        await message.channel.send("数字または `cancel` を入力してください。")
        return

    # Check if the message is a command (starts with prefix)
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    # Check if the message is in a Gemini-enabled channel
    if gemini_channel_ids and message.channel.id in gemini_channel_ids:
        # Auto-respond to all messages in Gemini-enabled channels
        async with message.channel.typing():
            try:
                response_text = await ask_gemini(message.channel.id, message.content)
                await send_response(message.channel, response_text)
            except Exception as e:
                await message.channel.send(f"An error occurred: {e}")


@bot.command(name="ask")
async def ask(ctx, *, prompt):
    """Asks Gemini a question."""
    async with ctx.typing():
        try:
            response_text = await ask_gemini(ctx.channel.id, prompt)
            await send_response(ctx.channel, response_text)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")


@bot.command(name="info")
async def info(ctx):
    """Displays information about the bot."""
    embed = discord.Embed(title="Bot Information", color=discord.Color.blue())
    embed.add_field(name="Model", value=current_model, inline=False)
    await ctx.send(embed=embed)


@bot.group(name="model")
async def model(ctx):
    """Model management commands."""
    if ctx.invoked_subcommand is None:
        await ctx.send(
            "使用方法:\n`!model list` - 利用可能なモデル一覧を表示\n`!model set` - 使用するモデルを変更"
        )


@model.command(name="list")
async def model_list(ctx):
    """Lists all available Gemini models."""
    async with ctx.typing():
        try:
            models = list(client.models.list())

            # Create embed for model list
            embed = discord.Embed(
                title="利用可能な Gemini モデル",
                description=f"現在使用中: **{current_model}**",
                color=discord.Color.green(),
            )

            # Group models by base name and show them
            model_names: list[str] = []
            for m in models:
                # Extract model name (e.g., "models/gemini-2.0-flash" -> "gemini-2.0-flash")
                name = m.name
                if name:
                    if name.startswith("models/"):
                        name = name.replace("models/", "")
                    model_names.append(name)

            # Sort model names
            model_names.sort()

            # Split into chunks if too many models
            chunk_size = 20
            for i in range(0, len(model_names), chunk_size):
                chunk = model_names[i : i + chunk_size]
                field_name = (
                    "モデル一覧"
                    if i == 0
                    else f"モデル一覧 (続き {i // chunk_size + 1})"
                )
                embed.add_field(
                    name=field_name,
                    value="\n".join(f"• {name}" for name in chunk),
                    inline=False,
                )

            embed.set_footer(text=f"合計: {len(model_names)} モデル")
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"モデル一覧の取得中にエラーが発生しました: {e}")


@model.command(name="set")
async def model_set(ctx):
    """Interactively set the Gemini model to use."""
    global pending_model_selections

    user_id = ctx.author.id

    async with ctx.typing():
        try:
            # Fetch available models
            models = list(client.models.list())
            model_names: list[str] = []
            for m in models:
                name = m.name
                if name:
                    if name.startswith("models/"):
                        name = name.replace("models/", "")
                    model_names.append(name)

            # Sort model names
            model_names.sort()

            # Register pending selection (overwrites any previous selection for this user)
            pending_model_selections[user_id] = model_names

            # Create numbered list
            model_list_text = "\n".join(
                f"{i + 1}. {name}" for i, name in enumerate(model_names)
            )

            # Send selection prompt
            embed = discord.Embed(
                title="モデルを選択してください",
                description=f"現在使用中: **{current_model}**\n\n番号を入力してモデルを選択してください。\n`cancel` でキャンセルできます。",
                color=discord.Color.blue(),
            )

            # Split into chunks if too many models
            chunk_size = 25
            for i in range(0, len(model_names), chunk_size):
                chunk = model_names[i : i + chunk_size]
                field_name = "モデル一覧" if i == 0 else f"モデル一覧 (続き)"
                field_value = "\n".join(
                    f"`{i + j + 1}`. {name}" for j, name in enumerate(chunk)
                )
                embed.add_field(name=field_name, value=field_value, inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"モデル一覧の取得中にエラーが発生しました: {e}")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
