# main.py
import discord
from discord.ext import commands
import logging
import os
import asyncio
from datetime import datetime, timezone

# ─── Logging Setup ───────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
log = logging.getLogger(__name__)

# ─── Bot Subclass Configuration ──────────────────────────────────────
class AdvancedBot(commands.Bot):
    def __init__(self):
        # Configure your bot's default intents
        intents = discord.Intents.default()
        intents.message_content = True  # Required for prefix commands
        intents.members = True          # Required for tracking user counts accurately
        
        super().__init__(
            command_prefix="!",       # Default fallback prefix for standard text commands
            intents=intents,
            help_command=None          # Disables the built-in default help command
        )
        
        # Meta properties used by the Help cog
        self.version = "2.0.0"
        self.start_time = None

    async def setup_hook(self) -> None:
        """Executed before the bot connects to Discord gateway."""
        self.start_time = datetime.now(timezone.utc)
        
        # Load the help cog (assuming help.py is in the same directory)
        try:
            await self.load_extension("help")
            log.info("Successfully loaded Help cog.")
        except Exception as e:
            log.warn(f"Help cog not loaded: {e}. (Ignore if help.py does not exist yet)")

    async def on_ready(self):
        """Executed when the bot successfully logs in."""
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"Connected to {len(self.guilds)} servers serving {len(self.users)} users.")
        
        # ─── Bot Presence / Status Line ──────────────────────────────
        await self.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.listening, 
                name="/help"
            )
        )
        log.info("Bot status presence has been updated.")

# ─── Command Sync Execution ──────────────────────────────────────────
bot = AdvancedBot()

@bot.command(name="sync", hidden=True)
@commands.is_owner()
async def sync_commands(ctx: commands.Context):
    """Owner-only text command to sync slash commands globally."""
    await ctx.send("🔄 Syncing application commands globally...")
    try:
        # discord.py v2: sync requires bot.tree.sync()
        synced = await bot.tree.sync()
        await ctx.send(f"✅ Successfully synced {len(synced)} slash commands globally.")
        log.info(f"Globally synced {len(synced)} application commands via owner request.")
    except Exception as e:
        await ctx.send(f"❌ Failed to sync commands: {e}")
        log.error(f"Error syncing application commands: {e}")

# ─── Entry Point ─────────────────────────────────────────────────────
def main():
    # Recommended approach: set this in your environment variables, or fallback to your token string
    TOKEN = os.getenv("DISCORD_BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
    
    if TOKEN == "YOUR_BOT_TOKEN_HERE" or not TOKEN:
        log.critical("Missing token! Please update the main() function with your actual bot token.")
        return

    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        log.critical("Invalid token provided. Connection aborted.")
    except Exception as e:
        log.critical(f"Bot failed to run: {e}")

if __name__ == "__main__":
    main()
