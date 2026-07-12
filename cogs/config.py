import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import logging
import asyncio
import copy
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

log = logging.getLogger(__name__)

class Config(commands.Cog):
    """Server configuration management with per-server settings."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # ─── Configuration Cache ──────────────────────────────────────
        self.guild_configs: Dict[int, Dict[str, Any]] = {}
        
        # ─── Default Configuration ────────────────────────────────────
        self.DEFAULT_CONFIG = {
            "prefix": "!",
            "timezone": "UTC",
            "mod_role": None,
            "admin_role": None,
            "mute_role": None,
            "autorole": None,
            "welcome_channel": None,
            "welcome_message": "Welcome {user} to {server}! 🎉",
            "leave_channel": None,
            "leave_message": "{user} left the server. 😢",
            "suggestion_channel": None,
            "report_channel": None,
            "log_channel": None,
            "leveling_enabled": True,
            "leveling_channel": None,
            "levelup_message": "{user} just leveled up to level {level}! 🎉",
            "auto_delete_invites": True,
            "auto_moderation": True,
            "profanity_filter": True,
            "spam_protection": True,
            "max_warnings": 5,
            "mute_duration": 10,
            "temp_ban_duration": 7,
            "economy_enabled": True,
            "economy_cooldown": 60,
            "daily_reward": 100,
            "music_enabled": True,
            "music_default_volume": 50,
            "ticket_category": "Tickets",
            "ticket_limit_per_user": 3,
            "reaction_roles": {}
        }
        
        # ─── Language Strings (English Only) ──────────────────────────
        self.strings = {
            "welcome": "Welcome {user} to {server}! 🎉",
            "leave": "{user} left the server. 😢",
            "levelup": "{user} just leveled up to level {level}! 🎉",
            "mute_reason": "You have been muted for {duration} minutes. Reason: {reason}",
            "unmute_reason": "You have been unmuted.",
            "kick_reason": "You have been kicked. Reason: {reason}",
            "ban_reason": "You have been banned. Reason: {reason}",
            "warn_reason": "You have been warned. Reason: {reason}",
            "no_permission": "You don't have permission to use this command.",
            "bot_no_permission": "I don't have permission to do that.",
            "user_not_found": "User not found.",
            "invalid_argument": "Invalid argument: {arg}",
            "command_on_cooldown": "Command on cooldown. Try again in {time} seconds.",
            "success": "✅ Success!",
            "error": "❌ Error: {error}"
        }

    # ─── Lifecycle ────────────────────────────────────────────────────

    async def cog_load(self):
        try:
            if os.path.exists("configs.json"):
                with open("configs.json", "r") as f:
                    data = json.load(f)
                    for guild_id, config in data.items():
                        self.guild_configs[int(guild_id)] = config
                log.info(f"Loaded configs for {len(self.guild_configs)} servers from file")
            
            try:
                from database import guild_configs_db
                cursor = guild_configs_db.find({})
                async for doc in cursor:
                    guild_id = doc.get("guild_id")
                    if guild_id:
                        if guild_id in self.guild_configs:
                            self.guild_configs[guild_id].update(doc)
                        else:
                            self.guild_configs[guild_id] = doc
                log.info(f"Loaded configs for {len(self.guild_configs)} servers from database")
            except ImportError:
                log.warning("guild_configs_db not available - using file-based configs")
                
        except Exception as e:
            log.error(f"Failed to load configs: {e}")

    async def cog_unload(self):
        try:
            with open("configs.json", "w") as f:
                json.dump(self.guild_configs, f, indent=4)
            log.info("Saved configs to file")
        except Exception as e:
            log.error(f"Failed to save configs: {e}")

    # ─── Helper Methods ──────────────────────────────────────────────

    def get_config(self, guild_id: int) -> Dict[str, Any]:
        config = self.guild_configs.get(guild_id, {})
        for key, value in self.DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config

    async def set_config(self, guild_id: int, key: str, value: Any):
        if guild_id not in self.guild_configs:
            self.guild_configs[guild_id] = copy.deepcopy(self.DEFAULT_CONFIG)
        self.guild_configs[guild_id][key] = value
        
        try:
            from database import guild_configs_db
            await guild_configs_db.update_one(
                {"guild_id": guild_id},
                {"$set": {key: value}},
                upsert=True
            )
        except ImportError:
            pass
        
        try:
            with open("configs.json", "w") as f:
                json.dump(self.guild_configs, f, indent=4)
        except:
            pass

    def get_string(self, key: str, **kwargs) -> str:
        """Get a localized string (English fallback)."""
        string = self.strings.get(key, key)
        try:
            return string.format(**kwargs)
        except:
            return string

    async def get_channel_from_config(self, guild: discord.Guild, config_key: str) -> Optional[discord.TextChannel]:
        config = self.get_config(guild.id)
        channel_id = config.get(config_key)
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def get_role_from_config(self, guild: discord.Guild, config_key: str) -> Optional[discord.Role]:
        config = self.get_config(guild.id)
        role_id = config.get(config_key)
        if not role_id:
            return None
        return guild.get_role(role_id)

    # ─── Configuration Commands ──────────────────────────────────────

    @commands.hybrid_group(name="config", description="Manage server configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await self.show_config(ctx)

    @config_group.command(name="show", description="Show current server configuration")
    async def show_config(self, ctx: commands.Context):
        config = self.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title=f"⚙️ Configuration - {ctx.guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        general = [
            f"📌 Prefix: `{config.get('prefix', '!')}`",
            f"🌍 Language: 🇬🇧 English",
            f"🕐 Timezone: `{config.get('timezone', 'UTC')}`"
        ]
        embed.add_field(name="📋 General Settings", value="\n".join(general), inline=False)
        
        roles = []
        for key, label in [("mod_role", "👮 Mod Role"), ("admin_role", "👑 Admin Role"), ("mute_role", "🔇 Mute Role")]:
            role = await self.get_role_from_config(ctx.guild, key)
            roles.append(f"{label}: {role.mention if role else '❌ Not Set'}")
        embed.add_field(name="🎭 Roles", value="\n".join(roles), inline=False)
        
        channels = []
        for key, label in [
            ("welcome_channel", "👋 Welcome Channel"), ("leave_channel", "👋 Leave Channel"),
            ("suggestion_channel", "💡 Suggestion Channel"), ("report_channel", "📢 Report Channel"),
            ("log_channel", "📋 Log Channel"), ("leveling_channel", "📈 Leveling Channel")
        ]:
            channel = await self.get_channel_from_config(ctx.guild, key)
            channels.append(f"{label}: {channel.mention if channel else '❌ Not Set'}")
        embed.add_field(name="📢 Channels", value="\n".join(channels), inline=False)
        
        features = []
        feature_keys = [
            ("leveling_enabled", "📈 Leveling"), ("auto_moderation", "🛡️ Auto-Moderation"),
            ("profanity_filter", "🔞 Profanity Filter"), ("spam_protection", "🚫 Spam Protection"),
            ("economy_enabled", "💰 Economy"), ("music_enabled", "🎵 Music")
        ]
        for key, label in feature_keys:
            value = config.get(key, True)
            features.append(f"{label}: {'✅' if value else '❌'}")
        embed.add_field(name="⚡ Features", value="\n".join(features), inline=False)
        
        limits = [
            f"⚠️ Max Warnings: `{config.get('max_warnings', 5)}`",
            f"🔇 Mute Duration: `{config.get('mute_duration', 10)} minutes`",
            f"⏳ Temp Ban Duration: `{config.get('temp_ban_duration', 7)} days`",
            f"🎫 Ticket Limit: `{config.get('ticket_limit_per_user', 3)}`"
        ]
        embed.add_field(name="📊 Limits", value="\n".join(limits), inline=False)
        
        economy = [
            f"💰 Daily Reward: `{config.get('daily_reward', 100)}`",
            f"⏱️ Cooldown: `{config.get('economy_cooldown', 60)} seconds`"
        ]
        embed.add_field(name="💎 Economy", value="\n".join(economy), inline=False)
        
        embed.set_footer(text=f"Made by yaduvanshi1816_ • Server ID: {ctx.guild.id}")
        await ctx.send(embed=embed)

    @config_group.command(name="setprefix", description="Set the bot prefix for this server")
    async def setprefix(self, ctx: commands.Context, prefix: str):
        if len(prefix) > 10:
            await ctx.send("❌ Prefix cannot be longer than 10 characters.", ephemeral=True)
            return
        await self.set_config(ctx.guild.id, "prefix", prefix)
        await ctx.send(f"✅ Prefix updated to: `{prefix}`", ephemeral=True)

    @config_group.command(name="setmodrole", description="Set the moderator role")
    async def setmodrole(self, ctx: commands.Context, role: discord.Role):
        await self.set_config(ctx.guild.id, "mod_role", role.id)
        await ctx.send(f"✅ Moderator role set to: {role.mention}", ephemeral=True)

    @config_group.command(name="setadminrole", description="Set the admin role")
    async def setadminrole(self, ctx: commands.Context, role: discord.Role):
        await self.set_config(ctx.guild.id, "admin_role", role.id)
        await ctx.send(f"✅ Admin role set to: {role.mention}", ephemeral=True)

    @config_group.command(name="setmuterole", description="Set the mute role")
    async def setmuterole(self, ctx: commands.Context, role: discord.Role):
        await self.set_config(ctx.guild.id, "mute_role", role.id)
        await ctx.send(f"✅ Mute role set to: {role.mention}", ephemeral=True)

    @config_group.command(name="setwelcome", description="Set the welcome channel and message")
    async def setwelcome(self, ctx: commands.Context, channel: discord.TextChannel, *, message: Optional[str] = None):
        await self.set_config(ctx.guild.id, "welcome_channel", channel.id)
        if message:
            await self.set_config(ctx.guild.id, "welcome_message", message)
        await ctx.send(f"✅ Welcome channel set to: {channel.mention}", ephemeral=True)

    @config_group.command(name="setleave", description="Set the leave channel and message")
    async def setleave(self, ctx: commands.Context, channel: discord.TextChannel, *, message: Optional[str] = None):
        await self.set_config(ctx.guild.id, "leave_channel", channel.id)
        if message:
            await self.set_config(ctx.guild.id, "leave_message", message)
        await ctx.send(f"✅ Leave channel set to: {channel.mention}", ephemeral=True)

    @config_group.command(name="setautorole", description="Set the auto-role for new members")
    async def setautorole(self, ctx: commands.Context, role: discord.Role):
        await self.set_config(ctx.guild.id, "autorole", role.id)
        await ctx.send(f"✅ Auto-role set to: {role.mention}", ephemeral=True)

    @config_group.command(name="setfeature", description="Enable/disable a feature")
    @app_commands.choices(feature=[
        app_commands.Choice(name="Leveling", value="leveling_enabled"),
        app_commands.Choice(name="Auto-Moderation", value="auto_moderation"),
        app_commands.Choice(name="Profanity Filter", value="profanity_filter"),
        app_commands.Choice(name="Spam Protection", value="spam_protection"),
        app_commands.Choice(name="Economy", value="economy_enabled"),
        app_commands.Choice(name="Music", value="music_enabled")
    ])
    @app_commands.choices(state=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable")
    ])
    async def setfeature(self, ctx: commands.Context, feature: str, state: str):
        feat_val = feature.value if hasattr(feature, 'value') else feature
        state_val = state.value if hasattr(state, 'value') else state
        
        value = state_val == "enable"
        await self.set_config(ctx.guild.id, feat_val, value)
        await ctx.send(f"✅ Feature `{feat_val}` has been **{'enabled' if value else 'disabled'}**", ephemeral=True)

    @config_group.command(name="setlimit", description="Set warning/ticket limits")
    @app_commands.choices(limit_type=[
        app_commands.Choice(name="Max Warnings", value="max_warnings"),
        app_commands.Choice(name="Mute Duration (minutes)", value="mute_duration"),
        app_commands.Choice(name="Temp Ban Duration (days)", value="temp_ban_duration"),
        app_commands.Choice(name="Ticket Limit per User", value="ticket_limit_per_user")
    ])
    async def setlimit(self, ctx: commands.Context, limit_type: str, value: int):
        lim_val = limit_type.value if hasattr(limit_type, 'value') else limit_type
        
        if value < 1:
            await ctx.send("❌ Value must be at least 1.", ephemeral=True)
            return
        if lim_val == "max_warnings" and value > 20:
            await ctx.send("❌ Max warnings cannot exceed 20.", ephemeral=True)
            return
        if lim_val == "mute_duration" and value > 1440:
            await ctx.send("❌ Mute duration cannot exceed 1440 minutes (24 hours).", ephemeral=True)
            return
        if lim_val == "temp_ban_duration" and value > 30:
            await ctx.send("❌ Temp ban duration cannot exceed 30 days.", ephemeral=True)
            return
            
        await self.set_config(ctx.guild.id, lim_val, value)
        await ctx.send(f"✅ Limit configuration updated.", ephemeral=True)

    @config_group.command(name="resetsettings", description="Reset all server settings to default")
    async def resetsettings(self, ctx: commands.Context):
        embed = discord.Embed(
            title="⚠️ Reset Settings",
            description="This will reset all server settings to default. Are you sure?",
            color=discord.Color.red()
        )
        confirm_msg = await ctx.send(embed=embed)
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and reaction.message.id == confirm_msg.id
            
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            if str(reaction.emoji) == "✅":
                self.guild_configs[ctx.guild.id] = copy.deepcopy(self.DEFAULT_CONFIG)
                with open("configs.json", "w") as f:
                    json.dump(self.guild_configs, f, indent=4)
                await ctx.send("✅ Settings have been reset to default.")
            else:
                await ctx.send("❌ Reset cancelled.")
        except asyncio.TimeoutError:
            await ctx.send("❌ Reset cancelled - timeout.")

    # ─── Apply Configuration on Join ─────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        role = await self.get_role_from_config(member.guild, "autorole")
        if role:
            try: await member.add_roles(role, reason="Auto-role")
            except: pass
                
        channel = await self.get_channel_from_config(member.guild, "welcome_channel")
        if channel:
            config = self.get_config(member.guild.id)
            message = config.get("welcome_message", self.DEFAULT_CONFIG["welcome_message"])
            formatted_message = message.format(
                user=member.mention,
                server=member.guild.name,
                member_count=member.guild.member_count
            )
            try: await channel.send(formatted_message)
            except: pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return
        channel = await self.get_channel_from_config(member.guild, "leave_channel")
        if channel:
            config = self.get_config(member.guild.id)
            message = config.get("leave_message", self.DEFAULT_CONFIG["leave_message"])
            formatted_message = message.format(
                user=member.name,
                server=member.guild.name,
                member_count=member.guild.member_count
            )
            try: await channel.send(formatted_message)
            except: pass

    # ─── Error Handling ──────────────────────────────────────────────

    @config_group.error
    async def on_config_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(self.get_string("no_permission"), ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(self.get_string("bot_no_permission"), ephemeral=True)
        elif isinstance(error, commands.NotOwner):
            await ctx.send("❌ This command is owner-only.", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(self.get_string("invalid_argument", arg=error.param.name), ephemeral=True)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(self.get_string("invalid_argument", arg=str(error)), ephemeral=True)
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(self.get_string("command_on_cooldown", time=round(error.retry_after, 1)), ephemeral=True)
        else:
            await ctx.send(self.get_string("error", error=str(error)), ephemeral=True)
            log.error(f"Unhandled error in config cog: {error}")

# ─── Setup Function ──────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))
