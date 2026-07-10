# config.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

log = logging.getLogger(__name__)

class Config(commands.Cog):
    """Server configuration management with per-server settings."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # ─── Configuration Cache ──────────────────────────────────────
        # Structure: { guild_id: { "prefix": str, "language": str, "timezone": str, ... } }
        self.guild_configs: Dict[int, Dict[str, Any]] = {}
        
        # ─── Default Configuration ────────────────────────────────────
        self.DEFAULT_CONFIG = {
            "prefix": "!",
            "language": "en",
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
        
        # ─── Language Strings ─────────────────────────────────────────
        self.languages = {
            "en": {
                "name": "English",
                "emoji": "🇬🇧",
                "strings": {
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
            },
            "es": {
                "name": "Spanish",
                "emoji": "🇪🇸",
                "strings": {
                    "welcome": "¡Bienvenido {user} a {server}! 🎉",
                    "leave": "{user} salió del servidor. 😢",
                    "levelup": "¡{user} acaba de subir al nivel {level}! 🎉",
                    "mute_reason": "Has sido silenciado por {duration} minutos. Razón: {reason}",
                    "unmute_reason": "Has sido desilenciado.",
                    "kick_reason": "Has sido expulsado. Razón: {reason}",
                    "ban_reason": "Has sido baneado. Razón: {reason}",
                    "warn_reason": "Has recibido una advertencia. Razón: {reason}",
                    "no_permission": "No tienes permiso para usar este comando.",
                    "bot_no_permission": "No tengo permiso para hacer eso.",
                    "user_not_found": "Usuario no encontrado.",
                    "invalid_argument": "Argumento inválido: {arg}",
                    "command_on_cooldown": "Comando en enfriamiento. Intenta de nuevo en {time} segundos.",
                    "success": "✅ ¡Éxito!",
                    "error": "❌ Error: {error}"
                }
            },
            "fr": {
                "name": "French",
                "emoji": "🇫🇷",
                "strings": {
                    "welcome": "Bienvenue {user} sur {server}! 🎉",
                    "leave": "{user} a quitté le serveur. 😢",
                    "levelup": "{user} vient de passer au niveau {level}! 🎉",
                    "mute_reason": "Vous avez été rendu muet pour {duration} minutes. Raison: {reason}",
                    "unmute_reason": "Vous avez été démuté.",
                    "kick_reason": "Vous avez été expulsé. Raison: {reason}",
                    "ban_reason": "Vous avez été banni. Raison: {reason}",
                    "warn_reason": "Vous avez reçu un avertissement. Raison: {reason}",
                    "no_permission": "Vous n'avez pas la permission d'utiliser cette commande.",
                    "bot_no_permission": "Je n'ai pas la permission de faire cela.",
                    "user_not_found": "Utilisateur non trouvé.",
                    "invalid_argument": "Argument invalide: {arg}",
                    "command_on_cooldown": "Commande en recharge. Réessayez dans {time} secondes.",
                    "success": "✅ Succès!",
                    "error": "❌ Erreur: {error}"
                }
            },
            "de": {
                "name": "German",
                "emoji": "🇩🇪",
                "strings": {
                    "welcome": "Willkommen {user} auf {server}! 🎉",
                    "leave": "{user} hat den Server verlassen. 😢",
                    "levelup": "{user} hat gerade Level {level} erreicht! 🎉",
                    "mute_reason": "Du wurdest für {duration} Minuten stummgeschaltet. Grund: {reason}",
                    "unmute_reason": "Du wurdest entstummt.",
                    "kick_reason": "Du wurdest gekickt. Grund: {reason}",
                    "ban_reason": "Du wurdest gebannt. Grund: {reason}",
                    "warn_reason": "Du wurdest verwarnt. Grund: {reason}",
                    "no_permission": "Du hast keine Berechtigung für diesen Befehl.",
                    "bot_no_permission": "Ich habe keine Berechtigung dafür.",
                    "user_not_found": "Benutzer nicht gefunden.",
                    "invalid_argument": "Ungültiges Argument: {arg}",
                    "command_on_cooldown": "Befehl abkühlen. Versuche es in {time} Sekunden erneut.",
                    "success": "✅ Erfolg!",
                    "error": "❌ Fehler: {error}"
                }
            }
        }

    # ─── Lifecycle ────────────────────────────────────────────────────

    async def cog_load(self):
        """Load configurations from file or database."""
        try:
            # Try to load from file first (fallback)
            if os.path.exists("configs.json"):
                with open("configs.json", "r") as f:
                    data = json.load(f)
                    for guild_id, config in data.items():
                        self.guild_configs[int(guild_id)] = config
                log.info(f"Loaded configs for {len(self.guild_configs)} servers from file")
            
            # Try to load from database if available
            try:
                from database import guild_configs_db
                cursor = guild_configs_db.find({})
                async for doc in cursor:
                    guild_id = doc.get("guild_id")
                    if guild_id:
                        # Merge with file configs (database takes priority)
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
        """Save configurations on unload."""
        try:
            # Save to file
            with open("configs.json", "w") as f:
                json.dump(self.guild_configs, f, indent=4)
            log.info("Saved configs to file")
        except Exception as e:
            log.error(f"Failed to save configs: {e}")

    # ─── Helper Methods ──────────────────────────────────────────────

    def get_config(self, guild_id: int) -> Dict[str, Any]:
        """Get configuration for a guild, with defaults."""
        config = self.guild_configs.get(guild_id, {})
        # Fill in missing values with defaults
        for key, value in self.DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config

    async def set_config(self, guild_id: int, key: str, value: Any):
        """Set a configuration value for a guild."""
        if guild_id not in self.guild_configs:
            self.guild_configs[guild_id] = self.DEFAULT_CONFIG.copy()
        self.guild_configs[guild_id][key] = value
        
        # Save to database if available
        try:
            from database import guild_configs_db
            await guild_configs_db.update_one(
                {"guild_id": guild_id},
                {"$set": {key: value}},
                upsert=True
            )
        except ImportError:
            pass
        
        # Save to file
        try:
            with open("configs.json", "w") as f:
                json.dump(self.guild_configs, f, indent=4)
        except:
            pass

    def get_string(self, guild_id: int, key: str, **kwargs) -> str:
        """Get a localized string for a guild."""
        config = self.get_config(guild_id)
        lang = config.get("language", "en")
        
        if lang not in self.languages:
            lang = "en"
            
        string = self.languages[lang]["strings"].get(key, self.languages["en"]["strings"].get(key, key))
        
        # Format with kwargs
        try:
            return string.format(**kwargs)
        except:
            return string

    async def get_channel_from_config(self, guild: discord.Guild, config_key: str) -> Optional[discord.TextChannel]:
        """Get a channel from the config."""
        config = self.get_config(guild.id)
        channel_id = config.get(config_key)
        
        if not channel_id:
            return None
            
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def get_role_from_config(self, guild: discord.Guild, config_key: str) -> Optional[discord.Role]:
        """Get a role from the config."""
        config = self.get_config(guild.id)
        role_id = config.get(config_key)
        
        if not role_id:
            return None
            
        role = guild.get_role(role_id)
        return role

    # ─── Configuration Commands ──────────────────────────────────────

    @commands.hybrid_group(name="config", description="Manage server configuration")
    @app_commands.checks.has_permissions(administrator=True)
    async def config_group(self, ctx: commands.Context):
        """Configuration management commands."""
        if ctx.invoked_subcommand is None:
            await self.show_config(ctx)

    @config_group.command(name="show", description="Show current server configuration")
    async def show_config(self, ctx: commands.Context):
        """Display the current server configuration."""
        config = self.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title=f"⚙️ Configuration - {ctx.guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # General Settings
        general = []
        general.append(f"📌 Prefix: `{config.get('prefix', '!')}`")
        general.append(f"🌍 Language: {self.languages.get(config.get('language', 'en'), {}).get('emoji', '🇬🇧')} {self.languages.get(config.get('language', 'en'), {}).get('name', 'English')}")
        general.append(f"🕐 Timezone: `{config.get('timezone', 'UTC')}`")
        embed.add_field(name="📋 General Settings", value="\n".join(general), inline=False)
        
        # Roles
        roles = []
        for key, label in [("mod_role", "👮 Mod Role"), ("admin_role", "👑 Admin Role"), ("mute_role", "🔇 Mute Role")]:
            role = await self.get_role_from_config(ctx.guild, key)
            roles.append(f"{label}: {role.mention if role else '❌ Not Set'}")
        embed.add_field(name="🎭 Roles", value="\n".join(roles), inline=False)
        
        # Channels
        channels = []
        for key, label in [
            ("welcome_channel", "👋 Welcome Channel"),
            ("leave_channel", "👋 Leave Channel"),
            ("suggestion_channel", "💡 Suggestion Channel"),
            ("report_channel", "📢 Report Channel"),
            ("log_channel", "📋 Log Channel"),
            ("leveling_channel", "📈 Leveling Channel")
        ]:
            channel = await self.get_channel_from_config(ctx.guild, key)
            channels.append(f"{label}: {channel.mention if channel else '❌ Not Set'}")
        embed.add_field(name="📢 Channels", value="\n".join(channels), inline=False)
        
        # Features
        features = []
        feature_keys = [
            ("leveling_enabled", "📈 Leveling"),
            ("auto_moderation", "🛡️ Auto-Moderation"),
            ("profanity_filter", "🔞 Profanity Filter"),
            ("spam_protection", "🚫 Spam Protection"),
            ("economy_enabled", "💰 Economy"),
            ("music_enabled", "🎵 Music")
        ]
        for key, label in feature_keys:
            value = config.get(key, True)
            features.append(f"{label}: {'✅' if value else '❌'}")
        embed.add_field(name="⚡ Features", value="\n".join(features), inline=False)
        
        # Limits
        limits = []
        limits.append(f"⚠️ Max Warnings: `{config.get('max_warnings', 5)}`")
        limits.append(f"🔇 Mute Duration: `{config.get('mute_duration', 10)} minutes`")
        limits.append(f"⏳ Temp Ban Duration: `{config.get('temp_ban_duration', 7)} days`")
        limits.append(f"🎫 Ticket Limit: `{config.get('ticket_limit_per_user', 3)}`")
        embed.add_field(name="📊 Limits", value="\n".join(limits), inline=False)
        
        # Economy
        economy = []
        economy.append(f"💰 Daily Reward: `{config.get('daily_reward', 100)}`")
        economy.append(f"⏱️ Cooldown: `{config.get('economy_cooldown', 60)} seconds`")
        embed.add_field(name="💎 Economy", value="\n".join(economy), inline=False)
        
        embed.set_footer(text=f"Made by yaduvanshi1816_ • Server ID: {ctx.guild.id}")
        
        await ctx.send(embed=embed)

    @config_group.command(name="setprefix", description="Set the bot prefix for this server")
    async def setprefix(self, ctx: commands.Context, prefix: str):
        """Change the bot prefix."""
        if len(prefix) > 10:
            await ctx.send("❌ Prefix cannot be longer than 10 characters.", ephemeral=True)
            return
            
        await self.set_config(ctx.guild.id, "prefix", prefix)
        await ctx.send(f"✅ Prefix updated to: `{prefix}`", ephemeral=True)

    @config_group.command(name="setlanguage", description="Set the server language")
    @app_commands.choices(language=[
        app_commands.Choice(name="English 🇬🇧", value="en"),
        app_commands.Choice(name="Spanish 🇪🇸", value="es"),
        app_commands.Choice(name="French 🇫🇷", value="fr"),
        app_commands.Choice(name="German 🇩🇪", value="de")
    ])
    async def setlanguage(self, ctx: commands.Context, language: app_commands.Choice[str]):
        """Change the server language."""
        await self.set_config(ctx.guild.id, "language", language.value)
        await ctx.send(
            f"✅ Language updated to: {self.languages[language.value]['emoji']} {self.languages[language.value]['name']}",
            ephemeral=True
        )

    @config_group.command(name="setmodrole", description="Set the moderator role")
    async def setmodrole(self, ctx: commands.Context, role: discord.Role):
        """Set which role has moderator permissions."""
        await self.set_config(ctx.guild.id, "mod_role", role.id)
        await ctx.send(f"✅ Moderator role set to: {role.mention}", ephemeral=True)

    @config_group.command(name="setadminrole", description="Set the admin role")
    async def setadminrole(self, ctx: commands.Context, role: discord.Role):
        """Set which role has admin permissions."""
        await self.set_config(ctx.guild.id, "admin_role", role.id)
        await ctx.send(f"✅ Admin role set to: {role.mention}", ephemeral=True)

    @config_group.command(name="setmuterole", description="Set the mute role")
    async def setmuterole(self, ctx: commands.Context, role: discord.Role):
        """Set which role is used for muting."""
        await self.set_config(ctx.guild.id, "mute_role", role.id)
        await ctx.send(f"✅ Mute role set to: {role.mention}", ephemeral=True)

    @config_group.command(name="setwelcome", description="Set the welcome channel and message")
    async def setwelcome(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        *, 
        message: Optional[str] = None
    ):
        """Set the welcome channel and message."""
        await self.set_config(ctx.guild.id, "welcome_channel", channel.id)
        if message:
            await self.set_config(ctx.guild.id, "welcome_message", message)
        await ctx.send(f"✅ Welcome channel set to: {channel.mention}", ephemeral=True)

    @config_group.command(name="setleave", description="Set the leave channel and message")
    async def setleave(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel,
        *,
        message: Optional[str] = None
    ):
        """Set the leave channel and message."""
        await self.set_config(ctx.guild.id, "leave_channel", channel.id)
        if message:
            await self.set_config(ctx.guild.id, "leave_message", message)
        await ctx.send(f"✅ Leave channel set to: {channel.mention}", ephemeral=True)

    @config_group.command(name="setautorole", description="Set the auto-role for new members")
    async def setautorole(self, ctx: commands.Context, role: discord.Role):
        """Set which role is automatically given to new members."""
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
    async def setfeature(
        self,
        ctx: commands.Context,
        feature: app_commands.Choice[str],
        state: app_commands.Choice[str]
    ):
        """Enable or disable a feature."""
        value = state.value == "enable"
        await self.set_config(ctx.guild.id, feature.value, value)
        
        status = "enabled" if value else "disabled"
        feature_name = feature.name
        await ctx.send(f"✅ {feature_name} has been **{status}**", ephemeral=True)

    @config_group.command(name="setlimit", description="Set warning/ticket limits")
    @app_commands.choices(limit_type=[
        app_commands.Choice(name="Max Warnings", value="max_warnings"),
        app_commands.Choice(name="Mute Duration (minutes)", value="mute_duration"),
        app_commands.Choice(name="Temp Ban Duration (days)", value="temp_ban_duration"),
        app_commands.Choice(name="Ticket Limit per User", value="ticket_limit_per_user")
    ])
    async def setlimit(
        self,
        ctx: commands.Context,
        limit_type: app_commands.Choice[str],
        value: int
    ):
        """Set various limits."""
        if value < 1:
            await ctx.send("❌ Value must be at least 1.", ephemeral=True)
            return
            
        if limit_type.value == "max_warnings" and value > 20:
            await ctx.send("❌ Max warnings cannot exceed 20.", ephemeral=True)
            return
            
        if limit_type.value == "mute_duration" and value > 1440:  # 24 hours
            await ctx.send("❌ Mute duration cannot exceed 1440 minutes (24 hours).", ephemeral=True)
            return
            
        if limit_type.value == "temp_ban_duration" and value > 30:
            await ctx.send("❌ Temp ban duration cannot exceed 30 days.", ephemeral=True)
            return
            
        await self.set_config(ctx.guild.id, limit_type.value, value)
        await ctx.send(f"✅ {limit_type.name} set to: `{value}`", ephemeral=True)

    @config_group.command(name="resetsettings", description="Reset all server settings to default")
    async def resetsettings(self, ctx: commands.Context):
        """Reset all settings to default."""
        # Confirm
        embed = discord.Embed(
            title="⚠️ Reset Settings",
            description="This will reset all server settings to default. Are you sure?",
            color=discord.Color.red()
        )
        confirm_msg = await ctx.send(embed=embed)
        
        # Add reactions for confirmation
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")
        
        def check(reaction, user):
            return user == ctx.author and reaction.message.id == confirm_msg.id
            
        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            if str(reaction.emoji) == "✅":
                self.guild_configs[ctx.guild.id] = self.DEFAULT_CONFIG.copy()
                # Save to file
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
        """Apply welcome message and auto-role on join."""
        if member.bot:
            return
            
        # Auto-role
        role = await self.get_role_from_config(member.guild, "autorole")
        if role:
            try:
                await member.add_roles(role, reason="Auto-role")
            except:
                pass
                
        # Welcome message
        channel = await self.get_channel_from_config(member.guild, "welcome_channel")
        if channel:
            config = self.get_config(member.guild.id)
            message = config.get("welcome_message", self.DEFAULT_CONFIG["welcome_message"])
            formatted_message = message.format(
                user=member.mention,
                server=member.guild.name,
                member_count=member.guild.member_count
            )
            try:
                await channel.send(formatted_message)
            except:
                pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Send leave message when a member leaves."""
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
            try:
                await channel.send(formatted_message)
            except:
                pass

    # ─── Error Handling ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Handle command errors gracefully."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(self.get_string(ctx.guild.id, "no_permission"), ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(self.get_string(ctx.guild.id, "bot_no_permission"), ephemeral=True)
        elif isinstance(error, commands.NotOwner):
            await ctx.send("❌ This command is owner-only.", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(
                self.get_string(ctx.guild.id, "invalid_argument", arg=error.param),
                ephemeral=True
            )
        elif isinstance(error, commands.BadArgument):
            await ctx.send(
                self.get_string(ctx.guild.id, "invalid_argument", arg=str(error)),
                ephemeral=True
            )
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                self.get_string(
                    ctx.guild.id,
                    "command_on_cooldown",
                    time=round(error.retry_after, 1)
                ),
                ephemeral=True
            )
        else:
            await ctx.send(
                self.get_string(ctx.guild.id, "error", error=str(error)),
                ephemeral=True
            )
            log.error(f"Unhandled error in config cog: {error}")

# ─── Setup Function ──────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(Config(bot))