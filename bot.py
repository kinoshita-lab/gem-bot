import os

import discord
from discord.ext import commands
from google import genai
from google.genai import types
from dotenv import load_dotenv

from history_manager import HistoryManager
from i18n import I18nManager


class LocalizedHelpCommand(commands.DefaultHelpCommand):
    """Custom help command with i18n support and grouped display."""

    # Command groups for organized help display
    COMMAND_GROUPS = {
        "general": ["help", "info", "lang"],
        "conversation": ["model", "prompt", "config"],
        "history": ["history", "branch"],
        "tools": ["image"],
    }

    def t(self, key: str, **kwargs) -> str:
        """Shortcut for translation."""
        return self.context.bot.i18n.t(key, **kwargs)

    def get_ending_note(self):
        """Return the ending note for the help command."""
        return self.t(
            "help_ending_note",
            prefix=self.context.clean_prefix,
            command=self.invoked_with,
        )

    def get_command_signature(self, command):
        """Return the command signature."""
        return (
            f"{self.context.clean_prefix}{command.qualified_name} {command.signature}"
        )

    async def send_bot_help(self, mapping):
        """Send help for all commands with organized groups."""
        embed = discord.Embed(
            title=self.t("help_title"),
            description=self.t("help_bot_description"),
            color=discord.Color.blue(),
        )

        # Collect all commands
        all_commands = {}
        for cog, cmds in mapping.items():
            filtered = await self.filter_commands(cmds, sort=True)
            for cmd in filtered:
                all_commands[cmd.name] = cmd

        # Display commands by group
        for group_key, cmd_names in self.COMMAND_GROUPS.items():
            group_commands = []
            for cmd_name in cmd_names:
                if cmd_name in all_commands:
                    cmd = all_commands[cmd_name]
                    desc = self._get_localized_command_help(cmd)
                    prefix = self.context.clean_prefix
                    # Show subcommands for group commands
                    if isinstance(cmd, commands.Group):
                        subcmds = " | ".join([f"{sub.name}" for sub in cmd.commands])
                        group_commands.append(
                            f"`{prefix}{cmd.name}` - {desc}\n  └ {subcmds}"
                        )
                    else:
                        group_commands.append(f"`{prefix}{cmd.name}` - {desc}")

            if group_commands:
                group_title = self.t(f"help_group_{group_key}")
                embed.add_field(
                    name=f"**{group_title}**",
                    value="\n".join(group_commands),
                    inline=False,
                )

        embed.set_footer(text=self.get_ending_note())
        await self.get_destination().send(embed=embed)

    def _get_localized_command_help(self, command) -> str:
        """Get localized help text for a command."""
        key = f"help_command_{command.name}"
        translated = self.t(key)
        # If no translation found (returns key), use original help
        if translated == key:
            return command.short_doc or command.help or ""
        return translated

    async def send_command_help(self, command):
        """Send help for a specific command."""
        embed = discord.Embed(
            title=f"{self.context.clean_prefix}{command.qualified_name}",
            description=self._get_localized_command_help(command),
            color=discord.Color.blue(),
        )

        if command.aliases:
            embed.add_field(
                name=self.t("help_aliases"),
                value=", ".join(command.aliases),
                inline=False,
            )

        usage = self.get_command_signature(command)
        embed.add_field(
            name=self.t("help_usage"),
            value=f"`{usage}`",
            inline=False,
        )

        await self.get_destination().send(embed=embed)

    async def send_group_help(self, group):
        """Send help for a command group."""
        embed = discord.Embed(
            title=f"{self.context.clean_prefix}{group.qualified_name}",
            description=self._get_localized_command_help(group),
            color=discord.Color.blue(),
        )

        filtered = await self.filter_commands(group.commands, sort=True)
        if filtered:
            subcommands = []
            for cmd in filtered:
                desc = self._get_localized_command_help(cmd)
                subcommands.append(f"`{cmd.name}` - {desc}")

            embed.add_field(
                name=self.t("help_subcommands"),
                value="\n".join(subcommands),
                inline=False,
            )

        await self.get_destination().send(embed=embed)


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

if not GEMINI_CHANNEL_ID:
    print("Error: GEMINI_CHANNEL_ID environment variable not set.")
    print("Please specify at least one channel ID where the bot should respond.")
    exit(1)

# Parse GEMINI_CHANNEL_ID (can be comma-separated for multiple channels)
enabled_channel_ids: set[int] = set()
for channel_id_str in GEMINI_CHANNEL_ID.split(","):
    channel_id_str = channel_id_str.strip()
    if channel_id_str:
        try:
            enabled_channel_ids.add(int(channel_id_str))
        except ValueError:
            print(
                f"Warning: Invalid channel ID '{channel_id_str}' in GEMINI_CHANNEL_ID"
            )

if not enabled_channel_ids:
    print("Error: No valid channel IDs found in GEMINI_CHANNEL_ID.")
    exit(1)


class GeminiBot(commands.Bot):
    """Custom Bot class with Gemini integration."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Gemini client
        self.gemini_client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=300000),  # 5 minutes in milliseconds
        )

        # Default model (used when a channel doesn't have a specific model set)
        self.default_model: str = "gemini-flash-latest"

        # Pending model selections: user_id -> {channel_id, models}
        self.pending_model_selections: dict[int, dict] = {}

        # Conversation history per channel
        self.conversation_history: dict[int, list] = {}

        # History manager for Git-based persistence
        self.history_manager = HistoryManager()

        # I18n manager for translations
        self.i18n = I18nManager()

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
        model = self.get_model(channel_id)
        self.history_manager.save_conversation(
            channel_id=channel_id,
            messages=messages,
            model=model,
            auto_commit=True,
        )

    def _reload_history_from_disk(self, channel_id: int):
        """Reload conversation history for a channel from disk.

        Used after branch switch to sync memory with the new branch's state.
        """
        data = self.history_manager.load_conversation(channel_id)
        if data and "messages" in data:
            history = []
            for msg in data["messages"]:
                history.append(
                    types.Content(
                        role=msg["role"],
                        parts=[types.Part.from_text(text=msg["content"])],
                    )
                )
            self.conversation_history[channel_id] = history
        else:
            self.conversation_history[channel_id] = []

    def get_model(self, channel_id: int) -> str:
        """Get the model for a specific channel.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Model name for the channel.
        """
        return self.history_manager.load_model(channel_id, self.default_model)

    def set_model(self, channel_id: int, model: str) -> None:
        """Set the model for a specific channel.

        Args:
            channel_id: Discord channel ID.
            model: Model name.
        """
        self.history_manager.save_model(channel_id, model)

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
            model = self.get_model(channel_id)

            # Load generation config
            gen_config = self.history_manager.load_generation_config(channel_id)

            # Build config with user settings
            config_params = {
                "system_instruction": system_prompt,
                "tools": [types.Tool(google_search=types.GoogleSearch())],
            }
            # Apply user-configured generation parameters
            config_params.update(gen_config)

            response = await self.gemini_client.aio.models.generate_content(
                model=model,
                config=types.GenerateContentConfig(**config_params),
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
bot = GeminiBot(command_prefix="!", intents=intents, help_command=None)

# Set custom help command
bot.help_command = LocalizedHelpCommand()


@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")
    print(f"Responding to messages in channels: {enabled_channel_ids}")

    # Send online message to all enabled channels
    for channel_id in enabled_channel_ids:
        channel = bot.get_channel(channel_id)
        if channel:
            try:
                await channel.send(bot.i18n.t("bot_online"))
            except Exception as e:
                print(f"Failed to send online message to channel {channel_id}: {e}")


@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(bot.i18n.t("command_not_found", command=ctx.invoked_with))
    else:
        # Re-raise other errors to see them in console
        raise error


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
            await message.channel.send(bot.i18n.t("model_select_cancelled"))
            return

        # Handle number selection
        if content.isdigit():
            index = int(content) - 1
            model_names = bot.pending_model_selections[user_id]["models"]
            channel_id = bot.pending_model_selections[user_id]["channel_id"]

            if 0 <= index < len(model_names):
                selected_model = model_names[index]
                bot.set_model(channel_id, selected_model)
                del bot.pending_model_selections[user_id]
                await message.channel.send(
                    bot.i18n.t("model_select_changed", model=selected_model)
                )
                return
            else:
                await message.channel.send(
                    bot.i18n.t("model_select_invalid_number", max=len(model_names))
                )
                return

        # Invalid input - prompt again
        await message.channel.send(bot.i18n.t("model_select_prompt"))
        return

    # Check if the message is a command (starts with prefix)
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    # Check if the message is in an enabled channel
    if message.channel.id in enabled_channel_ids:
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
