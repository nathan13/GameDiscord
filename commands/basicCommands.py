import discord
from discord.ext import commands


class basicCommands(commands.Cog):

    def __init__(self, bot:commands.Bot):

        self.bot = bot

    
    @commands.Cog.listener()
    async def on_message(self, msg: discord.message):
        if msg.content == "!bot":
          channel = msg.guild.get_channel(msg.channel.id)
          await channel.send(msg.author)
    

def setup(bot:commands.Bot):
    bot.add_cog(basicCommands(bot))