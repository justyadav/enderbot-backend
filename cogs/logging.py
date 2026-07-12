import discord
from discord.ext import commands
from discord import app_commands
import logging
import copy # Added for deepcopy
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple

log = logging.getLogger(__name__)

class GeneralLogging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_config: Dict[int, Dict] = {}
        self.message_cache: Dict[Tuple[int, int, int], Tuple[str, int, List[str]]] = {}
        self.MAX_CACHE_SIZE = 1000
        
        self.DEFAULT_CONFIG = {
            "mod_log": None,
            "message_log": None,
            "voice_log": None,
            "member_log": None,
            "server_log": None,
            "join_log": None,
            "automod_log": None,
            "enabled_events": [
                "message_delete", "message_edit", "message_bulk_delete",
                "voice_join", "voice_leave", "voice_move",
                "member_join", "member_leave", "member_update",
                "role_create", "role_delete", "role_update",
                "channel_create", "channel_delete", "channel_update",
                "guild_update", "ban_add", "ban_remove"
            ]
        }
        self.event_cooldowns: Dict[Tuple[int, int], datetime] = {}
        self.COOLDOWN_SECONDS = 2

    # ─── Updated Message Listener with Proper Fallback ───
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return
            
        # Fallback to DEFAULT_CONFIG if guild isn't set up yet
        config = self.log_config.get(message.guild.id, self.DEFAULT_CONFIG)
        if "message_delete" not in config.get("enabled_events", []) and "message_edit" not in config.get("enabled_events", []):
            return
            
        cache_key = (message.guild.id, message.channel.id, message.id)
        attachment_urls = [a.url for a in message.attachments]
        self.message_cache[cache_key] = (message.content, message.author.id, attachment_urls)
        
        if len(self.message_cache) > self.MAX_CACHE_SIZE:
            self.message_cache.popitem(last=False)

    # ─── Updated Command Using Deepcopy ───
    @app_commands.command(name="setlog", description="Set a logging channel for specific events")
    @app_commands.checks.has_permissions(administrator=True)
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
            # Fix: Use deepcopy so servers don't share the exact same list instance
            self.log_config[guild_id] = copy.deepcopy(self.DEFAULT_CONFIG)
            
        self.log_config[guild_id][log_type.value] = channel.id
        await self.save_config(guild_id)
        
        # ... rest of your command execution ...
