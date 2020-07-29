import os
import asyncio
import sqlalchemy as sa

from discord import utils
from discord.ext import commands
from common import *

#
# CONSTANTS
#

MUTED_TABLE = sa.Table(
    'muted', db_h.META,
    sa.Column('guild_id', sa.BigInteger, primary_key = True),
    sa.Column('user_id', sa.BigInteger, primary_key = True),
    sa.Column('unmutedate', sa.String, nullable = False)
)

MUTED_ROLE = "muted"
MUTETIME_LIMIT = time_h.args_to_delta(days = 1)
HISTORY_LIMIT = 300

#
# CLASSES
#

class Admin(commands.Cog):
    def __init__(self, client):
        self.client = client

    # Read mute list from disk on_ready to avoid permanent mutes
    @commands.Cog.listener()
    async def on_ready(self):
        muted_rows = await db_h.exec_query(MUTED_TABLE.select())
        currentdate = time_h.get_current_date()
        members_to_unmute = []

        for row in muted_rows:
            guild = self.client.get_guild(row[MUTED_TABLE.c.guild_id])
            member = guild.get_member(row[MUTED_TABLE.c.user_id])
            unmutedate = time_h.str_to_date(row[MUTED_TABLE.c.unmutedate])

            # Unmute immediately (group calls together)
            if currentdate >= unmutedate:
                members_to_unmute.append(member)
            # Unmute later
            else:
                unmuteseconds = (unmutedate - currentdate).total_seconds()
                asyncio.create_task(async_h.run_coro_in(self._unmute(member), unmuteseconds))

        if len(members_to_unmute) > 0: await self._unmute(*members_to_unmute)

    # Check if admin
    async def cog_check(self, ctx):
        return ctx.channel.permissions_for(ctx.message.author).administrator

    # Sudo me' timbers
    @commands.command()
    async def sudo(self, ctx):
        await ctx.send("You are now running with sudo privileges")

    # Clear channel messages for bot and command messages
    @commands.group(
        name = 'clear', 
        invoke_without_command = True, 
        help = "Clears all bot commands and messages in the channel, given a limit parameter.")
    async def _clear(self, ctx, lim = 30):
        if lim <= 0 or lim > HISTORY_LIMIT:
            await ctx.send("Choose a limit between 1 and {}".format(HISTORY_LIMIT))
        else:
            botuser = self.client.user
            prefixes = tuple(self.client.command_prefix)

            def is_cmd_or_bot(msg):
                if msg.author == botuser or msg.content.startswith(prefixes): return True
                return False

            await ctx.channel.purge(limit=lim, check=is_cmd_or_bot, before=ctx.message, bulk=True)

    # Clear ALL channel messages
    @_clear.command(
        name = 'all', 
        description = "Clears all chat messages in the channel, given a limit parameter.")
    async def _clear_all(self, ctx, lim = 30):
        if lim <= 0 or lim > HISTORY_LIMIT:
            await ctx.send("Choose a limit between 1 and {}".format(HISTORY_LIMIT))
        else:
            await ctx.channel.purge(limit=lim, before=ctx.message, bulk=True)

    # Unmute member(s) and remove them from the json list
    async def _unmute(self, *members):
        await db_h.exec_query(MUTED_TABLE.delete().where(
            sa.tuple_(
                MUTED_TABLE.c.guild_id, MUTED_TABLE.c.user_id
            ).in_(
                tuple(member.guild.id, member.id) for member in members)
            )
        )
        
        for member in members: 
            await member.remove_roles(utils.get(member.guild.roles, name = MUTED_ROLE))
            if member.voice: await member.move_to(channel = member.voice.channel)

    # Mute member for a given period of time
    @commands.command()
    async def mute(self, ctx, name, *time):
        member = None

        if len(ctx.message.mentions) > 1:
            await ctx.send("Only supply 1 user as a parameter")
            return

        member = ctx.message.mentions[0] if len(ctx.message.mentions) == 1 else ctx.guild.get_member_named(name)

        if member is None:
            await ctx.send("Could not find any user named {}".format(name))
            return

        mutetime = time_h.str_to_delta("".join(time))

        if mutetime <= time_h.DEFAULT_TIMEDELTA or mutetime > MUTETIME_LIMIT:
            await ctx.send("Specify a valid mute time between 0 and {}".format(str(MUTETIME_LIMIT)))
            return

        unmutedate = time_h.date_to_str(time_h.get_current_date() + mutetime)

        await db_h.exec_query(MUTED_TABLE.insert().values(
                guild_id = ctx.guild.id,
                user_id = member.id,
                unmutedate = unmutedate
            ).on_conflict_do_update(
                set_ = dict(unmutedate = unmutedate)
            )
        )

        await member.add_roles(utils.get(member.guild.roles, name = MUTED_ROLE))
        if member.voice: await member.move_to(channel = member.voice.channel)
        
        dm = await member.create_dm()
        await dm.send("You've been muted in {} for {}".format(ctx.guild, str(mutetime)))
        
        await async_h.run_coro_in(self._unmute(member), mutetime.total_seconds())

#
# SETUP
#

def setup(client):
    client.add_cog(Admin(client))

