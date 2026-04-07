"""Discord event handlers: on_ready, on_message, and message processing helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands

if TYPE_CHECKING:
    pass


class EventHandlers(commands.Cog):
    """Cog handling Discord events: on_ready, on_command_error, on_message.

    Replaces the free functions and @bot.event decorators that previously
    referenced the module-level ``bot`` global variable.
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # =========================================================================
    # Events
    # =========================================================================

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        print(f"We have logged in as {self.bot.user}")
        print(f"Responding to messages in channels: {self.bot.enabled_channel_ids}")

    @commands.Cog.listener()
    async def on_command_error(
        self, ctx: commands.Context, error: commands.CommandError
    ) -> None:
        """Handle command errors."""
        if isinstance(error, commands.CommandNotFound):
            await ctx.send(
                self.bot.i18n.t("command_not_found", command=ctx.invoked_with)
            )
        else:
            # Re-raise other errors to see them in console
            raise error

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages.

        Dispatches to specialized handlers based on message context.
        """
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return

        # Handle channel_instruction.md file upload (works in any channel)
        if await self._handle_instruction_upload(message):
            return

        # Handle GEMINI.md (master instruction) upload
        if await self._handle_master_instruction_upload(message):
            return

        # Handle pending branch selection interaction
        if await self._handle_branch_selection(message):
            return

        # Handle pending tool mode selection interaction
        if await self._handle_tool_mode_selection(message):
            return

        # Handle pending model selection interaction
        if await self._handle_model_selection(message):
            return

        # Handle pending delete confirmation interaction
        if await self._handle_delete_confirmation(message):
            return

        # Check if the message is a command (starts with prefix)
        if message.content.startswith(self.bot.command_prefix):
            await self.bot.process_commands(message)
            return

        # Auto-respond in enabled channels
        if message.channel.id in self.bot.enabled_channel_ids:
            await self._handle_auto_response(message)

    # =========================================================================
    # Message Handler Helpers
    # =========================================================================

    async def _handle_instruction_upload(self, message: discord.Message) -> bool:
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
                    self.bot.history_manager.save_system_prompt(channel_id, text)
                    await message.channel.send(
                        self.bot.i18n.t("prompt_updated_from_file")
                    )
                except UnicodeDecodeError:
                    await message.channel.send(
                        self.bot.i18n.t("prompt_file_decode_error")
                    )
                except Exception as e:
                    await message.channel.send(
                        self.bot.i18n.t("prompt_error", error=str(e))
                    )
                return True
        return False

    async def _handle_master_instruction_upload(
        self, message: discord.Message
    ) -> bool:
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
                    self.bot.history_manager.save_master_prompt(text)
                    await message.channel.send(
                        self.bot.i18n.t("master_prompt_updated")
                    )
                except UnicodeDecodeError:
                    await message.channel.send(
                        self.bot.i18n.t("master_prompt_decode_error")
                    )
                except Exception as e:
                    await message.channel.send(
                        self.bot.i18n.t("prompt_error", error=str(e))
                    )
                return True
        return False

    async def _handle_branch_selection(self, message: discord.Message) -> bool:
        """Handle pending branch selection interaction.

        Args:
            message: Discord message object.

        Returns:
            True if handled (should stop processing), False otherwise.
        """
        user_id = message.author.id
        if user_id not in self.bot.pending_branch_selections:
            return False

        content = message.content.strip().lower()

        # Handle cancel
        if content == "cancel":
            del self.bot.pending_branch_selections[user_id]
            await message.channel.send(self.bot.i18n.t("branch_select_cancelled"))
            return True

        # Handle number selection
        if content.isdigit():
            index = int(content) - 1
            branches = self.bot.pending_branch_selections[user_id]["branches"]
            channel_id = self.bot.pending_branch_selections[user_id]["channel_id"]
            action = self.bot.pending_branch_selections[user_id].get(
                "action", "switch"
            )

            if 0 <= index < len(branches):
                selected_branch = branches[index]
                try:
                    if action == "switch":
                        # Switch branch (auto-commits current state)
                        self.bot.history_manager.switch_branch(
                            channel_id, selected_branch
                        )
                        # Reload history from disk
                        self.bot._reload_history_from_disk(channel_id)
                        await message.channel.send(
                            self.bot.i18n.t(
                                "branch_switched", branch=selected_branch
                            )
                        )

                    elif action == "delete":
                        self.bot.history_manager.delete_branch(
                            channel_id, selected_branch
                        )
                        await message.channel.send(
                            self.bot.i18n.t(
                                "branch_deleted", branch=selected_branch
                            )
                        )

                    elif action == "merge":
                        # Commit current state before merge
                        self.bot.history_manager.commit(
                            channel_id, "Auto-save before merge"
                        )
                        # Merge branch
                        merged_count = self.bot.history_manager.merge_branch(
                            channel_id, selected_branch
                        )
                        # Reload history from disk
                        self.bot._reload_history_from_disk(channel_id)

                        if merged_count > 0:
                            await message.channel.send(
                                self.bot.i18n.t(
                                    "branch_merged",
                                    branch=selected_branch,
                                    count=merged_count,
                                )
                            )
                        else:
                            await message.channel.send(
                                self.bot.i18n.t("branch_merge_nothing")
                            )

                    del self.bot.pending_branch_selections[user_id]

                except Exception as e:
                    await message.channel.send(
                        self.bot.i18n.t("branch_error", error=e)
                    )
            else:
                await message.channel.send(
                    self.bot.i18n.t(
                        "branch_select_invalid_number", max=len(branches)
                    )
                )
            return True

        # Invalid input - prompt again
        await message.channel.send(self.bot.i18n.t("branch_select_prompt"))
        return True

    async def _handle_tool_mode_selection(self, message: discord.Message) -> bool:
        """Handle pending tool mode selection interaction.

        Args:
            message: Discord message object.

        Returns:
            True if handled (should stop processing), False otherwise.
        """
        user_id = message.author.id
        if user_id not in self.bot.pending_tool_mode_selections:
            return False

        content = message.content.strip().lower()

        # Handle cancel
        if content == "cancel":
            del self.bot.pending_tool_mode_selections[user_id]
            await message.channel.send(self.bot.i18n.t("mode_select_cancelled"))
            return True

        # Handle number selection
        if content.isdigit():
            index = int(content) - 1
            modes = self.bot.pending_tool_mode_selections[user_id]["modes"]
            channel_id = self.bot.pending_tool_mode_selections[user_id]["channel_id"]

            if 0 <= index < len(modes):
                selected_mode = modes[index]

                # Check authentication for calendar/todo
                if selected_mode in ("calendar", "todo"):
                    if (
                        not self.bot.calendar_auth
                        or not self.bot.calendar_auth.is_user_authenticated(user_id)
                    ):
                        key = f"mode_{selected_mode}_not_linked"
                        await message.channel.send(self.bot.i18n.t(key))
                        del self.bot.pending_tool_mode_selections[user_id]
                        return True

                self.bot.set_tool_mode(channel_id, selected_mode)
                del self.bot.pending_tool_mode_selections[user_id]
                await message.channel.send(
                    self.bot.i18n.t("mode_changed", mode=selected_mode)
                )
            else:
                await message.channel.send(
                    self.bot.i18n.t(
                        "mode_select_invalid_number", max=len(modes)
                    )
                )
            return True

        # Invalid input - prompt again
        await message.channel.send(self.bot.i18n.t("mode_select_prompt"))
        return True

    async def _handle_model_selection(self, message: discord.Message) -> bool:
        """Handle pending model selection interaction.

        Args:
            message: Discord message object.

        Returns:
            True if handled (should stop processing), False otherwise.
        """
        user_id = message.author.id
        if user_id not in self.bot.pending_model_selections:
            return False

        content = message.content.strip().lower()

        # Handle cancel
        if content == "cancel":
            del self.bot.pending_model_selections[user_id]
            await message.channel.send(self.bot.i18n.t("model_select_cancelled"))
            return True

        # Handle number selection
        if content.isdigit():
            index = int(content) - 1
            model_names = self.bot.pending_model_selections[user_id]["models"]
            channel_id = self.bot.pending_model_selections[user_id]["channel_id"]

            if 0 <= index < len(model_names):
                selected_model = model_names[index]
                self.bot.set_model(channel_id, selected_model)
                del self.bot.pending_model_selections[user_id]
                await message.channel.send(
                    self.bot.i18n.t("model_select_changed", model=selected_model)
                )
            else:
                await message.channel.send(
                    self.bot.i18n.t(
                        "model_select_invalid_number", max=len(model_names)
                    )
                )
            return True

        # Invalid input - prompt again
        await message.channel.send(self.bot.i18n.t("model_select_prompt"))
        return True

    async def _handle_delete_confirmation(self, message: discord.Message) -> bool:
        """Handle pending delete confirmation interaction.

        Args:
            message: Discord message object.

        Returns:
            True if handled (should stop processing), False otherwise.
        """
        user_id = message.author.id
        if user_id not in self.bot.pending_delete_confirmations:
            return False

        pending = self.bot.pending_delete_confirmations[user_id]
        channel_id = pending["channel_id"]

        # Only process if in the same channel
        if message.channel.id != channel_id:
            return False

        content = message.content.strip().lower()
        del self.bot.pending_delete_confirmations[user_id]

        if content == "yes":
            # Perform deletion
            indices = sorted(pending["indices"], reverse=True)
            history = self.bot.conversation_history.get(channel_id, [])

            for idx in indices:
                if 0 <= idx < len(history):
                    history.pop(idx)

            # Save updated history
            self.bot._save_history_to_disk(channel_id)

            await message.channel.send(
                self.bot.i18n.t(
                    "history_delete_success", count=len(pending["indices"])
                )
            )
        else:
            await message.channel.send(
                self.bot.i18n.t("history_delete_cancelled")
            )

        return True

    async def _handle_auto_response(self, message: discord.Message) -> None:
        """Handle auto-response to messages in enabled channels.

        Args:
            message: Discord message object.
        """
        async with message.channel.typing():
            try:
                # Check for image attachments
                images: list[tuple[bytes, str]] = []
                supported_types = {
                    "image/png",
                    "image/jpeg",
                    "image/gif",
                    "image/webp",
                }

                for attachment in message.attachments:
                    if (
                        attachment.content_type
                        and attachment.content_type in supported_types
                    ):
                        try:
                            image_data = await attachment.read()
                            images.append((image_data, attachment.content_type))
                        except Exception as e:
                            print(
                                f"Failed to download image {attachment.filename}: {e}"
                            )

                # Use message content or default prompt if only images
                prompt = (
                    message.content
                    if message.content
                    else self.bot.i18n.t("image_default_prompt")
                )

                response_text, usage_text = await self.bot.ask_gemini(
                    message.channel.id,
                    prompt,
                    images=images if images else None,
                    user_id=message.author.id,
                )

                # Send usage cost at the beginning (only once)
                if usage_text:
                    await message.channel.send(usage_text)

                # Prepend current mode indicator to response
                if self.bot.get_tool_mode_show(message.channel.id):
                    tool_mode = self.bot.get_tool_mode(message.channel.id)
                    tool_mode_names = {
                        "default": "Google\u691c\u7d22",
                        "calendar": "\u30ab\u30ec\u30f3\u30c0\u30fc",
                        "todo": "\u30bf\u30b9\u30af",
                    }
                    mode_name = tool_mode_names.get(tool_mode, tool_mode)
                    mode_indicator = (
                        f'\u30c4\u30fc\u30eb\u30e2\u30fc\u30c9 "{mode_name}" \u306b\u3088\u308b\u56de\u7b54\u3067\u3059\n\n'
                    )
                    display_text = mode_indicator + response_text
                else:
                    display_text = response_text

                await self.bot.send_response(message.channel, display_text)
            except Exception as e:
                error_str = str(e)
                if "DEADLINE_EXCEEDED" in error_str or "504" in error_str:
                    await message.channel.send(
                        self.bot.i18n.t(
                            "api_timeout_error", attempts=self.bot._MAX_API_RETRIES
                        )
                    )
                elif any(p in error_str for p in ("500", "503", "INTERNAL")):
                    await message.channel.send(
                        self.bot.i18n.t(
                            "api_server_error", attempts=self.bot._MAX_API_RETRIES
                        )
                    )
                else:
                    await message.channel.send(
                        self.bot.i18n.t("error_occurred", error=e)
                    )


async def setup(bot: commands.Bot) -> None:
    """Load the EventHandlers cog."""
    await bot.add_cog(EventHandlers(bot))
