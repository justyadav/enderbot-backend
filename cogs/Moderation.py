# moderation.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional, List

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_voice_channels = {}
        self.warn_data = {}
        self.ticket_counter = 0

    # ─── Helper Functions ──────────────────────────────────────────────

    def is_mod(self, member: discord.Member):
        return any(role.permissions.administrator or role.permissions.manage_messages for role in member.roles)

    def mod_check(self, ctx):
        if not self.is_mod(ctx.author):
            raise commands.MissingPermissions(["manage_messages"])
        return True

    async def mod_log(self, guild, action, target, moderator, reason=""):
        channel = discord.utils.get(guild.text_channels, name="mod-logs")
        if not channel:
            channel = guild.system_channel
        if channel:
            embed = discord.Embed(
                title=f"🔨 {action}",
                color=discord.Color.red() if "Warn" in action or "Ban" in action or "Kick" in action else discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            embed.add_field(name="Target", value=target.mention if target else "N/A", inline=False)
            embed.add_field(name="Moderator", value=moderator.mention, inline=False)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            await channel.send(embed=embed)

    # ─── Events ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"[✅] Moderation cog loaded.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # Auto-mod: invite links
        if "discord.gg/" in message.content and not self.is_mod(message.author):
            await message.delete()
            await message.channel.send(f"{message.author.mention} No invite links!", delete_after=5)
        # Spam detection simple
        if len(message.content.split()) > 30 and not self.is_mod(message.author):
            await message.delete()
            await message.channel.send(f"{message.author.mention} Please don't spam.", delete_after=5)

    # ─── Basic Mod Commands ──────────────────────────────────────────

    @commands.hybrid_command(name="kick", description="Kick a member")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided"):
        await member.kick(reason=reason)
        await self.mod_log(ctx.guild, "Kick", member, ctx.author, reason)
        await ctx.send(f"👢 Kicked {member.mention} | {reason}", ephemeral=True)

    @commands.hybrid_command(name="ban", description="Ban a member")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason="No reason provided"):
        await member.ban(reason=reason)
        await self.mod_log(ctx.guild, "Ban", member, ctx.author, reason)
        await ctx.send(f"🔨 Banned {member.mention} | {reason}", ephemeral=True)

    @commands.hybrid_command(name="unban", description="Unban a user by ID")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user_id: int, *, reason="No reason provided"):
        user = await self.bot.fetch_user(user_id)
        await ctx.guild.unban(user, reason=reason)
        await self.mod_log(ctx.guild, "Unban", user, ctx.author, reason)
        await ctx.send(f"♻️ Unbanned {user.name}#{user.discriminator}", ephemeral=True)

    @commands.hybrid_command(name="clear", description="Delete up to 100 messages")
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int):
        if amount > 100:
            amount = 100
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"🧹 Deleted {len(deleted)-1} messages.", ephemeral=True)

    @commands.hybrid_command(name="slowmode", description="Set slowmode in seconds")
    @commands.has_permissions(manage_messages=True)
    async def slowmode(self, ctx, seconds: int):
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(f"⏳ Slowmode set to {seconds}s", ephemeral=True)

    @commands.hybrid_command(name="mute", description="Timeout a member")
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, duration: int, *, reason="No reason"):
        until = datetime.utcnow() + timedelta(minutes=duration)
        await member.timeout(until, reason=reason)
        await self.mod_log(ctx.guild, "Mute", member, ctx.author, f"{duration}min | {reason}")
        await ctx.send(f"🤐 {member.mention} muted for {duration}min", ephemeral=True)

    @commands.hybrid_command(name="unmute", description="Remove timeout")
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        await member.timeout(None)
        await self.mod_log(ctx.guild, "Unmute", member, ctx.author)
        await ctx.send(f"🔊 {member.mention} unmuted", ephemeral=True)

    @commands.hybrid_command(name="warn", description="Warn a member")
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason="No reason"):
        key = f"{ctx.guild.id}_{member.id}"
        if key not in self.warn_data:
            self.warn_data[key] = []
        self.warn_data[key].append({"reason": reason, "mod": ctx.author.id, "time": datetime.utcnow().isoformat()})
        await self.mod_log(ctx.guild, "Warn", member, ctx.author, reason)
        await ctx.send(f"⚠️ {member.mention} warned | {reason}", ephemeral=True)

    @commands.hybrid_command(name="warns", description="Check warns for a member")
    @commands.has_permissions(kick_members=True)
    async def warns(self, ctx, member: discord.Member):
        key = f"{ctx.guild.id}_{member.id}"
        warns = self.warn_data.get(key, [])
        if not warns:
            await ctx.send(f"{member.mention} has no warnings.", ephemeral=True)
            return
        embed = discord.Embed(title=f"Warnings for {member}", color=discord.Color.orange())
        for i, w in enumerate(warns[-5:], 1):
            embed.add_field(name=f"#{i}", value=f"Reason: {w['reason']}\nMod: <@{w['mod']}>", inline=False)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="clearwarns", description="Clear all warns for a member")
    @commands.has_permissions(administrator=True)
    async def clearwarns(self, ctx, member: discord.Member):
        key = f"{ctx.guild.id}_{member.id}"
        self.warn_data.pop(key, None)
        await ctx.send(f"✅ Cleared all warns for {member.mention}", ephemeral=True)

    # ─── Advanced Mod Commands ────────────────────────────────────────

    @commands.hybrid_command(name="lock", description="Lock the current channel")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"🔒 {ctx.channel.mention} locked.")

    @commands.hybrid_command(name="unlock", description="Unlock the current channel")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send(f"🔓 {ctx.channel.mention} unlocked.")

    @commands.hybrid_command(name="nick", description="Change a member's nickname")
    @commands.has_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, nickname: str = None):
        old = member.display_name
        await member.edit(nick=nickname)
        await ctx.send(f"✏️ {old} → {nickname or member.name}", ephemeral=True)

    @commands.hybrid_command(name="move", description="Move all members from voice to another voice")
    @commands.has_permissions(move_members=True)
    async def move(self, ctx, from_ch: discord.VoiceChannel, to_ch: discord.VoiceChannel):
        for member in from_ch.members:
            await member.move_to(to_ch)
        await ctx.send(f"📦 Moved {len(from_ch.members)} members.", ephemeral=True)

    @commands.hybrid_command(name="vcreset", description="Disconnect all from a voice channel")
    @commands.has_permissions(move_members=True)
    async def vcreset(self, ctx, channel: discord.VoiceChannel):
        for member in channel.members:
            await member.move_to(None)
        await ctx.send(f"🔇 Cleared {channel.name}", ephemeral=True)

    # ─── Tickets ───────────────────────────────────────────────────────

    @commands.hybrid_command(name="ticket", description="Open a ticket")
    async def ticket(self, ctx):
        category = discord.utils.get(ctx.guild.categories, name="Tickets")
        if not category:
            category = await ctx.guild.create_category("Tickets")
        self.ticket_counter += 1
        channel = await ctx.guild.create_text_channel(
            f"ticket-{self.ticket_counter}",
            category=category,
            overwrites={
                ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                ctx.author: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
        )
        await channel.send(f"{ctx.author.mention} 🎫 Ticket created. Describe your issue.")
        await ctx.send(f"🎫 Ticket created: {channel.mention}", ephemeral=True)

    @commands.hybrid_command(name="close", description="Close a ticket")
    @commands.has_permissions(manage_channels=True)
    async def close(self, ctx):
        if "ticket-" not in ctx.channel.name:
            await ctx.send("This is not a ticket channel.", ephemeral=True)
            return
        await ctx.send("Deleting ticket in 5s...")
        await asyncio.sleep(5)
        await ctx.channel.delete()

    # ─── Cleanup & Mass Actions ──────────────────────────────────────

    @commands.hybrid_command(name="purgeuser", description="Delete all messages from a user in channel")
    @commands.has_permissions(manage_messages=True)
    async def purgeuser(self, ctx, user: discord.Member, limit: int = 50):
        deleted = 0
        async for msg in ctx.channel.history(limit=limit):
            if msg.author == user:
                await msg.delete()
                deleted += 1
                await asyncio.sleep(0.5)
        await ctx.send(f"🧹 Deleted {deleted} messages from {user.mention}", ephemeral=True)

    @commands.hybrid_command(name="purgecontains", description="Delete messages containing a word")
    @commands.has_permissions(manage_messages=True)
    async def purgecontains(self, ctx, word: str, limit: int = 50):
        deleted = 0
        async for msg in ctx.channel.history(limit=limit):
            if word.lower() in msg.content.lower():
                await msg.delete()
                deleted += 1
                await asyncio.sleep(0.3)
        await ctx.send(f"🧹 Deleted {deleted} messages containing '{word}'", ephemeral=True)

    # ─── Role Management ──────────────────────────────────────────────

    @commands.hybrid_command(name="addrole", description="Add a role to a member")
    @commands.has_permissions(manage_roles=True)
    async def addrole(self, ctx, member: discord.Member, role: discord.Role):
        await member.add_roles(role)
        await ctx.send(f"✅ Added {role.name} to {member.mention}", ephemeral=True)

    @commands.hybrid_command(name="removerole", description="Remove a role from a member")
    @commands.has_permissions(manage_roles=True)
    async def removerole(self, ctx, member: discord.Member, role: discord.Role):
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed {role.name} from {member.mention}", ephemeral=True)

    @commands.hybrid_command(name="roleall", description="Add a role to all members (use with care)")
    @commands.has_permissions(administrator=True)
    async def roleall(self, ctx, role: discord.Role):
        count = 0
        for member in ctx.guild.members:
            if role not in member.roles:
                try:
                    await member.add_roles(role)
                    count += 1
                    await asyncio.sleep(0.5)
                except:
                    pass
        await ctx.send(f"✅ Added {role.name} to {count} members.", ephemeral=True)

    # ─── Emergency ────────────────────────────────────────────────────

    @commands.hybrid_command(name="nuke", description="Delete and clone the channel")
    @commands.has_permissions(administrator=True)
    async def nuke(self, ctx):
        channel = ctx.channel
        new_channel = await channel.clone()
        await channel.delete()
        await new_channel.send("💥 Channel nuked and restored.", ephemeral=False)

    # ─── Error Handling ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.", ephemeral=True)
        else:
            await ctx.send(f"⚠️ Error: {str(error)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Moderation(bot))