import discord
from discord.ext import commands
from cogs.storage import set_log_channel_id, get_log_channel_id



class LogCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setlogchannel')
    @commands.has_permissions(administrator=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel):
        set_log_channel_id(ctx.guild.id, channel.id)
        await ctx.send(f"✅ Log channel set to {channel.mention}")

async def setup(bot):
    await bot.add_cog(LogCommands(bot))
