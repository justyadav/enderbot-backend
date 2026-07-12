import os
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
from fastapi.templating import Jinja2Templates
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

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil not installed - some stats will be unavailable")

# ─── Environment & Logging Setup ─────────────────────────────────────
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("EnderBot")

# ─── Configuration ──────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN")
MONGO_URI = os.getenv("MONGO_URI", "")
DB_NAME = os.getenv("DB_NAME", "discord_bot_db")
VERSION = os.getenv("BOT_VERSION", "2.0.0")
SUPPORT_SERVER_URL = os.getenv("SUPPORT_SERVER_URL", "https://discord.gg/PGwbyWX3DS")
USE_MONGODB = os.getenv("USE_MONGODB", "false").lower() == "true"
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# OAuth2 Config
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI", "https://enderbot-dashboard-1xtu.onrender.com/api/auth/callback")
FRONTEND_URL = "https://enderbot.dpdns.org"

print(f"✅ Configuration loaded:")
print(f"  - Token: {'✅' if TOKEN else '❌ Missing!'}")
print(f"  - OAuth2 Client ID: {'✅' if CLIENT_ID else '❌ Missing!'}")
print(f"  - MongoDB: {'✅ Enabled' if USE_MONGODB else '❌ Disabled'}")
print(f"  - Port: {os.getenv('PORT', '10000')}")

if not TOKEN:
    print("❌ CRITICAL: DISCORD_TOKEN is missing from environment variables!")
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
intents.voice_states = True
intents.bans = True
intents.integrations = True
intents.webhooks = True
intents.invites = True

bot = commands.Bot(
    command_prefix=commands.when_mentioned_or("/"),
    intents=intents,
    help_command=None
)

bot.start_time = datetime.now(timezone.utc)
bot.version = VERSION
bot.support_server = SUPPORT_SERVER_URL

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
        status_text = f"{total_servers} servers • {total_members} users • /help"
        await bot.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=status_text),
            status=discord.Status.online
        )
        log.info(f"🔄 Updated presence: {status_text}")
    except Exception as e:
        log.error(f"Failed to update status: {e}")

@update_status.before_loop
async def before_update_status():
    await bot.wait_until_ready()

@bot.event
async def on_ready():
    global bot_ready
    with bot_ready_lock:
        bot_ready = True
    log.info(f"🟢 Bot online as: {bot.user}")
    update_status.start()
    await load_extensions()

async def load_extensions():
    extensions = ['cogs.general', 'cogs.moderation', 'cogs.logging', 'cogs.autorole', 'cogs.config', 'cogs.help']
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            log.info(f"  ✅ Loaded: {ext}")
        except Exception as e:
            log.error(f"  ❌ Failed to load {ext}: {e}")
            
    try:
        synced = await bot.tree.sync()
        log.info(f"🔄 Synced {len(synced)} slash commands")
    except Exception as e:
        log.error(f"❌ Failed to sync slash commands: {e}")

# ─── FastAPI Lifespan Manager ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, db, mongo_connected
    try:
        if USE_MONGODB and MONGO_URI:
            try:
                log.info("📡 Connecting to MongoDB...")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://enderbot.dpdns.org",
        "https://enderbot-dashboard-1xtu.onrender.com",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Helper Logic ──────────────────────────────────────────────────
def format_uptime(delta) -> str:
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{delta.days}d {hours}h {minutes}m" if delta.days > 0 else f"{hours}h {minutes}m {seconds}s"

# ─── API Routes (OAuth2 & Guild Management) ─────────────────────────

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

@app.get("/api/status")
async def api_status():
    if not bot.is_ready():
        return JSONResponse({"status": "initializing"}, status_code=503)
    return {
        "status": "online",
        "bot": {"name": bot.user.name, "id": bot.user.id, "avatar": bot.user.display_avatar.url}
    }

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
        if (perms & 0x8 == 0x8) or (perms & 0x20 == 0x20): # Admin or Manage Guild
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
    uvicorn.run("main:app", host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", 10000)))
