import discord
import logging
import asyncio
from discord.ext import commands
from cogs.storage import get_log_channel_id, set_log_channel_id


logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.voice_states = True
intents.members = True
client = commands.Bot(command_prefix="!", intents=intents)

# Configure logging
logger = logging.getLogger('discord_bot')
logger.setLevel(logging.INFO)  # or DEBUG for more detail

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Format logs
formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s')
console_handler.setFormatter(formatter)

# Add to logger
logger.addHandler(console_handler)

# Load extensions the correct async way
@client.event
async def on_ready():
    print(f"{client.user} has connected to Discord!")

# Use setup_hook to load cogs properly
async def load_extensions():
    extensions = ['cogs.commands', 'cogs.voice', 'cogs.log']
    for ext in extensions:
        try:
            await client.load_extension(ext)
            print(f"Loaded {ext}")
        except Exception as e:
            print(f"Failed to load {ext}: {e}")

@client.event
async def on_command_error(ctx, error):
    print(f"Error in {ctx.command}: {error}") # to terminal
    await log_to_channel(client, ctx.guild, f"❌ Error in `{ctx.command}`: `{error}`") #in log channel

    if isinstance(error, commands.MissingRequiredArgument):
        if ctx.command.name == "play":
            await ctx.send(":bangbang: You need to provide a song name or URL. Try `!play <url>` or `!play <song name>`.")
        else:
            await ctx.send(f"⚠️ Missing argument: `{error.param.name}`.")
    elif isinstance(error, commands.CommandNotFound):
        logger.info(f"User '{ctx.author}' tried unknown command: {ctx.message.content}")
        await ctx.send("❌ That command doesn't exist.")
    elif isinstance(error, commands.CheckFailure):
        logger.warning(f"Blocked command '{ctx.command}' from user '{ctx.author}' in channel '{ctx.channel}'")
        await ctx.send("You can't use that command in this channel.")
    else:
        logger.error("Unhandled exception occurred", exc_info=True)
        raise error

async def log_to_channel(bot, guild, message):
    log_channel_id = get_log_channel_id(guild.id)
    if log_channel_id:
        channel = bot.get_channel(log_channel_id)
        if channel:
            await channel.send(message)
            
@client.event
async def setup_hook():
    await load_extensions()

# Load token from file
with open("token.txt", "r") as file:
    token = file.read().strip()

client.run(token)
