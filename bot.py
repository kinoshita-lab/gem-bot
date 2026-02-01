import io
import json
import os
import re

import aiohttp
import discord
from discord.ext import commands
from google import genai
from google.genai import types
from dotenv import load_dotenv

from history_manager import HistoryManager
from i18n import I18nManager
from calendar_manager import CalendarAuthManager
from calendar_tools import get_calendar_tools, CalendarToolHandler
from tasks_tools import get_tasks_tools, TasksToolHandler
from latex_renderer import LatexRenderer


class LocalizedHelpCommand(commands.DefaultHelpCommand):
    """Custom help command with i18n support and grouped display."""

    # Command groups for organized help display
    COMMAND_GROUPS = {
        "general": ["help", "info", "lang"],
        "conversation": ["model", "system_prompt", "channel_prompt", "config"],
        "history": ["history", "branch"],
        "tools": ["image", "mode"],
        "integrations": ["calendar"],
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
        description = self.t("help_bot_description")
        
        # Add system prompt info if available
        prompt_desc = self.t("help_prompt_system_description")
        if prompt_desc != "help_prompt_system_description":
            description += "\n\n" + prompt_desc

        embed = discord.Embed(
            title=self.t("help_title"),
            description=description,
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

        # Pending branch selections: user_id -> {channel_id, branches}
        self.pending_branch_selections: dict[int, dict] = {}

        # Pending mode selections: user_id -> {channel_id, modes}
        self.pending_tool_mode_selections: dict[int, dict] = {}

        # Pending delete confirmations: user_id -> {channel_id, indices}
        self.pending_delete_confirmations: dict[int, dict] = {}

        # Conversation history per channel
        self.conversation_history: dict[int, list] = {}

        # I18n manager for translations (must be initialized before HistoryManager)
        self.i18n = I18nManager()

        # History manager for Git-based persistence
        self.history_manager = HistoryManager(i18n=self.i18n)

        # Calendar auth manager (optional, only if credentials.json exists)
        self.calendar_auth: CalendarAuthManager | None = None
        self.calendar_tool_handler: CalendarToolHandler | None = None
        self.tasks_tool_handler: TasksToolHandler | None = None
        try:
            calendar_auth = CalendarAuthManager()
            if calendar_auth.is_credentials_configured():
                self.calendar_auth = calendar_auth
                self.calendar_tool_handler = CalendarToolHandler(calendar_auth, self.i18n)
                self.tasks_tool_handler = TasksToolHandler(calendar_auth, self.i18n)
                print("Google Calendar/Tasks integration enabled")
            else:
                print("Google Calendar/Tasks integration disabled (credentials.json not found)")
        except Exception as e:
            print(f"Google Calendar/Tasks integration disabled: {e}")

        # Tool mode per channel: channel_id -> mode name
        # Available modes: "default" (Google Search), "calendar"
        self.channel_tool_mode: dict[int, str] = {}

        # LaTeX renderer for math formulas
        self.latex_renderer = LatexRenderer(enabled=True)

    def get_tool_mode(self, channel_id: int) -> str:
        """Get the current tool mode for a channel.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Tool mode name ("default", "calendar", etc.)
        """
        return self.channel_tool_mode.get(channel_id, "default")

    def set_tool_mode(self, channel_id: int, mode: str) -> None:
        """Set the tool mode for a channel.

        Args:
            channel_id: Discord channel ID.
            mode: Tool mode name.
        """
        self.channel_tool_mode[channel_id] = mode

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
                parts = []

                # Load images first if present
                if "images" in msg:
                    for image_path in msg["images"]:
                        image_data = self.history_manager.load_image(
                            channel_id, image_path
                        )
                        if image_data:
                            data, mime_type = image_data
                            parts.append(
                                types.Part.from_bytes(data=data, mime_type=mime_type)
                            )

                # Add text content
                parts.append(types.Part.from_text(text=msg["content"]))

                history.append(types.Content(role=msg["role"], parts=parts))
            self.conversation_history[channel_id] = history
        print(f"Loaded conversation history for {len(saved_conversations)} channels")

    def _save_history_to_disk(self, channel_id: int):
        """Save conversation history for a channel to disk."""
        if channel_id not in self.conversation_history:
            return

        history = self.conversation_history[channel_id]
        messages = self.history_manager.convert_to_serializable(history, channel_id)
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
                parts = []

                # Load images first if present
                if "images" in msg:
                    for image_path in msg["images"]:
                        image_data = self.history_manager.load_image(
                            channel_id, image_path
                        )
                        if image_data:
                            img_bytes, mime_type = image_data
                            parts.append(
                                types.Part.from_bytes(data=img_bytes, mime_type=mime_type)
                            )

                # Add text content
                parts.append(types.Part.from_text(text=msg["content"]))

                history.append(types.Content(role=msg["role"], parts=parts))
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

    async def _send_text(self, channel, text: str) -> None:
        """Send text to a channel, splitting intelligently.
        
        Ensures code blocks are sent as separate messages and not split mid-block
        if possible. Handles splitting of messages > 2000 chars.

        Args:
            channel: Discord channel to send to.
            text: Text to send.
        """
        text = text.strip()
        if not text:
            return

        # Split text by code blocks to treat them as independent parts
        # Regex captures the delimiter (code block) so we keep it in the list
        segments = re.split(r"(```[\s\S]*?```)", text)

        for segment in segments:
            if not segment.strip():
                continue

            if segment.startswith("```") and segment.endswith("```"):
                # -- CODE BLOCK --
                if len(segment) <= 2000:
                    await channel.send(segment)
                else:
                    # Handle massive code blocks > 2000 chars
                    # We must split, but try to preserve code block formatting for each chunk
                    content = segment[3:-3] # Remove outer backticks
                    
                    # Extract language if present
                    lang = ""
                    first_newline = content.find("\n")
                    if first_newline != -1:
                        possible_lang = content[:first_newline].strip()
                        if possible_lang.isalnum(): # Simple check for lang tag
                            lang = possible_lang
                            content = content[first_newline+1:] # Remove lang line from content for splitting
                    
                    # Maximum content size per chunk (2000 - wrappers)
                    # Wrapper overhead: ```lang\n...``` -> 3 + len(lang) + 1 + 3 = 7 + len(lang)
                    wrapper_overhead = 7 + len(lang)
                    chunk_size = 2000 - wrapper_overhead
                    
                    for i in range(0, len(content), chunk_size):
                        chunk_content = content[i : i + chunk_size]
                        # Reconstruct code block for this chunk
                        chunk_msg = f"```{lang}\n{chunk_content}```"
                        await channel.send(chunk_msg)

            else:
                # -- REGULAR TEXT --
                # Split into 2000 character chunks
                # We can be smarter here too: split by newlines if possible
                if len(segment) <= 2000:
                    await channel.send(segment)
                else:
                    current_chunk = ""
                    lines = segment.split("\n")
                    for line in lines:
                        # +1 for the newline we'll add back
                        if len(current_chunk) + len(line) + 1 > 2000:
                            if current_chunk:
                                await channel.send(current_chunk)
                                current_chunk = ""
                            
                            # If a single line is massive, we still have to hard split it
                            if len(line) > 2000:
                                for i in range(0, len(line), 2000):
                                    await channel.send(line[i:i+2000])
                            else:
                                current_chunk = line
                        else:
                            if current_chunk:
                                current_chunk += "\n" + line
                            else:
                                current_chunk = line
                    
                    if current_chunk:
                        await channel.send(current_chunk)

    def _format_tables(self, text: str) -> str:
        """Wrap Markdown tables in code blocks for better Discord display.

        Preserves existing code blocks to avoid double-wrapping.

        Args:
            text: Original markdown text.

        Returns:
            Text with tables wrapped in code blocks.
        """
        # 1. Identify existing code blocks to protect them
        code_block_ranges = []
        # Matches ```...``` (multi-line) or `...` (inline)
        for match in re.finditer(r"(`{1,3})[\s\S]*?\1", text):
            code_block_ranges.append(match.span())

        lines = text.split("\n")
        output_lines = []
        in_table = False
        table_buffer = []

        # Helper to check if a line is inside an existing code block
        def is_in_code_block(line_index, lines):
            # Approximate character position
            # This is a bit expensive but accurate enough for message usage
            current_pos = 0
            for i in range(line_index):
                current_pos += len(lines[i]) + 1  # +1 for newline
            
            line_end = current_pos + len(lines[line_index])
            
            for start, end in code_block_ranges:
                # If the line overlaps with a code block
                if (current_pos >= start and current_pos < end) or \
                   (line_end > start and line_end <= end) or \
                   (start >= current_pos and end <= line_end):
                    return True
            return False

        # Regex for table separator row (e.g., |---| or |:---:|)
        separator_pattern = re.compile(r"^\s*\|?(\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")

        for i, line in enumerate(lines):
            # If we are already building a table
            if in_table:
                # Check if this line continues the table (starts with |)
                if line.strip().startswith("|"):
                    table_buffer.append(line)
                else:
                    # End of table
                    output_lines.append("```")
                    output_lines.extend(table_buffer)
                    output_lines.append("```")
                    in_table = False
                    table_buffer = []
                    output_lines.append(line)
                continue

            # Check for table start (look ahead for separator)
            if not is_in_code_block(i, lines):
                # Potential header: current line has |, next line is separator
                if "|" in line and i + 1 < len(lines):
                    next_line = lines[i + 1]
                    if separator_pattern.match(next_line):
                        # Start of new table
                        in_table = True
                        table_buffer.append(line)
                        continue

            output_lines.append(line)

        # Flush any remaining table buffer
        if in_table:
            output_lines.append("```")
            output_lines.extend(table_buffer)
            output_lines.append("```")

        return "\n".join(output_lines)

    async def send_response(self, channel, response_text: str):
        """Send a response to a channel with inline LaTeX rendering.

        If the response contains LaTeX formulas ($$...$$ or \\[...\\]),
        the text is split at formula positions. For each formula:
        1. The preceding text + original TeX markup is sent as text
        2. The rendered formula image is sent

        Args:
            channel: Discord channel to send to.
            response_text: Response text, possibly containing LaTeX.
        """
        # Handle empty response
        if not response_text:
            await channel.send("No response from Gemini.")
            return

        # Format tables to be wrapped in code blocks
        response_text = self._format_tables(response_text)

        # If no LaTeX or rendering disabled, send as plain text
        if not self.latex_renderer.enabled or not self.latex_renderer.has_latex(response_text):
            await self._send_text(channel, response_text)
            return

        # Split text by formula positions and send segments in order
        segments = self.latex_renderer.split_text_by_formulas(response_text)

        # Buffer to accumulate text before sending with formula
        text_buffer = ""

        for segment in segments:
            if segment["type"] == "text":
                # Accumulate text
                text_buffer += segment["content"]
            else:
                # Formula segment: send accumulated text + original TeX markup
                text_to_send = text_buffer + segment["original"]
                await self._send_text(channel, text_to_send)
                text_buffer = ""

                # Render and send formula as image
                image_data = await self.latex_renderer.render_formula(
                    segment["content"],
                )
                if image_data:
                    try:
                        file = discord.File(
                            io.BytesIO(image_data),
                            filename="formula.png",
                        )
                        await channel.send(file=file)
                    except Exception as e:
                        print(f"Failed to send LaTeX image: {e}")

        # Send any remaining text after the last formula
        if text_buffer:
            await self._send_text(channel, text_buffer)

    # =========================================================================
    # ask_gemini Helper Methods
    # =========================================================================

    def _build_user_content(
        self,
        prompt: str,
        images: list[tuple[bytes, str]] | None = None,
    ) -> types.Content:
        """Build user content from prompt and optional images.

        Args:
            prompt: Text prompt from user.
            images: Optional list of (image_data, mime_type) tuples.

        Returns:
            Content object for the user message.
        """
        parts = []

        # Add images first if provided
        if images:
            for image_data, mime_type in images:
                parts.append(
                    types.Part.from_bytes(data=image_data, mime_type=mime_type)
                )

        # Add text prompt
        parts.append(types.Part.from_text(text=prompt))

        return types.Content(role="user", parts=parts)

    def _get_tools_for_mode(self, channel_id: int) -> list:
        """Get the appropriate tools based on channel's tool mode.

        Args:
            channel_id: Discord channel ID.

        Returns:
            List of Tool objects for the current mode.
        """
        tool_mode = self.get_tool_mode(channel_id)

        if tool_mode == "calendar" and self.calendar_tool_handler:
            return get_calendar_tools(self.i18n)
        elif tool_mode == "todo" and self.tasks_tool_handler:
            return get_tasks_tools(self.i18n)
        else:
            # Default: Google Search
            return [types.Tool(google_search=types.GoogleSearch())]

    # Mode-specific system prompt instruction keys (mapped to i18n keys)
    _MODE_INSTRUCTION_KEYS = {
        "default": "mode_instruction_default",
        "todo": "mode_instruction_todo",
        "calendar": "mode_instruction_calendar",
    }

    def _get_mode_instruction(self, mode: str) -> str:
        """Get localized mode instruction for the given tool mode.

        Args:
            mode: Tool mode name ("todo", "calendar", etc.)

        Returns:
            Localized mode instruction string, or empty string if not applicable.
        """
        i18n_key = self._MODE_INSTRUCTION_KEYS.get(mode)
        if i18n_key:
            return self.i18n.t(i18n_key)
        return ""

    def _build_system_prompt(self, channel_id: int) -> str:
        """Build the system prompt with mode-specific instructions.

        Args:
            channel_id: Discord channel ID.

        Returns:
            Complete system prompt string.
        """
        base_prompt = self.history_manager.load_system_prompt(channel_id)
        tool_mode = self.get_tool_mode(channel_id)

        # Add mode-specific instruction if applicable
        mode_instruction = self._get_mode_instruction(tool_mode)
        if mode_instruction:
            if base_prompt:
                # Structure with XML tags to clarify priority
                return f"""<priority-instructions>
{mode_instruction}
</priority-instructions>

<base-instructions>
{base_prompt}
</base-instructions>"""
            return mode_instruction

        return base_prompt

    async def _extract_grounding_sources(self, response) -> list[dict]:
        """Extract source URLs and titles from grounding metadata.

        Args:
            response: Gemini API response.

        Returns:
            List of source dictionaries with 'uri' and 'title' keys.
        """
        sources = []

        # Early return if no candidates
        if not response.candidates:
            return sources

        candidate = response.candidates[0]

        # Check for grounding_metadata
        if not hasattr(candidate, "grounding_metadata") or not candidate.grounding_metadata:
            return sources

        grounding_metadata = candidate.grounding_metadata

        # Extract from grounding_chunks (contains web sources)
        if hasattr(grounding_metadata, "grounding_chunks") and grounding_metadata.grounding_chunks:
            for chunk in grounding_metadata.grounding_chunks:
                if hasattr(chunk, "web") and chunk.web:
                    web = chunk.web
                    source = {}
                    if hasattr(web, "uri") and web.uri:
                        source["uri"] = web.uri
                    if hasattr(web, "title") and web.title:
                        source["title"] = web.title
                    if source.get("uri"):
                        sources.append(source)

        # Deduplicate by URI while preserving order
        seen_uris = set()
        unique_sources = []
        for source in sources:
            uri = source.get("uri")
            if uri and uri not in seen_uris:
                seen_uris.add(uri)
                unique_sources.append(source)

        # Resolve vertexaisearch URLs
        async with aiohttp.ClientSession() as session:
            for source in unique_sources:
                uri = source.get("uri")
                if uri and "vertexaisearch.cloud.google.com" in uri:
                    try:
                        async with session.head(
                            uri, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            source["uri"] = str(resp.url)
                    except Exception:
                        # Fallback to original URI if resolution fails
                        pass

        return unique_sources

    def _format_grounding_sources(self, sources: list[dict]) -> str:
        """Format grounding sources as a reference section.

        Args:
            sources: List of source dictionaries with 'uri' and 'title' keys.

        Returns:
            Formatted reference section string, or empty string if no sources.
        """
        if not sources:
            return ""

        header = self.i18n.t("grounding_sources_header")
        lines = [header]

        for source in sources:
            uri = source.get("uri", "")
            title = source.get("title", "")
            if title:
                lines.append(f"- [{title}](<{uri}>)")
            else:
                lines.append(f"- <{uri}>")

        return "\n".join(lines)

    async def ask_gemini(
        self,
        channel_id: int,
        prompt: str,
        images: list[tuple[bytes, str]] | None = None,
        user_id: int | None = None,
    ) -> str:
        """Send a prompt to Gemini and return the response.

        Args:
            channel_id: Discord channel ID.
            prompt: Text prompt from user.
            images: Optional list of (image_data, mime_type) tuples.
            user_id: Discord user ID (for calendar integration).

        Returns:
            Response text from Gemini.
        """
        # Initialize conversation history for this channel if not exists
        if channel_id not in self.conversation_history:
            self.conversation_history[channel_id] = []

        # Build and add user message to history
        user_content = self._build_user_content(prompt, images)
        self.conversation_history[channel_id].append(user_content)

        try:
            # Build configuration
            model = self.get_model(channel_id)
            config_params = {
                "system_instruction": self._build_system_prompt(channel_id),
                "tools": self._get_tools_for_mode(channel_id),
            }

            config_params.update(self.history_manager.load_generation_config(channel_id))

            # Call Gemini API
            response = await self.gemini_client.aio.models.generate_content(
                model=model,
                config=types.GenerateContentConfig(**config_params),
                contents=self.conversation_history[channel_id],
            )

            # Process response (handle function calls if in calendar or todo mode)
            tool_mode = self.get_tool_mode(channel_id)
            if tool_mode in ("calendar", "todo"):
                response_text = await self._process_response(
                    response, channel_id, model, config_params, user_id
                )
            else:
                # Default mode: extract response text and append grounding sources
                response_text = response.text or ""

                # Extract and append grounding sources for default (search) mode
                grounding_sources = await self._extract_grounding_sources(response)
                if grounding_sources:
                    sources_text = self._format_grounding_sources(grounding_sources)
                    response_text = response_text + sources_text

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

    # =========================================================================
    # _process_response Helper Methods
    # =========================================================================

    # Function name to handler mapping
    _CALENDAR_FUNCTIONS = frozenset({
        "list_calendar_events",
        "create_calendar_event",
        "update_calendar_event",
        "delete_calendar_event",
    })

    _TASKS_FUNCTIONS = frozenset({
        "list_task_lists",
        "list_tasks",
        "create_task",
        "update_task",
        "complete_task",
        "delete_task",
    })

    def _extract_function_calls(self, response) -> list:
        """Extract function calls from Gemini response.

        Args:
            response: Gemini API response.

        Returns:
            List of function call objects, empty if none found.
        """
        # Early returns for invalid response structure
        if not response.candidates:
            return []

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            return []

        # Collect function calls
        return [
            part.function_call
            for part in candidate.content.parts
            if hasattr(part, "function_call") and part.function_call
        ]

    async def _execute_function_calls(
        self,
        function_calls: list,
        user_id: int | None,
    ) -> list:
        """Execute multiple function calls and return response parts.

        Args:
            function_calls: List of function call objects.
            user_id: Discord user ID.

        Returns:
            List of function response Part objects.
        """
        responses = []
        for fc in function_calls:
            result = await self._execute_single_function(fc, user_id)
            responses.append(
                types.Part.from_function_response(name=fc.name, response=result)
            )
        return responses

    async def _execute_single_function(
        self,
        function_call,
        user_id: int | None,
    ) -> dict:
        """Execute a single function call and return the result.

        Args:
            function_call: Function call object from Gemini.
            user_id: Discord user ID.

        Returns:
            Function result dictionary.
        """
        function_name = function_call.name
        function_args = dict(function_call.args) if function_call.args else {}

        # Route to appropriate handler
        if function_name in self._CALENDAR_FUNCTIONS:
            return await self._handle_calendar_function(
                function_name, function_args, user_id
            )

        if function_name in self._TASKS_FUNCTIONS:
            return await self._handle_tasks_function(
                function_name, function_args, user_id
            )

        return {"error": f"Unknown function: {function_name}"}

    async def _handle_calendar_function(
        self,
        function_name: str,
        function_args: dict,
        user_id: int | None,
    ) -> dict:
        """Handle calendar function calls.

        Args:
            function_name: Name of the calendar function.
            function_args: Arguments for the function.
            user_id: Discord user ID.

        Returns:
            Function result dictionary.
        """
        if not self.calendar_tool_handler:
            return {"error": "Calendar integration not configured"}
        if not user_id:
            return {"error": "User ID not available"}

        return await self.calendar_tool_handler.handle_function_call(
            function_name, function_args, user_id
        )

    async def _handle_tasks_function(
        self,
        function_name: str,
        function_args: dict,
        user_id: int | None,
    ) -> dict:
        """Handle tasks function calls.

        Args:
            function_name: Name of the tasks function.
            function_args: Arguments for the function.
            user_id: Discord user ID.

        Returns:
            Function result dictionary.
        """
        if not self.tasks_tool_handler:
            return {"error": "Tasks integration not configured"}
        if not user_id:
            return {"error": "User ID not available"}

        return await self.tasks_tool_handler.handle_function_call(
            function_name, function_args, user_id
        )

    def _update_history_with_function_calls(
        self,
        channel_id: int,
        model_content,
        function_responses: list,
    ) -> None:
        """Update conversation history with function call and responses.

        Args:
            channel_id: Discord channel ID.
            model_content: Model's content containing function calls.
            function_responses: List of function response Part objects.
        """
        # Add model's function call to history
        self.conversation_history[channel_id].append(model_content)

        # Add function responses to history
        self.conversation_history[channel_id].append(
            types.Content(role="user", parts=function_responses)
        )

    async def _process_response(
        self,
        response,
        channel_id: int,
        model: str,
        config_params: dict,
        user_id: int | None,
    ) -> str:
        """Process Gemini response, handling function calls if present.

        Uses early return pattern for cleaner control flow.
        Recursively processes chained function calls.

        Args:
            response: Gemini API response.
            channel_id: Discord channel ID.
            model: Model name.
            config_params: Generation config parameters.
            user_id: Discord user ID.

        Returns:
            Final response text.
        """
        # Extract function calls (empty list if none)
        function_calls = self._extract_function_calls(response)

        # No function calls - return text response
        if not function_calls:
            return response.text or ""

        # Execute all function calls
        function_responses = await self._execute_function_calls(function_calls, user_id)

        # Update history with function calls and responses
        self._update_history_with_function_calls(
            channel_id,
            response.candidates[0].content,
            function_responses,
        )

        # Get follow-up response from Gemini
        final_response = await self.gemini_client.aio.models.generate_content(
            model=model,
            config=types.GenerateContentConfig(**config_params),
            contents=self.conversation_history[channel_id],
        )

        # Recursively process in case of chained function calls
        return await self._process_response(
            final_response, channel_id, model, config_params, user_id
        )


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




@bot.event
async def on_command_error(ctx, error):
    """Handle command errors."""
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(bot.i18n.t("command_not_found", command=ctx.invoked_with))
    else:
        # Re-raise other errors to see them in console
        raise error


# =============================================================================
# Message Handler Helper Functions
# =============================================================================


async def _handle_instruction_upload(message) -> bool:
    """Handle channel_instruction.md file upload.

    Args:
        message: Discord message object.

    Returns:
        True if handled (should stop processing), False otherwise.
    """
    for attachment in message.attachments:
        if attachment.filename == "channel_instruction.md":
            try:
                content = await attachment.read()
                text = content.decode("utf-8")
                channel_id = message.channel.id
                bot.history_manager.save_system_prompt(channel_id, text)
                await message.channel.send(bot.i18n.t("prompt_updated_from_file"))
            except UnicodeDecodeError:
                await message.channel.send(bot.i18n.t("prompt_file_decode_error"))
            except Exception as e:
                await message.channel.send(bot.i18n.t("prompt_error", error=str(e)))
            return True
    return False


async def _handle_master_instruction_upload(message) -> bool:
    """Handle GEMINI.md (master instruction) file upload.

    Args:
        message: Discord message object.

    Returns:
        True if handled (should stop processing), False otherwise.
    """
    for attachment in message.attachments:
        if attachment.filename == "GEMINI.md":
            try:
                content = await attachment.read()
                text = content.decode("utf-8")
                bot.history_manager.save_master_prompt(text)
                await message.channel.send(bot.i18n.t("master_prompt_updated"))
            except UnicodeDecodeError:
                await message.channel.send(bot.i18n.t("master_prompt_decode_error"))
            except Exception as e:
                await message.channel.send(bot.i18n.t("prompt_error", error=str(e)))
            return True
    return False


async def _handle_branch_selection(message) -> bool:
    """Handle pending branch selection interaction.

    Args:
        message: Discord message object.

    Returns:
        True if handled (should stop processing), False otherwise.
    """
    user_id = message.author.id
    if user_id not in bot.pending_branch_selections:
        return False

    content = message.content.strip().lower()

    # Handle cancel
    if content == "cancel":
        del bot.pending_branch_selections[user_id]
        await message.channel.send(bot.i18n.t("branch_select_cancelled"))
        return True

    # Handle number selection
    if content.isdigit():
        index = int(content) - 1
        branches = bot.pending_branch_selections[user_id]["branches"]
        channel_id = bot.pending_branch_selections[user_id]["channel_id"]
        action = bot.pending_branch_selections[user_id].get("action", "switch")

        if 0 <= index < len(branches):
            selected_branch = branches[index]
            try:
                if action == "switch":
                    # Switch branch (auto-commits current state)
                    bot.history_manager.switch_branch(channel_id, selected_branch)
                    # Reload history from disk
                    bot._reload_history_from_disk(channel_id)
                    await message.channel.send(
                        bot.i18n.t("branch_switched", branch=selected_branch)
                    )

                elif action == "delete":
                    bot.history_manager.delete_branch(channel_id, selected_branch)
                    await message.channel.send(
                        bot.i18n.t("branch_deleted", branch=selected_branch)
                    )

                elif action == "merge":
                     # Commit current state before merge
                    bot.history_manager.commit(channel_id, "Auto-save before merge")
                    # Merge branch
                    merged_count = bot.history_manager.merge_branch(
                        channel_id, selected_branch
                    )
                    # Reload history from disk
                    bot._reload_history_from_disk(channel_id)

                    if merged_count > 0:
                        await message.channel.send(
                            bot.i18n.t("branch_merged", branch=selected_branch, count=merged_count)
                        )
                    else:
                        await message.channel.send(bot.i18n.t("branch_merge_nothing"))

                del bot.pending_branch_selections[user_id]
                
            except Exception as e:
                await message.channel.send(bot.i18n.t("branch_error", error=e))
        else:
            await message.channel.send(
                bot.i18n.t("branch_select_invalid_number", max=len(branches))
            )
        return True

    # Invalid input - prompt again
    await message.channel.send(bot.i18n.t("branch_select_prompt"))
    return True


async def _handle_tool_mode_selection(message) -> bool:
    """Handle pending tool mode selection interaction.

    Args:
        message: Discord message object.

    Returns:
        True if handled (should stop processing), False otherwise.
    """
    user_id = message.author.id
    if user_id not in bot.pending_tool_mode_selections:
        return False

    content = message.content.strip().lower()

    # Handle cancel
    if content == "cancel":
        del bot.pending_tool_mode_selections[user_id]
        await message.channel.send(bot.i18n.t("mode_select_cancelled"))
        return True

    # Handle number selection
    if content.isdigit():
        index = int(content) - 1
        modes = bot.pending_tool_mode_selections[user_id]["modes"]
        channel_id = bot.pending_tool_mode_selections[user_id]["channel_id"]

        if 0 <= index < len(modes):
            selected_mode = modes[index]
            
            # Check authentication for calendar/todo
            if selected_mode in ("calendar", "todo"):
                if not bot.calendar_auth or not bot.calendar_auth.is_user_authenticated(user_id):
                    key = f"mode_{selected_mode}_not_linked"
                    await message.channel.send(bot.i18n.t(key))
                    del bot.pending_tool_mode_selections[user_id]
                    return True

            bot.set_tool_mode(channel_id, selected_mode)
            del bot.pending_tool_mode_selections[user_id]
            await message.channel.send(
                bot.i18n.t("mode_changed", mode=selected_mode)
            )
        else:
            await message.channel.send(
                bot.i18n.t("mode_select_invalid_number", max=len(modes))
            )
        return True

    # Invalid input - prompt again
    await message.channel.send(bot.i18n.t("mode_select_prompt"))
    return True


async def _handle_model_selection(message) -> bool:
    """Handle pending model selection interaction.

    Args:
        message: Discord message object.

    Returns:
        True if handled (should stop processing), False otherwise.
    """
    user_id = message.author.id
    if user_id not in bot.pending_model_selections:
        return False

    content = message.content.strip().lower()

    # Handle cancel
    if content == "cancel":
        del bot.pending_model_selections[user_id]
        await message.channel.send(bot.i18n.t("model_select_cancelled"))
        return True

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
        else:
            await message.channel.send(
                bot.i18n.t("model_select_invalid_number", max=len(model_names))
            )
        return True

    # Invalid input - prompt again
    await message.channel.send(bot.i18n.t("model_select_prompt"))
    return True


async def _handle_delete_confirmation(message) -> bool:
    """Handle pending delete confirmation interaction.

    Args:
        message: Discord message object.

    Returns:
        True if handled (should stop processing), False otherwise.
    """
    user_id = message.author.id
    if user_id not in bot.pending_delete_confirmations:
        return False

    pending = bot.pending_delete_confirmations[user_id]
    channel_id = pending["channel_id"]

    # Only process if in the same channel
    if message.channel.id != channel_id:
        return False

    content = message.content.strip().lower()
    del bot.pending_delete_confirmations[user_id]

    if content == "yes":
        # Perform deletion
        indices = sorted(pending["indices"], reverse=True)
        history = bot.conversation_history.get(channel_id, [])

        for idx in indices:
            if 0 <= idx < len(history):
                history.pop(idx)

        # Save updated history
        bot._save_history_to_disk(channel_id)

        await message.channel.send(
            bot.i18n.t("history_delete_success", count=len(pending["indices"]))
        )
    else:
        await message.channel.send(bot.i18n.t("history_delete_cancelled"))

    return True


async def _handle_auto_response(message) -> None:
    """Handle auto-response to messages in enabled channels.

    Args:
        message: Discord message object.
    """
    async with message.channel.typing():
        try:
            # Check for image attachments
            images = []
            supported_types = {"image/png", "image/jpeg", "image/gif", "image/webp"}

            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type in supported_types:
                    try:
                        image_data = await attachment.read()
                        images.append((image_data, attachment.content_type))
                    except Exception as e:
                        print(f"Failed to download image {attachment.filename}: {e}")

            # Use message content or default prompt if only images
            prompt = message.content if message.content else bot.i18n.t("image_default_prompt")

            response_text = await bot.ask_gemini(
                message.channel.id,
                prompt,
                images=images if images else None,
                user_id=message.author.id,
            )

            # Prepend current mode indicator to response
            tool_mode = bot.get_tool_mode(message.channel.id)
            mode_indicator = f"[{tool_mode}] "
            display_text = mode_indicator + response_text

            await bot.send_response(message.channel, display_text)
        except Exception as e:
            await message.channel.send(f"An error occurred: {e}")


@bot.event
async def on_message(message):
    """Handle incoming messages.

    Dispatches to specialized handlers based on message context.
    Cyclomatic Complexity reduced from 18 to 5 by extracting handlers.
    """
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Handle channel_instruction.md file upload (works in any channel)
    if await _handle_instruction_upload(message):
        return

    # Handle GEMINI.md (master instruction) upload
    if await _handle_master_instruction_upload(message):
        return

    # Handle pending branch selection interaction
    if await _handle_branch_selection(message):
        return

    # Handle pending tool mode selection interaction
    if await _handle_tool_mode_selection(message):
        return

    # Handle pending model selection interaction
    if await _handle_model_selection(message):
        return

    # Handle pending delete confirmation interaction
    if await _handle_delete_confirmation(message):
        return

    # Check if the message is a command (starts with prefix)
    if message.content.startswith(bot.command_prefix):
        await bot.process_commands(message)
        return

    # Auto-respond in enabled channels
    if message.channel.id in enabled_channel_ids:
        await _handle_auto_response(message)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
