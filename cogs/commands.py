import io
import zipfile
from datetime import datetime

import discord
from discord.ext import commands
from google.genai import types

from calendar_manager import CalendarAuthManager


class Commands(commands.Cog):
    """All bot commands."""

    # Recommended models shown at the top of the list
    RECOMMENDED_MODELS = ["gemini-flash-latest", "gemini-3-pro-preview"]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def t(self, key: str, **kwargs) -> str:
        """Shortcut for translation."""
        return self.bot.i18n.t(key, **kwargs)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    async def _fetch_and_sort_models(self) -> tuple[list[str], list[str]]:
        """Fetch and sort available Gemini models.

        Returns:
            Tuple of (recommended_models, other_models) lists.
        """
        models = [m async for m in await self.bot.gemini_client.aio.models.list()]

        # Extract and clean model names
        model_names = []
        for m in models:
            name = m.name
            if name:
                if name.startswith("models/"):
                    name = name.replace("models/", "")
                model_names.append(name)

        model_names.sort()

        # Separate recommended from others
        recommended = [m for m in self.RECOMMENDED_MODELS if m in model_names]
        other_models = [m for m in model_names if m not in recommended]

        return recommended, other_models

    def _build_model_fields(
        self,
        embed: discord.Embed,
        recommended: list[str],
        other_models: list[str],
        numbered: bool = False,
        chunk_size: int = 20,
    ) -> None:
        """Add model list fields to an embed.

        Args:
            embed: Discord embed to add fields to.
            recommended: List of recommended model names.
            other_models: List of other model names.
            numbered: Whether to show numbers for selection.
            chunk_size: Max models per field.
        """
        # Add recommended models field
        if recommended:
            if numbered:
                value = "\n".join(
                    f"`{i + 1}`. {name}" for i, name in enumerate(recommended)
                )
            else:
                value = "\n".join(f"• {name}" for name in recommended)
            embed.add_field(
                name=self.t("model_list_recommended"),
                value=value,
                inline=False,
            )

        # Add other models in chunks
        offset = len(recommended) if numbered else 0
        for i in range(0, len(other_models), chunk_size):
            chunk = other_models[i : i + chunk_size]
            field_name = (
                self.t("model_list_field")
                if i == 0
                else self.t("model_list_field_continued", num=i // chunk_size + 1)
            )
            if numbered:
                value = "\n".join(
                    f"`{offset + i + j + 1}`. {name}" for j, name in enumerate(chunk)
                )
            else:
                value = "\n".join(f"• {name}" for name in chunk)
            embed.add_field(name=field_name, value=value, inline=False)

    def _get_message_preview(self, msg, max_length: int = 50) -> str:
        """Extract and truncate message content for preview.

        Args:
            msg: Message content object.
            max_length: Maximum preview length.

        Returns:
            Truncated message preview string.
        """
        content = ""
        if msg.parts:
            for part in msg.parts:
                if hasattr(part, "text") and part.text:
                    content = part.text
                    break

        # Truncate and clean
        preview = content[:max_length] + "..." if len(content) > max_length else content
        return preview.replace("\n", " ")

    @commands.command(name="info")
    async def info(self, ctx: commands.Context):
        """Displays information about the bot."""
        channel_id = ctx.channel.id
        model = self.bot.get_model(channel_id)
        branch = self.bot.history_manager.get_current_branch(channel_id)
        embed = discord.Embed(
            title=self.t("bot_info_title"), color=discord.Color.blue()
        )
        embed.add_field(name=self.t("model"), value=model, inline=False)
        embed.add_field(name=self.t("branch"), value=branch or "N/A", inline=False)
        await ctx.send(embed=embed)

    async def _handle_invalid_subcommand(
        self, ctx: commands.Context, usage_key: str
    ) -> None:
        """Handle invalid or missing subcommand."""
        # Check if a subcommand was attempted (message has more than just the command)
        args = ctx.message.content.lstrip(ctx.prefix or "!").split()[1:]
        if args:
            # Invalid subcommand was specified
            await ctx.send(self.t("subcommand_not_found", subcommand=args[0]))
        await ctx.send(self.t(usage_key))

    @commands.group(name="model")
    async def model(self, ctx: commands.Context):
        """Model management commands."""
        if ctx.invoked_subcommand is None:
            await self._handle_invalid_subcommand(ctx, "model_usage")

    @model.command(name="list")
    async def model_list(self, ctx: commands.Context):
        """Lists all available Gemini models."""
        async with ctx.typing():
            try:
                recommended, other_models = await self._fetch_and_sort_models()
                current_model = self.bot.get_model(ctx.channel.id)
                total_count = len(recommended) + len(other_models)

                embed = discord.Embed(
                    title=self.t("model_list_title"),
                    description=self.t("model_list_current", model=current_model),
                    color=discord.Color.green(),
                )

                self._build_model_fields(embed, recommended, other_models)
                embed.set_footer(text=self.t("model_list_footer", count=total_count))

                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(self.t("model_list_error", error=e))

    @model.command(name="set")
    async def model_set(self, ctx: commands.Context):
        """Interactively set the Gemini model to use."""
        user_id = ctx.author.id
        channel_id = ctx.channel.id

        async with ctx.typing():
            try:
                recommended, other_models = await self._fetch_and_sort_models()
                ordered_models = recommended + other_models
                current_model = self.bot.get_model(channel_id)

                # Register pending selection
                self.bot.pending_model_selections[user_id] = {
                    "channel_id": channel_id,
                    "models": ordered_models,
                }

                embed = discord.Embed(
                    title=self.t("model_select_title"),
                    description=self.t("model_select_description", model=current_model),
                    color=discord.Color.blue(),
                )

                self._build_model_fields(
                    embed, recommended, other_models, numbered=True, chunk_size=25
                )

                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(self.t("model_list_error", error=e))

    @commands.command(name="lang")
    async def lang(self, ctx: commands.Context, language: str | None = None):
        """Changes the display language."""
        supported = self.bot.i18n.get_supported_languages()
        langs_str = ", ".join(supported)

        if language is None:
            # Show current language and usage
            await ctx.send(
                self.t("lang_usage", langs=langs_str, current=self.bot.i18n.language)
            )
            return

        if language not in supported:
            await ctx.send(self.t("lang_invalid", langs=langs_str))
            return

        self.bot.i18n.language = language
        await ctx.send(self.t("lang_changed", lang=language))

    @commands.group(name="history")
    async def history(self, ctx: commands.Context):
        """Conversation history management commands."""
        if ctx.invoked_subcommand is None:
            await self._handle_invalid_subcommand(ctx, "history_usage")

    def _calculate_history_range(
        self, total: int, start: int | None, count: int
    ) -> tuple[int, int]:
        """Calculate start and end indices for history display.

        Args:
            total: Total number of messages.
            start: User-specified start (1-based) or None for last N.
            count: Number of messages to show.

        Returns:
            Tuple of (start_index, end_index) for slicing.
        """
        count = max(1, min(count, 50))  # Limit to reasonable range

        if start is None:
            start_index = max(0, total - count)
        else:
            start_index = max(0, min(start - 1, total - 1))

        end_index = min(start_index + count, total)
        return start_index, end_index

    def _build_history_lines(
        self, messages: list, start_index: int, max_preview: int = 50
    ) -> list[str]:
        """Build formatted lines for history display.

        Args:
            messages: List of message objects.
            start_index: Starting index for numbering.
            max_preview: Maximum preview length.

        Returns:
            List of formatted message lines.
        """
        lines = []
        for i, msg in enumerate(messages):
            actual_index = start_index + i + 1  # 1-based
            role = msg.role.upper()
            preview = self._get_message_preview(msg, max_preview)
            lines.append(f"`{actual_index}`. [{role}] {preview}")
        return lines

    @history.command(name="list")
    async def history_list(
        self, ctx: commands.Context, start: int | None = None, count: int = 10
    ):
        """List conversation history with message numbers."""
        channel_id = ctx.channel.id

        try:
            history = self.bot.conversation_history.get(channel_id, [])

            if not history:
                await ctx.send(self.t("history_list_empty"))
                return

            total = len(history)
            start_index, end_index = self._calculate_history_range(total, start, count)
            shown_messages = history[start_index:end_index]

            embed = discord.Embed(
                title=self.t("history_list_title"),
                color=discord.Color.blue(),
            )

            # Build and add message lines
            lines = self._build_history_lines(shown_messages, start_index)
            chunk_size = 10
            for i in range(0, len(lines), chunk_size):
                chunk = lines[i : i + chunk_size]
                field_name = (
                    "\u200b" if i == 0
                    else f"{self.t('history_list_title')} ({i // chunk_size + 1})"
                )
                embed.add_field(name=field_name, value="\n".join(chunk), inline=False)

            embed.set_footer(
                text=self.t("history_list_footer", shown=len(shown_messages), total=total)
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(self.t("history_error", error=e))

    def _get_deletion_indices(self, history: list, idx: int) -> list[int]:
        """Get indices of messages to delete (including paired message).

        Args:
            history: Conversation history list.
            idx: Index of target message (0-based).

        Returns:
            List of indices to delete.
        """
        target_msg = history[idx]
        indices = [idx]

        if target_msg.role == "user":
            # Also delete next model response if exists
            if idx + 1 < len(history) and history[idx + 1].role == "model":
                indices.append(idx + 1)
        elif target_msg.role == "model":
            # Also delete previous user message if exists
            if idx - 1 >= 0 and history[idx - 1].role == "user":
                indices.insert(0, idx - 1)

        return indices

    def _build_deletion_preview(self, history: list, indices: list[int]) -> list[str]:
        """Build preview strings for messages to be deleted.

        Args:
            history: Conversation history list.
            indices: Indices of messages to delete.

        Returns:
            List of formatted preview strings.
        """
        previews = []
        for i in sorted(indices):
            msg = history[i]
            role = msg.role.upper()
            preview = self._get_message_preview(msg, max_length=100)
            previews.append(f"`{i + 1}`. [{role}] {preview}")
        return previews

    @history.command(name="delete")
    async def history_delete(self, ctx: commands.Context, index: int | None = None):
        """Delete a message and its pair from history."""
        if index is None:
            await ctx.send(self.t("history_delete_usage"))
            return

        channel_id = ctx.channel.id
        user_id = ctx.author.id

        try:
            history = self.bot.conversation_history.get(channel_id, [])

            if not history:
                await ctx.send(self.t("history_list_empty"))
                return

            idx = index - 1  # Convert to 0-based
            if idx < 0 or idx >= len(history):
                await ctx.send(self.t("history_delete_not_found", index=index))
                return

            indices_to_delete = self._get_deletion_indices(history, idx)
            messages_preview = self._build_deletion_preview(history, indices_to_delete)

            # Register pending confirmation
            self.bot.pending_delete_confirmations[user_id] = {
                "channel_id": channel_id,
                "indices": indices_to_delete,
            }

            await ctx.send(
                self.t(
                    "history_delete_confirm",
                    messages="\n".join(messages_preview),
                )
            )
        except Exception as e:
            await ctx.send(self.t("history_error", error=e))

    @history.command(name="clear")
    async def history_clear(self, ctx: commands.Context):
        """Clear all conversation history for this channel."""
        channel_id = ctx.channel.id

        try:
            # Clear conversation in history manager
            self.bot.history_manager.clear_conversation(channel_id)

            # Clear memory
            self.bot.conversation_history[channel_id] = []

            await ctx.send(self.t("history_cleared"))
        except Exception as e:
            await ctx.send(self.t("history_error", error=e))

    @history.command(name="export")
    async def history_export(self, ctx: commands.Context, filename: str | None = None):
        """Export conversation history to ZIP file with Markdown and images."""
        channel_id = ctx.channel.id

        try:
            # Load conversation data
            data = self.bot.history_manager.load_conversation(channel_id)

            if not data or not data.get("messages"):
                await ctx.send(self.t("history_export_empty"))
                return

            # Get branch name
            branch = self.bot.history_manager.get_current_branch(channel_id)

            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"{channel_id}_{branch}_{timestamp}"

            # Check if there are any images in the conversation
            has_images = any(
                "images" in msg and msg["images"]
                for msg in data.get("messages", [])
            )

            if has_images:
                # Create ZIP file with Markdown and images
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    # Add Markdown file
                    md_content = self._build_export_markdown(data, channel_id, branch)
                    zf.writestr("conversation.md", md_content.encode("utf-8"))

                    # Add image files
                    for msg in data.get("messages", []):
                        if "images" in msg:
                            for image_path in msg["images"]:
                                image_data = self.bot.history_manager.load_image(
                                    channel_id, image_path
                                )
                                if image_data:
                                    zf.writestr(image_path, image_data[0])

                zip_buffer.seek(0)
                file = discord.File(zip_buffer, filename=f"{filename}.zip")
            else:
                # No images, just send Markdown file
                md_content = self._build_export_markdown(data, channel_id, branch)
                file = discord.File(
                    io.BytesIO(md_content.encode("utf-8")),
                    filename=f"{filename}.md",
                )

            await ctx.send(self.t("history_export_success"), file=file)
        except Exception as e:
            await ctx.send(self.t("history_error", error=e))

    def _build_export_markdown(self, data: dict, channel_id: int, branch: str) -> str:
        """Build Markdown content from conversation data."""
        lines = [
            "# Conversation Export",
            "",
            f"- **Channel ID**: {channel_id}",
            f"- **Branch**: {branch}",
            f"- **Model**: {data.get('model', 'N/A')}",
            f"- **Exported at**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            "",
            "## Conversation",
            "",
        ]

        for msg in data.get("messages", []):
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")

            # Format timestamp if available
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

            lines.append(f"### {role} ({timestamp})")
            lines.append("")

            # Add images if present
            if "images" in msg:
                for image_path in msg["images"]:
                    lines.append(f"![image]({image_path})")
                    lines.append("")

            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    @commands.group(name="branch")
    async def branch(self, ctx: commands.Context):
        """Branch management commands."""
        if ctx.invoked_subcommand is None:
            await self._handle_invalid_subcommand(ctx, "branch_usage")

    @branch.command(name="create")
    async def branch_create(
        self, ctx: commands.Context, branch_name: str | None = None
    ):
        """Create a new branch from the current conversation and switch to it."""
        if branch_name is None:
            await ctx.send(self.t("branch_create_usage"))
            return

        channel_id = ctx.channel.id

        try:
            # Commit current state before branching
            self.bot.history_manager.commit(channel_id, "Auto-save before branch")

            # Create and switch to new branch
            self.bot.history_manager.create_branch(channel_id, branch_name, switch=True)

            # Reload history from disk (same content, but now on new branch)
            self.bot._reload_history_from_disk(channel_id)

            await ctx.send(self.t("branch_created", branch=branch_name))
        except RuntimeError as e:
            await ctx.send(self.t("branch_error", error=e))
        except Exception as e:
            await ctx.send(self.t("branch_error", error=e))

    @branch.command(name="list")
    async def branch_list(self, ctx: commands.Context):
        """List all branches for this channel."""
        channel_id = ctx.channel.id

        try:
            branches = self.bot.history_manager.list_branches(channel_id)
            current = self.bot.history_manager.get_current_branch(channel_id)

            if not branches:
                await ctx.send(self.t("branch_list_empty"))
                return

            # Format branch list with current branch highlighted
            branch_lines = []
            for b in branches:
                if b == current:
                    branch_lines.append(f"• **{b}** {self.t('branch_list_current')}")
                else:
                    branch_lines.append(f"• {b}")

            embed = discord.Embed(
                title=self.t("branch_list_title"),
                description="\n".join(branch_lines),
                color=discord.Color.blue(),
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(self.t("branch_error", error=e))

    @branch.command(name="switch")
    async def branch_switch(
        self, ctx: commands.Context, branch_name: str | None = None
    ):
        """Switch to a different branch."""
        # If no branch name, show list instead
        if branch_name is None:
            await self.branch_list(ctx)
            return

        channel_id = ctx.channel.id

        try:
            # Check if branch exists
            branches = self.bot.history_manager.list_branches(channel_id)
            if branch_name not in branches:
                await ctx.send(self.t("branch_not_found", branch=branch_name))
                return

            # Switch branch (auto-commits current state)
            self.bot.history_manager.switch_branch(channel_id, branch_name)

            # Reload history from disk
            self.bot._reload_history_from_disk(channel_id)

            await ctx.send(self.t("branch_switched", branch=branch_name))
        except Exception as e:
            await ctx.send(self.t("branch_error", error=e))

    @branch.command(name="delete")
    async def branch_delete(
        self, ctx: commands.Context, branch_name: str | None = None
    ):
        """Delete a branch."""
        if branch_name is None:
            await ctx.send(self.t("branch_delete_usage"))
            return

        channel_id = ctx.channel.id

        try:
            self.bot.history_manager.delete_branch(channel_id, branch_name)
            await ctx.send(self.t("branch_deleted", branch=branch_name))
        except RuntimeError as e:
            await ctx.send(self.t("branch_error", error=e))
        except Exception as e:
            await ctx.send(self.t("branch_error", error=e))

    @branch.command(name="merge")
    async def branch_merge(self, ctx: commands.Context, branch_name: str | None = None):
        """Merge another branch into the current branch."""
        if branch_name is None:
            await ctx.send(self.t("branch_merge_usage"))
            return

        channel_id = ctx.channel.id

        try:
            # Commit current state before merge
            self.bot.history_manager.commit(channel_id, "Auto-save before merge")

            # Merge branch
            merged_count = self.bot.history_manager.merge_branch(
                channel_id, branch_name
            )

            # Reload history from disk
            self.bot._reload_history_from_disk(channel_id)

            if merged_count > 0:
                await ctx.send(
                    self.t("branch_merged", branch=branch_name, count=merged_count)
                )
            else:
                await ctx.send(self.t("branch_merge_nothing"))
        except RuntimeError as e:
            await ctx.send(self.t("branch_error", error=e))
        except Exception as e:
            await ctx.send(self.t("branch_error", error=e))

    @commands.group(name="system_prompt")
    async def system_prompt(self, ctx: commands.Context):
        """System prompt management commands (Master Instruction)."""
        if ctx.invoked_subcommand is None:
            await self._handle_invalid_subcommand(ctx, "prompt_usage")

    @system_prompt.command(name="show")
    async def prompt_show(self, ctx: commands.Context):
        """Show the current master system prompt."""
        try:
            # Load master prompt directly from file
            master_path = self.bot.history_manager.get_master_prompt_path()
            content = master_path.read_text(encoding="utf-8") if master_path.exists() else ""

            if not content.strip():
                await ctx.send(self.t("prompt_show_empty"))
                return

            # Discord message limit is 2000 chars, use embed for better formatting
            # Split if too long
            if len(content) <= 1900:
                embed = discord.Embed(
                    title=self.t("prompt_show_title"),
                    description=f"```\n{content}\n```",
                    color=discord.Color.blue(),
                )
                await ctx.send(embed=embed)
            else:
                # Split into chunks
                await ctx.send(self.t("prompt_show_title"))
                chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)]
                for chunk in chunks:
                    await ctx.send(f"```\n{chunk}\n```")
        except Exception as e:
            await ctx.send(self.t("prompt_error", error=e))

    @system_prompt.command(name="download")
    async def prompt_download(self, ctx: commands.Context):
        """Download the current master system prompt as a file."""
        try:
            master_path = self.bot.history_manager.get_master_prompt_path()
            content = master_path.read_text(encoding="utf-8") if master_path.exists() else ""

            if not content.strip():
                await ctx.send(self.t("prompt_download_empty"))
                return

            # Create discord.File from content
            file = discord.File(
                io.BytesIO(content.encode("utf-8")),
                filename="GEMINI.md",
            )

            await ctx.send(self.t("prompt_download_success"), file=file)
        except Exception as e:
            await ctx.send(self.t("prompt_error", error=e))

    @commands.command(name="image")
    async def image(self, ctx: commands.Context, *, prompt: str | None = None):
        """Generate an image from a text prompt."""
        if prompt is None:
            await ctx.send(self.t("image_usage"))
            return

        async with ctx.typing():
            try:
                response = await self.bot.gemini_client.aio.models.generate_content(
                    model="gemini-2.0-flash-exp-image-generation",
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    ),
                    contents=prompt,
                )

                if not response.candidates or not response.candidates[0].content:
                    await ctx.send(self.t("image_no_response"))
                    return

                text_response = None
                image_data = None
                image_mime = None

                for part in response.candidates[0].content.parts:
                    if hasattr(part, "text") and part.text:
                        text_response = part.text
                    if hasattr(part, "inline_data") and part.inline_data:
                        image_data = part.inline_data.data
                        image_mime = part.inline_data.mime_type

                if image_data:
                    # Determine file extension from mime type
                    ext = "png"
                    if image_mime:
                        if "jpeg" in image_mime or "jpg" in image_mime:
                            ext = "jpg"
                        elif "webp" in image_mime:
                            ext = "webp"

                    # Create discord.File from image data
                    file = discord.File(
                        io.BytesIO(image_data), filename=f"generated_image.{ext}"
                    )

                    # Send with optional text description
                    if text_response:
                        await ctx.send(text_response, file=file)
                    else:
                        await ctx.send(file=file)
                elif text_response:
                    # Model returned only text (e.g., explaining why it can't generate)
                    await ctx.send(text_response)
                else:
                    await ctx.send(self.t("image_no_response"))

            except Exception as e:
                await ctx.send(self.t("image_error", error=e))

    @commands.group(name="channel_prompt")
    async def channel_prompt(self, ctx: commands.Context):
        """Channel instruction management commands."""
        if ctx.invoked_subcommand is None:
            await self._handle_invalid_subcommand(ctx, "channel_prompt_usage")

    @channel_prompt.command(name="show")
    async def channel_prompt_show(self, ctx: commands.Context):
        """Show the current channel instruction."""
        channel_id = ctx.channel.id

        try:
            content = self.bot.history_manager.load_channel_prompt(channel_id)

            if not content.strip():
                await ctx.send(self.t("channel_prompt_show_empty"))
                return

            # Discord message limit is 2000 chars, use embed for better formatting
            # Split if too long
            if len(content) <= 1900:
                embed = discord.Embed(
                    title=self.t("channel_prompt_show_title"),
                    description=f"```\n{content}\n```",
                    color=discord.Color.blue(),
                )
                await ctx.send(embed=embed)
            else:
                # Split into chunks
                await ctx.send(self.t("channel_prompt_show_title"))
                chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)]
                for chunk in chunks:
                    await ctx.send(f"```\n{chunk}\n```")
        except Exception as e:
            await ctx.send(self.t("channel_prompt_error", error=e))

    @channel_prompt.command(name="download")
    async def channel_prompt_download(self, ctx: commands.Context):
        """Download the current channel instruction as a file."""
        channel_id = ctx.channel.id

        try:
            content = self.bot.history_manager.load_channel_prompt(channel_id)

            if not content.strip():
                await ctx.send(self.t("channel_prompt_download_empty"))
                return

            # Create discord.File from content
            file = discord.File(
                io.BytesIO(content.encode("utf-8")),
                filename="channel_instruction.md",
            )

            await ctx.send(self.t("channel_prompt_download_success"), file=file)
        except Exception as e:
            await ctx.send(self.t("channel_prompt_error", error=e))

    @channel_prompt.command(name="clear")
    async def channel_prompt_clear(self, ctx: commands.Context):
        """Clear the channel instruction."""
        channel_id = ctx.channel.id

        try:
            self.bot.history_manager.save_system_prompt(channel_id, "")
            await ctx.send(self.t("channel_prompt_clear_success"))
        except Exception as e:
            await ctx.send(self.t("channel_prompt_error", error=e))

    @commands.group(name="config")
    async def config(self, ctx: commands.Context):
        """Generation config management commands."""
        if ctx.invoked_subcommand is None:
            await self._handle_invalid_subcommand(ctx, "config_usage")

    @config.command(name="show")
    async def config_show(self, ctx: commands.Context):
        """Show current generation config."""
        channel_id = ctx.channel.id

        try:
            gen_config = self.bot.history_manager.load_generation_config(channel_id)
            schema = self.bot.history_manager.GENERATION_CONFIG_SCHEMA

            embed = discord.Embed(
                title=self.t("config_show_title"),
                color=discord.Color.blue(),
            )

            for key, key_schema in schema.items():
                if key in gen_config:
                    value = gen_config[key]
                    status = f"**{value}**"
                else:
                    status = self.t("config_default")

                # Show range info
                range_info = f"({key_schema['min']} - {key_schema['max']})"
                embed.add_field(
                    name=f"{key} {range_info}",
                    value=status,
                    inline=True,
                )

            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(self.t("config_error", error=e))

    @config.command(name="set")
    async def config_set(
        self, ctx: commands.Context, key: str | None = None, value: str | None = None
    ):
        """Set a generation config value."""
        if key is None or value is None:
            schema = self.bot.history_manager.GENERATION_CONFIG_SCHEMA
            valid_keys = ", ".join(schema.keys())
            await ctx.send(self.t("config_set_usage", valid_keys=valid_keys))
            return

        channel_id = ctx.channel.id

        try:
            self.bot.history_manager.save_generation_config_value(
                channel_id, key, value
            )
            await ctx.send(
                self.t("config_set_success", config_key=key, config_value=value)
            )
        except ValueError as e:
            await ctx.send(self.t("config_error", error=e))
        except Exception as e:
            await ctx.send(self.t("config_error", error=e))

    @config.command(name="reset")
    async def config_reset(self, ctx: commands.Context, key: str | None = None):
        """Reset generation config to default."""
        channel_id = ctx.channel.id

        try:
            self.bot.history_manager.reset_generation_config(channel_id, key)
            if key:
                await ctx.send(self.t("config_reset_key", config_key=key))
            else:
                await ctx.send(self.t("config_reset_all"))
        except Exception as e:
            await ctx.send(self.t("config_error", error=e))


    # ==================== Mode Commands ====================

    # Available tool modes
    # Internal values: "default" (Google Search), "calendar", "todo"
    TOOL_MODES = {
        "default": "Default - Google検索を使用",
        "calendar": "Calendar - Google Calendarを使用（要連携）",
        "todo": "Todo - Google Tasksを使用（要連携）",
    }

    @commands.group(name="mode")
    async def mode(self, ctx: commands.Context):
        """Switch tool mode for this channel."""
        if ctx.invoked_subcommand is None:
            # Show current mode and available modes
            channel_id = ctx.channel.id
            current_mode = self.bot.get_tool_mode(channel_id)

            embed = discord.Embed(
                title=self.t("mode_title"),
                color=discord.Color.blue(),
            )
            embed.add_field(
                name=self.t("mode_current"),
                value=f"`{current_mode}` - {self.TOOL_MODES.get(current_mode, '')}",
                inline=False,
            )

            modes_list = "\n".join(
                f"`{mode}` - {desc}" for mode, desc in self.TOOL_MODES.items()
            )
            embed.add_field(
                name=self.t("mode_available"),
                value=modes_list,
                inline=False,
            )
            embed.add_field(
                name=self.t("mode_usage_title"),
                value=self.t("mode_usage"),
                inline=False,
            )

            await ctx.send(embed=embed)

    @mode.command(name="default")
    async def mode_default(self, ctx: commands.Context):
        """Switch to default mode (Google Search)."""
        channel_id = ctx.channel.id
        self.bot.set_tool_mode(channel_id, "default")
        await ctx.send(self.t("mode_changed", mode="default"))

    @mode.command(name="calendar")
    async def mode_calendar(self, ctx: commands.Context):
        """Switch to Calendar mode."""
        channel_id = ctx.channel.id
        user_id = ctx.author.id

        # Check if calendar is configured
        calendar_auth = self._get_calendar_auth()
        if calendar_auth is None:
            await self._send_google_setup_guide(ctx)
            return

        # Check if user is authenticated
        if not calendar_auth.is_user_authenticated(user_id):
            await ctx.send(self.t("mode_calendar_not_linked"))
            return

        self.bot.set_tool_mode(channel_id, "calendar")
        await ctx.send(self.t("mode_changed", mode="calendar"))

    @mode.command(name="todo")
    async def mode_todo(self, ctx: commands.Context):
        """Switch to Todo mode (Google Tasks)."""
        channel_id = ctx.channel.id
        user_id = ctx.author.id

        # Check if calendar/tasks is configured (uses same credentials)
        calendar_auth = self._get_calendar_auth()
        if calendar_auth is None:
            await self._send_google_setup_guide(ctx)
            return

        # Check if user is authenticated
        if not calendar_auth.is_user_authenticated(user_id):
            await ctx.send(self.t("mode_todo_not_linked"))
            return

        self.bot.set_tool_mode(channel_id, "todo")
        await ctx.send(self.t("mode_changed", mode="todo"))

    # ==================== Google Commands ====================

    def _get_calendar_auth(self) -> CalendarAuthManager | None:
        """Get the calendar auth manager from bot, or None if not available."""
        if hasattr(self.bot, "calendar_auth") and self.bot.calendar_auth is not None:
            return self.bot.calendar_auth
        return None

    async def _send_google_setup_guide(self, ctx: commands.Context) -> None:
        """Send a helpful setup guide when credentials.json is missing or invalid."""
        # Create a temporary manager just to check configuration status
        temp_manager = CalendarAuthManager()
        config_status = temp_manager.get_configuration_status()

        error_code = config_status.get("error_code", "unknown")
        setup_url = config_status.get("setup_url", "https://console.cloud.google.com/apis/credentials")

        # Build embed with setup instructions
        embed = discord.Embed(
            title=self.t("google_setup_required_title"),
            color=discord.Color.orange(),
        )

        # Error-specific message
        if error_code == "file_not_found":
            embed.description = self.t("google_setup_file_not_found")
        elif error_code == "invalid_json":
            embed.description = self.t("google_setup_invalid_json")
        elif error_code == "missing_installed":
            embed.description = self.t("google_setup_wrong_format")
        elif error_code in ("missing_client_id", "missing_client_secret"):
            embed.description = self.t("google_setup_missing_fields")
        else:
            embed.description = self.t("google_setup_unknown_error", message=config_status.get("message", ""))

        # Add setup steps
        embed.add_field(
            name=self.t("google_setup_steps_title"),
            value=self.t("google_setup_steps"),
            inline=False,
        )

        # Add link to Google Cloud Console
        embed.add_field(
            name=self.t("google_setup_link_title"),
            value=setup_url,
            inline=False,
        )

        await ctx.send(embed=embed)

    @commands.group(name="google")
    async def google(self, ctx: commands.Context):
        """Google integration commands."""
        if ctx.invoked_subcommand is None:
            await self._handle_invalid_subcommand(ctx, "google_usage")

    @google.command(name="link")
    async def google_link(self, ctx: commands.Context):
        """Link your Google account."""
        user_id = ctx.author.id

        calendar_auth = self._get_calendar_auth()

        # Check if calendar manager is available and configured
        if calendar_auth is None:
            await self._send_google_setup_guide(ctx)
            return

        # Check if credentials.json is valid
        if not calendar_auth.is_credentials_configured():
            await self._send_google_setup_guide(ctx)
            return

        # Check if already authenticated
        if calendar_auth.is_user_authenticated(user_id):
            await ctx.send(self.t("google_already_linked"))
            return

        try:
            # Start OAuth flow
            auth_url, future = await calendar_auth.start_auth_flow(user_id)

            # Send DM with auth URL for privacy
            try:
                dm_channel = await ctx.author.create_dm()
                await dm_channel.send(self.t("google_link_dm", url=auth_url))
                await ctx.send(self.t("google_link_check_dm"))
            except discord.Forbidden:
                # Can't DM user, send in channel (less secure but functional)
                await ctx.send(self.t("google_link_url", url=auth_url))

            # Wait for auth to complete (with timeout)
            try:
                await future
                await ctx.send(self.t("google_link_success", user=ctx.author.mention))
            except TimeoutError:
                await ctx.send(self.t("google_link_timeout"))
            except Exception as e:
                await ctx.send(self.t("google_link_error", error=str(e)))

        except FileNotFoundError:
            await self._send_google_setup_guide(ctx)
        except Exception as e:
            await ctx.send(self.t("google_error", error=str(e)))

    @google.command(name="unlink")
    async def google_unlink(self, ctx: commands.Context):
        """Unlink your Google account."""
        user_id = ctx.author.id

        calendar_auth = self._get_calendar_auth()

        if calendar_auth is None:
            await self._send_google_setup_guide(ctx)
            return

        if calendar_auth.revoke_user(user_id):
            await ctx.send(self.t("google_unlink_success"))
        else:
            await ctx.send(self.t("google_not_linked"))

    @google.command(name="status")
    async def google_status(self, ctx: commands.Context):
        """Check your Google account connection status."""
        user_id = ctx.author.id

        calendar_auth = self._get_calendar_auth()

        # If not configured, show setup guide
        if calendar_auth is None:
            await self._send_google_setup_guide(ctx)
            return

        # Check if credentials.json is valid
        if not calendar_auth.is_credentials_configured():
            await self._send_google_setup_guide(ctx)
            return

        status = calendar_auth.get_auth_status(user_id)

        if status["authenticated"]:
            embed = discord.Embed(
                title=self.t("google_status_title"),
                description=self.t("google_status_connected"),
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title=self.t("google_status_title"),
                description=self.t(
                    "google_status_not_connected",
                    reason=status.get("message", ""),
                ),
                color=discord.Color.orange(),
            )
            embed.add_field(
                name=self.t("google_status_hint_title"),
                value=self.t("google_status_hint"),
                inline=False,
            )

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    """Load the Commands cog."""
    await bot.add_cog(Commands(bot))
