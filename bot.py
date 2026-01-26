import os

import discord
from discord.ext import commands
from google import genai
from google.genai import types
from dotenv import load_dotenv

from history_manager import HistoryManager

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_CHANNEL_ID = os.getenv("GEMINI_CHANNEL_ID")

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


class GeminiBot(commands.Bot):
    """Custom Bot class with Gemini integration."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Gemini client
        self.gemini_client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=300000),  # 5 minutes in milliseconds
        )

        # Current model (can be changed at runtime via !model set)
        self.current_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # Pending model selections: user_id -> list of model names
        self.pending_model_selections: dict[int, list[str]] = {}

        # Conversation history per channel
        self.conversation_history: dict[int, list] = {}

        # History manager for Git-based persistence
        self.history_manager = HistoryManager()

    async def setup_hook(self):
        """Load cogs when the bot starts."""
        await self.load_extension("cogs.commands")

        # Load existing conversation histories from disk
        self._load_histories_from_disk()

    def _load_histories_from_disk(self):
        """Load all conversation histories from disk on startup."""
        saved_conversations = self.history_manager.load_all_conversations()
        for channel_id, messages in saved_conversations.items():
            # Convert saved messages back to Gemini Content format
            history = []
            for msg in messages:
                history.append(
                    types.Content(
                        role=msg["role"],
                        parts=[types.Part.from_text(text=msg["content"])],
                    )
                )
            self.conversation_history[channel_id] = history
        print(f"Loaded conversation history for {len(saved_conversations)} channels")

    def _save_history_to_disk(self, channel_id: int):
        """Save conversation history for a channel to disk."""
        if channel_id not in self.conversation_history:
            return

        history = self.conversation_history[channel_id]
        messages = self.history_manager.convert_to_serializable(history)
        self.history_manager.save_conversation(
            channel_id=channel_id,
            messages=messages,
            model=self.current_model,
            auto_commit=True,
        )

    async def send_response(self, channel, response_text: str):
        """Send a response to a channel, splitting if necessary."""
        # Discord has a 2000 character limit per message.
        if len(response_text) > 2000:
            for i in range(0, len(response_text), 2000):
                await channel.send(response_text[i : i + 2000])
        else:
            await channel.send(
                response_text if response_text else "No response from Gemini."
            )

    async def ask_gemini(self, channel_id: int, prompt: str) -> str:
        """Send a prompt to Gemini and return the response."""
        # Initialize conversation history for this channel if not exists
        if channel_id not in self.conversation_history:
            self.conversation_history[channel_id] = []

        # Add user's message to history
        self.conversation_history[channel_id].append(
            types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
        )

        try:
            # Load channel-specific system prompt
            system_prompt = self.history_manager.load_system_prompt(channel_id)

            response = await self.gemini_client.aio.models.generate_content(
                model=self.current_model,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
                contents=self.conversation_history[channel_id],
            )
            response_text = response.text or ""

            # Add model's response to history
            self.conversation_history[channel_id].append(
                types.Content(
                    role="model", parts=[types.Part.from_text(text=response_text)]
                )
            )

            # Save to disk with Git commit
            self._save_history_to_disk(channel_id)

            return response_text
        except Exception as e:
            # Remove the last user message from history if an error occurred
            if self.conversation_history[channel_id]:
                self.conversation_history[channel_id].pop()
            raise e


# Initialize Discord Bot
intents = discord.Intents.default()
intents.message_content = True
bot = GeminiBot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    if gemini_channel_ids:
        print(f"Gemini auto-response enabled for channels: {gemini_channel_ids}")
    else:
        print("Gemini auto-response disabled (GEMINI_CHANNEL_ID not set)")


@bot.event
async def on_message(message):
    """Handle incoming messages."""
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    user_id = message.author.id

    # Check if this user has a pending model selection
    if user_id in bot.pending_model_selections:
        content = message.content.strip().lower()

        # Handle cancel
        if content == "cancel":
            del bot.pending_model_selections[user_id]
            await message.channel.send("モデル選択をキャンセルしました。")
            return

        # Handle number selection
        if content.isdigit():
            index = int(content) - 1
            model_names = bot.pending_model_selections[user_id]

            if 0 <= index < len(model_names):
                bot.current_model = model_names[index]
                del bot.pending_model_selections[user_id]
                await message.channel.send(
                    f"モデルを **{bot.current_model}** に変更しました。"
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
                response_text = await bot.ask_gemini(
                    message.channel.id, message.content
                )
                await bot.send_response(message.channel, response_text)
            except Exception as e:
                await message.channel.send(f"An error occurred: {e}")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
