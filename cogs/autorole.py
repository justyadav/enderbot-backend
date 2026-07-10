# autorole.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Tuple
import json
import os

log = logging.getLogger(__name__)

class AutoRole(commands.Cog):
    """Advanced auto-role system with multiple features and logging."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # ─── Configuration Cache ──────────────────────────────────────
        # Structure: { guild_id: {
        #     "autorole": role_id,
        #     "autorole_bots": role_id,
        #     "autorole_members": role_id,
        #     "autorole_verified": role_id,
        #     "autorole_boosters": role_id,
        #     "autorole_delay": seconds,
        #     "autorole_message": str,
        #     "autorole_log_channel": channel_id,
        #     "autorole_remove_on_leave": bool,
        #     "autorole_roles": [role_id1, role_id2],
        #     "autorole_conditions": {
        #         "account_age_days": int,
        #         "require_verified": bool,
        #         "join_channel": channel_id,
        #         "exclude_bots": bool
        #     }
        # }}
        self.role_configs: Dict[int, Dict] = {}
        
        # ─── Pending Auto-Roles ──────────────────────────────────────
        # Structure: { guild_id: { user_id: join_time } }
        self.pending_roles: Dict[int, Dict[int, datetime]] = {}
        
        # ─── Default Configuration ────────────────────────────────────
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
            "autorole_conditions": {
                "account_age_days": 0,
                "require_verified": False,
                "join_channel": None,
                "exclude_bots": True
            }
        }
        
        # ─── Tasks ────────────────────────────────────────────────────
        self.role_task: Optional[asyncio.Task] = None

    # ─── Lifecycle ────────────────────────────────────────────────────

    async def cog_load(self):
        """Load configurations and start background task."""
        try:
            # Load from file if exists
            if os.path.exists("autorole_configs.json"):
                with open("autorole_configs.json", "r") as f:
                    data = json.load(f)
                    for guild_id, config in data.items():
                        self.role_configs[int(guild_id)] = config
                log.info(f"Loaded auto-role configs for {len(self.role_configs)} servers")
                
            # Try to load from database if available
            try:
                from database import autorole_configs_db
                cursor = autorole_configs_db.find({})
                async for doc in cursor:
                    guild_id = doc.get("guild_id")
                    if guild_id:
                        if guild_id in self.role_configs:
                            self.role_configs[guild_id].update(doc)
                        else:
                            self.role_configs[guild_id] = doc
                log.info(f"Loaded auto-role configs from database")
            except ImportError:
                log.warning("autorole_configs_db not available - using file-based configs")
                
        except Exception as e:
            log.error(f"Failed to load auto-role configs: {e}")
            
        # Start background task for pending roles
        self.role_task = asyncio.create_task(self.process_pending_roles())

    async def cog_unload(self):
        """Save configurations and cleanup tasks."""
        # Cancel background task
        if self.role_task:
            self.role_task.cancel()
            try:
                await self.role_task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                log.error(f"Error during task cancellation: {e}")
            
        try:
            with open("autorole_configs.json", "w") as f:
                json.dump(self.role_configs, f, indent=4)
            log.info("Saved auto-role configs to file")
        except Exception as e:
            log.error(f"Failed to save auto-role configs: {e}")

    # ─── Background Task ─────────────────────────────────────────────

    async def process_pending_roles(self):
        """Process pending auto-roles for new members."""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                current_time = datetime.now(timezone.utc)
                
                # Create a copy of keys to avoid modification during iteration
                guild_ids = list(self.pending_roles.keys())
                
                for guild_id in guild_ids:
                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        del self.pending_roles[guild_id]
                        continue
                        
                    config = self.get_config(guild_id)
                    delay = config.get("autorole_delay", 0)
                    
                    # Get members to process
                    members_to_remove = []
                    for user_id, join_time in list(self.pending_roles[guild_id].items()):
                        # Check if delay has passed
                        if (current_time - join_time).total_seconds() >= delay:
                            member = guild.get_member(user_id)
                            if member:
                                await self.apply_roles(member)
                            members_to_remove.append(user_id)
                            
                    # Remove processed members
                    for user_id in members_to_remove:
                        if user_id in self.pending_roles[guild_id]:
                            del self.pending_roles[guild_id][user_id]
                            
                    # Clean up empty dicts
                    if not self.pending_roles[guild_id]:
                        del self.pending_roles[guild_id]
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in pending roles task: {e}")
                
            await asyncio.sleep(10)  # Check every 10 seconds

    # ─── Helper Methods ──────────────────────────────────────────────

    def get_config(self, guild_id: int) -> Dict:
        """Get configuration for a guild."""
        config = self.role_configs.get(guild_id, {})
        # Fill in missing values with defaults
        for key, value in self.DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config

    async def save_config(self, guild_id: int):
        """Save guild configuration."""
        try:
            # Save to file
            with open("autorole_configs.json", "w") as f:
                json.dump(self.role_configs, f, indent=4)
                
            # Save to database if available
            try:
                from database import autorole_configs_db
                config = self.role_configs.get(guild_id, {})
                if config:
                    await autorole_configs_db.update_one(
                        {"guild_id": guild_id},
                        {"$set": config},
                        upsert=True
                    )
            except ImportError:
                pass
                
        except Exception as e:
            log.error(f"Failed to save auto-role config: {e}")

    async def get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get the configured log channel."""
        config = self.get_config(guild.id)
        channel_id = config.get("autorole_log_channel")
        
        if not channel_id:
            return None
            
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            return channel
        return None

    async def log_action(
        self,
        guild: discord.Guild,
        member: discord.Member,
        action: str,
        roles: List[discord.Role] = None
    ):
        """Log auto-role actions to the configured channel."""
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
        embed.add_field(name="User ID", value=member.id, inline=True)
        
        if roles:
            role_names = ", ".join([role.mention for role in roles])
            embed.add_field(name="Roles", value=role_names, inline=False)
            
        embed.set_footer(text=f"Made by yaduvanshi1816_ • Guild ID: {guild.id}")
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            log.error(f"Failed to send log: {e}")

    async def apply_roles(self, member: discord.Member) -> bool:
        """Apply auto-roles to a member."""
        if not member.guild:
            return False
            
        config = self.get_config(member.guild.id)
        roles_to_add = []
        
        # Check conditions first
        conditions = config.get("autorole_conditions", {})
        
        # Account age check
        account_age_days = conditions.get("account_age_days", 0)
        if account_age_days > 0:
            age = (datetime.now(timezone.utc) - member.created_at).days
            if age < account_age_days:
                return False
                
        # Verified check (using account age as a proxy)
        if conditions.get("require_verified", False):
            age = (datetime.now(timezone.utc) - member.created_at).days
            if age < 7:  # Require account to be at least 7 days old
                return False
                
        # Exclude bots
        if conditions.get("exclude_bots", True) and member.bot:
            # Still apply bot roles if configured
            bot_role_id = config.get("autorole_bots")
            if bot_role_id:
                role = member.guild.get_role(bot_role_id)
                if role:
                    roles_to_add.append(role)
            return await self.add_roles(member, roles_to_add)
            
        # Get auto-roles
        # Single role (legacy)
        single_role_id = config.get("autorole")
        if single_role_id:
            role = member.guild.get_role(single_role_id)
            if role:
                roles_to_add.append(role)
                
        # Multiple roles
        role_ids = config.get("autorole_roles", [])
        for role_id in role_ids:
            role = member.guild.get_role(role_id)
            if role:
                roles_to_add.append(role)
                
        # Member role
        member_role_id = config.get("autorole_members")
        if member_role_id:
            role = member.guild.get_role(member_role_id)
            if role:
                roles_to_add.append(role)
                
        # Verified role
        verified_role_id = config.get("autorole_verified")
        if verified_role_id:
            role = member.guild.get_role(verified_role_id)
            if role:
                roles_to_add.append(role)
                
        # Booster role
        if member.premium_since:
            booster_role_id = config.get("autorole_boosters")
            if booster_role_id:
                role = member.guild.get_role(booster_role_id)
                if role:
                    roles_to_add.append(role)
                    
        # Remove duplicates
        roles_to_add = list(set(roles_to_add))
        
        if not roles_to_add:
            return False
            
        return await self.add_roles(member, roles_to_add)

    async def add_roles(self, member: discord.Member, roles: List[discord.Role]) -> bool:
        """Add roles to a member with proper error handling."""
        if not roles:
            return False
            
        # Filter roles we can manage
        manageable_roles = []
        for role in roles:
            if role < member.guild.me.top_role and role != member.guild.default_role:
                manageable_roles.append(role)
                
        if not manageable_roles:
            log.warning(f"Cannot manage any of the requested roles for {member}")
            return False
            
        try:
            await member.add_roles(*manageable_roles, reason="Auto-role assignment")
            
            # Log the action
            await self.log_action(member.guild, member, "Roles Assigned", manageable_roles)
            
            # Send welcome message if configured
            config = self.get_config(member.guild.id)
            message = config.get("autorole_message")
            if message:
                channel = await self.get_log_channel(member.guild)
                if channel:
                    formatted_message = message.format(
                        user=member.mention,
                        server=member.guild.name,
                        roles=", ".join([role.name for role in manageable_roles])
                    )
                    try:
                        await channel.send(formatted_message)
                    except Exception as e:
                        log.error(f"Failed to send welcome message: {e}")
                        
            return True
            
        except discord.Forbidden:
            log.warning(f"Missing permissions to assign roles in {member.guild.name}")
            return False
        except Exception as e:
            log.error(f"Failed to assign roles to {member}: {e}")
            return False

    async def remove_roles(self, member: discord.Member) -> bool:
        """Remove auto-roles when member leaves."""
        if not member.guild:
            return False
            
        config = self.get_config(member.guild.id)
        
        # Check if we should remove roles on leave
        if not config.get("autorole_remove_on_leave", True):
            return False
            
        roles_to_remove = []
        
        # Get all auto-roles
        role_ids = []
        if config.get("autorole"):
            role_ids.append(config.get("autorole"))
        if config.get("autorole_members"):
            role_ids.append(config.get("autorole_members"))
        if config.get("autorole_verified"):
            role_ids.append(config.get("autorole_verified"))
        if config.get("autorole_boosters"):
            role_ids.append(config.get("autorole_boosters"))
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
            log.error(f"Failed to remove roles from {member}: {e}")
            return False

    # ─── Events ──────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join events."""
        if not member.guild:
            return
            
        config = self.get_config(member.guild.id)
        delay = config.get("autorole_delay", 0)
        
        if delay > 0:
            # Add to pending roles
            if member.guild.id not in self.pending_roles:
                self.pending_roles[member.guild.id] = {}
            self.pending_roles[member.guild.id][member.id] = datetime.now(timezone.utc)
        else:
            # Apply immediately
            await self.apply_roles(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle member leave events."""
        if not member.guild:
            return
            
        # Remove from pending roles
        if member.guild.id in self.pending_roles:
            self.pending_roles[member.guild.id].pop(member.id, None)
            
        # Remove auto-roles
        await self.remove_roles(member)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Handle member updates (e.g., boosting)."""
        if not after.guild:
            return
            
        # Check if member just boosted
        if not before.premium_since and after.premium_since:
            config = self.get_config(after.guild.id)
            booster_role_id = config.get("autorole_boosters")
            if booster_role_id:
                role = after.guild.get_role(booster_role_id)
                if role and role < after.guild.me.top_role:
                    try:
                        await after.add_roles(role, reason="Server booster")
                        await self.log_action(after.guild, after, "Booster Role Added", [role])
                    except Exception as e:
                        log.error(f"Failed to add booster role to {after}: {e}")

    # ─── Configuration Commands ──────────────────────────────────────

    @commands.hybrid_group(name="autorole", description="Manage auto-role settings")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_group(self, ctx: commands.Context):
        """Auto-role configuration commands."""
        if ctx.invoked_subcommand is None:
            await self.show_autorole_config(ctx)

    @autorole_group.command(name="set", description="Set a single role for new members")
    async def autorole_set(self, ctx: commands.Context, role: discord.Role):
        """Set the auto-role for new members."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot manage this role. Please move it below my top role.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Auto-role set to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="add", description="Add a role to the auto-role list")
    async def autorole_add(self, ctx: commands.Context, role: discord.Role):
        """Add a role to the auto-role list (multiple roles)."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot manage this role. Please move it below my top role.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        if "autorole_roles" not in config:
            config["autorole_roles"] = []
            
        if role.id in config["autorole_roles"]:
            await ctx.send(f"❌ {role.mention} is already in the auto-role list.", ephemeral=True)
            return
            
        config["autorole_roles"].append(role.id)
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Added {role.mention} to auto-role list.", ephemeral=True)

    @autorole_group.command(name="remove", description="Remove a role from the auto-role list")
    async def autorole_remove(self, ctx: commands.Context, role: discord.Role):
        """Remove a role from the auto-role list."""
        config = self.get_config(ctx.guild.id)
        
        if role.id in config.get("autorole_roles", []):
            config["autorole_roles"].remove(role.id)
            self.role_configs[ctx.guild.id] = config
            await self.save_config(ctx.guild.id)
            await ctx.send(f"✅ Removed {role.mention} from auto-role list.", ephemeral=True)
        elif config.get("autorole") == role.id:
            config["autorole"] = None
            self.role_configs[ctx.guild.id] = config
            await self.save_config(ctx.guild.id)
            await ctx.send(f"✅ Removed {role.mention} as the primary auto-role.", ephemeral=True)
        else:
            await ctx.send(f"❌ {role.mention} is not in the auto-role list.", ephemeral=True)

    @autorole_group.command(name="setdelay", description="Set delay before applying auto-roles")
    async def autorole_delay(self, ctx: commands.Context, seconds: int):
        """Set how many seconds to wait before applying auto-roles."""
        if seconds < 0 or seconds > 600:
            await ctx.send("❌ Delay must be between 0 and 600 seconds (10 minutes).", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_delay"] = seconds
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Auto-role delay set to: `{seconds} seconds`", ephemeral=True)

    @autorole_group.command(name="setlog", description="Set the log channel for auto-roles")
    async def autorole_log(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the channel for auto-role logs."""
        config = self.get_config(ctx.guild.id)
        config["autorole_log_channel"] = channel.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Auto-role log channel set to: {channel.mention}", ephemeral=True)

    @autorole_group.command(name="setmessage", description="Set the message sent when auto-roles are applied")
    async def autorole_message(self, ctx: commands.Context, *, message: Optional[str] = None):
        """Set the auto-role message. Use {user}, {server}, {roles} as placeholders."""
        config = self.get_config(ctx.guild.id)
        config["autorole_message"] = message
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        
        if message:
            await ctx.send("✅ Auto-role message set.", ephemeral=True)
            
            # Show preview
            preview = message.format(
                user=ctx.author.mention,
                server=ctx.guild.name,
                roles="Role1, Role2"
            )
            embed = discord.Embed(
                title="📨 Message Preview",
                description=preview,
                color=discord.Color.blue()
            )
            embed.set_footer(text="Placeholders: {user}, {server}, {roles}")
            await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.send("✅ Auto-role message disabled.", ephemeral=True)

    @autorole_group.command(name="setmemberrole", description="Set a special role for human members")
    async def autorole_memberrole(self, ctx: commands.Context, role: discord.Role):
        """Set a role that will be given to human members only."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot manage this role. Please move it below my top role.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_members"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Member role set to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="setbotrole", description="Set a special role for bots")
    async def autorole_botrole(self, ctx: commands.Context, role: discord.Role):
        """Set a role that will be given to bots."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot manage this role. Please move it below my top role.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_bots"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Bot role set to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="setboosterrole", description="Set a role for server boosters")
    async def autorole_boosterrole(self, ctx: commands.Context, role: discord.Role):
        """Set a role that will be given to server boosters."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot manage this role. Please move it below my top role.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_boosters"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Booster role set to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="setverifiedrole", description="Set a role for verified members")
    async def autorole_verifiedrole(self, ctx: commands.Context, role: discord.Role):
        """Set a role that will be given to verified members."""
        if role >= ctx.guild.me.top_role:
            await ctx.send("❌ I cannot manage this role. Please move it below my top role.", ephemeral=True)
            return
            
        config = self.get_config(ctx.guild.id)
        config["autorole_verified"] = role.id
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(f"✅ Verified role set to: {role.mention}", ephemeral=True)

    @autorole_group.command(name="setcondition", description="Set conditions for auto-roles")
    @app_commands.choices(condition=[
        app_commands.Choice(name="Account Age (days)", value="account_age_days"),
        app_commands.Choice(name="Require Verified", value="require_verified"),
        app_commands.Choice(name="Exclude Bots", value="exclude_bots")
    ])
    async def autorole_condition(
        self,
        ctx: commands.Context,
        condition: app_commands.Choice[str],
        value: str
    ):
        """Set conditions for auto-role assignment."""
        config = self.get_config(ctx.guild.id)
        if "autorole_conditions" not in config:
            config["autorole_conditions"] = {}
            
        if condition.value == "account_age_days":
            try:
                days = int(value)
                if days < 0 or days > 365:
                    await ctx.send("❌ Days must be between 0 and 365.", ephemeral=True)
                    return
                config["autorole_conditions"]["account_age_days"] = days
                await ctx.send(f"✅ Account age requirement set to: `{days} days`", ephemeral=True)
            except ValueError:
                await ctx.send("❌ Please provide a valid number of days.", ephemeral=True)
                return
                
        elif condition.value == "require_verified":
            config["autorole_conditions"]["require_verified"] = value.lower() in ["true", "yes", "1", "on"]
            await ctx.send(
                f"✅ Verified requirement set to: {'✅' if config['autorole_conditions']['require_verified'] else '❌'}",
                ephemeral=True
            )
            
        elif condition.value == "exclude_bots":
            config["autorole_conditions"]["exclude_bots"] = value.lower() in ["true", "yes", "1", "on"]
            await ctx.send(
                f"✅ Bot exclusion set to: {'✅' if config['autorole_conditions']['exclude_bots'] else '❌'}",
                ephemeral=True
            )
            
        self.role_configs[ctx.guild.id] = config
        await self.save_config(ctx.guild.id)

    @autorole_group.command(name="removeonleave", description="Enable/disable role removal on leave")
    @app_commands.choices(state=[
        app_commands.Choice(name="Enable", value="enable"),
        app_commands.Choice(name="Disable", value="disable")
    ])
    async def autorole_remove_leave(
        self,
        ctx: commands.Context,
        state: app_commands.Choice[str]
    ):
        """Enable or disable removing auto-roles when a member leaves."""
        value = state.value == "enable"
        config = self.get_config(ctx.guild.id)
        config["autorole_remove_on_leave"] = value
        self.role_configs[ctx.guild.id] = config
        
        await self.save_config(ctx.guild.id)
        await ctx.send(
            f"✅ Role removal on leave: **{state.name}d**",
            ephemeral=True
        )

    @autorole_group.command(name="show", description="Show current auto-role configuration")
    async def show_autorole_config(self, ctx: commands.Context):
        """Display the current auto-role configuration."""
        config = self.get_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🎭 Auto-Role Configuration",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        # Primary auto-role
        role_id = config.get("autorole")
        if role_id:
            role = ctx.guild.get_role(role_id)
            role_value = role.mention if role else "❌ Deleted Role"
        else:
            role_value = "❌ Not Set"
        embed.add_field(name="Primary Auto-Role", value=role_value, inline=True)
        
        # Multiple roles
        roles = []
        for role_id in config.get("autorole_roles", []):
            role = ctx.guild.get_role(role_id)
            if role:
                roles.append(role.mention)
            else:
                roles.append("❌ Deleted Role")
        embed.add_field(
            name=f"Additional Roles ({len(roles)})",
            value="\n".join(roles) if roles else "None",
            inline=True
        )
        
        # Special roles
        special_roles = {
            "autorole_members": "Member Role",
            "autorole_bots": "Bot Role",
            "autorole_verified": "Verified Role",
            "autorole_boosters": "Booster Role"
        }
        special_values = []
        for key, label in special_roles.items():
            role_id = config.get(key)
            if role_id:
                role = ctx.guild.get_role(role_id)
                special_values.append(f"{label}: {role.mention if role else '❌ Deleted'}")
            else:
                special_values.append(f"{label}: ❌ Not Set")
        embed.add_field(name="Special Roles", value="\n".join(special_values), inline=False)
        
        # Settings
        settings = []
        settings.append(f"⏱️ Delay: `{config.get('autorole_delay', 0)} seconds`")
        settings.append(f"🚫 Remove on Leave: {'✅' if config.get('autorole_remove_on_leave', True) else '❌'}")
        
        channel_id = config.get("autorole_log_channel")
        if channel_id:
            channel = ctx.guild.get_channel(channel_id)
            settings.append(f"📋 Log Channel: {channel.mention if channel else '❌ Deleted'}")
        else:
            settings.append("📋 Log Channel: ❌ Not Set")
            
        embed.add_field(name="⚙️ Settings", value="\n".join(settings), inline=False)
        
        # Conditions
        conditions = config.get("autorole_conditions", {})
        condition_values = []
        condition_values.append(f"📅 Account Age: `{conditions.get('account_age_days', 0)} days`")
        condition_values.append(f"✅ Require Verified: {'✅' if conditions.get('require_verified', False) else '❌'}")
        condition_values.append(f"🤖 Exclude Bots: {'✅' if conditions.get('exclude_bots', True) else '❌'}")
        embed.add_field(name="📋 Conditions", value="\n".join(condition_values), inline=False)
        
        # Message preview
        message = config.get("autorole_message")
        if message:
            preview = message.format(
                user=ctx.author.mention,
                server=ctx.guild.name,
                roles="Role1, Role2"
            )
            embed.add_field(name="📨 Message", value=preview[:1024], inline=False)
        else:
            embed.add_field(name="📨 Message", value="❌ Not Set", inline=False)
            
        embed.set_footer(text=f"Made by yaduvanshi1816_ • Server ID: {ctx.guild.id}")
        
        await ctx.send(embed=embed, ephemeral=True)

    @autorole_group.command(name="clear", description="Clear all auto-role settings")
    async def autorole_clear(self, ctx: commands.Context):
        """Clear all auto-role configurations."""
        embed = discord.Embed(
            title="⚠️ Clear Auto-Roles",
            description="This will remove all auto-role configurations. Are you sure?",
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
                self.role_configs[ctx.guild.id] = self.DEFAULT_CONFIG.copy()
                await self.save_config(ctx.guild.id)
                
                # Clear pending roles for this guild
                self.pending_roles.pop(ctx.guild.id, None)
                
                await ctx.send("✅ Auto-role configurations have been cleared.")
            else:
                await ctx.send("❌ Operation cancelled.")
        except asyncio.TimeoutError:
            await ctx.send("❌ Operation cancelled - timeout.")

    @autorole_group.command(name="apply", description="Manually apply auto-roles to a member")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole_apply(self, ctx: commands.Context, member: discord.Member):
        """Manually apply auto-roles to a specific member."""
        success = await self.apply_roles(member)
        if success:
            await ctx.send(f"✅ Applied auto-roles to {member.mention}", ephemeral=True)
        else:
            await ctx.send(f"❌ Failed to apply auto-roles to {member.mention}. Check bot permissions.", ephemeral=True)

    # ─── Error Handling ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Handle command errors gracefully."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have permission to manage roles. Please check my permissions.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.", ephemeral=True)
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send("❌ Role not found.", ephemeral=True)
        else:
            await ctx.send(f"⚠️ An error occurred: {error}", ephemeral=True)
            log.error(f"Unhandled error in autorole cog: {error}")

# ─── Setup Function ──────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(AutoRole(bot))
