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
            log.error(f"Failed to load Help cog: {e}")

    async def on_ready(self):
        """Executed when the bot successfully logs in."""
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"Connected to {len(self.guilds)} servers serving {len(self.users)} users.")
        
        # ─── Bot Presence / Status Line ──────────────────────────────
        # You can change 'status' to: discord.Status.online, .idle, .dnd, or .invisible
        # You can change 'type' to: ActivityType.listening, .watching, or .playing
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
    main()import os
import sys
import asyncio
import logging
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import threading
import traceback

print("=" * 60)
print("🚀 EnderBot v2.0.0 - Starting Up on Render")
print(f"📁 Current Directory: {os.getcwd()}")
try:
    print(f"📄 Files in directory: {os.listdir('.')}")
except Exception as e:
    print(f"❌ Cannot list files: {e}")
print(f"🐍 Python Version: {sys.version}")
print("=" * 60)

import discord
from discord.ext import commands, tasks
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn
import httpx

# Try to import optional dependencies
try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    print("⚠️ motor not installed - MongoDB functionality will be restricted")

# ─── Environment & Logging Setup ─────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger("EnderBot")

# ─── Configuration ──────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "discord_bot_db")
VERSION = os.getenv("BOT_VERSION", "2.0.0")
SUPPORT_SERVER_URL = os.getenv("SUPPORT_SERVER_URL", "https://discord.gg/PGwbyWX3DS")
USE_MONGODB = os.getenv("USE_MONGODB", "false").lower() == "true"

# OAuth2 Config
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://enderbot-dashboard-1xtu.onrender.com/api/auth/callback")
FRONTEND_URL = "https://enderbot.dpdns.org"

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN is missing!")
    sys.exit(1)

# ─── Global Variables ──────────────────────────────────────────────
db_client: Optional[Any] = None
db: Optional[Any] = None
mongo_connected = False
bot_ready = False
bot_ready_lock = threading.Lock()

# ─── Discord Bot Setup ─────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("/"),
    intents=intents,
    help_command=None
)

bot.start_time = datetime.now(timezone.utc)
bot.version = VERSION

# ─── In-Memory Database Fallback ──────────────────────────────────
class InMemoryDB:
    def __init__(self):
        self.collections = {}
        
    def __getattr__(self, name):
        if name not in self.collections:
            self.collections[name] = InMemoryCollection()
        return self.collections[name]
    
    def __getitem__(self, name):
        return self.__getattr__(name)
        
    async def command(self, cmd):
        return {"ok": 1}

class InMemoryCollection:
    def __init__(self):
        self.data = []
        self.index = 0
        
    async def find_one(self, filter_dict):
        for item in self.data:
            if all(item.get(k) == v for k, v in filter_dict.items()):
                return item
        return None

    async def find(self, filter_dict=None):
        if not filter_dict:
            return self.data
        results = []
        for item in self.data:
            if all(item.get(k) == v for k, v in filter_dict.items()):
                results.append(item)
        return results
        
    async def update_one(self, filter_dict, update_dict, upsert=False):
        doc = await self.find_one(filter_dict)
        set_data = update_dict.get('$set', {})
        if doc:
            for k, v in set_data.items():
                doc[k] = v
            return {'matched_count': 1, 'modified_count': 1}
        elif upsert:
            new_doc = filter_dict.copy()
            for k, v in set_data.items():
                new_doc[k] = v
            self.index += 1
            new_doc['_id'] = self.index
            self.data.append(new_doc)
            return {'matched_count': 0, 'modified_count': 0, 'upserted_id': self.index}
        return {'matched_count': 0, 'modified_count': 0}

# ─── Pydantic Validation Models ──────────────────────────────────────
class GuildSettingsUpdate(BaseModel):
    prefix: Optional[str] = None
    economy_enabled: Optional[bool] = None

# ─── Dynamic Status Loop ────────────────────────────────────────────
@tasks.loop(minutes=5)
async def update_status():
    if not bot.is_ready():
        return
    try:
        total_servers = len(bot.guilds)
        total_members = sum(guild.member_count or 0 for guild in bot.guilds)
        status_text = f"{total_servers} servers • {total_members} users"
        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=status_text)
        )
    except Exception as e:
        log.error(f"Failed to update status: {e}")

@bot.event
async def on_ready():
    global bot_ready
    with bot_ready_lock:
        bot_ready = True
    log.info(f"🟢 Bot online as: {bot.user}")
    update_status.start()
    await load_extensions()

async def load_extensions():
    extensions = ['cogs.general', 'cogs.logging', 'cogs.autorole', 'cogs.config', 'cogs.help']
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            log.info(f"  ✅ Loaded: {ext}")
        except Exception as e:
            log.error(f"  ❌ Failed to load {ext}: {e}")
            
    try:
        await bot.tree.sync()
    except Exception as e:
        log.error(f"❌ Failed to sync slash commands: {e}")

# ─── FastAPI Lifespan Manager ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, db, mongo_connected
    try:
        if USE_MONGODB and MONGO_URI:
            try:
                db_client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
                db = db_client[DB_NAME]
                await db.command("ping")
                mongo_connected = True
                log.info("✅ MongoDB connection established")
            except Exception as e:
                log.error(f"❌ MongoDB failed: {e}. Falling back to In-Memory.")
                db = InMemoryDB()
        else:
            db = InMemoryDB()
            
        bot.db = db
        bot.mongo_connected = mongo_connected
        
        asyncio.create_task(bot.start(TOKEN))
        yield
    finally:
        if update_status.is_running():
            update_status.cancel()
        await bot.close()

app = FastAPI(title="EnderRes Dashboard", version=VERSION, lifespan=lifespan)

# ─── CORS Middleware ───────────────────────────────────────────────
# Solves the preflight origin problem completely by allowing routing requests globally.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routes ─────────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    if not bot.is_ready():
        return JSONResponse({"status": "initializing"}, status_code=503)
    return {
        "status": "online",
        "bot": {"name": bot.user.name, "id": bot.user.id, "avatar": bot.user.display_avatar.url}
    }

@app.get("/api/auth/login")
async def auth_login():
    scope = "identify guilds"
    discord_login_url = (
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={httpx.URL(REDIRECT_URI)}"
        f"&response_type=code"
        f"&scope={scope}"
    )
    return RedirectResponse(discord_login_url)

@app.get("/api/auth/callback")
async def auth_callback(code: str):
    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    async with httpx.AsyncClient() as client:
        token_res = await client.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
        if token_res.status_code != 200:
            raise HTTPException(status_code=400, detail="Token exchange failed.")
        
        access_token = token_res.json().get('access_token')
        return RedirectResponse(f"{FRONTEND_URL}/#token={access_token}")

@app.get("/api/guilds")
async def api_guilds(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized Access")
        
    token = auth_header.split(" ")[1]
    async with httpx.AsyncClient() as client:
        user_guilds_res = await client.get("https://discord.com/api/users/@me/guilds", headers={"Authorization": f"Bearer {token}"})
        if user_guilds_res.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid Session Token")
        user_guilds = user_guilds_res.json()
        
    valid_guilds = []
    for g in user_guilds:
        perms = int(g.get("permissions", 0))
        if (perms & 0x8 == 0x8) or (perms & 0x20 == 0x20):
            bot_guild = bot.get_guild(int(g["id"]))
            valid_guilds.append({
                "id": g["id"],
                "name": g["name"],
                "icon": f"https://cdn.discordapp.com/icons/{g['id']}/{g['icon']}.png" if g['icon'] else None,
                "bot_in_guild": bot_guild is not None,
                "member_count": bot_guild.member_count if bot_guild else 0
            })
    return valid_guilds

@app.get("/api/guilds/{guild_id}")
async def api_guild_detail(guild_id: int, request: Request):
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not visible to bot")
        
    config = {}
    if bot.db:
        doc = await bot.db["guild_settings"].find_one({"guild_id": guild_id})
        if doc:
            config = {"prefix": doc.get("prefix"), "economy_enabled": doc.get("economy_enabled")}
            
    return {"id": guild.id, "name": guild.name, "config": config}

@app.post("/api/guilds/{guild_id}/settings")
async def update_guild_settings(guild_id: int, settings: GuildSettingsUpdate):
    update_data = {}
    if settings.prefix is not None:
        update_data["prefix"] = settings.prefix[:5]
    if settings.economy_enabled is not None:
        update_data["economy_enabled"] = settings.economy_enabled

    if bot.db:
        await bot.db["guild_settings"].update_one({"guild_id": guild_id}, {"$set": update_data}, upsert=True)
        return {"status": "success"}
    raise HTTPException(status_code=500, detail="Database Offline")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
