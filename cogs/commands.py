import asyncio
import base64
import io
import zipfile
from datetime import datetime
from typing import Literal

import discord
from discord import app_commands
from discord.ext import commands
from google.genai import types

from calendar_manager import CalendarAuthManager


class Commands(commands.Cog):
    """All bot commands."""

    # Recommended models shown at the top of the list
    RECOMMENDED_MODELS = ["gemini-flash-latest", "gemini-3-pro-preview"]

    # Available tool modes
    # Internal values: "default" (Google Search), "calendar", "todo"
    TOOL_MODES = {
        "default": "Default - Google Search",
        "calendar": "Calendar - Google Calendar (Requires Link)",
        "todo": "Todo - Google Tasks (Requires Link)",
    }

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

    async def _is_model_usable(self, model_name: str) -> bool:
        """Check if a model is usable by making a simple API call.

        Args:
            model_name: Name of the model to test.

        Returns:
            True if model is usable, False otherwise.
        """
        try:
            response = await self.bot.gemini_client.aio.models.generate_content(
                model=model_name,
                config=types.GenerateContentConfig(
                    system_instruction="",
                ),
                contents="Hi",
            )
            return response is not None
        except Exception as e:
            error_str = str(e)
            if "404" in error_str or "429" in error_str or "400" in error_str:
                return False
            return False

    async def _fetch_models_to_cache(self) -> None:
        """Fetch models from API and cache them on the bot instance."""
        recommended, all_models = await self._fetch_and_sort_models()

        # Filter to only usable models
        usable_models = []
        semaphore = asyncio.Semaphore(5)

        async def check_model(model_name: str) -> tuple[str, bool]:
            async with semaphore:
                usable = await self._is_model_usable(model_name)
                return model_name, usable

        tasks = [check_model(m) for m in all_models]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                continue
            model_name, usable = result
            if usable:
                usable_models.append(model_name)

        self.bot.recommended_models = [m for m in recommended if m in usable_models]
        self.bot.available_models = usable_models

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

    def _get_calendar_auth(self) -> CalendarAuthManager | None:
        """Get the calendar auth manager from bot, or None if not available."""
        if hasattr(self.bot, "calendar_auth") and self.bot.calendar_auth is not None:
            return self.bot.calendar_auth
        return None
    
    async def _send_google_setup_guide(self, interaction: discord.Interaction) -> None:
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

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # =========================================================================
    # Autocomplete Handlers
    # =========================================================================

    async def model_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for model selection."""
        if not self.bot.available_models:
            return []

        all_models = self.bot.recommended_models + [
            m for m in self.bot.available_models if m not in self.bot.recommended_models
        ]

        return [
            app_commands.Choice(name=model, value=model)
            for model in all_models
            if current.lower() in model.lower()
        ][:25]

    async def branch_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for branch selection."""
        channel_id = interaction.channel_id
        branches = self.bot.history_manager.list_branches(channel_id)
        
        return [
            app_commands.Choice(name=branch, value=branch)
            for branch in branches
            if current.lower() in branch.lower()
        ][:25]

    async def config_key_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for config keys."""
        schema = self.bot.history_manager.GENERATION_CONFIG_SCHEMA
        return [
            app_commands.Choice(name=key, value=key)
            for key in schema.keys()
            if current.lower() in key.lower()
        ][:25]

    async def history_delete_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        """Autocomplete for history delete - shows message previews."""
        channel_id = interaction.channel_id
        history = self.bot.conversation_history.get(channel_id, [])

        choices = []
        for i, msg in enumerate(history):
            index = i + 1
            if current and not str(index).startswith(current):
                continue
            role = msg.role.upper()
            preview = self._get_message_preview(msg, max_length=40)
            choices.append(
                app_commands.Choice(name=f"{index}. [{role}] {preview}", value=str(index))
            )

        return choices[:25]

    # =========================================================================
    # Slash Commands Group: /gem
    # =========================================================================
    
    # Root group
    gem_group = app_commands.Group(name="gem", description="Gemini Bot Commands")

    # Subgroups
    model_group = app_commands.Group(name="model", parent=gem_group, description="Model management")
    history_group = app_commands.Group(name="history", parent=gem_group, description="History management")
    branch_group = app_commands.Group(name="branch", parent=gem_group, description="Branch management")
    mode_group = app_commands.Group(name="mode", parent=gem_group, description="Tool mode management")
    config_group = app_commands.Group(name="config", parent=gem_group, description="Generation config")
    
    # Prompt management (Directly under gem_group to avoid nesting limits)
    system_prompt_group = app_commands.Group(name="system-prompt", parent=gem_group, description="System prompt (Master) management")
    channel_prompt_group = app_commands.Group(name="channel-prompt", parent=gem_group, description="Channel prompt management")
    
    google_group = app_commands.Group(name="google", parent=gem_group, description="Google integration")
    thought_signature_group = app_commands.Group(name="thought-signature", parent=gem_group, description="Thought signature management")


    # --- Basic Commands ---

    @gem_group.command(name="info")
    async def info(self, interaction: discord.Interaction):
        """Displays information about the bot."""
        channel_id = interaction.channel_id
        model = self.bot.get_model(channel_id)
        branch = self.bot.history_manager.get_current_branch(channel_id)
        
        embed = discord.Embed(
            title=self.t("bot_info_title"), color=discord.Color.blue()
        )
        embed.add_field(name=self.t("model"), value=model, inline=False)
        embed.add_field(name=self.t("branch"), value=branch or "N/A", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @gem_group.command(name="lang")
    @app_commands.describe(language="The language to set")
    @app_commands.choices(language=[
        app_commands.Choice(name="English", value="en"),
        app_commands.Choice(name="Japanese", value="ja"),
    ])
    async def lang(self, interaction: discord.Interaction, language: app_commands.Choice[str]):
        """Changes the display language."""
        self.bot.i18n.language = language.value
        await interaction.response.send_message(self.t("lang_changed", lang=language.value))

    @gem_group.command(name="image")
    @app_commands.describe(prompt="The prompt for image generation")
    async def image(self, interaction: discord.Interaction, prompt: str):
        """Generate an image from a text prompt."""
        await interaction.response.defer() # Long running task

        try:
            response = await self.bot.gemini_client.aio.models.generate_content(
                model="gemini-2.0-flash-exp-image-generation",
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
                contents=prompt,
            )

            if not response.candidates or not response.candidates[0].content:
                await interaction.followup.send(self.t("image_no_response"))
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
                    await interaction.followup.send(content=text_response, file=file)
                else:
                    await interaction.followup.send(file=file)
            elif text_response:
                # Model returned only text
                await interaction.followup.send(text_response)
            else:
                await interaction.followup.send(self.t("image_no_response"))

        except Exception as e:
            await interaction.followup.send(self.t("image_error", error=e))

    # --- Model Group ---

    @model_group.command(name="list")
    async def model_list(self, interaction: discord.Interaction):
        """Lists all available Gemini models."""
        await interaction.response.defer()
        
        try:
            recommended, other_models = await self._fetch_and_sort_models()
            current_model = self.bot.get_model(interaction.channel_id)
            total_count = len(recommended) + len(other_models)

            embed = discord.Embed(
                title=self.t("model_list_title"),
                description=self.t("model_list_current", model=current_model),
                color=discord.Color.green(),
            )

            # Add recommended models field
            if recommended:
                embed.add_field(
                    name=self.t("model_list_recommended"),
                    value="\n".join(f"• {name}" for name in recommended),
                    inline=False,
                )

            # Add other models in chunks (simplified for slash command embed)
            if other_models:
                # Just show first 20 other models to avoid hit limits
                chunk = other_models[:20]
                value = "\n".join(f"• {name}" for name in chunk)
                if len(other_models) > 20:
                    value += f"\n... and {len(other_models) - 20} more"
                
                embed.add_field(name=self.t("model_list_field"), value=value, inline=False)

            embed.set_footer(text=self.t("model_list_footer", count=total_count))
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(self.t("model_list_error", error=e))

    @model_group.command(name="set")
    @app_commands.describe(model="The model to use")
    @app_commands.autocomplete(model=model_autocomplete)
    async def model_set(self, interaction: discord.Interaction, model: str):
        """Set the Gemini model to use."""
        channel_id = interaction.channel_id
        
        # Verify model exists? 
        # Actually, allowing any string is fine as new models might appear before we update cache.
        # But if we wanted to be strict, we'd check against API list.
        # For now, trust the user input (especially with autocomplete help).
        
        self.bot.set_model(channel_id, model)
        await interaction.response.send_message(
            self.t("model_select_changed", model=model)
        )

    # --- History Group ---

    @history_group.command(name="list")
    @app_commands.describe(start="Starting message number (optional)", count="Number of messages to show (max 50)")
    async def history_list(self, interaction: discord.Interaction, start: int = None, count: int = 10):
        """List conversation history with message numbers."""
        channel_id = interaction.channel_id
        
        try:
            history = self.bot.conversation_history.get(channel_id, [])

            if not history:
                await interaction.response.send_message(self.t("history_list_empty"))
                return

            total = len(history)
            
            # Logic from old command
            count = max(1, min(count, 50))
            if start is None:
                start_index = max(0, total - count)
            else:
                start_index = max(0, min(start - 1, total - 1))
            
            end_index = min(start_index + count, total)
            shown_messages = history[start_index:end_index]

            embed = discord.Embed(
                title=self.t("history_list_title"),
                color=discord.Color.blue(),
            )

            # Build lines
            lines = []
            for i, msg in enumerate(shown_messages):
                actual_index = start_index + i + 1
                role = msg.role.upper()
                preview = self._get_message_preview(msg)
                lines.append(f"`{actual_index}`. [{role}] {preview}")

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
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(self.t("history_error", error=e))

    @history_group.command(name="delete")
    @app_commands.describe(index="The message number to delete")
    @app_commands.autocomplete(index=history_delete_autocomplete)
    async def history_delete(self, interaction: discord.Interaction, index: str):
        """Delete a message and its pair from memory (does not delete Discord messages)."""
        channel_id = interaction.channel_id

        try:
            index_int = int(index)
        except ValueError:
            await interaction.response.send_message(self.t("history_delete_invalid_index"))
            return

        try:
            history = self.bot.conversation_history.get(channel_id, [])
            if not history:
                await interaction.response.send_message(self.t("history_list_empty"))
                return

            idx = index_int - 1
            if idx < 0 or idx >= len(history):
                await interaction.response.send_message(self.t("history_delete_not_found", index=index_int))
                return
            
            # Calculate what to delete (logic copied from original)
            target_msg = history[idx]
            indices_to_delete = [idx]
            if target_msg.role == "user":
                 if idx + 1 < len(history) and history[idx + 1].role == "model":
                    indices_to_delete.append(idx + 1)
            elif target_msg.role == "model":
                if idx - 1 >= 0 and history[idx - 1].role == "user":
                    indices_to_delete.insert(0, idx - 1)
            
            # Perform deletion
            sorted_indices = sorted(indices_to_delete, reverse=True)
            for i in sorted_indices:
                history.pop(i)
                
            self.bot._save_history_to_disk(channel_id)
            
            await interaction.response.send_message(
                 self.t("history_delete_success", count=len(indices_to_delete))
            )
        except Exception as e:
            await interaction.response.send_message(self.t("history_error", error=e))

    @history_group.command(name="clear")
    async def history_clear(self, interaction: discord.Interaction):
        """Clear all conversation history from memory for this channel."""
        channel_id = interaction.channel_id
        try:
            self.bot.history_manager.clear_conversation(channel_id)
            self.bot.conversation_history[channel_id] = []
            await interaction.response.send_message(self.t("history_cleared"))
        except Exception as e:
             await interaction.response.send_message(self.t("history_error", error=e))

    @history_group.command(name="export")
    @app_commands.describe(filename="Optional filename for the zip/md file")
    async def history_export(self, interaction: discord.Interaction, filename: str = None):
        """Export conversation history to ZIP file with Markdown and images."""
        await interaction.response.defer()
        channel_id = interaction.channel_id

        try:
            data = self.bot.history_manager.load_conversation(channel_id)
            if not data or not data.get("messages"):
                await interaction.followup.send(self.t("history_export_empty"))
                return

            branch = self.bot.history_manager.get_current_branch(channel_id)
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"{channel_id}_{branch}_{timestamp}"

            # Check for images
            has_images = any(
                "images" in msg and msg["images"]
                for msg in data.get("messages", [])
            )
            
            # Helper to build MD (copied logic)
            def build_md(data, channel_id, branch):
                lines = [
                    "# Conversation Export", "",
                    f"- **Channel ID**: {channel_id}",
                    f"- **Branch**: {branch}",
                    f"- **Model**: {data.get('model', 'N/A')}",
                    f"- **Exported at**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    "", "---", "", "## Conversation", ""
                ]
                for msg in data.get("messages", []):
                    role = msg.get("role", "unknown").capitalize()
                    content = msg.get("content", "")
                    timestamp = msg.get("timestamp", "")
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass
                    lines.append(f"### {role} ({timestamp})")
                    lines.append("")
                    if "images" in msg:
                        for image_path in msg["images"]:
                            lines.append(f"![image]({image_path})")
                            lines.append("")
                    lines.append(content)
                    lines.append("")
                return "\n".join(lines)

            if has_images:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                    md_content = build_md(data, channel_id, branch)
                    zf.writestr("conversation.md", md_content.encode("utf-8"))

                    # Export thought signature if exists
                    thought_signature = self.bot.history_manager.load_thought_signature(channel_id)
                    if thought_signature:
                        signature_b64 = base64.b64encode(thought_signature).decode("utf-8")
                        zf.writestr("thought_signature.txt", signature_b64.encode("utf-8"))

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
                # Export thought signature if exists (even without images)
                thought_signature = self.bot.history_manager.load_thought_signature(channel_id)
                if thought_signature:
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        md_content = build_md(data, channel_id, branch)
                        zf.writestr("conversation.md", md_content.encode("utf-8"))
                        signature_b64 = base64.b64encode(thought_signature).decode("utf-8")
                        zf.writestr("thought_signature.txt", signature_b64.encode("utf-8"))

                    zip_buffer.seek(0)
                    file = discord.File(zip_buffer, filename=f"{filename}.zip")
                else:
                    md_content = build_md(data, channel_id, branch)
                    file = discord.File(
                        io.BytesIO(md_content.encode("utf-8")),
                        filename=f"{filename}.md",
                    )

            await interaction.followup.send(self.t("history_export_success"), file=file)
        except Exception as e:
            await interaction.followup.send(self.t("history_error", error=e))

    # --- Branch Group ---

    @branch_group.command(name="list")
    async def branch_list(self, interaction: discord.Interaction):
        """List all branches for this channel."""
        channel_id = interaction.channel_id
        try:
            branches = self.bot.history_manager.list_branches(channel_id)
            current = self.bot.history_manager.get_current_branch(channel_id)

            if not branches:
                await interaction.response.send_message(self.t("branch_list_empty"))
                return

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
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(self.t("branch_error", error=e))

    @branch_group.command(name="create")
    @app_commands.describe(name="Name of the new branch")
    async def branch_create(self, interaction: discord.Interaction, name: str):
        """Create a new branch from current conversation and switch to it."""
        channel_id = interaction.channel_id
        try:
            self.bot.history_manager.commit(channel_id, "Auto-save before branch")
            self.bot.history_manager.create_branch(channel_id, name, switch=True)
            self.bot._reload_history_from_disk(channel_id)
            await interaction.response.send_message(self.t("branch_created", branch=name))
        except Exception as e:
            await interaction.response.send_message(self.t("branch_error", error=e))

    @branch_group.command(name="switch")
    @app_commands.describe(branch="Branch to switch to")
    @app_commands.autocomplete(branch=branch_autocomplete)
    async def branch_switch(self, interaction: discord.Interaction, branch: str):
        """Switch to a different branch."""
        channel_id = interaction.channel_id
        try:
            # Check existence first? switch_branch might throw error if not exists
            self.bot.history_manager.switch_branch(channel_id, branch)
            self.bot._reload_history_from_disk(channel_id)
            await interaction.response.send_message(self.t("branch_switched", branch=branch))
        except Exception as e:
            await interaction.response.send_message(self.t("branch_error", error=e))

    @branch_group.command(name="delete")
    @app_commands.describe(branch="Branch to delete")
    @app_commands.autocomplete(branch=branch_autocomplete)
    async def branch_delete(self, interaction: discord.Interaction, branch: str):
        """Delete a branch."""
        channel_id = interaction.channel_id
        try:
            self.bot.history_manager.delete_branch(channel_id, branch)
            await interaction.response.send_message(self.t("branch_deleted", branch=branch))
        except Exception as e:
            await interaction.response.send_message(self.t("branch_error", error=e))

    @branch_group.command(name="merge")
    @app_commands.describe(branch="Branch to merge into current")
    @app_commands.autocomplete(branch=branch_autocomplete)
    async def branch_merge(self, interaction: discord.Interaction, branch: str):
        """Merge another branch into the current branch."""
        channel_id = interaction.channel_id
        try:
            self.bot.history_manager.commit(channel_id, "Auto-save before merge")
            merged_count = self.bot.history_manager.merge_branch(channel_id, branch)
            self.bot._reload_history_from_disk(channel_id)
            
            if merged_count > 0:
                await interaction.response.send_message(
                    self.t("branch_merged", branch=branch, count=merged_count)
                )
            else:
                await interaction.response.send_message(self.t("branch_merge_nothing"))
        except Exception as e:
            await interaction.response.send_message(self.t("branch_error", error=e))

    @branch_group.command(name="rename")
    @app_commands.describe(new_name="New name for the current branch")
    async def branch_rename(self, interaction: discord.Interaction, new_name: str):
        """Rename current branch."""
        channel_id = interaction.channel_id
        try:
            old_name = self.bot.history_manager.get_current_branch(channel_id)
            self.bot.history_manager.rename_branch(channel_id, new_name)
            await interaction.response.send_message(
                self.t("branch_renamed", old=old_name, new=new_name)
            )
        except Exception as e:
             await interaction.response.send_message(self.t("branch_error", error=e))

    # --- Mode Group ---

    @mode_group.command(name="set")
    @app_commands.describe(mode="The tool mode to use")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Default (Google Search)", value="default"),
        app_commands.Choice(name="Calendar", value="calendar"),
        app_commands.Choice(name="Todo", value="todo"),
    ])
    async def mode_set(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        """Set the tool mode for this channel."""
        channel_id = interaction.channel_id
        user_id = interaction.user.id
        selected_mode = mode.value

        # Check authentication for calendar/todo
        if selected_mode in ("calendar", "todo"):
            calendar_auth = self._get_calendar_auth()
            
            if calendar_auth is None:
                await self._send_google_setup_guide(interaction)
                return

            if not calendar_auth.is_user_authenticated(user_id):
                # We need localized strings for "not linked"
                key = f"mode_{selected_mode}_not_linked"
                # If key doesn't exist, fallback? The original code constructed key like this.
                await interaction.response.send_message(self.t(key))
                return

        self.bot.set_tool_mode(channel_id, selected_mode)
        await interaction.response.send_message(
            self.t("mode_changed", mode=selected_mode)
        )

    # --- Config Group ---

    @config_group.command(name="show")
    async def config_show(self, interaction: discord.Interaction):
        """Show current generation config."""
        channel_id = interaction.channel_id
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
                
                range_info = f"({key_schema['min']} - {key_schema['max']})"
                embed.add_field(
                    name=f"{key} {range_info}",
                    value=status,
                    inline=True
                )
            
            await interaction.response.send_message(embed=embed)
        except Exception as e:
             await interaction.response.send_message(self.t("config_error", error=e))

    @config_group.command(name="set")
    @app_commands.describe(key="Config key", value="Value to set")
    @app_commands.autocomplete(key=config_key_autocomplete)
    async def config_set(self, interaction: discord.Interaction, key: str, value: str):
        """Set a generation config value."""
        channel_id = interaction.channel_id
        try:
            self.bot.history_manager.save_generation_config_value(
                channel_id, key, value
            )
            await interaction.response.send_message(
                self.t("config_set_success", config_key=key, config_value=value)
            )
        except Exception as e:
             await interaction.response.send_message(self.t("config_error", error=e))

    @config_group.command(name="reset")
    @app_commands.describe(key="Config key to reset (optional, leave empty to reset all)")
    @app_commands.autocomplete(key=config_key_autocomplete)
    async def config_reset(self, interaction: discord.Interaction, key: str = None):
        """Reset generation config to default."""
        channel_id = interaction.channel_id
        try:
            self.bot.history_manager.reset_generation_config(channel_id, key)
            if key:
                await interaction.response.send_message(self.t("config_reset_key", config_key=key))
            else:
                await interaction.response.send_message(self.t("config_reset_all"))
        except Exception as e:
            await interaction.response.send_message(self.t("config_error", error=e))

    # --- Prompt Group ---
    
    # System Prompt (Master)
    
    @system_prompt_group.command(name="show")
    async def prompt_system_show(self, interaction: discord.Interaction):
        """Show the current master system prompt."""
        try:
            master_path = self.bot.history_manager.get_master_prompt_path()
            content = master_path.read_text(encoding="utf-8") if master_path.exists() else ""
            
            if not content.strip():
                await interaction.response.send_message(self.t("prompt_show_empty"))
                return

            if len(content) <= 1900:
                embed = discord.Embed(
                    title=self.t("prompt_show_title"),
                    description=f"```\n{content}\n```",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(self.t("prompt_show_title"))
                chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)]
                for chunk in chunks:
                    await interaction.followup.send(f"```\n{chunk}\n```")
        except Exception as e:
            await interaction.response.send_message(self.t("prompt_error", error=e))

    @system_prompt_group.command(name="download")
    async def prompt_system_download(self, interaction: discord.Interaction):
        """Download the current master system prompt as a file."""
        try:
            master_path = self.bot.history_manager.get_master_prompt_path()
            content = master_path.read_text(encoding="utf-8") if master_path.exists() else ""

            if not content.strip():
                await interaction.response.send_message(self.t("prompt_download_empty"))
                return

            file = discord.File(
                io.BytesIO(content.encode("utf-8")),
                filename="GEMINI.md",
            )
            await interaction.response.send_message(self.t("prompt_download_success"), file=file)
        except Exception as e:
            await interaction.response.send_message(self.t("prompt_error", error=e))

    # Channel Prompt
    
    @channel_prompt_group.command(name="show")
    async def prompt_channel_show(self, interaction: discord.Interaction):
        """Show the current channel instruction."""
        channel_id = interaction.channel_id
        try:
            content = self.bot.history_manager.load_channel_prompt(channel_id)
            if not content.strip():
                await interaction.response.send_message(self.t("channel_prompt_show_empty"))
                return

            if len(content) <= 1900:
                embed = discord.Embed(
                    title=self.t("channel_prompt_show_title"),
                    description=f"```\n{content}\n```",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(self.t("channel_prompt_show_title"))
                chunks = [content[i : i + 1900] for i in range(0, len(content), 1900)]
                for chunk in chunks:
                    await interaction.followup.send(f"```\n{chunk}\n```")
        except Exception as e:
             await interaction.response.send_message(self.t("channel_prompt_error", error=e))

    @channel_prompt_group.command(name="download")
    async def prompt_channel_download(self, interaction: discord.Interaction):
        """Download the current channel instruction as a file."""
        channel_id = interaction.channel_id
        try:
            content = self.bot.history_manager.load_channel_prompt(channel_id)
            if not content.strip():
                await interaction.response.send_message(self.t("channel_prompt_download_empty"))
                return

            file = discord.File(
                io.BytesIO(content.encode("utf-8")),
                filename="channel_instruction.md",
            )
            await interaction.response.send_message(self.t("channel_prompt_download_success"), file=file)
        except Exception as e:
            await interaction.response.send_message(self.t("channel_prompt_error", error=e))

    @channel_prompt_group.command(name="clear")
    async def prompt_channel_clear(self, interaction: discord.Interaction):
        """Clear the channel instruction."""
        channel_id = interaction.channel_id
        try:
            self.bot.history_manager.save_system_prompt(channel_id, "")
            await interaction.response.send_message(self.t("channel_prompt_clear_success"))
        except Exception as e:
            await interaction.response.send_message(self.t("channel_prompt_error", error=e))


    # --- Google Group ---

    @google_group.command(name="link")
    async def google_link(self, interaction: discord.Interaction):
        """Link your Google account."""
        user_id = interaction.user.id
        calendar_auth = self._get_calendar_auth()
        
        if calendar_auth is None:
            await self._send_google_setup_guide(interaction)
            return

        if not calendar_auth.is_credentials_configured():
            await self._send_google_setup_guide(interaction)
            return

        if calendar_auth.is_user_authenticated(user_id):
            await interaction.response.send_message(self.t("google_already_linked"), ephemeral=True)
            return

        # Defer because auth flow might take a moment to generate URL
        await interaction.response.defer(ephemeral=True)

        try:
            auth_url, future = await calendar_auth.start_auth_flow(user_id)
            
            # Send DM or Ephemeral message with URL
            # Slash commands allow ephemeral responses, so we can send it right here safely!
            await interaction.followup.send(
                self.t("google_link_url", url=auth_url),
                ephemeral=True
            )

            # Wait for auth completion
            try:
                await future
                await interaction.followup.send(
                    self.t("google_link_success", user=interaction.user.mention),
                    ephemeral=True
                )
            except TimeoutError:
                await interaction.followup.send(self.t("google_link_timeout"), ephemeral=True)
            except Exception as e:
                await interaction.followup.send(self.t("google_link_error", error=str(e)), ephemeral=True)

        except FileNotFoundError:
            await self._send_google_setup_guide(interaction)
        except Exception as e:
            await interaction.followup.send(self.t("google_error", error=str(e)), ephemeral=True)

    @google_group.command(name="unlink")
    async def google_unlink(self, interaction: discord.Interaction):
        """Unlink your Google account."""
        user_id = interaction.user.id
        calendar_auth = self._get_calendar_auth()

        if calendar_auth is None:
            await self._send_google_setup_guide(interaction)
            return

        if calendar_auth.revoke_user(user_id):
            await interaction.response.send_message(self.t("google_unlink_success"), ephemeral=True)
        else:
            await interaction.response.send_message(self.t("google_not_linked"), ephemeral=True)

    @google_group.command(name="status")
    async def google_status(self, interaction: discord.Interaction):
        """Check your Google account connection status."""
        user_id = interaction.user.id
        calendar_auth = self._get_calendar_auth()

        if calendar_auth is None or not calendar_auth.is_credentials_configured():
            await self._send_google_setup_guide(interaction)
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

        await interaction.response.send_message(embed=embed, ephemeral=True)


    # --- Thought Signature Group ---

    @thought_signature_group.command(name="download")
    async def thought_signature_download(self, interaction: discord.Interaction):
        """Download thought signature as a file."""
        await interaction.response.defer()
        channel_id = interaction.channel_id

        thought_signature = self.bot.history_manager.load_thought_signature(channel_id)
        if not thought_signature:
            await interaction.followup.send(self.t("thought_signature_not_found"))
            return

        signature_b64 = base64.b64encode(thought_signature).decode("utf-8")
        file = discord.File(
            io.BytesIO(signature_b64.encode("utf-8")),
            filename="thought_signature.txt"
        )
        await interaction.followup.send(self.t("thought_signature_download_success"), file=file)

    @thought_signature_group.command(name="upload")
    @app_commands.describe(file="thought_signature.txt file")
    async def thought_signature_upload(self, interaction: discord.Interaction, file: discord.Attachment):
        """Upload and set thought signature from a file."""
        await interaction.response.defer()
        channel_id = interaction.channel_id

        try:
            content = await file.read()
            signature_b64 = content.decode("utf-8").strip()
            signature = base64.b64decode(signature_b64)
            self.bot.history_manager.save_thought_signature(channel_id, signature)
            await interaction.followup.send(self.t("thought_signature_upload_success"))
        except Exception as e:
            await interaction.followup.send(self.t("thought_signature_upload_error", error=e))

    @thought_signature_group.command(name="clear")
    async def thought_signature_clear(self, interaction: discord.Interaction):
        """Clear thought signature for this channel."""
        channel_id = interaction.channel_id
        self.bot.history_manager.clear_thought_signature(channel_id)
        await interaction.response.send_message(self.t("thought_signature_cleared"))


async def setup(bot: commands.Bot):
    """Load the Commands cog."""
    await bot.add_cog(Commands(bot))
