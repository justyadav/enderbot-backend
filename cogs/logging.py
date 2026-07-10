# logging.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
from collections import defaultdict

log = logging.getLogger(__name__)

class GeneralLogging(commands.Cog):
    """Advanced logging system with per-server configuration and multiple log channels."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # ─── Logging Configuration Cache ─────────────────────────────
        # Structure: { guild_id: {
        #     "mod_log": channel_id or None,
        #     "message_log": channel_id or None,
        #     "voice_log": channel_id or None,
        #     "member_log": channel_id or None,
        #     "server_log": channel_id or None,
        #     "join_log": channel_id or None,
        #     "automod_log": channel_id or None,
        #     "enabled_events": ["message_delete", ...]
        # }}
        self.log_config: Dict[int, Dict] = {}
        
        # ─── Message Cache for Edit Logging ──────────────────────────
        self.message_cache: Dict[Tuple[int, int, int], Tuple[str, int, List[str]]] = {}
        self.MAX_CACHE_SIZE = 1000
        
        # ─── Default Configuration ────────────────────────────────────
        self.DEFAULT_CONFIG = {
            "mod_log": None,
            "message_log": None,
            "voice_log": None,
            "member_log": None,
            "server_log": None,
            "join_log": None,
            "automod_log": None,
            "enabled_events": [
                "message_delete",
                "message_edit",
                "message_bulk_delete",
                "voice_join",
                "voice_leave",
                "voice_move",
                "member_join",
                "member_leave",
                "member_update",
                "role_create",
                "role_delete",
                "role_update",
                "channel_create",
                "channel_delete",
                "channel_update",
                "guild_update",
                "ban_add",
                "ban_remove",
                "unban",
                "kick",
                "mute",
                "warn"
            ]
        }
        
        # ─── Event Cooldowns ──────────────────────────────────────────
        self.event_cooldowns: Dict[Tuple[int, int], datetime] = {}
        self.COOLDOWN_SECONDS = 2

    # ─── Lifecycle ────────────────────────────────────────────────────

    async def cog_load(self):
        """Load logging configurations from the bot's database or file."""
        # Try to load from the bot's database if available
        if hasattr(self.bot, 'db') and self.bot.db:
            try:
                # Check if it's an in-memory fallback or real MongoDB
                if hasattr(self.bot.db, 'guild_logging_settings'):
                    # Use the collection
                    cursor = self.bot.db.guild_logging_settings.find({})
                    async for doc in cursor:
                        guild_id = doc.get("guild_id")
                        if guild_id:
                            # Convert channel IDs to int
                            config = {}
                            for key, value in doc.items():
                                if key.endswith("_log") and value:
                                    config[key] = int(value)
                                elif key == "enabled_events":
                                    config[key] = value
                            self.log_config[int(guild_id)] = config
                    log.info(f"Loaded logging config for {len(self.log_config)} servers from bot.db")
                else:
                    log.warning("Bot database does not have 'guild_logging_settings' collection")
            except Exception as e:
                log.error(f"Failed to load logging configs from database: {e}")
        else:
            log.warning("Bot database not available - logging configs will be in-memory only")
            
        # Also try to load from file as fallback
        try:
            import json
            import os
            if os.path.exists("logging_configs.json"):
                with open("logging_configs.json", "r") as f:
                    data = json.load(f)
                    for guild_id, config in data.items():
                        if int(guild_id) not in self.log_config:
                            self.log_config[int(guild_id)] = config
                log.info(f"Loaded logging configs from file for {len(data)} servers")
        except Exception as e:
            pass

    async def cog_unload(self):
        """Save configurations and cleanup."""
        try:
            import json
            with open("logging_configs.json", "w") as f:
                json.dump(self.log_config, f, indent=4)
            log.info("Saved logging configs to file")
        except Exception as e:
            log.error(f"Failed to save logging configs: {e}")
        
        self.message_cache.clear()

    # ─── Helper Methods ──────────────────────────────────────────────

    async def get_log_channel(
        self, 
        guild: discord.Guild, 
        log_type: str
    ) -> Optional[discord.TextChannel]:
        """Get a specific log channel for the guild."""
        config = self.log_config.get(guild.id, {})
        channel_id = config.get(log_type)
        
        if not channel_id:
            return None
            
        channel = guild.get_channel(channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            # Channel doesn't exist - clear it from config
            if guild.id in self.log_config and log_type in self.log_config[guild.id]:
                self.log_config[guild.id][log_type] = None
                await self.save_config(guild.id)
            return None
            
        # Check if bot can send messages
        if not channel.permissions_for(guild.me).send_messages:
            return None
            
        return channel

    async def save_config(self, guild_id: int):
        """Save guild logging config to file and database if available."""
        config = self.log_config.get(guild_id, {})
        if not config:
            return
            
        # Save to file
        try:
            import json
            with open("logging_configs.json", "w") as f:
                json.dump(self.log_config, f, indent=4)
        except:
            pass
            
        # Save to database if available
        if hasattr(self.bot, 'db') and self.bot.db:
            try:
                if hasattr(self.bot.db, 'guild_logging_settings'):
                    await self.bot.db.guild_logging_settings.update_one(
                        {"guild_id": guild_id},
                        {"$set": config},
                        upsert=True
                    )
            except Exception as e:
                log.error(f"Failed to save logging config to database: {e}")

    async def send_log(
        self,
        guild: discord.Guild,
        log_type: str,
        embed: discord.Embed,
        extra_embed: Optional[discord.Embed] = None
    ):
        """Send a log embed to the appropriate channel."""
        channel = await self.get_log_channel(guild, log_type)
        if not channel:
            return
            
        try:
            await channel.send(embed=embed)
            if extra_embed:
                await channel.send(embed=extra_embed)
        except Exception as e:
            log.error(f"Failed to send log to {channel.name}: {e}")

    def create_base_embed(
        self, 
        title: str, 
        color: discord.Color,
        description: Optional[str] = None
    ) -> discord.Embed:
        """Create a base embed with standard footer."""
        embed = discord.Embed(
            title=title,
            color=color,
            description=description,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="Made by yaduvanshi1816_")
        return embed

    # ─── Event: Message Delete ──────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild:
            return
        cache_key = (message.guild.id, message.channel.id, message.id)
        cached = self.message_cache.pop(cache_key, None)
        
        embed = self.create_base_embed("🗑️ Message Deleted", discord.Color.red())
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Message ID", value=message.id, inline=True)
        
        if cached:
            content, author_id, attachments = cached
            if len(content) > 1024:
                content = content[:1021] + "..."
            embed.add_field(name="Content", value=f"```\n{content}\n```", inline=False)
            if attachments:
                embed.add_field(name="Attachments", value=f"{len(attachments)} files", inline=True)
        else:
            embed.add_field(name="Content", value="*Message not cached*", inline=False)
            
        await self.send_log(message.guild, "message_log", embed)

    # ─── Event: Message Edit ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if not before.guild or before.author.bot:
            return
        if before.content == after.content and before.attachments == after.attachments:
            return
            
        embed = self.create_base_embed("✏️ Message Edited", discord.Color.gold())
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Message ID", value=before.id, inline=True)
        
        before_content = before.content or "*No content*"
        after_content = after.content or "*No content*"
        if len(before_content) > 1024:
            before_content = before_content[:1021] + "..."
        if len(after_content) > 1024:
            after_content = after_content[:1021] + "..."
            
        embed.add_field(name="Before", value=f"```\n{before_content}\n```", inline=False)
        embed.add_field(name="After", value=f"```\n{after_content}\n```", inline=False)
        
        if before.attachments or after.attachments:
            embed.add_field(name="Attachments", value=f"Before: {len(before.attachments)} | After: {len(after.attachments)}", inline=True)
            
        await self.send_log(before.guild, "message_log", embed)

    # ─── Event: Bulk Message Delete ──────────────────────────────────

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages: List[discord.Message]):
        if not messages or not messages[0].guild:
            return
        guild = messages[0].guild
        channel = messages[0].channel
        
        embed = self.create_base_embed("📦 Bulk Messages Deleted", discord.Color.dark_red())
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Messages Deleted", value=len(messages), inline=True)
        
        sample = messages[:5]
        content_samples = []
        for msg in sample:
            content = msg.content or "*No content*"
            if len(content) > 50:
                content = content[:47] + "..."
            content_samples.append(f"{msg.author.name}: {content}")
        if content_samples:
            embed.add_field(name="Sample (max 5)", value="```\n" + "\n".join(content_samples) + "\n```", inline=False)
            
        await self.send_log(guild, "message_log", embed)

    # ─── Event: Voice State Updates ──────────────────────────────────

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if not member.guild:
            return
        cooldown_key = (member.guild.id, member.id)
        if cooldown_key in self.event_cooldowns:
            if (datetime.now(timezone.utc) - self.event_cooldowns[cooldown_key]).total_seconds() < self.COOLDOWN_SECONDS:
                return
        self.event_cooldowns[cooldown_key] = datetime.now(timezone.utc)
        
        if before.channel is None and after.channel is not None:
            embed = self.create_base_embed("🔊 Voice Join", discord.Color.green())
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Channel", value=after.channel.mention, inline=True)
            await self.send_log(member.guild, "voice_log", embed)
        elif before.channel is not None and after.channel is None:
            embed = self.create_base_embed("🔇 Voice Leave", discord.Color.red())
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="Channel", value=before.channel.mention, inline=True)
            await self.send_log(member.guild, "voice_log", embed)
        elif before.channel != after.channel and before.channel is not None and after.channel is not None:
            embed = self.create_base_embed("↔️ Voice Move", discord.Color.gold())
            embed.add_field(name="User", value=member.mention, inline=True)
            embed.add_field(name="From", value=before.channel.mention, inline=True)
            embed.add_field(name="To", value=after.channel.mention, inline=True)
            await self.send_log(member.guild, "voice_log", embed)

    # ─── Event: Member Join ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.guild:
            return
        embed = self.create_base_embed("👋 Member Joined", discord.Color.green())
        embed.add_field(name="User", value=f"{member.mention} ({member.name}#{member.discriminator})", inline=False)
        embed.add_field(name="User ID", value=member.id, inline=True)
        embed.add_field(name="Created Account", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Member Count", value=member.guild.member_count, inline=True)
        if (datetime.now(timezone.utc) - member.created_at).days < 30:
            embed.add_field(name="⚠️ Warning", value="Account created within the last 30 days!", inline=False)
            embed.color = discord.Color.orange()
        await self.send_log(member.guild, "join_log", embed)
        await self.send_log(member.guild, "member_log", embed)

    # ─── Event: Member Leave ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not member.guild:
            return
        embed = self.create_base_embed("👋 Member Left", discord.Color.red())
        embed.add_field(name="User", value=f"{member.name}#{member.discriminator}", inline=False)
        embed.add_field(name="User ID", value=member.id, inline=True)
        embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>" if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="Member Count", value=member.guild.member_count, inline=True)
        if member.joined_at:
            duration = datetime.now(timezone.utc) - member.joined_at
            days = duration.days
            if days > 0:
                embed.add_field(name="Time in Server", value=f"{days} days", inline=True)
            else:
                hours = duration.seconds // 3600
                embed.add_field(name="Time in Server", value=f"{hours} hours", inline=True)
        await self.send_log(member.guild, "join_log", embed)
        await self.send_log(member.guild, "member_log", embed)

    # ─── Event: Member Update ────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not before.guild:
            return
        if before.nick != after.nick:
            embed = self.create_base_embed("✏️ Nickname Changed", discord.Color.blue())
            embed.add_field(name="User", value=after.mention, inline=True)
            embed.add_field(name="Before", value=before.nick or "None", inline=True)
            embed.add_field(name="After", value=after.nick or "None", inline=True)
            await self.send_log(before.guild, "member_log", embed)
            
        before_roles = set(before.roles)
        after_roles = set(after.roles)
        added_roles = after_roles - before_roles
        removed_roles = before_roles - after_roles
        
        for role in [r for r in added_roles if r != before.guild.default_role]:
            embed = self.create_base_embed("➕ Role Added", discord.Color.green())
            embed.add_field(name="User", value=after.mention, inline=True)
            embed.add_field(name="Role", value=role.mention, inline=True)
            await self.send_log(before.guild, "member_log", embed)
        for role in [r for r in removed_roles if r != before.guild.default_role]:
            embed = self.create_base_embed("➖ Role Removed", discord.Color.red())
            embed.add_field(name="User", value=after.mention, inline=True)
            embed.add_field(name="Role", value=role.mention, inline=True)
            await self.send_log(before.guild, "member_log", embed)

    # ─── Event: Ban/Unban ────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User):
        embed = self.create_base_embed("🔨 Member Banned", discord.Color.dark_red())
        embed.add_field(name="User", value=f"{user.name}#{user.discriminator}", inline=False)
        embed.add_field(name="User ID", value=user.id, inline=True)
        embed.add_field(name="Banned At", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.ban):
            if entry.target == user:
                embed.add_field(name="Moderator", value=entry.user.mention, inline=True)
                embed.add_field(name="Reason", value=entry.reason or "No reason provided", inline=False)
                break
        await self.send_log(guild, "mod_log", embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User):
        embed = self.create_base_embed("♻️ Member Unbanned", discord.Color.green())
        embed.add_field(name="User", value=f"{user.name}#{user.discriminator}", inline=False)
        embed.add_field(name="User ID", value=user.id, inline=True)
        embed.add_field(name="Unbanned At", value=f"<t:{int(datetime.now(timezone.utc).timestamp())}:F>", inline=True)
        async for entry in guild.audit_logs(limit=5, action=discord.AuditLogAction.unban):
            if entry.target == user:
                embed.add_field(name="Moderator", value=entry.user.mention, inline=True)
                embed.add_field(name="Reason", value=entry.reason or "No reason provided", inline=False)
                break
        await self.send_log(guild, "mod_log", embed)

    # ─── Event: Guild Update ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        if before.name != after.name:
            embed = self.create_base_embed("🏷️ Server Name Changed", discord.Color.blue())
            embed.add_field(name="Before", value=before.name, inline=True)
            embed.add_field(name="After", value=after.name, inline=True)
            await self.send_log(after, "server_log", embed)
        if before.icon != after.icon:
            embed = self.create_base_embed("🖼️ Server Icon Changed", discord.Color.blue())
            embed.add_field(name="Server", value=after.name, inline=True)
            if after.icon:
                embed.set_thumbnail(url=after.icon.url)
            await self.send_log(after, "server_log", embed)

    # ─── Event: Channel Updates ──────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        embed = self.create_base_embed("📝 Channel Created", discord.Color.green())
        embed.add_field(name="Name", value=channel.name, inline=True)
        embed.add_field(name="Type", value=channel.type, inline=True)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
        if isinstance(channel, discord.TextChannel):
            embed.add_field(name="NSFW", value="Yes" if channel.nsfw else "No", inline=True)
        elif isinstance(channel, discord.VoiceChannel):
            embed.add_field(name="User Limit", value=channel.user_limit or "Unlimited", inline=True)
        await self.send_log(channel.guild, "server_log", embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        embed = self.create_base_embed("🗑️ Channel Deleted", discord.Color.red())
        embed.add_field(name="Name", value=channel.name, inline=True)
        embed.add_field(name="Type", value=channel.type, inline=True)
        embed.add_field(name="Category", value=channel.category.name if channel.category else "None", inline=True)
        await self.send_log(channel.guild, "server_log", embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        if before.name != after.name:
            embed = self.create_base_embed("✏️ Channel Name Changed", discord.Color.gold())
            embed.add_field(name="Before", value=before.name, inline=True)
            embed.add_field(name="After", value=after.name, inline=True)
            embed.add_field(name="Type", value=before.type, inline=True)
            await self.send_log(after.guild, "server_log", embed)

    # ─── Event: Role Updates ─────────────────────────────────────────

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        embed = self.create_base_embed("➕ Role Created", discord.Color.green())
        embed.add_field(name="Name", value=role.name, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        embed.add_field(name="Position", value=role.position, inline=True)
        embed.add_field(name="Mentionable", value="Yes" if role.mentionable else "No", inline=True)
        embed.add_field(name="Hoisted", value="Yes" if role.hoist else "No", inline=True)
        await self.send_log(role.guild, "server_log", embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        embed = self.create_base_embed("➖ Role Deleted", discord.Color.red())
        embed.add_field(name="Name", value=role.name, inline=True)
        embed.add_field(name="Color", value=str(role.color), inline=True)
        await self.send_log(role.guild, "server_log", embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.name != after.name:
            embed = self.create_base_embed("✏️ Role Name Changed", discord.Color.gold())
            embed.add_field(name="Before", value=before.name, inline=True)
            embed.add_field(name="After", value=after.name, inline=True)
            await self.send_log(after.guild, "server_log", embed)
        if before.color != after.color:
            embed = self.create_base_embed("🎨 Role Color Changed", discord.Color.gold())
            embed.add_field(name="Role", value=after.mention, inline=True)
            embed.add_field(name="Before", value=str(before.color), inline=True)
            embed.add_field(name="After", value=str(after.color), inline=True)
            await self.send_log(after.guild, "server_log", embed)

    # ─── Message Cache ────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
        config = self.log_config.get(message.guild.id, {})
        if not config.get("enabled_events", []):
            return
        cache_key = (message.guild.id, message.channel.id, message.id)
        attachment_urls = [a.url for a in message.attachments]
        self.message_cache[cache_key] = (message.content, message.author.id, attachment_urls)
        if len(self.message_cache) > self.MAX_CACHE_SIZE:
            to_remove = len(self.message_cache) - self.MAX_CACHE_SIZE
            for _ in range(to_remove):
                self.message_cache.popitem(last=False)

    # ─── Configuration Commands ──────────────────────────────────────

    @app_commands.command(name="setlog", description="Set a logging channel for specific events")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(log_type=[
        app_commands.Choice(name="Mod Actions (Kick/Ban/Warn/Mute)", value="mod_log"),
        app_commands.Choice(name="Message Events (Delete/Edit)", value="message_log"),
        app_commands.Choice(name="Voice Events (Join/Leave/Move)", value="voice_log"),
        app_commands.Choice(name="Member Events (Join/Leave/Update)", value="member_log"),
        app_commands.Choice(name="Server Events (Channel/Role/Guild Updates)", value="server_log"),
        app_commands.Choice(name="Join/Leave Events", value="join_log"),
        app_commands.Choice(name="Automod Events (Spam/Filter)", value="automod_log")
    ])
    async def setlog(
        self,
        interaction: discord.Interaction,
        log_type: app_commands.Choice[str],
        channel: discord.TextChannel
    ):
        guild_id = interaction.guild_id
        if not guild_id:
            return await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        if guild_id not in self.log_config:
            self.log_config[guild_id] = self.DEFAULT_CONFIG.copy()
        self.log_config[guild_id][log_type.value] = channel.id
        await self.save_config(guild_id)
        test_embed = self.create_base_embed(
            "✅ Logging Channel Set",
            discord.Color.green(),
            f"**{log_type.name}** will now be logged to {channel.mention}"
        )
        try:
            await channel.send(embed=test_embed)
        except:
            pass
        await interaction.response.send_message(
            f"✅ Logging for **{log_type.name}** set to {channel.mention}",
            ephemeral=True
        )

    @app_commands.command(name="removelog", description="Remove a logging channel")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.choices(log_type=[
        app_commands.Choice(name="Mod Actions", value="mod_log"),
        app_commands.Choice(name="Message Events", value="message_log"),
        app_commands.Choice(name="Voice Events", value="voice_log"),
        app_commands.Choice(name="Member Events", value="member_log"),
        app_commands.Choice(name="Server Events", value="server_log"),
        app_commands.Choice(name="Join/Leave Events", value="join_log"),
        app_commands.Choice(name="Automod Events", value="automod_log")
    ])
    async def removelog(
        self,
        interaction: discord.Interaction,
        log_type: app_commands.Choice[str]
    ):
        guild_id = interaction.guild_id
        if not guild_id:
            return await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        if guild_id not in self.log_config:
            return await interaction.response.send_message("❌ No logging configuration found for this server.", ephemeral=True)
        self.log_config[guild_id][log_type.value] = None
        await self.save_config(guild_id)
        await interaction.response.send_message(
            f"✅ Removed logging for **{log_type.name}**",
            ephemeral=True
        )

    @app_commands.command(name="logsettings", description="View current logging configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def logsettings(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        if not guild_id:
            return await interaction.response.send_message("❌ This command must be used in a server.", ephemeral=True)
        config = self.log_config.get(guild_id, self.DEFAULT_CONFIG.copy())
        embed = self.create_base_embed("📋 Logging Configuration", discord.Color.blue())
        log_types = {
            "mod_log": "Mod Actions",
            "message_log": "Message Events",
            "voice_log": "Voice Events",
            "member_log": "Member Events",
            "server_log": "Server Events",
            "join_log": "Join/Leave",
            "automod_log": "Automod"
        }
        for key, display in log_types.items():
            channel_id = config.get(key)
            if channel_id:
                channel = interaction.guild.get_channel(channel_id)
                if channel:
                    value = f"✅ {channel.mention}"
                else:
                    value = "❌ Deleted Channel"
            else:
                value = "❌ Not Set"
            embed.add_field(name=display, value=value, inline=True)
        enabled = config.get("enabled_events", [])
        if enabled:
            embed.add_field(
                name="Enabled Events",
                value=f"```\n{', '.join(enabled[:10])}{'...' if len(enabled) > 10 else ''}\n```",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ─── Setup Function ──────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(GeneralLogging(bot))