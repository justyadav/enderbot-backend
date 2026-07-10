import discord
from discord.ext import commands
from discord import app_commands
import re
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from database import guild_settings  # Import global MongoDB collection

log = logging.getLogger(__name__)

class ModUtils(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.invite_regex = re.compile(r"(discord\.gg|discord\.com/invite)/[a-zA-Z0-9]+")
        
        # Automod configuration state cache
        # Structure: { guild_id: {"anti_invite": bool, "anti_link": bool} }
        self.filter_cache = {}

        # Anti-Spam tracking cache
        # Structure: { (guild_id, user_id): [timestamp1, timestamp2, ...] }
        self.spam_cooldowns = {}
        
        # Hardcoded anti-spam parameters
        self.SPAM_MAX_MESSAGES = 5
        self.SPAM_WINDOW_SECONDS = 3.0
        self.MUTE_DURATION_MINUTES = 10

    async def cog_load(self):
        """Pre-loads filter rules from MongoDB into memory on startup."""
        try:
            cursor = guild_settings.find({})
            async for doc in cursor:
                guild_id = doc.get("guild_id")
                if guild_id:
                    self.filter_cache[int(guild_id)] = {
                        "anti_invite": doc.get("anti_invite", True),
                        "anti_link": doc.get("anti_link", False)
                    }
            log.info(f"Successfully cached automod settings for {len(self.filter_cache)} servers.")
        except Exception as e:
            log.error(f"Failed to build automod cache on boot: {e}")

    # --- EVENT: CONTENT FILTERING & AUTOMATED ANTI-SPAM ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Whitelist server staff from automod triggers
        if message.author.guild_permissions.manage_messages:
            return

        current_time = datetime.now(timezone.utc)
        guild_id = message.guild.id
        user_id = message.author.id
        cache_key = (guild_id, user_id)

        # =====================================================
        # 🛡️ ANTI-SPAM DETECTION ENGINE
        # =====================================================
        if cache_key not in self.spam_cooldowns:
            self.spam_cooldowns[cache_key] = []

        # Append current message timestamp and strip out old expired timestamps
        self.spam_cooldowns[cache_key].append(current_time)
        self.spam_cooldowns[cache_key] = [
            ts for ts in self.spam_cooldowns[cache_key]
            if (current_time - ts).total_seconds() <= self.SPAM_WINDOW_SECONDS
        ]

        # Trigger punishment if user hits the maximum allowed message limit within the timeframe
        if len(self.spam_cooldowns[cache_key]) > self.SPAM_MAX_MESSAGES:
            self.spam_cooldowns[cache_key].clear() # Reset log window to prevent double triggers
            
            try:
                # Apply native Discord timeout duration
                duration = timedelta(minutes=self.MUTE_DURATION_MINUTES)
                await message.author.timeout(duration, reason="Ender Bot v2: Automated Chat Spam Trigger")
                
                # Notify the channel
                await message.channel.send(
                    f"🛑 {message.author.mention} has been muted for {self.MUTE_DURATION_MINUTES} minutes due to excessive spamming.",
                    delete_after=10
                )
                
                # Forward to backend log processing cog if active
                logging_cog = self.bot.get_cog("GeneralLogging")
                if logging_cog:
                    log_channel = await logging_cog.get_log_channel(message.guild, "automod_roles")
                    if log_channel:
                        embed = discord.Embed(
                            title="🚨 Anti-Spam Mitigation Triggered",
                            description=f"**User:** {message.author.mention} ({message.author.name})\n**Action:** Timeout Applied\n**Duration:** {self.MUTE_DURATION_MINUTES} Minutes",
                            color=discord.Color.dark_red(),
                            timestamp=current_time
                        )
                        embed.set_footer(text=f"User ID: {user_id} • Made by yaduvanshi1816_")
                        await log_channel.send(embed=embed)
            except discord.Forbidden:
                pass
            return

        # =====================================================
        # 🔗 TEXT URL CONTENT FILTERS
        # =====================================================
        guild_cache = self.filter_cache.get(guild_id, {"anti_invite": True, "anti_link": False})
        anti_invite_enabled = guild_cache.get("anti_invite", True)
        anti_link_enabled = guild_cache.get("anti_link", False)

        # 1. Anti-Invite Link Filter
        if anti_invite_enabled and self.invite_invite_check(message.content):
            try:
                await message.delete()
                await message.channel.send(f"❌ {message.author.mention}, discord invite links are prohibited here!", delete_after=5)
            except discord.Forbidden:
                pass
            return

        # 2. General Anti-Link Filter
        if anti_link_enabled and self.link_check(message.content):
            try:
                await message.delete()
                await message.channel.send(f"❌ {message.author.mention}, posting external links is restricted in this channel!", delete_after=5)
            except discord.Forbidden:
                pass

    def invite_invite_check(self, text: str) -> bool:
        return bool(self.invite_regex.search(text))

    def link_check(self, text: str) -> bool:
        return "http://" in text.lower() or "https://" in text.lower()

    # --- TOGGLE ANTI-INVITE COMMAND ---
    @app_commands.command(name="filter-invites", description="Toggle automatic deletion of Discord invite links.")
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.choices(status=[
        app_commands.Choice(name="Enable", value="on"),
        app_commands.Choice(name="Disable", value="off")
    ])
    async def filter_invites(self, interaction: discord.Interaction, status: app_commands.Choice[str]):
        is_enabled = (status.value == "on")
        guild_id = interaction.guild_id

        await guild_settings.update_one(
            {"guild_id": guild_id},
            {"$set": {"anti_invite": is_enabled}},
            upsert=True
        )

        if guild_id not in self.filter_cache:
            self.filter_cache[guild_id] = {"anti_invite": True, "anti_link": False}
        self.filter_cache[guild_id]["anti_invite"] = is_enabled

        await interaction.response.send_message(f"🛡️ Anti-Invite filter has been set to: **{status.name}d**.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ModUtils(bot))