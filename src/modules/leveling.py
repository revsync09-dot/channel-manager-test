"""
XP and leveling system for the bot.
"""
import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timedelta
import random
import math


class LevelingSystem:
    def __init__(self, db):
        self.db = db
        self.xp_cooldowns = {}
    
    def calculate_level(self, xp: int) -> int:
        """Calculate level from XP"""
        # Level = floor(sqrt(XP / 100))
        return int(math.sqrt(xp / 100))
    
    def calculate_xp_for_level(self, level: int) -> int:
        """Calculate XP needed for a specific level"""
        return level * level * 100
    
    def get_user_xp(self, guild_id: int, user_id: int) -> tuple[int, int]:
        """Get user's XP and level"""
        xp = self.db.get_user_xp(guild_id, user_id)
        level = self.calculate_level(xp)
        return xp, level
    
    def add_xp(self, guild_id: int, user_id: int, amount: int) -> tuple[int, int, bool]:
        """Add XP to user, returns (new_xp, new_level, leveled_up)"""
        old_xp, old_level = self.get_user_xp(guild_id, user_id)
        new_xp = self.db.add_user_xp(guild_id, user_id, amount)
        new_level = self.calculate_level(new_xp)
        leveled_up = new_level > old_level
        return new_xp, new_level, leveled_up
    
    def set_xp(self, guild_id: int, user_id: int, xp: int) -> tuple[int, int]:
        """Set user's XP"""
        self.db.set_user_xp(guild_id, user_id, xp)
        level = self.calculate_level(xp)
        return xp, level
    
    def can_gain_xp(self, guild_id: int, user_id: int) -> bool:
        """Check if user is off cooldown for XP gain"""
        key = f"{guild_id}_{user_id}"
        if key in self.xp_cooldowns:
            return datetime.utcnow() >= self.xp_cooldowns[key]
        return True
    
    def gain_message_xp(self, guild_id: int, user_id: int) -> tuple[int, int, bool]:
        """Gain XP from sending a message"""
        key = f"{guild_id}_{user_id}"
        self.xp_cooldowns[key] = datetime.utcnow() + timedelta(seconds=60)
        
        config = self.db.get_guild_config(guild_id) or {}
        min_xp = config.get("xp_min", 15)
        max_xp = config.get("xp_max", 25)
        
        xp_gain = random.randint(min_xp, max_xp)
        return self.add_xp(guild_id, user_id, xp_gain)
    
    def get_leaderboard(self, guild_id: int, limit: int = 10):
        """Get XP leaderboard"""
        return self.db.get_xp_leaderboard(guild_id, limit)
    
    def get_level_role(self, guild_id: int, level: int):
        """Get role for a specific level"""
        return self.db.get_level_role(guild_id, level)
    
    def get_all_level_roles(self, guild_id: int):
        """Get all level roles"""
        return self.db.get_all_level_roles(guild_id)
    
    def get_default_level_milestones(self):
        """Get default level milestones for role creation"""
        return [5, 10, 20, 30, 50, 80, 100]
    
    def generate_level_role_name(self, level: int) -> str:
        """Generate a name for a level role"""
        if level < 10:
            return f"Beginner {level}"
        elif level < 30:
            return f"Member {level}"
        elif level < 50:
            return f"Veteran {level}"
        elif level < 80:
            return f"Elite {level}"
        else:
            return f"Legend {level}"
    
    def generate_level_role_color(self, level: int) -> int:
        """Generate a color for a level role based on level"""
        colors = {
            5: 0x95A5A6,   # Gray
            10: 0x3498DB,  # Blue
            20: 0x2ECC71,  # Green
            30: 0x9B59B6,  # Purple
            50: 0xE74C3C,  # Red
            80: 0xF39C12,  # Orange
            100: 0xF1C40F  # Gold
        }
        # Find closest color
        closest = min(colors.keys(), key=lambda x: abs(x - level))
        return colors[closest]


async def create_leveling_roles(guild: discord.Guild, milestones: list[int], leveling: LevelingSystem, bot):
    """Create level roles for specified milestones"""
    created_roles = []
    
    for level in milestones:
        role_name = leveling.generate_level_role_name(level)
        role_color = leveling.generate_level_role_color(level)
        
        try:
            # Check if role already exists
            existing_role = discord.utils.get(guild.roles, name=role_name)
            if existing_role:
                bot.db.set_level_role(guild.id, level, existing_role.id)
                created_roles.append((level, existing_role))
                continue
            
            # Create new role
            role = await guild.create_role(
                name=role_name,
                color=discord.Color(role_color),
                hoist=False,
                mentionable=False,
                reason=f"Auto-created level {level} role"
            )
            
            # Store in database
            bot.db.set_level_role(guild.id, level, role.id)
            created_roles.append((level, role))
        except Exception as e:
            print(f"Failed to create role for level {level}: {e}")
    
    return created_roles


async def create_leveling_info_channel(guild: discord.Guild, bot):
    """Create an info channel for leveling system"""
    try:
        # Find or create INFO category
        category = discord.utils.get(guild.categories, name="📋 INFO")
        if not category:
            category = await guild.create_category("📋 INFO", reason="Leveling system setup")
        
        # Check if channel exists
        existing_channel = discord.utils.get(guild.text_channels, name="📊-levels-info")
        if existing_channel:
            return existing_channel
        
        # Create channel
        channel = await guild.create_text_channel(
            "📊-levels-info",
            category=category,
            topic="Level roles and XP information",
            reason="Leveling system info channel"
        )
        
        # Set permissions - read only
        await channel.set_permissions(
            guild.default_role,
            send_messages=False,
            add_reactions=False,
            read_messages=True
        )
        
        # Get level roles
        level_roles = bot.leveling.get_all_level_roles(guild.id)
        
        # Create info embed
        embed = discord.Embed(
            title="📊 Leveling System",
            description="Gain XP by chatting and level up to unlock exclusive roles!",
            color=0x9B59B6
        )
        
        embed.add_field(
            name="How to Level Up",
            value="• Send messages to earn XP\n• XP cooldown: 60 seconds\n• Check your rank with `/rank`\n• View leaderboard with `/levels`",
            inline=False
        )
        
        # Add level roles info
        if level_roles:
            role_list = ""
            for level, role_id in sorted(level_roles):
                role = guild.get_role(role_id)
                if role:
                    xp_needed = bot.leveling.calculate_xp_for_level(level)
                    role_list += f"**Level {level}** ({xp_needed:,} XP) → {role.mention}\n"
            
            if role_list:
                embed.add_field(
                    name="🎭 Level Roles",
                    value=role_list,
                    inline=False
                )
        
        embed.add_field(
            name="Commands",
            value="`/rank` - View your rank\n`/levels` - View leaderboard\n`/setlevel` - Admin only\n`/addxp` - Admin only",
            inline=False
        )
        
        embed.set_footer(text="Keep chatting to level up!")
        
        await channel.send(embed=embed)
        return channel
        
    except Exception as e:
        print(f"Failed to create leveling info channel: {e}")
        return None


async def create_rules_info_channel(guild: discord.Guild):
    """Create a rules info channel"""
    try:
        # Find or create INFO category
        category = discord.utils.get(guild.categories, name="📋 INFO")
        if not category:
            category = await guild.create_category("📋 INFO", reason="Server setup")
        
        # Check if channel exists
        existing_channel = discord.utils.get(guild.text_channels, name="📜-rules")
        if existing_channel:
            return existing_channel
        
        # Create channel
        channel = await guild.create_text_channel(
            "📜-rules",
            category=category,
            topic="Server rules and guidelines",
            reason="Rules info channel"
        )
        
        # Set permissions - read only
        await channel.set_permissions(
            guild.default_role,
            send_messages=False,
            add_reactions=False,
            read_messages=True
        )
        
        # Create rules embed
        embed = discord.Embed(
            title="📜 Server Rules",
            description="Please read and follow these rules to keep our community safe and friendly.",
            color=0xE74C3C
        )
        
        rules = [
            "**1. Be Respectful** - Treat everyone with respect. No harassment, hate speech, or discrimination.",
            "**2. No Spam** - Don't spam messages, emojis, or mentions. Keep conversations meaningful.",
            "**3. No NSFW Content** - Keep all content appropriate for all ages.",
            "**4. Follow Discord ToS** - All Discord Terms of Service and Community Guidelines apply.",
            "**5. Use Appropriate Channels** - Post content in the correct channels.",
            "**6. No Self-Promotion** - Don't advertise without permission from staff.",
            "**7. Listen to Staff** - Follow instructions from moderators and admins.",
            "**8. Have Fun!** - Enjoy your time here and make friends!"
        ]
        
        embed.add_field(
            name="Rules",
            value="\n\n".join(rules),
            inline=False
        )
        
        embed.add_field(
            name="⚠️ Consequences",
            value="Breaking rules may result in warnings, timeouts, kicks, or bans depending on severity.",
            inline=False
        )
        
        embed.set_footer(text="Last updated: " + datetime.utcnow().strftime("%B %d, %Y"))
        
        await channel.send(embed=embed)
        return channel
        
    except Exception as e:
        print(f"Failed to create rules info channel: {e}")
        return None


async def check_level_roles(bot, guild_id: int, user_id: int, new_level: int):
    """Check and assign level roles"""
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    
    member = guild.get_member(user_id)
    if not member:
        return
    
    level_roles = bot.leveling.get_all_level_roles(guild_id)
    
    for level, role_id in level_roles:
        role = guild.get_role(role_id)
        if not role:
            continue
        
        if new_level >= level:
            if role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Reached level {level}")
                except:
                    pass
        else:
            if role in member.roles:
                try:
                    await member.remove_roles(role, reason=f"No longer level {level}")
                except:
                    pass


def setup_leveling_commands(bot, leveling: LevelingSystem):
    """Setup leveling slash commands"""
    
    @bot.tree.command(name="rank", description="Check your rank and level")
    @app_commands.describe(user="User to check rank for")
    async def rank_command(interaction: discord.Interaction, user: discord.User = None):
        target = user or interaction.user
        xp, level = leveling.get_user_xp(interaction.guild_id, target.id)
        
        current_level_xp = leveling.calculate_xp_for_level(level)
        next_level_xp = leveling.calculate_xp_for_level(level + 1)
        xp_progress = xp - current_level_xp
        xp_needed = next_level_xp - current_level_xp
        
        # Calculate progress percentage
        progress_percent = (xp_progress / xp_needed) * 100
        progress_bar_length = 20
        filled = int((progress_percent / 100) * progress_bar_length)
        bar = "█" * filled + "░" * (progress_bar_length - filled)
        
        embed = discord.Embed(
            title=f"📊 Rank - {target.display_name}",
            color=0x9B59B6
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="XP", value=f"**{xp:,}**", inline=True)
        embed.add_field(name="Messages", value=f"~{xp // 20}", inline=True)
        embed.add_field(
            name="Progress to Next Level",
            value=f"{bar} {progress_percent:.1f}%\n{xp_progress:,} / {xp_needed:,} XP",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="levels", description="View XP leaderboard")
    async def levels_command(interaction: discord.Interaction):
        leaders = leveling.get_leaderboard(interaction.guild_id)
        
        if not leaders:
            await interaction.response.send_message("No leveling data yet!", ephemeral=True)
            return
        
        description = ""
        for i, (user_id, xp) in enumerate(leaders, 1):
            user = await bot.fetch_user(user_id)
            level = leveling.calculate_level(xp)
            medal = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"**{i}.**"
            description += f"{medal} {user.mention} - Level **{level}** ({xp:,} XP)\n"
        
        embed = discord.Embed(
            title="📊 XP Leaderboard",
            description=description,
            color=0x9B59B6
        )
        await interaction.response.send_message(embed=embed)
    
    @bot.tree.command(name="setlevel", description="Set a user's level (Admin only)")
    @app_commands.describe(user="User to set level", level="Level to set")
    async def setlevel_command(interaction: discord.Interaction, user: discord.User, level: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permission!", ephemeral=True)
            return
        
        if level < 0:
            await interaction.response.send_message("❌ Level must be positive!", ephemeral=True)
            return
        
        xp = leveling.calculate_xp_for_level(level)
        leveling.set_xp(interaction.guild_id, user.id, xp)
        
        await check_level_roles(bot, interaction.guild_id, user.id, level)
        
        await interaction.response.send_message(f"✅ Set {user.mention}'s level to **{level}** ({xp:,} XP)", ephemeral=True)
    
    @bot.tree.command(name="addxp", description="Add XP to a user (Admin only)")
    @app_commands.describe(user="User to give XP", amount="Amount of XP to add")
    async def addxp_command(interaction: discord.Interaction, user: discord.User, amount: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permission!", ephemeral=True)
            return
        
        new_xp, new_level, leveled_up = leveling.add_xp(interaction.guild_id, user.id, amount)
        
        await check_level_roles(bot, interaction.guild_id, user.id, new_level)
        
        msg = f"✅ Added **{amount:,}** XP to {user.mention}\nNew level: **{new_level}** ({new_xp:,} XP)"
        if leveled_up:
            msg += "\n🎉 They leveled up!"
        
        await interaction.response.send_message(msg, ephemeral=True)
    
    @bot.tree.command(name="levelrole", description="Set a role reward for reaching a level (Admin only)")
    @app_commands.describe(level="Level to reward at", role="Role to give")
    async def levelrole_command(interaction: discord.Interaction, level: int, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permission!", ephemeral=True)
            return
        
        if level < 1:
            await interaction.response.send_message("❌ Level must be at least 1!", ephemeral=True)
            return
        
        bot.db.set_level_role(interaction.guild_id, level, role.id)
        await interaction.response.send_message(f"✅ Set {role.mention} as reward for reaching level **{level}**", ephemeral=True)
    
    @bot.tree.command(name="removelevelrole", description="Remove a level role reward (Admin only)")
    @app_commands.describe(level="Level to remove reward from")
    async def removelevelrole_command(interaction: discord.Interaction, level: int):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permission!", ephemeral=True)
            return
        
        bot.db.remove_level_role(interaction.guild_id, level)
        await interaction.response.send_message(f"✅ Removed level role reward for level **{level}**", ephemeral=True)
    
    @bot.tree.command(name="leveling_setup", description="Setup leveling system with roles and info channel (Admin only)")
    @app_commands.describe(
        milestones="Level milestones for roles (e.g., '5,10,20,30,50,80,100')",
        create_info_channel="Create an info channel explaining the leveling system",
        create_rules_channel="Create a rules channel for the server"
    )
    async def leveling_setup_command(
        interaction: discord.Interaction,
        milestones: str = "5,10,20,30,50,80,100",
        create_info_channel: bool = True,
        create_rules_channel: bool = False
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ You need administrator permission!", ephemeral=True)
            return
        
        await interaction.response.defer(thinking=True, ephemeral=True)
        
        try:
            # Parse milestones
            milestone_list = [int(x.strip()) for x in milestones.split(',')]
            milestone_list = sorted(set(milestone_list))  # Remove duplicates and sort
            
            if not milestone_list:
                await interaction.followup.send("❌ No valid milestones provided!", ephemeral=True)
                return
            
            # Create roles
            created_roles = await create_leveling_roles(interaction.guild, milestone_list, leveling, bot)
            
            # Create info channel if requested
            info_channel = None
            if create_info_channel:
                info_channel = await create_leveling_info_channel(interaction.guild, bot)
            
            # Create rules channel if requested
            rules_channel = None
            if create_rules_channel:
                rules_channel = await create_rules_info_channel(interaction.guild)
            
            # Build response
            response = f"✅ **Leveling System Setup Complete!**\n\n"
            response += f"**Roles Created:** {len(created_roles)}\n"
            
            for level, role in created_roles[:5]:  # Show first 5
                response += f"• Level {level} → {role.mention}\n"
            
            if len(created_roles) > 5:
                response += f"• ... and {len(created_roles) - 5} more\n"
            
            if info_channel:
                response += f"\n**Info Channel:** {info_channel.mention}"
            
            if rules_channel:
                response += f"\n**Rules Channel:** {rules_channel.mention}"
            
            response += "\n\nUsers will automatically receive roles when they reach the specified levels!"
            
            await interaction.followup.send(response, ephemeral=True)
            
        except ValueError:
            await interaction.followup.send("❌ Invalid milestone format! Use comma-separated numbers like: 5,10,20,30", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Setup failed: {str(e)}", ephemeral=True)


def init_leveling(bot):
    """Initialize leveling system"""
    leveling = LevelingSystem(bot.db)
    bot.leveling = leveling
    setup_leveling_commands(bot, leveling)
    
    @bot.listen("on_message")
    async def on_message(message):
        if message.author.bot:
            return
        
        if not message.guild:
            return
        
        # Check if leveling is enabled
        config = bot.db.get_guild_config(message.guild.id) or {}
        if not config.get("leveling_enabled", True):
            return
        
        # Check if user can gain XP
        if not leveling.can_gain_xp(message.guild.id, message.author.id):
            return
        
        # Gain XP
        new_xp, new_level, leveled_up = leveling.gain_message_xp(message.guild.id, message.author.id)
        
        # Check level roles
        await check_level_roles(bot, message.guild.id, message.author.id, new_level)
        
        # Send level up message
        if leveled_up:
            level_up_channel = config.get("level_up_channel_id")
            if level_up_channel:
                channel = bot.get_channel(int(level_up_channel))
                if channel:
                    embed = discord.Embed(
                        title="🎉 Level Up!",
                        description=f"{message.author.mention} reached level **{new_level}**!",
                        color=0x9B59B6
                    )
                    try:
                        await channel.send(embed=embed)
                    except:
                        pass
            else:
                # Send in current channel
                embed = discord.Embed(
                    title="🎉 Level Up!",
                    description=f"Congratulations {message.author.mention}, you reached level **{new_level}**!",
                    color=0x9B59B6
                )
                try:
                    await message.channel.send(embed=embed, delete_after=10)
                except:
                    pass
    
    return leveling
