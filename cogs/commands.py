import discord
from discord.ext import commands


class Commands(commands.Cog):
    """All bot commands."""

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

                # Split into chunks if too many models
                chunk_size = 20
                for i in range(0, len(model_names), chunk_size):
                    chunk = model_names[i : i + chunk_size]
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

                current_model = self.bot.get_model(channel_id)

                # Register pending selection (overwrites any previous selection for this user)
                self.bot.pending_model_selections[user_id] = {
                    "channel_id": channel_id,
                    "models": model_names,
                }

                # Send selection prompt
                embed = discord.Embed(
                    title=self.t("model_select_title"),
                    description=self.t("model_select_description", model=current_model),
                    color=discord.Color.blue(),
                )

                # Split into chunks if too many models
                chunk_size = 25
                for i in range(0, len(model_names), chunk_size):
                    chunk = model_names[i : i + chunk_size]
                    field_name = (
                        self.t("model_list_field")
                        if i == 0
                        else self.t(
                            "model_list_field_continued", num=i // chunk_size + 1
                        )
                    )
                    field_value = "\n".join(
                        f"`{i + j + 1}`. {name}" for j, name in enumerate(chunk)
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


async def setup(bot: commands.Bot):
    """Load the Commands cog."""
    await bot.add_cog(Commands(bot))
