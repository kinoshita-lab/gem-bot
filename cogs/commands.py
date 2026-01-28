import io
from datetime import datetime

import discord
from discord.ext import commands
from google.genai import types


class Commands(commands.Cog):
    """All bot commands."""

    # Recommended models shown at the top of the list
    RECOMMENDED_MODELS = ["gemini-flash-latest", "gemini-3-pro-preview"]

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def t(self, key: str, **kwargs) -> str:
        """Shortcut for translation."""
        return self.bot.i18n.t(key, **kwargs)

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

    @commands.group(name="model")
    async def model(self, ctx: commands.Context):
        """Model management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send(self.t("model_usage"))

    @model.command(name="list")
    async def model_list(self, ctx: commands.Context):
        """Lists all available Gemini models."""
        async with ctx.typing():
            try:
                models = [
                    m async for m in await self.bot.gemini_client.aio.models.list()
                ]
                current_model = self.bot.get_model(ctx.channel.id)

                # Create embed for model list
                embed = discord.Embed(
                    title=self.t("model_list_title"),
                    description=self.t("model_list_current", model=current_model),
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

                # Separate recommended models from the rest
                recommended = [m for m in self.RECOMMENDED_MODELS if m in model_names]
                other_models = [m for m in model_names if m not in recommended]

                # Add recommended models field
                if recommended:
                    embed.add_field(
                        name=self.t("model_list_recommended"),
                        value="\n".join(f"• {name}" for name in recommended),
                        inline=False,
                    )

                # Split other models into chunks if too many
                chunk_size = 20
                for i in range(0, len(other_models), chunk_size):
                    chunk = other_models[i : i + chunk_size]
                    field_name = (
                        self.t("model_list_field")
                        if i == 0
                        else self.t(
                            "model_list_field_continued", num=i // chunk_size + 1
                        )
                    )
                    embed.add_field(
                        name=field_name,
                        value="\n".join(f"• {name}" for name in chunk),
                        inline=False,
                    )

                embed.set_footer(
                    text=self.t("model_list_footer", count=len(model_names))
                )
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
                # Fetch available models
                models = [
                    m async for m in await self.bot.gemini_client.aio.models.list()
                ]
                model_names: list[str] = []
                for m in models:
                    name = m.name
                    if name:
                        if name.startswith("models/"):
                            name = name.replace("models/", "")
                        model_names.append(name)

                # Sort model names
                model_names.sort()

                # Separate recommended models from the rest
                recommended = [m for m in self.RECOMMENDED_MODELS if m in model_names]
                other_models = [m for m in model_names if m not in recommended]

                # Create ordered list: recommended first, then others
                ordered_models = recommended + other_models

                current_model = self.bot.get_model(channel_id)

                # Register pending selection (overwrites any previous selection for this user)
                self.bot.pending_model_selections[user_id] = {
                    "channel_id": channel_id,
                    "models": ordered_models,
                }

                # Send selection prompt
                embed = discord.Embed(
                    title=self.t("model_select_title"),
                    description=self.t("model_select_description", model=current_model),
                    color=discord.Color.blue(),
                )

                # Add recommended models field
                if recommended:
                    field_value = "\n".join(
                        f"`{j + 1}`. {name}" for j, name in enumerate(recommended)
                    )
                    embed.add_field(
                        name=self.t("model_list_recommended"),
                        value=field_value,
                        inline=False,
                    )

                # Split other models into chunks if too many
                chunk_size = 25
                offset = len(recommended)
                for i in range(0, len(other_models), chunk_size):
                    chunk = other_models[i : i + chunk_size]
                    field_name = (
                        self.t("model_list_field")
                        if i == 0
                        else self.t(
                            "model_list_field_continued", num=i // chunk_size + 1
                        )
                    )
                    field_value = "\n".join(
                        f"`{offset + i + j + 1}`. {name}"
                        for j, name in enumerate(chunk)
                    )
                    embed.add_field(name=field_name, value=field_value, inline=False)

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
            await ctx.send(self.t("history_usage"))

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
            # Limit count to reasonable range
            count = max(1, min(count, 50))

            # Determine start index (1-based input, convert to 0-based)
            if start is None:
                # Default: show last N messages
                start_index = max(0, total - count)
            else:
                # User specified start (1-based)
                start_index = max(0, min(start - 1, total - 1))

            # Calculate end index
            end_index = min(start_index + count, total)
            shown_messages = history[start_index:end_index]

            embed = discord.Embed(
                title=self.t("history_list_title"),
                color=discord.Color.blue(),
            )

            # Build message list
            lines = []
            for i, msg in enumerate(shown_messages):
                actual_index = start_index + i + 1  # 1-based index
                role = msg.role.upper()
                # Get text content from parts
                content = ""
                if msg.parts:
                    for part in msg.parts:
                        if hasattr(part, "text") and part.text:
                            content = part.text
                            break
                # Truncate long messages
                preview = content[:50] + "..." if len(content) > 50 else content
                # Replace newlines with spaces for cleaner display
                preview = preview.replace("\n", " ")
                lines.append(f"`{actual_index}`. [{role}] {preview}")

            # Split into multiple fields if too long
            chunk_size = 10
            for i in range(0, len(lines), chunk_size):
                chunk = lines[i : i + chunk_size]
                field_name = (
                    self.t("history_list_title")
                    if i == 0
                    else f"{self.t('history_list_title')} ({i // chunk_size + 1})"
                )
                embed.add_field(
                    name=field_name if i > 0 else "\u200b",  # Zero-width space for first
                    value="\n".join(chunk),
                    inline=False,
                )

            embed.set_footer(
                text=self.t("history_list_footer", shown=len(shown_messages), total=total)
            )
            await ctx.send(embed=embed)
        except Exception as e:
            await ctx.send(self.t("history_error", error=e))

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

            # Convert to 0-based index
            idx = index - 1

            if idx < 0 or idx >= len(history):
                await ctx.send(self.t("history_delete_not_found", index=index))
                return

            # Determine which messages to delete (pair deletion)
            target_msg = history[idx]
            indices_to_delete = [idx]

            if target_msg.role == "user":
                # If user message, also delete next model response if exists
                if idx + 1 < len(history) and history[idx + 1].role == "model":
                    indices_to_delete.append(idx + 1)
            elif target_msg.role == "model":
                # If model message, also delete previous user message if exists
                if idx - 1 >= 0 and history[idx - 1].role == "user":
                    indices_to_delete.insert(0, idx - 1)

            # Build confirmation message
            messages_preview = []
            for i in sorted(indices_to_delete):
                msg = history[i]
                role = msg.role.upper()
                content = ""
                if msg.parts:
                    for part in msg.parts:
                        if hasattr(part, "text") and part.text:
                            content = part.text
                            break
                preview = content[:100] + "..." if len(content) > 100 else content
                preview = preview.replace("\n", " ")
                messages_preview.append(f"`{i + 1}`. [{role}] {preview}")

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
        """Export conversation history to Markdown file."""
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

            # Build Markdown content
            md_content = self._build_export_markdown(data, channel_id, branch)

            # Create discord.File
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
            lines.append(content)
            lines.append("")

        return "\n".join(lines)

    @commands.group(name="branch")
    async def branch(self, ctx: commands.Context):
        """Branch management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send(self.t("branch_usage"))

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

    @commands.group(name="prompt")
    async def prompt(self, ctx: commands.Context):
        """System prompt management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send(self.t("prompt_usage"))

    @prompt.command(name="show")
    async def prompt_show(self, ctx: commands.Context):
        """Show the current system prompt."""
        channel_id = ctx.channel.id

        try:
            content = self.bot.history_manager.load_system_prompt(channel_id)

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

    @prompt.command(name="set")
    async def prompt_set(self, ctx: commands.Context, *, content: str | None = None):
        """Set the system prompt."""
        if content is None:
            await ctx.send(self.t("prompt_set_usage"))
            return

        channel_id = ctx.channel.id

        try:
            self.bot.history_manager.save_system_prompt(channel_id, content)
            await ctx.send(self.t("prompt_set_success"))
        except Exception as e:
            await ctx.send(self.t("prompt_error", error=e))

    @prompt.command(name="clear")
    async def prompt_clear(self, ctx: commands.Context):
        """Clear the system prompt."""
        channel_id = ctx.channel.id

        try:
            self.bot.history_manager.save_system_prompt(channel_id, "")
            await ctx.send(self.t("prompt_clear_success"))
        except Exception as e:
            await ctx.send(self.t("prompt_error", error=e))

    @prompt.command(name="append")
    async def prompt_append(self, ctx: commands.Context, *, content: str | None = None):
        """Append text to the system prompt."""
        if content is None:
            await ctx.send(self.t("prompt_append_usage"))
            return

        channel_id = ctx.channel.id

        try:
            current = self.bot.history_manager.load_system_prompt(channel_id)
            # Append with newline if current content exists
            if current.strip():
                new_content = current + "\n" + content
            else:
                new_content = content
            self.bot.history_manager.save_system_prompt(channel_id, new_content)
            await ctx.send(self.t("prompt_append_success"))
        except Exception as e:
            await ctx.send(self.t("prompt_error", error=e))

    @prompt.command(name="download")
    async def prompt_download(self, ctx: commands.Context):
        """Download the current system prompt as a file."""
        channel_id = ctx.channel.id

        try:
            content = self.bot.history_manager.load_system_prompt(channel_id)

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

    @commands.group(name="config")
    async def config(self, ctx: commands.Context):
        """Generation config management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send(self.t("config_usage"))

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


async def setup(bot: commands.Bot):
    """Load the Commands cog."""
    await bot.add_cog(Commands(bot))
