import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
import platform
import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
import logging

# Configuration
SUPPORT_SERVER_URL = "https://discord.gg/PGwbyWX3DS"
BOT_INVITE_URL = "https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands"
VERSION = "2.0.0"
OWNER_IDS = [1165248657466085377]  # Replace with your actual Discord User ID(s) as integers

log = logging.getLogger(__name__)

class General(commands.Cog):
    """General utility commands for the bot."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.color = discord.Color.blue()
        self.start_time = datetime.now(timezone.utc)
        
        # ─── Data Arrays ──────────────────────────────────────────────
        self.fun_facts = [
            "The first computer virus was created in 1983.",
            "The average person spends 6 months of their life waiting for red lights to turn green.",
            "A day on Venus is longer than a year on Venus.",
            "The Eiffel Tower can be 15 cm taller during the summer due to thermal expansion.",
            "Octopuses have three hearts and blue blood.",
            "There are more stars in the universe than grains of sand on all beaches on Earth.",
            "The shortest war in history was between Britain and Zanzibar in 1896, lasting 38 minutes.",
            "A group of flamingos is called a 'flamboyance'.",
            "The longest word in English has 189,819 letters and takes 3.5 hours to pronounce.",
            "Cows have best friends and get stressed when they are separated."
        ]
        
        self.motivational_quotes = [
            "✨ Success is not final, failure is not fatal: it is the courage to continue that counts.",
            "💪 The only way to do great work is to love what you do.",
            "🚀 Believe you can and you're halfway there.",
            "🌟 It does not matter how slowly you go as long as you do not stop.",
            "🌈 The future belongs to those who believe in the beauty of their dreams.",
            "🔥 Success usually comes to those who are too busy to be looking for it.",
            "⭐ The best time to plant a tree was 20 years ago. The second best time is now.",
            "💫 It's not whether you get knocked down, it's whether you get up.",
            "🎯 The only limit to our realization of tomorrow is our doubts of today.",
            "🏆 You are never too old to set another goal or to dream a new dream."
        ]
        
        self.ai_responses = [
            "I've processed your request and the answer is 42. Always 42. 🤖",
            "Beep boop! I've calculated the probability of your success at 98.7%! 📊",
            "I've consulted my AI overlords and they said: 'Send memes.' 📈",
            "My neural network suggests you take a break and get some coffee. ☕",
            "According to my calculations, the answer you're looking for is... friendship! 🤝",
            "I've analyzed 10,000 possible responses and chose this one randomly. 🎲",
            "My algorithms detect that you are a cool person. This is a fact. 🧠",
            "I would tell you the answer, but I'm afraid it would blow your human mind. 🤯",
            "Your query has been filed under 'important stuff' and will be processed at warp speed! 🚀",
            "I'm not saying it's aliens, but... it's probably aliens. 👽"
        ]

    def get_uptime(self) -> str:
        """Get bot uptime in a human-readable format."""
        delta = datetime.now(timezone.utc) - self.start_time
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

    # ─── Slash Commands ──────────────────────────────────────────────

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        """Check bot latency and response time."""
        await interaction.response.defer(ephemeral=False)
        
        start_time = datetime.now(timezone.utc)
        latency = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        websocket_latency = round(self.bot.latency * 1000, 2)
        
        embed = discord.Embed(
            title="🏓 Pong!",
            color=self.color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="WebSocket Latency", value=f"`{websocket_latency}ms`", inline=True)
        embed.add_field(name="API Latency", value=f"`{round(latency, 2)}ms`", inline=True)
        embed.add_field(name="Status", value="🟢 Online", inline=True)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="stats", description="Display bot statistics")
    async def stats(self, interaction: discord.Interaction):
        """Display detailed bot statistics."""
        await interaction.response.defer(ephemeral=False)
        
        total_guilds = len(self.bot.guilds)
        total_users = len(self.bot.users)
        total_commands = len(self.bot.tree.get_commands())
        uptime = self.get_uptime()
        latency = round(self.bot.latency * 1000, 2)
        
        embed = discord.Embed(
            title="📊 Bot Statistics",
            color=self.color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="Servers", value=f"`{total_guilds}`", inline=True)
        embed.add_field(name="Users", value=f"`{total_users}`", inline=True)
        embed.add_field(name="Commands", value=f"`{total_commands}`", inline=True)
        embed.add_field(name="Uptime", value=f"`{uptime}`", inline=True)
        embed.add_field(name="Latency", value=f"`{latency}ms`", inline=True)
        embed.add_field(name="Python Version", value=f"`{platform.python_version()}`", inline=True)
        embed.add_field(name="discord.py Version", value=f"`{discord.__version__}`", inline=True)
        
        if self.bot.user.display_avatar:
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="serverinfo", description="Get information about the current server")
    async def serverinfo(self, interaction: discord.Interaction):
        """Display detailed server information."""
        await interaction.response.defer(ephemeral=False)
        guild = interaction.guild
        
        if not guild:
            await interaction.followup.send("❌ This command must be used in a server.")
            return
        
        embed = discord.Embed(
            title=f"📋 Server Information - {guild.name}",
            color=guild.owner.color if guild.owner else self.color,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="Server ID", value=f"`{guild.id}`", inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        
        members = guild.members
        bots = len([m for m in members if m.bot])
        humans = len(members) - bots
        text_channels = len([c for c in guild.channels if isinstance(c, discord.TextChannel)])
        voice_channels = len([c for c in guild.channels if isinstance(c, discord.VoiceChannel)])
        categories = len([c for c in guild.channels if isinstance(c, discord.CategoryChannel)])
        
        embed.add_field(name="Members", value=f"`{len(members)}` (👤 {humans} | 🤖 {bots})", inline=True)
        embed.add_field(name="Channels", value=f"`{len(guild.channels)}` (💬 {text_channels} | 🔊 {voice_channels} | 📁 {categories})", inline=True)
        embed.add_field(name="Roles", value=f"`{len(guild.roles)}`", inline=True)
        embed.add_field(name="Emojis", value=f"`{len(guild.emojis)}/{guild.emoji_limit}`", inline=True)
        embed.add_field(name="Boost Level", value=f"`{guild.premium_tier} (Level {guild.premium_tier})`", inline=True)
        embed.add_field(name="Boosts", value=f"`{guild.premium_subscription_count}`", inline=True)
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="userinfo", description="Get information about a user")
    async def userinfo(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Display detailed user information."""
        await interaction.response.defer(ephemeral=False)
        member = member or interaction.user
        
        embed = discord.Embed(
            title=f"👤 User Information - {member.name}",
            color=member.color if member.color != discord.Color.default() else self.color,
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="User ID", value=f"`{member.id}`", inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Account Created", value=f"<t:{int(member.created_at.timestamp())}:R>", inline=True)
        if interaction.guild and member.joined_at:
            embed.add_field(name="Joined Server", value=f"<t:{int(member.joined_at.timestamp())}:R>", inline=True)
        
        status = str(member.status).title()
        status_map = {
            "Online": "🟢 Online",
            "Idle": "🟡 Idle",
            "Do_Not_Disturb": "🔴 DND",
            "Dnd": "🔴 DND",
            "Offline": "⚫ Offline"
        }
        embed.add_field(name="Status", value=status_map.get(status, status), inline=True)
        
        if member.activity:
            activity_type = str(member.activity.type).split('.')[-1].title()
            embed.add_field(name="Activity", value=f"`{activity_type}` - {member.activity.name}", inline=True)
        
        if interaction.guild:
            roles = [role.mention for role in reversed(member.roles) if role != interaction.guild.default_role]
            if roles:
                roles_display = " ".join(roles[:10])
                if len(roles) > 10:
                    roles_display += f" and {len(roles) - 10} more..."
                embed.add_field(name=f"Roles ({len(roles)})", value=roles_display, inline=False)
        
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="avatar", description="Display a user's avatar")
    async def avatar(self, interaction: discord.Interaction, member: Optional[discord.Member] = None):
        """Display a user's avatar in high resolution."""
        await interaction.response.defer(ephemeral=False)
        member = member or interaction.user
        
        embed = discord.Embed(
            title=f"🖼️ {member.name}'s Avatar",
            color=member.color if member.color != discord.Color.default() else self.color
        )
        embed.set_image(url=member.display_avatar.url)
        embed.set_footer(text=f"User ID: {member.id} • Made by yaduvanshi1816_")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="invite", description="Get the bot's invite link")
    async def invite(self, interaction: discord.Interaction):
        """Display bot invite and support links."""
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(
            title="🤖 Invite Me!",
            description="Add me to your server and level up your community!",
            color=self.color
        )
        embed.add_field(name="📥 Invite Link", value=f"[Click Here to Invite]({BOT_INVITE_URL})", inline=False)
        embed.add_field(name="💬 Support Server", value=f"[Join the Community]({SUPPORT_SERVER_URL})", inline=False)
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="support", description="Get support server invite")
    async def support(self, interaction: discord.Interaction):
        """Display support server link."""
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(
            title="💬 Support Server",
            description="Join our community for help, updates, and more!",
            color=self.color
        )
        embed.add_field(name="Invite Link", value=f"[Click Here]({SUPPORT_SERVER_URL})", inline=False)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="uptime", description="Check how long the bot has been online")
    async def uptime(self, interaction: discord.Interaction):
        """Display bot uptime."""
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(
            title="⏰ Bot Uptime",
            description="I've been online for:",
            color=self.color
        )
        embed.add_field(name="📊 Uptime", value=f"```\n{self.get_uptime()}\n```", inline=False)
        embed.add_field(name="📅 Started At", value=f"<t:{int(self.start_time.timestamp())}:F>", inline=True)
        embed.add_field(name="⌛ Relative", value=f"<t:{int(self.start_time.timestamp())}:R>", inline=True)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="about", description="About the bot")
    async def about(self, interaction: discord.Interaction):
        """Display information about the bot."""
        await interaction.response.defer(ephemeral=False)
        embed = discord.Embed(
            title=f"🤖 About {self.bot.user.name}",
            description=f"Version: `{VERSION}`\nA powerful, feature-rich Discord bot built with discord.py.",
            color=self.color
        )
        embed.add_field(name="👑 Creator", value="yaduvanshi1816_", inline=True)
        embed.add_field(name="📚 Library", value="discord.py", inline=True)
        embed.add_field(name="🐍 Python", value=platform.python_version(), inline=True)
        embed.add_field(name="📊 Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="👥 Users", value=str(len(self.bot.users)), inline=True)
        embed.add_field(name="⚡ Uptime", value=self.get_uptime(), inline=True)
        
        if SUPPORT_SERVER_URL:
            embed.add_field(name="💬 Support", value=f"[Join Server]({SUPPORT_SERVER_URL})", inline=False)
        
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        embed.set_footer(text="Made by yaduvanshi1816_")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="random", description="Generate a random number")
    @app_commands.describe(
        start="Starting number (default: 1)",
        end="Ending number (default: 100)"
    )
    async def random_number(self, interaction: discord.Interaction, start: int = 1, end: int = 100):
        """Generate a random number between start and end."""
        await interaction.response.defer(ephemeral=False)
        if start > end:
            await interaction.followup.send("❌ Start must be less than end.", ephemeral=True)
            return
            
        result = random.randint(start, end)
        embed = discord.Embed(
            title="🎲 Random Number",
            description=f"Your random number between **{start}** and **{end}** is:",
            color=self.color
        )
        embed.add_field(name="Result", value=f"```\n{result}\n```", inline=False)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="flip", description="Flip a coin")
    async def flip(self, interaction: discord.Interaction):
        """Flip a coin and get heads or tails."""
        await interaction.response.defer(ephemeral=False)
        result = random.choice(["Heads", "Tails"])
        
        embed = discord.Embed(
            title="🪙 Coin Flip",
            color=self.color
        )
        embed.add_field(name="Result", value=f"```\n{result}\n```", inline=False)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="roll", description="Roll a dice")
    @app_commands.describe(sides="Number of sides on the dice (default: 6)")
    async def roll(self, interaction: discord.Interaction, sides: int = 6):
        """Roll a dice with a specified number of sides."""
        await interaction.response.defer(ephemeral=False)
        if sides < 2:
            await interaction.followup.send("❌ Dice must have at least 2 sides.", ephemeral=True)
            return
        if sides > 100:
            await interaction.followup.send("❌ Dice cannot have more than 100 sides.", ephemeral=True)
            return
            
        result = random.randint(1, sides)
        embed = discord.Embed(
            title="🎲 Dice Roll",
            description=f"Rolling a **{sides}**-sided die...",
            color=self.color
        )
        embed.add_field(name="Result", value=f"```\n{result}\n```", inline=False)
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="choice", description="Make a choice from multiple options")
    @app_commands.describe(options="Comma-separated options (e.g., pizza,pasta,sushi)")
    async def choice(self, interaction: discord.Interaction, *, options: str):
        """Choose randomly from a list of comma-separated options."""
        await interaction.response.defer(ephemeral=False)
        choices = [opt.strip() for opt in options.split(",")]
        if len(choices) < 2:
            await interaction.followup.send("❌ Please provide at least 2 options separated by commas.", ephemeral=True)
            return
            
        result = random.choice(choices)
        embed = discord.Embed(
            title="🤔 Decision Time",
            description="I choose:",
            color=self.color
        )
        embed.add_field(name="🎯 Result", value=f"```\n{result}\n```", inline=False)
        embed.add_field(
            name="📋 Options",
            value="\n".join([f"• {opt}" for opt in choices[:10]]),
            inline=False
        )
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="poll", description="Create a poll")
    @app_commands.describe(
        question="The poll question",
        option1="First option",
        option2="Second option",
        option3="Third option (optional)",
        option4="Fourth option (optional)"
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None
    ):
        """Create a poll with up to 4 options."""
        await interaction.response.defer(ephemeral=False)
        options = [option1, option2]
        if option3:
            options.append(option3)
        if option4:
            options.append(option4)
            
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
        description = "\n".join([f"{emojis[i]} {opt}" for i, opt in enumerate(options)])
        
        embed = discord.Embed(
            title=f"📊 Poll: {question}",
            description=description,
            color=self.color,
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Poll created by {interaction.user.name} • Made by yaduvanshi1816_")
        
        poll_msg = await interaction.followup.send(embed=embed)
        
        for i in range(len(options)):
            await poll_msg.add_reaction(emojis[i])

    @app_commands.command(name="fact", description="Get a random fun fact")
    async def fact(self, interaction: discord.Interaction):
        """Get a random interesting fact."""
        await interaction.response.defer(ephemeral=False)
        fact_text = random.choice(self.fun_facts)
        embed = discord.Embed(
            title="💡 Fun Fact",
            description=fact_text,
            color=self.color
        )
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="motivate", description="Get a motivational quote")
    async def motivate(self, interaction: discord.Interaction):
        """Get a random motivational quote."""
        await interaction.response.defer(ephemeral=False)
        quote = random.choice(self.motivational_quotes)
        embed = discord.Embed(
            title="🌟 Motivation",
            description=quote,
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ai", description="Get an AI-like response")
    @app_commands.describe(query="Your question or query for the AI")
    async def ai_response(self, interaction: discord.Interaction, query: Optional[str] = None):
        """Get a fun AI-like response to your query."""
        await interaction.response.defer(ephemeral=False)
        response = random.choice(self.ai_responses)
        if query:
            embed = discord.Embed(
                title="🤖 AI Response",
                description=f"**Your query:** {query}\n\n**My response:** {response}",
                color=self.color
            )
        else:
            embed = discord.Embed(
                title="🤖 AI Says",
                description=response,
                color=self.color
            )
        embed.set_footer(text=f"Made by yaduvanshi1816_ • {VERSION}")
        
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="serverlist", description="List all servers the bot is in")
    async def serverlist(self, interaction: discord.Interaction):
        """List all servers the bot is in (owner only)."""
        if interaction.user.id not in OWNER_IDS:
            await interaction.response.send_message("❌ This command is owner-only.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        servers = [f"• {guild.name} (`{guild.id}`) - {guild.member_count} members" for guild in self.bot.guilds]
            
        chunks = [servers[i:i+20] for i in range(0, len(servers), 20)]
        
        for i, chunk in enumerate(chunks):
            embed = discord.Embed(
                title=f"📋 Server List (Page {i+1}/{len(chunks)})",
                description="\n".join(chunk),
                color=self.color
            )
            embed.set_footer(text=f"Total: {len(servers)} servers")
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="sync", description="Sync slash commands")
    async def sync(self, interaction: discord.Interaction):
        """Sync slash commands (owner only)."""
        if interaction.user.id not in OWNER_IDS:
            await interaction.response.send_message("❌ This command is owner-only.", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send("🔄 Syncing slash commands...", ephemeral=True)
        try:
            await self.bot.tree.sync()
            await interaction.followup.send("✅ Slash commands synced successfully!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to sync: {e}", ephemeral=True)

    @app_commands.command(name="echo", description="Make the bot say something")
    @app_commands.describe(message="The message to echo")
    async def echo(self, interaction: discord.Interaction, *, message: str):
        """Make the bot repeat a message."""
        await interaction.response.send_message(message)

    @app_commands.command(name="embed", description="Send a custom embed")
    @app_commands.describe(
        title="Embed title",
        description="Embed description",
        color="Hex color code (e.g., #FF0000)",
        footer="Footer text"
    )
    async def embed_cmd(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        color: Optional[str] = None,
        footer: Optional[str] = None
    ):
        """Send a custom embed."""
        try:
            color_int = int(color.replace("#", ""), 16) if color else self.color.value
        except ValueError:
            color_int = self.color.value
            
        embed = discord.Embed(
            title=title,
            description=description,
            color=color_int,
            timestamp=datetime.now(timezone.utc)
        )
        if footer:
            embed.set_footer(text=footer)
            
        await interaction.response.send_message(embed=embed)

# ─── Setup Function ──────────────────────────────────────────────────

async def setup(bot: commands.Bot):
    """Add the cog to the bot."""
    await bot.add_cog(General(bot))
