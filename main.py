# main.py
import os
import sys
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional, Any
import threading
import traceback
import aiohttp

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
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import uvicorn

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
USE_MONGODB = os.getenv("USE_MONGODB", "false").lower() == "true")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# ─── OAuth Configuration ───
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "")

print(f"✅ Configuration loaded:")
print(f"  - Token: {'✅' if TOKEN else '❌ Missing!'}")
print(f"  - MongoDB: {'✅ Enabled' if USE_MONGODB else '❌ Disabled'}")

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

# ─── Bot Start Time ─────────────────────────────────────────────────
bot.start_time = datetime.now(timezone.utc)
bot.version = VERSION
bot.support_server = SUPPORT_SERVER_URL

# ─── In-Memory Database Fallback ──────────────────────────────────
class InMemoryDB:
    def __init__(self):
        self.data = {}
        self.collections = {}
        self._ping_ok = True
    
    def __getattr__(self, name):
        if name not in self.collections:
            self.collections[name] = InMemoryCollection()
        return self.collections[name]
    
    async def command(self, cmd):
        return {"ok": 1}
    
    async def list_collection_names(self):
        return list(self.collections.keys())
    
    def close(self):
        pass

class InMemoryCollection:
    def __init__(self):
        self.data = []
        self.index = 0
    
    async def find_one(self, filter_dict):
        for item in self.data:
            matches = True
            for key, value in filter_dict.items():
                if item.get(key) != value:
                    matches = False
                    break
            if matches:
                return item
        return None
    
    async def find(self, filter_dict=None):
        if not filter_dict:
            return self.data
        results = []
        for item in self.data:
            matches = True
            for key, value in filter_dict.items():
                if item.get(key) != value:
                    matches = False
                    break
            if matches:
                results.append(item)
        return results
    
    async def insert_one(self, document):
        self.index += 1
        document['_id'] = self.index
        self.data.append(document)
        return {'inserted_id': self.index}
    
    async def update_one(self, filter_dict, update_dict, upsert=False):
        doc = await self.find_one(filter_dict)
        if doc:
            for key, value in update_dict.get('$set', {}).items():
                doc[key] = value
            return {'matched_count': 1, 'modified_count': 1}
        elif upsert:
            new_doc = filter_dict.copy()
            for key, value in update_dict.get('$set', {}).items():
                new_doc[key] = value
            await self.insert_one(new_doc)
            return {'matched_count': 0, 'modified_count': 0, 'upserted_id': self.index}
        return {'matched_count': 0, 'modified_count': 0}
    
    async def delete_one(self, filter_dict):
        for i, item in enumerate(self.data):
            matches = True
            for key, value in filter_dict.items():
                if item.get(key) != value:
                    matches = False
                    break
            if matches:
                del self.data[i]
                return {'deleted_count': 1}
        return {'deleted_count': 0}
    
    async def count_documents(self, filter_dict=None):
        if not filter_dict:
            return len(self.data)
        count = 0
        for item in self.data:
            matches = True
            for key, value in filter_dict.items():
                if item.get(key) != value:
                    matches = False
                    break
            if matches:
                count += 1
        return count

# ─── Dynamic Status Loop ────────────────────────────────────────────
@tasks.loop(minutes=5)
async def update_status():
    if not bot.is_ready():
        return
    try:
        total_servers = len(bot.guilds)
        total_members = sum(guild.member_count or 0 for guild in bot.guilds)
        total_commands = len(bot.tree.get_commands())
        status_text = f"{total_servers} servers • {total_members} users • /help"
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=status_text
            ),
            status=discord.Status.online
        )
        log.info(f"🔄 Updated presence: {status_text}")
    except Exception as e:
        log.error(f"Failed to update status: {e}")

@update_status.before_loop
async def before_update_status():
    await bot.wait_until_ready()
    log.info("🔄 Status update loop started")

# ─── Discord Bot Events ─────────────────────────────────────────────

@bot.event
async def on_ready():
    global bot_ready
    with bot_ready_lock:
        bot_ready = True
    
    log.info(f"🟢 Bot is online as: {bot.user.name}#{bot.user.discriminator}")
    log.info(f"📊 Connected to {len(bot.guilds)} guilds")
    log.info(f"👥 Serving {sum(guild.member_count or 0 for guild in bot.guilds)} users")
    log.info(f"🔗 Invite URL: https://discord.com/oauth2/authorize?client_id={bot.user.id}&permissions=8&scope=bot%20applications.commands")
    log.info(f"📦 Database: {'MongoDB' if mongo_connected else 'In-Memory (Fallback)'}")
    
    await load_extensions()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(f"❌ You need `{', '.join(error.missing_permissions)}` permission to use this command.")
        return
    
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send(f"❌ I need `{', '.join(error.missing_permissions)}` permission to do that.")
        return
    
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Missing required argument: `{error.param}`")
        return
    
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"❌ Invalid argument: {error}")
        return
    
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Command on cooldown. Try again in {error.retry_after:.1f}s")
        return
    
    log.error(f"Unhandled command error: {error}")
    await ctx.send("⚠️ An unexpected error occurred. Please try again later.")

@bot.event
async def on_guild_join(guild):
    log.info(f"➕ Joined guild: {guild.name} ({guild.id}) with {guild.member_count} members")

@bot.event
async def on_guild_remove(guild):
    log.info(f"➖ Left guild: {guild.name} ({guild.id})")

# ─── Load Extensions ─────────────────────────────────────────────────

async def load_extensions():
    extensions = [
        'cogs.general',
        'cogs.moderation',
        'cogs.logging',
        'cogs.autorole',
        'cogs.config',
        'cogs.help'
    ]
    
    log.info("📦 Loading extensions...")
    for ext in extensions:
        try:
            await bot.load_extension(ext)
            log.info(f"  ✅ Loaded: {ext}")
        except Exception as e:
            log.error(f"  ❌ Failed to load {ext}: {e}")
            traceback.print_exc()
    
    try:
        synced = await bot.tree.sync()
        log.info(f"🔄 Synced {len(synced)} slash commands")
    except Exception as e:
        log.error(f"❌ Failed to sync slash commands: {e}")
        traceback.print_exc()

# ─── FastAPI Lifespan Manager ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_client, db, mongo_connected
    
    log.info("🚀 Starting EnderBot v2...")
    
    try:
        # Connect to MongoDB (or use fallback)
        if USE_MONGODB and MONGO_URI:
            try:
                log.info("📡 Connecting to MongoDB...")
                from motor.motor_asyncio import AsyncIOMotorClient
                db_client = AsyncIOMotorClient(
                    MONGO_URI,
                    serverSelectionTimeoutMS=5000,
                    connectTimeoutMS=5000,
                    socketTimeoutMS=5000
                )
                db = db_client[DB_NAME]
                await db.command("ping")
                mongo_connected = True
                log.info("✅ MongoDB connection established")
            except Exception as e:
                log.error(f"❌ MongoDB connection failed: {e}")
                log.warning("⚠️ Falling back to in-memory database")
                mongo_connected = False
                db = InMemoryDB()
        else:
            log.warning("⚠️ MongoDB disabled or not configured. Using in-memory database.")
            mongo_connected = False
            db = InMemoryDB()
        
        bot.db = db
        bot.mongo_connected = mongo_connected
        
        # Start the bot
        log.info("🤖 Starting Discord bot...")
        bot_task = asyncio.create_task(bot.start(TOKEN))
        
        # Wait for bot to be ready
        log.info("⏳ Waiting for bot to connect...")
        timeout = 60
        start = datetime.now(timezone.utc)
        
        while not bot_ready and (datetime.now(timezone.utc) - start).seconds < timeout:
            await asyncio.sleep(0.5)
        
        if not bot_ready:
            log.error("❌ Bot connection timed out after 60 seconds")
            raise RuntimeError("Bot connection timed out")
        
        log.info("✅ Bot startup complete")
            
    except Exception as e:
        log.error(f"❌ Startup error: {e}")
        traceback.print_exc()
        raise
    
    yield
    
    log.info("🛑 Shutting down EnderBot...")
    try:
        if update_status.is_running():
            update_status.cancel()
            log.info("  ✅ Status loop stopped")
        if bot.is_ready():
            await bot.close()
            log.info("  ✅ Bot connection closed")
        if db_client and mongo_connected:
            db_client.close()
            log.info("  ✅ Database connection closed")
    except Exception as e:
        log.error(f"❌ Shutdown error: {e}")
        traceback.print_exc()
    
    log.info("✅ Shutdown complete")

# ─── FastAPI Application ────────────────────────────────────────────
app = FastAPI(
    title="EnderBot API",
    description="Discord Bot API Endpoints",
    version=VERSION,
    lifespan=lifespan
)

# ─── CORS Middleware ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "https://enderbot.dpdns.org",
        "http://localhost:3000",
        "http://localhost:8080"
    ] if FRONTEND_URL else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── API Routes ─────────────────────────────────────────────────────

@app.get("/api/status")
async def api_status():
    """Get bot status and statistics"""
    if not bot.is_ready():
        return JSONResponse({
            "status": "initializing",
            "message": "Bot is starting up..."
        }, status_code=503)
    
    total_commands = len(bot.tree.get_commands())
    total_guilds = len(bot.guilds)
    total_users = sum(guild.member_count or 0 for guild in bot.guilds)
    uptime = datetime.now(timezone.utc) - bot.start_time
    
    return {
        "status": "online",
        "database": "connected" if mongo_connected else "fallback",
        "bot": {
            "name": bot.user.name,
            "id": bot.user.id,
            "discriminator": bot.user.discriminator,
            "avatar": bot.user.display_avatar.url
        },
        "stats": {
            "guilds": total_guilds,
            "users": total_users,
            "commands": total_commands,
            "latency_ms": round(bot.latency * 1000, 2),
            "uptime_seconds": int(uptime.total_seconds()),
            "uptime_formatted": format_uptime(uptime),
            "start_time": bot.start_time.isoformat()
        },
        "version": VERSION
    }

@app.get("/api/guilds")
async def api_guilds():
    """Get list of all guilds the bot is in"""
    if not bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot is not ready")
    
    guilds_list = []
    for guild in bot.guilds:
        guilds_list.append({
            "id": guild.id,
            "name": guild.name,
            "icon": guild.icon.url if guild.icon else None,
            "member_count": guild.member_count or 0,
            "owner_id": guild.owner_id,
            "owner_name": str(guild.owner) if guild.owner else None,
            "created_at": guild.created_at.isoformat()
        })
    
    return guilds_list

@app.get("/api/guilds/{guild_id}")
async def api_guild_detail(guild_id: int):
    """Get detailed information about a specific guild"""
    if not bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot is not ready")
    
    guild = bot.get_guild(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    
    config = {}
    if bot.db:
        try:
            if not isinstance(bot.db, InMemoryDB):
                doc = await bot.db["guild_settings"].find_one({"guild_id": guild_id})
            else:
                doc = await bot.db.guild_settings.find_one({"guild_id": guild_id})
            if doc:
                config = doc
        except:
            pass
    
    return {
        "id": guild.id,
        "name": guild.name,
        "icon": guild.icon.url if guild.icon else None,
        "banner": guild.banner.url if guild.banner else None,
        "description": guild.description,
        "member_count": guild.member_count or 0,
        "owner_id": guild.owner_id,
        "owner_name": str(guild.owner) if guild.owner else None,
        "created_at": guild.created_at.isoformat(),
        "joined_at": guild.me.joined_at.isoformat() if guild.me.joined_at else None,
        "premium_tier": guild.premium_tier,
        "premium_subscription_count": guild.premium_subscription_count,
        "verification_level": str(guild.verification_level),
        "features": guild.features,
        "channel_count": len(guild.channels),
        "voice_count": len(guild.voice_channels),
        "role_count": len(guild.roles),
        "emoji_count": len(guild.emojis),
        "config": config
    }

@app.get("/api/bot/info")
async def bot_info():
    """Get basic bot information"""
    if not bot.is_ready():
        raise HTTPException(status_code=503, detail="Bot is not ready")
    
    return {
        "name": bot.user.name,
        "id": bot.user.id,
        "discriminator": bot.user.discriminator,
        "avatar": bot.user.display_avatar.url,
        "version": VERSION,
        "created_at": bot.user.created_at.isoformat(),
        "support_server": SUPPORT_SERVER_URL
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    db_status = "disconnected"
    if mongo_connected:
        db_status = "connected"
    elif bot.db:
        db_status = "fallback"
    
    return {
        "status": "healthy",
        "bot": "ready" if bot.is_ready() else "initializing",
        "database": db_status,
        "version": VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

# ─── Helper Functions ──────────────────────────────────────────────

def format_uptime(delta) -> str:
    """Format uptime duration"""
    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    elif hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

# ─── Main Execution ─────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    host = os.getenv("HOST", "0.0.0.0")
    
    print(f"🚀 Starting EnderBot v{VERSION}")
    print(f"🌐 API server: http://{host}:{port}")
    print(f"📡 Press Ctrl+C to stop")
    print("=" * 60)
    
    try:
        uvicorn.run(
            "main:app",
            host=host,
            port=port,
            log_level="info",
            access_log=False,
            reload=False
        )
    except KeyboardInterrupt:
        print("\n🛑 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
