import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List
import json

log = logging.getLogger(__name__)

class AutoRole(commands.Cog):
    """Advanced auto-role system with database persistence and logging."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # Memory Cache for quick events reading
        self.role_configs: Dict[int, Dict] = {}
        
        # Pending Auto-Roles structure: { guild_id: { user_id: join_time } }
        self.pending_roles: Dict[int, Dict[int, datetime]] = {}
        
        self.DEFAULT_CONFIG = {
            "autorole": None,
            "autorole_bots": None,
            "autorole_members": None,
            "autorole_verified": None,
            "autorole_boosters": None,
            "autorole_delay": 0,
            "autorole_message": None,
            "autorole_log_channel": None,
            "autorole_remove_on_leave": True,
            "autorole_roles": [],
            "account_age_days": 0,
            "require_verified": False,
            "exclude_bots": True
        }
        
        self.role_task: Optional[asyncio.Task] = None

    # ─── Lifecycle ────────────────────────────────────────────────────

    async def cog_load(self):
        """Initialize database tables and cache data into memory."""
        # Create tables if they do not exist
        async with self.bot.db.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS autorole_configs (
                    guild_id INTEGER PRIMARY KEY,
                    config_json TEXT
                )
            """)
        await self.bot.db.commit()

        # Load configurations from Database into cache
        try:
            async with self.bot.db.cursor() as cursor:
                await cursor.execute("SELECT guild_id, config_json FROM autorole_configs")
                rows = await cursor.fetchall()
                for guild_id, config_json in rows:
                    self.role_configs[guild_id] = json.loads(config_json)
            log.info(f"Loaded auto-role configurations for {len(self.role_configs)} servers.")
        except Exception as e:
            log.error(f"Failed to load auto-role configs from database: {e}")
            
        # Start background task for pending delayed roles
        self.role_task = asyncio.create_task(self.process_pending_roles())

    async def cog_unload(self):
        """Cancel background tasks securely."""
        if self.role_task:
            self.role_task.cancel()
            try:
                await self.role_task
            except asyncio.CancelledError:
                pass

    # ─── Background Task ─────────────────────────────────────────────

    async def process_pending_roles(self):
        """Process pending auto-roles for new members when delays expire."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                current_time = datetime.now(timezone.utc)
                guild_ids = list(self.pending_roles.keys())
                
                for guild_id in guild_ids:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        del self.pending_roles[guild_id]
                        continue
                        
                    config = self.get_config(guild_id)
                    delay = config.get("autorole_delay", 0)
                    
                    members_to_remove = []
                    for user_id, join_time in list(self.pending_roles[guild_id].items()):
                        if (current_time - join_time).total_seconds() >= delay:
                            member = guild.get_member(user_id)
                            if member:
                                await self.apply_roles(member)
                            members_to_remove.append(user_id)
                            
                    for user_id in members_to_remove:
                        if user_id in self.pending_roles[guild_id]:
                            del self.pending_roles[guild_id][user_id]
                            
                    if not self.pending_roles[guild_id]:
                        del self.pending_roles[guild_id]
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in pending roles task: {e}")
                
            await asyncio.sleep(10)

    # ─── Data Access Helpers ──────────────────────────────────────────

    def get_config(self, guild_id: int) -> Dict:
        """Fetch config from cache or inject defaults."""
        config = self.role_configs.get(guild_id, {})
        for key, value in self.DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config

    async def save_config(self, guild_id: int):
        """Commit structural adjustments directly to the database."""
        try:
            config = self.role_configs.get(guild_id, {})
            config_json = json.dumps(config)
            
            async with self.bot.db.cursor() as cursor:
                await cursor.execute(
                    "INSERT INTO autorole_configs (guild_id, config_json) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET config_json=EXCLUDED.config_json",
                    (guild_id, config_json)
                )
            await self.bot.db.commit()
        except Exception as e:
            log.error(f"Failed to save auto-role configuration for guild {guild_id}: {e}")

    async def get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        config = self.get_config(guild.id)
        channel_id = config.get("autorole_log_channel")
        if not channel_id:
            return None
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def log_action(self, guild: discord.Guild, member: discord.Member, action: str, roles: List[discord.Role] = None):
        channel = await self.get_log_channel(guild)
        if not channel:
            return
            
        embed = discord.Embed(
            title="🎭 Auto-Role Action",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="User", value=f"{member.mention} ({member.name})", inline=False)
        embed.add_field(name="Action", value=action, inline=True)
        embed.add_field(name="User ID", value=str(member.id), inline=True)
        
        if roles:
            role_names = ", ".join([role.mention for role in roles])
            embed.add_field(name="Roles", value=role_names, inline=False)
            
        try:
            await channel.send(embed=embed)
        except Exception as e:
            log.error(f"Failed to send log message: {e}")

    # ─── Execution Logic ──────────────────────────────────────────────

    async def apply_roles(self, member: discord.Member) -> bool:
        if not member.guild:
            return False
            
        config = self.get_config(member.guild.id)
        roles_to_add = []
        
        # Check Account Age condition
        account_age_days = config.get("account_age_days", 0)
        if account_age_days > 0:
            age = (datetime.now(timezone.utc) - member.created_at).days
            if age < account_age_days:
                return False
                
        # Check Account Verification proxy condition
        if config.get("require_verified", False):
            age = (datetime.now(timezone.utc) - member.created_at).days
            if age < 7:
                return False
                
        # Handle Bots separation
        if member.bot:
            if config.get("exclude_bots", True):
                bot_role_id = config.get("autorole_bots")
                if bot_role_id:
                    role = member.guild.get_role(bot_role_id)
                    if role:
                        roles_to_add.append(role)
                return await self.add_roles(member, roles_to_add)
            
        # Compile standard roles mapping
        single_role_id = config.get("autorole")
        if single_role_id:
            role = member.guild.get_role(single_role_id)
            if role: roles_to_add.append(role)
                
        role_ids = config.get("autorole_roles", [])
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role: roles_to_add.append(role)
                
        member_role_id = config.get("autorole_members")
        if member_role_id and not member.bot:
            role = member.guild.get_role(member_role_id)
            if role: roles_to_add.append(role)
                
        verified_role_id = config.get("autorole_verified")
        if verified_role_id:
            role = member.guild.get_role(verified_role_id)
            if role: roles_to_add.append(role)
                
        if member.premium_since:
            booster_role_id = config.get("autorole_boosters")
            if booster_role_id:
                role = member.guild.get_role(booster_role_id)
                if role: roles_to_add.append(role)
                    
        roles_to_add = list(set(roles_to_add))
        if not roles_to_add:
            return False
            
        return await self.add_roles(member, roles_to_add)

    async def add_roles(self, member: discord.Member, roles: List[discord.Role]) -> bool:
        if not roles:
            return False
            
        manageable_roles = [r for r in roles if r < member.guild.me.top_role and r != member.guild.default_role]
        if not manageable_roles:
            return False
            
        try:
            await member.add_roles(*manageable_roles, reason="Auto-role assignment")
            await self.log_action(member.guild, member, "Roles Assigned", manageable_roles)
            
            config = self.get_config(member.guild.id)
            msg_format = config.get("autorole_message")
            if msg_format:
                channel = await self.get_log_channel(member.guild)
                if channel:
                    formatted = msg_format.format(
                        user=member.mention,
                        server=member.guild.name,
                        roles=", ".join([r.name for r in manageable_roles])
                    )
                    await channel.send(formatted)
            return True
        except discord.Forbidden:
            return False
        except Exception as e:
            log.error(f"Failed to assign roles to {member.id}: {e}")
            return False

    async def remove_roles(self, member: discord.Member) -> bool:
        if not member.guild:
            return False
            
        config = self.get_config(member.guild.id)
        if not config.get("autorole_remove_on_leave", True):
            return False
            
        roles_to_remove = []
        role_ids = []
        
        if config.get("autorole"): role_ids.append(config.get("autorole"))
        if config.get("autorole_members"): role_ids.append(config.get("autorole_members"))
        if config.get("autorole_verified"): role_ids.append(config.get("autorole_verified"))
        if config.get("autorole_boosters"): role_ids.append(config.get("autorole_boosters"))
        role_ids.extend(config.get("autorole_roles", []))
        
        for role_id in role_ids:
            if role_id:
                role = member.guild.get_role(role_id)
                if role and role in member.roles and role < member.guild.me.top_role:
                    roles_to_remove.append(role)
                    
        if not roles_to_remove:
            return False
            
        try:
            await member.remove_roles(*roles_to_remove, reason="Auto-role removal on leave")
            await self.log_action(member.guild, member, "Roles Removed", roles_to_remove)
            return True
        except Exception as e:
            log.error(f"Failed to remove roles from departing user {member.id}: {e}")
            return False

    # ─── Events ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if not member.guild:
            return
            
        config = self.get_config(member.guild.id)
        delay = config.get("autorole_delay", 0)
        
        if delay > 0:
            if member.guild.id not in self.pending_roles:
                self.pending_roles[member.guild.id] = {}
            self.pending_roles[member.guild.id][member.id] = datetime.now(timezone.utc)
        else:
            await self.apply_roles(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if not member.guild:
            return
            
        if member.guild.id in self.pending_roles:
            self.pending_roles[member.guild.id].pop(member.id, None)
            
        await self.remove_roles(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if not after.guild:
            return
            
        if not before.premium_since and after.premium_since:
            config = self.get_config(after.guild.id)
            booster_role_id = config.get("autorole_boosters")
            if booster_role_id:
                role = after.guild.get_role(booster_role_id)
                if role and role < after.guild.me.top_role:
                    try:
                        await after.add_roles(role, reason="Server booster tracking validation")
                        await self.log_action(after.guild, after, "Booster Role Added", [role])
                    except Exception as e:
                        log.error(f"Failed to update booster status parameters for {after.id}: {e}")

    # ─── Configuration Commands ──────────────────────────────────────

    @commands.hybrid_group(name="autorole", description="Manage auto-role settings")
    @commands.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def autorole_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await self.show_autorole_config(ctx)

    @autorole_group.command(name="set", description="Set a single role for new members")
    async def autorole_set(self, ctx: commands.Context, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot manage this role. Please move it below my top role.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Primary auto-role set to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="add", description="Add a role to the auto-role list")
    async def autorole_add(self, ctx: commands.Context, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot manage this role. Please move it below my top role.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        if "autorole_roles" not in config:
            config["autorole_roles"] = []
            
        if role.id in config["autorole_roles"]:
            await ctx.send(f"❌ {role.mention} is already in the additional auto-role array list.", ephemeral=True)
            return
            
        config["autorole_roles"].append(role.id)
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Added {role.mention} to configuration cluster.", ephemeral=True)

    @autorole_group.command(name="remove", description="Remove a role from the auto-role list")
    async def autorole_remove(self, ctx: commands.Context, role: discord.Role):
        config = self.get_config(ctx.guild.id)
        
        if role.id in config.get("autorole_roles", []):
            config["autorole_roles"].remove(role.id)
            self.role_configs[ctx.guild.id] = config
            await self.save_config(ctx.guild.id)
            await ctx.send(f"✅ Removed {role.mention} from data matrix stack.", ephemeral=True)
        elif config.get("autorole") == role.id:
            config["autorole"] = None
            self.role_configs[ctx.guild.id] = config
            await self.save_config(ctx.guild.id)
            await ctx.send(f"✅ Deallocated primary status for role {role.name}.", ephemeral=True)
        else:
            await ctx.send(f"❌ {role.mention} was not tracked in target registry.", ephemeral=True)

    @autorole_group.command(name="setdelay", description="Set delay before applying auto-roles")
    async def autorole_delay(self, ctx: commands.Context, seconds: int):
        if seconds < 0 or seconds > 600:
            await ctx.send("❌ Delay parameters out of index bounds (Must be between 0-600 seconds).", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_delay"] = seconds
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Auto-role execution delay registered: `{seconds}s`", ephemeral=True)

    @autorole_group.command(name="setlog", description="Set the log channel for auto-roles")
    async def autorole_log(self, ctx: commands.Context, channel: discord.TextChannel):
        config = self.get_config(ctx.guild.id)
        config["autorole_log_channel"] = channel.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Log stream redirected to: {channel.mention}", ephemeral=True)

    @autorole_group.command(name="setmessage", description="Set the message sent when auto-roles are applied")
    async def autorole_message(self, ctx: commands.Context, *, message: Optional[str] = None):
        config = self.get_config(ctx.guild.id)
        config["autorole_message"] = message
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        
        if message:
            await ctx.send("✅ System message payload cached.", ephemeral=True)
            preview = message.format(user=ctx.author.mention, server=ctx.guild.name, roles="Role1, Role2")
            embed = discord.Embed(title="📨 Message Preview", description=preview, color=discord.Color.blue())
            await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.send("✅ System message routing disabled.", ephemeral=True)

    @autorole_group.command(name="setmemberrole", description="Set a special role for human members")
    async def autorole_memberrole(self, ctx: commands.Context, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ Hierarchy error: Target role exceeds bot permission limits.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_members"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Human verification role mapped to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="setbotrole", description="Set a special role for bots")
    async def autorole_botrole(self, ctx: commands.Context, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ Hierarchy error: Target role exceeds bot permission limits.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_bots"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Bot instance identifier role mapped to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="setboosterrole", description="Set a role for server boosters")
    async def autorole_boosterrole(self, ctx: commands.Context, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ Hierarchy error: Target role exceeds bot permission limits.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_boosters"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Premium booster role structural tracking linked to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="setverifiedrole", description="Set a role for verified members")
    async def autorole_verifiedrole(self, ctx: commands.Context, role: discord.Role):
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ Hierarchy error: Target role exceeds bot permission limits.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_verified"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Verified verification key role mapped to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="setcondition", description="Set conditions for auto-roles")
    @app_commands.choices(condition=[
        app_commands.Choice(name="Account Age (days)", value="account_age_days"),
        app_commands.Choice(name="Require Verified", value="require_verified"),
        app_commands.Choice(name="Exclude Bots", value="exclude_bots")
    ])
    async def autorole_condition(self, ctx: commands.Context, condition: app_commands.Choice[str], value: str):
        config = self.get_config(ctx.guild.id)
            
        if condition.value == "account_age_days":
            try:
                days = int(value)
                if days < 0 or days > 365:
                    await ctx.send("❌ Parameter limits exceeded (0-365 days restriction).", ephemeral=True)
                    return
                config["account_age_days"] = days
                await ctx.send(f"✅ Temporal filter threshold initialized: `{days} days`", ephemeral=True)
            except ValueError:
                await ctx.send("❌ Numerical formatting validation error.", ephemeral=True)
                return
                
        elif condition.value == "require_verified":
            config["require_verified"] = value.lower() in ["true", "yes", "1", "on"]
            await ctx.send(f"✅ Verification matrix requirement changed.", ephemeral=True)
            
        elif condition.value == "exclude_bots":
            config["exclude_bots"] = value.lower() in ["true", "yes", "1", "on"]
            await ctx.send(f"✅ Anti-bot execution parameters changed.", ephemeral=True)
            
        self.role_configs[ctx.guild.id] = config
        await self.save_config(ctx.guild.id)

    @autorole_group.command(name="removeonleave", description="Enable/disable role removal on leave")
    @app_commands.choices(state=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable")
    ])
    async def autorole_remove_leave(self, ctx: commands.Context, state: app_commands.Choice[str]):
        value = state.value == "enable"
        config = self.get_config(ctx.guild.id)
        config["autorole_remove_on_leave"] = value
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ State updated: Role removal tracking changed to **{state.name}d**", ephemeral=True)

    @autorole_group.command(name="show", description="Show current auto-role configuration")
    async def show_autorole_config(self, ctx: commands.Context):
        config = self.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🎭 Auto-Role Configuration Parameters",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        role_id = config.get("autorole")
        if role_id:
            role = ctx.guild.get_role(role_id)
            role_value = role.mention if role else "❌ Missing Object ID"
        else:
            role_value = "❌ Track Nullified"
        embed.add_field(name="Primary Target Assignment", value=role_value, inline=True)
        
        roles = []
        for r_id in config.get("autorole_roles", []):
            role = ctx.guild.get_role(r_id)
            roles.append(role.mention if role else "❌ Missing Object ID")
        embed.add_field(name=f"Sub-Arrays Mapped ({len(roles)})", value="\n".join(roles) if roles else "None", inline=True)
        
        special_roles = {
            "autorole_members": "Member Class Identification",
            "autorole_bots": "System Automation Engine Tracking",
            "autorole_verified": "Identity Authentication Flag",
            "autorole_boosters": "Premium Node Tier Indicator"
        }
        special_values = []
        for key, label in special_roles.items():
            r_id = config.get(key)
            if r_id:
                role = ctx.guild.get_role(r_id)
                special_values.append(f"{label}: {role.mention if role else '❌ Missing'}")
            else:
                special_values.append(f"{label}: ❌ Empty Pointer")
        embed.add_field(name="Assigned Special Role Clusters", value="\n".join(special_values), inline=False)
        
        settings = [
            f"⏱️ Buffer Execution Time out: `{config.get('autorole_delay', 0)}s`",
            f"🚫 Active Purging on Exit: {'✅' if config.get('autorole_remove_on_leave', True) else '❌'}"
        ]
        
        ch_id = config.get("autorole_log_channel")
        if ch_id:
            channel = ctx.guild.get_channel(ch_id)
            settings.append(f"📋 Output Stream Pipe: {channel.mention if channel else '❌ Disconnected'}")
        else:
            settings.append("📋 Output Stream Pipe: ❌ Unlinked")
            
        embed.add_field(name="⚙️ Operational Flags", value="\n".join(settings), inline=False)
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(AutoRole(bot))
