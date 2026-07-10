# help.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, Dict, List, Union
from datetime import datetime, timezone
import itertools

log = logging.getLogger(__name__)

class Help(commands.Cog):
    """Advanced help system with categories, pagination, and detailed command info."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        
        # ─── Help Configuration ──────────────────────────────────────
        self.color = discord.Color.blue()
        self.embed_color = 0x5865F2  # Discord blurple
        
        # ─── Command Categories ──────────────────────────────────────
        self.categories = {
            "moderation": {
                "emoji": "🔨",
                "name": "Moderation",
                "description": "Commands for moderating your server",
                "commands": ["kick", "ban", "unban", "mute", "unmute", "warn", "warnings", "clearwarnings", 
                           "clear", "slowmode", "lock", "unlock", "nickname", "voicekick", "voicemove", "nuke"]
            },
            "logging": {
                "emoji": "📋",
                "name": "Logging",
                "description": "Commands for setting up server logging",
                "commands": ["setlog", "removelog", "logsettings"]
            },
            "autorole": {
                "emoji": "🎭",
                "name": "Auto-Role",
                "description": "Commands for automatic role assignment",
                "commands": ["autorole"]
            },
            "general": {
                "emoji": "ℹ️",
                "name": "General",
                "description": "Useful general-purpose commands",
                "commands": ["ping", "stats", "serverinfo", "userinfo", "avatar", "invite", "support", 
                           "uptime", "about", "random", "flip", "roll", "choice", "poll", "fact", "motivate", "ai"]
            },
            "config": {
                "emoji": "⚙️",
                "name": "Configuration",
                "description": "Commands for configuring the bot",
                "commands": ["config"]
            },
            "fun": {
                "emoji": "🎮",
                "name": "Fun",
                "description": "Fun and entertaining commands",
                "commands": ["echo", "embed", "fact", "motivate", "ai", "random", "flip", "roll", "choice", "poll"]
            },
            "utility": {
                "emoji": "🛠️",
                "name": "Utility",
                "description": "Utility commands for various tasks",
                "commands": ["serverinfo", "userinfo", "avatar", "invite", "support", "uptime", "stats"]
            }
        }
        
        # ─── Command Aliases ──────────────────────────────────────────
        self.command_aliases = {
            "purge": "clear",
            "delete": "clear",
            "timeout": "mute",
            "untimeout": "unmute",
            "nick": "nickname",
            "vckick": "voicekick",
            "vcmove": "voicemove",
            "memberinfo": "userinfo",
            "server": "serverinfo",
            "botinfo": "about",
            "coinflip": "flip",
            "dice": "roll",
            "choose": "choice"
        }
        
        # ─── Command Permissions ─────────────────────────────────────
        self.command_permissions = {
            "kick": "Kick Members",
            "ban": "Ban Members",
            "unban": "Ban Members",
            "mute": "Moderate Members",
            "unmute": "Moderate Members",
            "warn": "Kick Members",
            "warnings": "Kick Members",
            "clearwarnings": "Administrator",
            "clear": "Manage Messages",
            "slowmode": "Manage Messages",
            "lock": "Manage Channels",
            "unlock": "Manage Channels",
            "nickname": "Manage Nicknames",
            "voicekick": "Move Members",
            "voicemove": "Move Members",
            "nuke": "Administrator",
            "echo": "Manage Messages",
            "embed": "Manage Messages",
            "config": "Administrator",
            "setlog": "Administrator",
            "removelog": "Administrator",
            "logsettings": "Administrator",
            "autorole": "Administrator",
            "filter-invites": "Manage Guild",
            "filter-links": "Manage Guild",
            "filter-spam": "Manage Guild",
            "settings": "Manage Guild"
        }

    # ─── Helper Methods ──────────────────────────────────────────────

    def get_command_signature(self, command: Union[commands.Command, app_commands.Command]) -> str:
        """Get the command signature with parameters."""
        if isinstance(command, app_commands.Command):
            # Slash command
            params = []
            for param in command.parameters:
                if param.required:
                    params.append(f"<{param.name}>")
                else:
                    params.append(f"[{param.name}]")
            return f"/{command.name} {' '.join(params)}"
        else:
            # Prefix command
            if command.usage:
                return f"{command.qualified_name} {command.usage}"
            params = []
            for param in command.params.values():
                if param.name not in ['self', 'ctx']:
                    if param.default is not param.empty:
                        params.append(f"[{param.name}]")
                    else:
                        params.append(f"<{param.name}>")
            return f"{command.qualified_name} {' '.join(params)}"

    def get_command_description(self, command: Union[commands.Command, app_commands.Command]) -> str:
        """Get the command description."""
        if isinstance(command, app_commands.Command):
            return command.description or "No description available."
        else:
            return command.help or "No description available."

    def get_command_permissions(self, command_name: str) -> str:
        """Get the required permissions for a command."""
        return self.command_permissions.get(command_name, "None")

    def get_command_category(self, command_name: str) -> Optional[str]:
        """Get the category of a command."""
        for category, data in self.categories.items():
            if command_name in data["commands"]:
                return category
        return None

    def get_command_aliases(self, command_name: str) -> List[str]:
        """Get aliases for a command."""
        aliases = []
        for alias, cmd in self.command_aliases.items():
            if cmd == command_name:
                aliases.append(alias)
        return aliases

    async def get_command_info(self, command_name: str) -> Optional[Dict]:
        """Get detailed information about a command."""
        # Check if it's a prefix command
        prefix_cmd = self.bot.get_command(command_name)
        if prefix_cmd:
            return {
                "type": "prefix",
                "object": prefix_cmd,
                "name": prefix_cmd.qualified_name,
                "signature": self.get_command_signature(prefix_cmd),
                "description": self.get_command_description(prefix_cmd),
                "permissions": self.get_command_permissions(command_name),
                "category": self.get_command_category(command_name),
                "aliases": prefix_cmd.aliases,
                "hidden": prefix_cmd.hidden or False
            }
        
        # Check if it's a slash command
        slash_cmd = self.bot.tree.get_command(command_name)
        if slash_cmd:
            return {
                "type": "slash",
                "object": slash_cmd,
                "name": slash_cmd.name,
                "signature": self.get_command_signature(slash_cmd),
                "description": self.get_command_description(slash_cmd),
                "permissions": self.get_command_permissions(command_name),
                "category": self.get_command_category(command_name),
                "aliases": self.get_command_aliases(command_name),
                "hidden": False
            }
        
        return None

    # ─── Help Commands ───────────────────────────────────────────────

    @app_commands.command(name="help", description="Get help with the bot commands")
    @app_commands.describe(
        command="Specific command to get help for",
        category="Category of commands to view"
    )
    async def help(
        self,
        interaction: discord.Interaction,
        command: Optional[str] = None,
        category: Optional[str] = None
    ):
        """Get help for all commands or a specific command."""
        
        # ─── Help for Specific Command ───────────────────────────────
        if command:
            cmd_info = await self.get_command_info(command.lower())
            if cmd_info:
                await self.send_command_help(interaction, cmd_info)
            else:
                await interaction.response.send_message(
                    f"❌ Command `{command}` not found.",
                    ephemeral=True
                )
            return
            
        # ─── Help for Specific Category ──────────────────────────────
        if category:
            category = category.lower()
            if category in self.categories:
                await self.send_category_help(interaction, category)
            else:
                categories_list = ", ".join(self.categories.keys())
                await interaction.response.send_message(
                    f"❌ Category `{category}` not found. Available: {categories_list}",
                    ephemeral=True
                )
            return
            
        # ─── Main Help Menu ──────────────────────────────────────────
        await self.send_main_help(interaction)

    async def send_main_help(self, interaction: discord.Interaction):
        """Send the main help menu with all categories."""
        embed = discord.Embed(
            title=f"🤖 {self.bot.user.name} Help Menu",
            description=f"**Version:** `{getattr(self.bot, 'version', '2.0.0')}`\n"
                       f"**Prefix:** `/` (slash commands only)\n"
                       f"**Commands:** {len(self.bot.tree.get_commands())} slash commands\n\n"
                       f"Use `/help command:<command>` for detailed info\n"
                       f"Use `/help category:<category>` for category help\n\n"
                       f"**📊 Quick Stats:**\n"
                       f"• Servers: `{len(self.bot.guilds)}`\n"
                       f"• Users: `{len(self.bot.users)}`\n"
                       f"• Uptime: `{self.get_bot_uptime()}`",
            color=self.embed_color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Add categories
        for category_id, data in self.categories.items():
            emoji = data["emoji"]
            name = data["name"]
            description = data["description"]
            
            # Count commands in category
            cmd_count = len(data["commands"])
            embed.add_field(
                name=f"{emoji} {name} ({cmd_count})",
                value=f"{description}\n`/help category:{category_id}`",
                inline=True
            )
            
        embed.add_field(
            name="📌 Important Notes",
            value="• Some commands require specific permissions\n"
                  "• Use `/` for all commands\n"
                  "• [Required] <parameters> vs [Optional] parameters",
            inline=False
        )
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    async def send_category_help(self, interaction: discord.Interaction, category: str):
        """Send help for a specific category."""
        category_data = self.categories.get(category)
        if not category_data:
            return
            
        embed = discord.Embed(
            title=f"{category_data['emoji']} {category_data['name']} Commands",
            description=category_data['description'],
            color=self.embed_color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Get all commands in this category
        commands_info = []
        for cmd_name in category_data["commands"]:
            cmd_info = await self.get_command_info(cmd_name)
            if cmd_info and not cmd_info.get("hidden", False):
                commands_info.append(cmd_info)
        
        # Sort commands
        commands_info.sort(key=lambda x: x["name"])
        
        # Add commands to embed
        for cmd in commands_info:
            signature = cmd["signature"]
            description = cmd["description"]
            perms = cmd["permissions"]
            
            # Truncate description if too long
            if len(description) > 80:
                description = description[:77] + "..."
                
            # Show permission if not None
            if perms != "None":
                description += f"\n*Required: {perms}*"
                
            # Show aliases
            if cmd["aliases"]:
                description += f"\n*Aliases: {', '.join(cmd['aliases'])}*"
                
            embed.add_field(
                name=f"`{signature}`",
                value=description,
                inline=False
            )
        
        if not commands_info:
            embed.description += "\n\n⚠️ No visible commands in this category."
            
        embed.set_footer(text=f"Made by yaduvanshi1816_ • Use /help command:<command> for detailed info")
        
        await interaction.response.send_message(embed=embed)

    async def send_command_help(self, interaction: discord.Interaction, cmd_info: Dict):
        """Send detailed help for a specific command."""
        cmd = cmd_info["object"]
        cmd_type = cmd_info["type"]
        cmd_name = cmd_info["name"]
        signature = cmd_info["signature"]
        description = cmd_info["description"]
        permissions = cmd_info["permissions"]
        category = cmd_info["category"]
        aliases = cmd_info["aliases"]
        
        embed = discord.Embed(
            title=f"📖 Command: {cmd_name}",
            color=self.embed_color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Basic info
        embed.add_field(name="📝 Description", value=description, inline=False)
        embed.add_field(name="🔧 Usage", value=f"`{signature}`", inline=False)
        
        # Type and permissions
        cmd_type_display = "Slash Command" if cmd_type == "slash" else "Prefix Command"
        embed.add_field(name="📌 Type", value=cmd_type_display, inline=True)
        embed.add_field(name="🛡️ Required Permissions", value=permissions, inline=True)
        
        # Category
        if category and category in self.categories:
            cat_data = self.categories[category]
            embed.add_field(
                name="📂 Category",
                value=f"{cat_data['emoji']} {cat_data['name']}",
                inline=True
            )
            
        # Aliases
        if aliases:
            embed.add_field(
                name="🔗 Aliases",
                value=", ".join([f"`{a}`" for a in aliases]),
                inline=False
            )
            
        # Parameters for prefix commands
        if cmd_type == "prefix" and hasattr(cmd, "params"):
            params = []
            for param_name, param in cmd.params.items():
                if param_name in ['self', 'ctx']:
                    continue
                required = "Required" if param.default is param.empty else "Optional"
                param_desc = f"`{param_name}` - {required}"
                if param.default is not param.empty:
                    param_desc += f" (default: `{param.default}`)"
                params.append(param_desc)
                
            if params:
                embed.add_field(
                    name="📊 Parameters",
                    value="\n".join(params),
                    inline=False
                )
                
        # Examples for slash commands
        if cmd_type == "slash" and hasattr(cmd, "parameters"):
            params = []
            for param in cmd.parameters:
                required = "Required" if param.required else "Optional"
                param_desc = f"`{param.name}` - {required}"
                if param.description:
                    param_desc += f" - {param.description}"
                params.append(param_desc)
                
            if params:
                embed.add_field(
                    name="📊 Parameters",
                    value="\n".join(params[:10]),
                    inline=False
                )
                
        # Example usage
        example = f"/{cmd_name}" if cmd_type == "slash" else f"{cmd_name}"
        embed.add_field(
            name="💡 Example",
            value=f"`{example}`",
            inline=False
        )
        
        embed.set_footer(text=f"Made by yaduvanshi1816_ • Requested by {interaction.user.name}")
        
        await interaction.response.send_message(embed=embed)

    def get_bot_uptime(self) -> str:
        """Get bot uptime string."""
        if hasattr(self.bot, 'start_time'):
            delta = datetime.now(timezone.utc) - self.bot.start_time
            days = delta.days
            hours, remainder = divmod(delta.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if days > 0:
                return f"{days}d {hours}h {minutes}m"
            elif hours > 0:
                return f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                return f"{minutes}m {seconds}s"
            else:
                return f"{seconds}s"
        return "Unknown"

    # ─── Additional Help Commands ────────────────────────────────────

    @app_commands.command(name="commands", description="List all available commands")
    async def commands_list(self, interaction: discord.Interaction):
        """List all available commands."""
        embed = discord.Embed(
            title="📋 All Commands",
            description=f"Total: {len(self.bot.tree.get_commands())} slash commands",
            color=self.embed_color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Group by category
        category_commands = {}
        for category_id, data in self.categories.items():
            category_commands[category_id] = {
                "emoji": data["emoji"],
                "name": data["name"],
                "commands": []
            }
            
        # Add commands to categories
        for cmd_name in self.categories["general"]["commands"]:
            # Check if command exists
            cmd_info = await self.get_command_info(cmd_name)
            if cmd_info and not cmd_info.get("hidden", False):
                category_commands["general"]["commands"].append(cmd_name)
                
        # Add other categories
        for category_id, data in self.categories.items():
            if category_id != "general":
                for cmd_name in data["commands"]:
                    cmd_info = await self.get_command_info(cmd_name)
                    if cmd_info and not cmd_info.get("hidden", False):
                        category_commands[category_id]["commands"].append(cmd_name)
        
        # Build embed
        for category_id, data in category_commands.items():
            if data["commands"]:
                commands_str = "`, `".join(data["commands"])
                embed.add_field(
                    name=f"{data['emoji']} {data['name']} ({len(data['commands'])})",
                    value=f"`{commands_str}`",
                    inline=False
                )
                
        embed.set_footer(text=f"Made by yaduvanshi1816_ • Use /help command:<command> for details")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="permissions", description="Show permissions for a command")
    @app_commands.describe(command="The command to check permissions for")
    async def permissions(self, interaction: discord.Interaction, command: str):
        """Check what permissions are needed for a command."""
        cmd_info = await self.get_command_info(command.lower())
        if not cmd_info:
            await interaction.response.send_message(
                f"❌ Command `{command}` not found.",
                ephemeral=True
            )
            return
            
        embed = discord.Embed(
            title=f"🛡️ Permissions for `{cmd_info['name']}`",
            color=self.embed_color,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Required Permission",
            value=cmd_info["permissions"],
            inline=True
        )
        embed.add_field(
            name="Command Type",
            value="Slash" if cmd_info["type"] == "slash" else "Prefix",
            inline=True
        )
        
        # Check if user has permission
        if isinstance(interaction.user, discord.Member):
            has_perm = True
            if cmd_info["permissions"] != "None" and cmd_info["permissions"] != "Administrator":
                # Check if user has the required permission
                perm_name = cmd_info["permissions"].lower().replace(" ", "_")
                if hasattr(interaction.user.guild_permissions, perm_name):
                    has_perm = getattr(interaction.user.guild_permissions, perm_name)
                else:
                    has_perm = False
                    
            if cmd_info["permissions"] == "Administrator":
                has_perm = interaction.user.guild_permissions.administrator
                
            embed.add_field(
                name="You Have Permission",
                value="✅ Yes" if has_perm else "❌ No",
                inline=True
            )
            
        embed.set_footer(text=f"Made by yaduvanshi1816_")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bothelp", description="Get help for server administrators")
    @app_commands.checks.has_permissions(administrator=True)
    async def bothelp_admin(self, interaction: discord.Interaction):
        """Get detailed help for setting up the bot."""
        embed = discord.Embed(
            title="🛠️ Administrator Setup Guide",
            description="Welcome! Here's how to set up the bot for your server.",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="1️⃣ Basic Configuration",
            value="• Use `/config show` to view current settings\n"
                  "• Use `/config setprefix <prefix>` to change the prefix\n"
                  "• Use `/config setlanguage <language>` to change the language",
            inline=False
        )
        
        embed.add_field(
            name="2️⃣ Moderation Setup",
            value="• `/config setmodrole @role` - Set mod role\n"
                  "• `/config setadminrole @role` - Set admin role\n"
                  "• `/config setmuterole @role` - Set mute role\n"
                  "• `/config setfeature` - Enable/disable features",
            inline=False
        )
        
        embed.add_field(
            name="3️⃣ Logging Setup",
            value="• `/setlog <type> #channel` - Set log channels\n"
                  "• `/logsettings` - View current logging setup",
            inline=False
        )
        
        embed.add_field(
            name="4️⃣ Auto-Role Setup",
            value="• `/autorole set @role` - Set primary auto-role\n"
                  "• `/autorole add @role` - Add additional roles\n"
                  "• `/autorole setdelay <seconds>` - Set delay before assignment\n"
                  "• `/autorole show` - View current configuration",
            inline=False
        )
        
        embed.add_field(
            name="5️⃣ Auto-Mod Setup",
            value="• `/filter-invites` - Toggle invite filter\n"
                  "• `/filter-links` - Toggle link filter\n"
                  "• `/filter-spam` - Toggle spam protection\n"
                  "• `/settings` - View all current settings",
            inline=False
        )
        
        embed.add_field(
            name="6️⃣ Additional Features",
            value="• Leveling system (coming soon)\n"
                  "• Economy system (coming soon)\n"
                  "• Music system (coming soon)",
            inline=False
        )
        
        embed.set_footer(text="Made by yaduvanshi1816_ • For more help, join the support server!")
        
        await interaction.response.send_message(embed=embed)

    # ─── Auto-Complete for Help ──────────────────────────────────────

    @help.autocomplete("command")
    async def help_command_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for command names in help command."""
        # Get all commands
        commands_list = []
        
        # Prefix commands
        for cmd in self.bot.commands:
            if not cmd.hidden:
                commands_list.append(cmd.name)
                commands_list.extend(cmd.aliases)
                
        # Slash commands
        for cmd in self.bot.tree.get_commands():
            commands_list.append(cmd.name)
            
        # Filter based on current input
        filtered = [cmd for cmd in commands_list if current.lower() in cmd.lower()][:25]
        
        return [app_commands.Choice(name=cmd, value=cmd) for cmd in filtered]

    @help.autocomplete("category")
    async def help_category_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        """Autocomplete for categories in help command."""
        categories = list(self.categories.keys())
        filtered = [cat for cat in categories if current.lower() in cat.lower()][:25]
        
        return [app_commands.Choice(name=self.categories[cat]["name"], value=cat) for cat in filtered]

    # ─── Error Handling ──────────────────────────────────────────────

    @help.error
    async def help_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        """Handle command errors gracefully."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to use this command.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.CommandNotFound):
            await interaction.response.send_message(
                "❌ Command not found.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"⚠️ An error occurred: {error}",
                ephemeral=True
            )
            log.error(f"Unhandled error in help cog: {error}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Handle command errors gracefully."""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You don't have permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I don't have permission to do that.", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param}`", ephemeral=True)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument: {error}", ephemeral=True)
        else:
            await ctx.send(f"⚠️ An error occurred: {error}", ephemeral=True)
            log.error(f"Unhandled error in help cog: {error}")

# ─── Setup Function ──────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(Help(bot))