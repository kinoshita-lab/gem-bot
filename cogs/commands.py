import discord
from discord.ext import commands


class Commands(commands.Cog):
    """All bot commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ask")
    async def ask(self, ctx: commands.Context, *, prompt: str):
        """Asks Gemini a question."""
        async with ctx.typing():
            try:
                response_text = await self.bot.ask_gemini(ctx.channel.id, prompt)
                await self.bot.send_response(ctx.channel, response_text)
            except Exception as e:
                await ctx.send(f"An error occurred: {e}")

    @commands.command(name="info")
    async def info(self, ctx: commands.Context):
        """Displays information about the bot."""
        embed = discord.Embed(title="Bot Information", color=discord.Color.blue())
        embed.add_field(name="Model", value=self.bot.current_model, inline=False)
        await ctx.send(embed=embed)

    @commands.group(name="model")
    async def model(self, ctx: commands.Context):
        """Model management commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "使用方法:\n`!model list` - 利用可能なモデル一覧を表示\n`!model set` - 使用するモデルを変更"
            )

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
                    title="利用可能な Gemini モデル",
                    description=f"現在使用中: **{self.bot.current_model}**",
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
                    title="モデルを選択してください",
                    description=f"現在使用中: **{self.bot.current_model}**\n\n番号を入力してモデルを選択してください。\n`cancel` でキャンセルできます。",
                    color=discord.Color.blue(),
                )

                # Split into chunks if too many models
                chunk_size = 25
                for i in range(0, len(model_names), chunk_size):
                    chunk = model_names[i : i + chunk_size]
                    field_name = "モデル一覧" if i == 0 else "モデル一覧 (続き)"
                    field_value = "\n".join(
                        f"`{i + j + 1}`. {name}" for j, name in enumerate(chunk)
                    )
                    embed.add_field(name=field_name, value=field_value, inline=False)

                await ctx.send(embed=embed)

            except Exception as e:
                await ctx.send(f"モデル一覧の取得中にエラーが発生しました: {e}")


async def setup(bot: commands.Bot):
    """Load the Commands cog."""
    await bot.add_cog(Commands(bot))
