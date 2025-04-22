import discord
from discord.ext import commands

class DeleteMessages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    #Delete messages in d-bot-requests, might get rid of this
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.channel.name == "d-bot-requests" and message.content != "":
            await message.channel.purge(limit=1)

async def setup(bot):
    await bot.add_cog(DeleteMessages(bot))
