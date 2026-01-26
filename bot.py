import os
import discord
from discord.ext import commands
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Check for required environment variables
if not DISCORD_TOKEN:
    print("Error: DISCORD_BOT_TOKEN environment variable not set.")
    exit(1)

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY environment variable not set.")
    exit(1)

# Initialize Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)

# Initialize Discord Bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.command(name='ask')
async def ask(ctx, *, prompt):
    """Asks Gemini a question."""
    async with ctx.typing():
        try:
            response = client.models.generate_content(
                model="gemini-3-pro-preview",
                contents=prompt,
            )
            # Discord has a 2000 character limit per message.
            # For simplicity, we'll just send the first 2000 characters if it's too long,
            # or split it. Let's do a simple split for now.
            response_text = response.text
            if len(response_text) > 2000:
                for i in range(0, len(response_text), 2000):
                    await ctx.send(response_text[i:i+2000])
            else:
                await ctx.send(response_text)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
