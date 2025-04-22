import discord
from discord.ext import commands

class GeneralCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hello(self, ctx, *args):
        print(ctx.author)
        print(ctx.guild)
        for arg in args:
            await ctx.send(arg)

async def setup(bot):
    await bot.add_cog(GeneralCommands(bot))
