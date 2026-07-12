import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from datetime import timedelta
from typing import Optional

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.temp_voice_channels = {}
        self.ticket_counter = 0

    # ─── Helper Functions ──────────────────────────────────────────────

    def is_mod(self, member: discord.Member):
        return any(role.permissions.administrator or role.permissions.manage_messages for role in member.roles)

    async def mod_log(self, guild, action, target, moderator, reason=""):
        channel = discord.utils.get(guild.text_channels, name="mod-logs")
        if not channel:
            channel = guild.system_channel
        if channel:
            embed = discord.Embed(
                title=f"🔨 {action}",
                color=discord.Color.red() if action in ["Kick", "Ban", "Warn", "Mute"] else discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Target", value=target.mention if target else "N/A", inline=False)
            embed.add_field(name="Moderator", value=moderator.mention, inline=False)
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass 

    # ─── Events ────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"[✅] Moderation cog loaded.")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        
        # Auto-mod: invite links
        if "discord.gg/" in message.content and not self.is_mod(message.author):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention} No invite links!", delete_after=5)
            except discord.Forbidden:
                pass
                
        # Spam detection simple
        if len(message.content.split()) > 30 and not self.is_mod(message.author):
            try:
                await message.delete()
                await message.channel.send(f"{message.author.mention} Please don't spam.", delete_after=5)
            except discord.Forbidden:
                pass

    # ─── Basic Mod Commands ──────────────────────────────────────────

    @commands.hybrid_command(name="kick", description="Kick a member")
    @commands.has_permissions(kick_members=True)
    @app_commands.default_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason="No reason provided"):
        await member.kick(reason=reason)
        await self.mod_log(ctx.guild, "Kick", member, ctx.author, reason)
        await ctx.send(f"👢 Kicked {member.mention} | {reason}", ephemeral=True)

    @commands.hybrid_command(name="ban", description="Ban a member")
    @commands.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason="No reason provided"):
        await member.ban(reason=reason)
        await self.mod_log(ctx.guild, "Ban", member, ctx.author, reason)
        await ctx.send(f"🔨 Banned {member.mention} | {reason}", ephemeral=True)

    @commands.hybrid_command(name="unban", description="Unban a user by ID")
    @commands.has_permissions(ban_members=True)
    @app_commands.default_permissions(ban_members=True)
    async def unban(self, ctx, user_id: str, *, reason="No reason provided"):
        user = await self.bot.fetch_user(int(user_id))
        await ctx.guild.unban(user, reason=reason)
        await self.mod_log(ctx.guild, "Unban", user, ctx.author, reason)
        await ctx.send(f"♻️ Unbanned {user.name}", ephemeral=True)

    @commands.hybrid_command(name="clear", description="Delete up to 100 messages")
    @commands.has_permissions(manage_messages=True)
    @app_commands.default_permissions(manage_messages=True)
    async def clear(self, ctx, amount: int):
        amount = min(amount, 100)
        await ctx.defer(ephemeral=True)
        deleted = await ctx.channel.purge(limit=amount + 1)
        await ctx.send(f"🧹 Deleted {len(deleted)-1} messages.", ephemeral=True)

    @commands.hybrid_command(name="slowmode", description="Set slowmode in seconds")
    @commands.has_permissions(manage_messages=True)
    @app_commands.default_permissions(manage_messages=True)
    async def slowmode(self, ctx, seconds: int):
        await ctx.channel.edit(slowmode_delay=seconds)
        await ctx.send(f"⏳ Slowmode set to {seconds}s", ephemeral=True)

    @commands.hybrid_command(name="mute", description="Timeout a member")
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, duration: int, *, reason="No reason"):
        until = discord.utils.utcnow() + timedelta(minutes=duration)
        await member.timeout(until, reason=reason)
        await self.mod_log(ctx.guild, "Mute", member, ctx.author, f"{duration}min | {reason}")
        await ctx.send(f"🤐 {member.mention} muted for {duration}min", ephemeral=True)

    @commands.hybrid_command(name="unmute", description="Remove timeout")
    @commands.has_permissions(moderate_members=True)
    @app_commands.default_permissions(moderate_members=True)
    async def unmute(self, ctx, member: discord.Member):
        await member.timeout(None)
        await self.mod_log(ctx.guild, "Unmute", member, ctx.author)
        await ctx.send(f"🔊 {member.mention} unmuted", ephemeral=True)

    # ─── Warn Database System ─────────────────────────────────────────

    @commands.hybrid_command(name="warn", description="Warn a member")
    @commands.has_permissions(kick_members=True)
    @app_commands.default_permissions(kick_members=True)
    async def warn(self, ctx, member: discord.Member, *, reason="No reason"):
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "INSERT INTO warnings (guild_id, user_id, moderator_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
                (str(ctx.guild.id), str(member.id), str(ctx.author.id), reason, discord.utils.utcnow().isoformat())
            )
        await self.bot.db.commit()

        await self.mod_log(ctx.guild, "Warn", member, ctx.author, reason)
        await ctx.send(f"⚠️ {member.mention} warned | {reason}", ephemeral=True)

    @commands.hybrid_command(name="warns", description="Check warns for a member")
    @commands.has_permissions(kick_members=True)
    @app_commands.default_permissions(kick_members=True)
    async def warns(self, ctx, member: discord.Member):
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "SELECT moderator_id, reason FROM warnings WHERE guild_id = ? AND user_id = ? ORDER BY timestamp DESC LIMIT 5",
                (str(ctx.guild.id), str(member.id))
            )
            rows = await cursor.fetchall()

        if not rows:
            await ctx.send(f"{member.mention} has no warnings.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Warnings for {member}", color=discord.Color.orange())
        for i, (mod_id, reason) in enumerate(rows, 1):
            embed.add_field(name=f"⚠️ Warning #{i}", value=f"**Reason:** {reason}\n**Mod:** <@{mod_id}>", inline=False)
            
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="clearwarns", description="Clear all warns for a member")
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def clearwarns(self, ctx, member: discord.Member):
        async with self.bot.db.cursor() as cursor:
            await cursor.execute(
                "DELETE FROM warnings WHERE guild_id = ? AND user_id = ?",
                (str(ctx.guild.id), str(member.id))
            )
        await self.bot.db.commit()
        await ctx.send(f"✅ Cleared all warns for {member.mention}", ephemeral=True)

    # ─── Advanced Mod Commands ────────────────────────────────────────

    @commands.hybrid_command(name="lock", description="Lock the current channel")
    @commands.has_permissions(manage_channels=True)
    @app_commands.default_permissions(manage_channels=True)
    async def lock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False)
        await ctx.send(f"🔒 {ctx.channel.mention} locked.")

    @commands.hybrid_command(name="unlock", description="Unlock the current channel")
    @commands.has_permissions(manage_channels=True)
    @app_commands.default_permissions(manage_channels=True)
    async def unlock(self, ctx):
        await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=True)
        await ctx.send(f"🔓 {ctx.channel.mention} unlocked.")

    @commands.hybrid_command(name="nick", description="Change a member's nickname")
    @commands.has_permissions(manage_nicknames=True)
    @app_commands.default_permissions(manage_nicknames=True)
    async def nick(self, ctx, member: discord.Member, *, nickname: str = None):
        old = member.display_name
        await member.edit(nick=nickname)
        await ctx.send(f"✏️ {old} → {nickname or member.name}", ephemeral=True)

    @commands.hybrid_command(name="move", description="Move all members to another voice channel")
    @commands.has_permissions(move_members=True)
    @app_commands.default_permissions(move_members=True)
    async def move(self, ctx, from_ch: discord.VoiceChannel, to_ch: discord.VoiceChannel):
        for member in from_ch.members:
            await member.move_to(to_ch)
        await ctx.send(f"📦 Moved members to {to_ch.mention}.", ephemeral=True)

    @commands.hybrid_command(name="vcreset", description="Disconnect all from a voice channel")
    @commands.has_permissions(move_members=True)
    @app_commands.default_permissions(move_members=True)
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
    @app_commands.default_permissions(manage_channels=True)
    async def close(self, ctx):
        if "ticket-" not in ctx.channel.name:
            await ctx.send("This is not a ticket channel.", ephemeral=True)
            return
        await ctx.send("Deleting ticket in 5s...")
        await asyncio.sleep(5)
        await ctx.channel.delete()

    # ─── Optimized Cleanup / Mass Actions ─────────────────────────────

    @commands.hybrid_command(name="purgeuser", description="Mass delete messages from a user")
    @commands.has_permissions(manage_messages=True)
    @app_commands.default_permissions(manage_messages=True)
    async def purgeuser(self, ctx, user: discord.Member, limit: int = 50):
        await ctx.defer(ephemeral=True)
        def is_user(m):
            return m.author.id == user.id
        
        deleted = await ctx.channel.purge(limit=limit, check=is_user)
        await ctx.send(f"🧹 Deleted {len(deleted)} messages from {user.mention}", ephemeral=True)

    @commands.hybrid_command(name="purgecontains", description="Delete messages containing a word")
    @commands.has_permissions(manage_messages=True)
    @app_commands.default_permissions(manage_messages=True)
    async def purgecontains(self, ctx, word: str, limit: int = 50):
        await ctx.defer(ephemeral=True)
        def contains_word(m):
            return word.lower() in m.content.lower()
            
        deleted = await ctx.channel.purge(limit=limit, check=contains_word)
        await ctx.send(f"🧹 Deleted {len(deleted)} messages containing '{word}'", ephemeral=True)

    # ─── Role Management ──────────────────────────────────────────────

    @commands.hybrid_command(name="addrole", description="Add a role to a member")
    @commands.has_permissions(manage_roles=True)
    @app_commands.default_permissions(manage_roles=True)
    async def addrole(self, ctx, member: discord.Member, role: discord.Role):
        await member.add_roles(role)
        await ctx.send(f"✅ Added {role.name} to {member.mention}", ephemeral=True)

    @commands.hybrid_command(name="removerole", description="Remove a role from a member")
    @commands.has_permissions(manage_roles=True)
    @app_commands.default_permissions(manage_roles=True)
    async def removerole(self, ctx, member: discord.Member, role: discord.Role):
        await member.remove_roles(role)
        await ctx.send(f"✅ Removed {role.name} from {member.mention}", ephemeral=True)

    # ─── Emergency ────────────────────────────────────────────────────

    @commands.hybrid_command(name="nuke", description="Delete and clone the channel")
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def nuke(self, ctx):
        channel = ctx.channel
        new_channel = await channel.clone()
        await channel.delete()
        await new_channel.send("💥 Channel nuked and restored.")

    # ─── Error Handling ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.", ephemeral=True)
        elif isinstance(error, commands.CommandInvokeError) and "Missing Permissions" in str(error):
            await ctx.send("❌ The bot doesn't have permissions to execute this action.", ephemeral=True)
        else:
            print(f"Error in cog command: {error}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
