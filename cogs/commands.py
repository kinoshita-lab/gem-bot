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
        embed = discord.Embed(
            title=self.t("bot_info_title"), color=discord.Color.blue()
        )
        embed.add_field(
            name=self.t("model"), value=self.bot.current_model, inline=False
        )
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

                # Create embed for model list
                embed = discord.Embed(
                    title=self.t("model_list_title"),
                    description=self.t(
                        "model_list_current", model=self.bot.current_model
                    ),
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

                # Register pending selection (overwrites any previous selection for this user)
                self.bot.pending_model_selections[user_id] = model_names

                # Send selection prompt
                embed = discord.Embed(
                    title=self.t("model_select_title"),
                    description=self.t(
                        "model_select_description", model=self.bot.current_model
                    ),
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


async def setup(bot: commands.Bot):
    """Load the Commands cog."""
    await bot.add_cog(Commands(bot))
