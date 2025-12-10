"""
Moderation system with kick, ban, mute, warn, and logging.
"""
import discord
from discord import app_commands
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio


# Store warnings: {guild_id: {user_id: [{"reason": str, "moderator": str, "timestamp": datetime}]}}
WARNINGS: Dict[int, Dict[int, List[dict]]] = {}

# Store mute tasks: {guild_id: {user_id: task}}
MUTE_TASKS: Dict[int, Dict[int, asyncio.Task]] = {}

# Moderation log channel: {guild_id: channel_id}
MOD_LOG_CHANNELS: Dict[int, int] = {}


async def log_moderation(guild: discord.Guild, embed: discord.Embed):
    """Log moderation action to configured channel"""
    if guild.id in MOD_LOG_CHANNELS:
        channel_id = MOD_LOG_CHANNELS[guild.id]
        channel = guild.get_channel(channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            try:
                await channel.send(embed=embed)
            except:
                pass


def add_warning(guild_id: int, user_id: int, reason: str, moderator: str):
    """Add a warning to a user"""
    if guild_id not in WARNINGS:
        WARNINGS[guild_id] = {}
    
    if user_id not in WARNINGS[guild_id]:
        WARNINGS[guild_id][user_id] = []
    
    WARNINGS[guild_id][user_id].append({
        "reason": reason,
        "moderator": moderator,
        "timestamp": datetime.utcnow()
    })


def get_warnings(guild_id: int, user_id: int) -> List[dict]:
    """Get all warnings for a user"""
    if guild_id not in WARNINGS:
        return []
    
    if user_id not in WARNINGS[guild_id]:
        return []
    
    return WARNINGS[guild_id][user_id]


def clear_warnings(guild_id: int, user_id: int):
    """Clear all warnings for a user"""
    if guild_id in WARNINGS and user_id in WARNINGS[guild_id]:
        del WARNINGS[guild_id][user_id]


async def auto_unmute(guild_id: int, user_id: int, duration: int):
    """Auto-unmute user after duration (in seconds)"""
    await asyncio.sleep(duration)
    
    # Remove from tasks
    if guild_id in MUTE_TASKS and user_id in MUTE_TASKS[guild_id]:
        del MUTE_TASKS[guild_id][user_id]


def setup_moderation_commands(bot):
    """Setup moderation slash commands"""
    
    @bot.tree.command(name="kick", description="Kick a member from the server")
    @app_commands.describe(member="Member to kick", reason="Reason for kick")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick_command(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ You cannot kick this member (role hierarchy).", ephemeral=True)
            return
        
        if member.id == interaction.guild.owner_id:
            await interaction.response.send_message("❌ You cannot kick the server owner.", ephemeral=True)
            return
        
        try:
            # DM user before kicking
            try:
                dm_embed = discord.Embed(
                    title=f"Kicked from {interaction.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=0xED4245,
                    timestamp=datetime.utcnow()
                )
                dm_embed.set_footer(text=f"Kicked by {interaction.user.name}")
                await member.send(embed=dm_embed)
            except:
                pass
            
            await member.kick(reason=f"{reason} | By {interaction.user.name}")
            
            # Log action
            log_embed = discord.Embed(
                title="🦶 Member Kicked",
                color=0xED4245,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=True)
            log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.set_thumbnail(url=member.display_avatar.url)
            
            await log_moderation(interaction.guild, log_embed)
            await interaction.response.send_message(f"✅ Kicked {member.mention} - {reason}", ephemeral=True)
        
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to kick this member.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to kick: {e}", ephemeral=True)
    
    
    @bot.tree.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(
        member="Member to ban",
        reason="Reason for ban",
        delete_days="Days of messages to delete (0-7)"
    )
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban_command(
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
        delete_days: app_commands.Range[int, 0, 7] = 0
    ):
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ You cannot ban this member (role hierarchy).", ephemeral=True)
            return
        
        if member.id == interaction.guild.owner_id:
            await interaction.response.send_message("❌ You cannot ban the server owner.", ephemeral=True)
            return
        
        try:
            # DM user before banning
            try:
                dm_embed = discord.Embed(
                    title=f"Banned from {interaction.guild.name}",
                    description=f"**Reason:** {reason}",
                    color=0x5D3FD3,
                    timestamp=datetime.utcnow()
                )
                dm_embed.set_footer(text=f"Banned by {interaction.user.name}")
                await member.send(embed=dm_embed)
            except:
                pass
            
            await member.ban(
                reason=f"{reason} | By {interaction.user.name}",
                delete_message_days=delete_days
            )
            
            # Log action
            log_embed = discord.Embed(
                title="🔨 Member Banned",
                color=0x5D3FD3,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=True)
            log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.add_field(name="Messages Deleted", value=f"{delete_days} days", inline=True)
            log_embed.set_thumbnail(url=member.display_avatar.url)
            
            await log_moderation(interaction.guild, log_embed)
            await interaction.response.send_message(f"✅ Banned {member.mention} - {reason}", ephemeral=True)
        
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to ban this member.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to ban: {e}", ephemeral=True)
    
    
    @bot.tree.command(name="unban", description="Unban a user by ID")
    @app_commands.describe(user_id="User ID to unban", reason="Reason for unban")
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban_command(interaction: discord.Interaction, user_id: str, reason: str = "No reason provided"):
        try:
            uid = int(user_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid user ID.", ephemeral=True)
            return
        
        try:
            user = await bot.fetch_user(uid)
            await interaction.guild.unban(user, reason=f"{reason} | By {interaction.user.name}")
            
            # Log action
            log_embed = discord.Embed(
                title="✅ Member Unbanned",
                color=0x57F287,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=True)
            log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.set_thumbnail(url=user.display_avatar.url)
            
            await log_moderation(interaction.guild, log_embed)
            await interaction.response.send_message(f"✅ Unbanned {user.mention}", ephemeral=True)
        
        except discord.NotFound:
            await interaction.response.send_message("❌ User not found or not banned.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to unban.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to unban: {e}", ephemeral=True)
    
    
    @bot.tree.command(name="timeout", description="Timeout a member (Discord native timeout)")
    @app_commands.describe(
        member="Member to timeout",
        duration="Duration in minutes",
        reason="Reason for timeout"
    )
    @app_commands.checks.has_permissions(moderate_members=True)
    async def timeout_command(
        interaction: discord.Interaction,
        member: discord.Member,
        duration: app_commands.Range[int, 1, 40320],  # Max 28 days
        reason: str = "No reason provided"
    ):
        if member.top_role >= interaction.user.top_role:
            await interaction.response.send_message("❌ You cannot timeout this member (role hierarchy).", ephemeral=True)
            return
        
        try:
            until = discord.utils.utcnow() + timedelta(minutes=duration)
            await member.timeout(until, reason=f"{reason} | By {interaction.user.name}")
            
            # Log action
            log_embed = discord.Embed(
                title="⏰ Member Timed Out",
                color=0xFEE75C,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=True)
            log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Duration", value=f"{duration} minutes", inline=True)
            log_embed.add_field(name="Until", value=discord.utils.format_dt(until, "F"), inline=True)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.set_thumbnail(url=member.display_avatar.url)
            
            await log_moderation(interaction.guild, log_embed)
            await interaction.response.send_message(
                f"✅ Timed out {member.mention} for {duration} minutes - {reason}",
                ephemeral=True
            )
        
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to timeout this member.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to timeout: {e}", ephemeral=True)
    
    
    @bot.tree.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(member="Member to remove timeout from", reason="Reason for removal")
    @app_commands.checks.has_permissions(moderate_members=True)
    async def untimeout_command(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        try:
            await member.timeout(None, reason=f"{reason} | By {interaction.user.name}")
            
            # Log action
            log_embed = discord.Embed(
                title="✅ Timeout Removed",
                color=0x57F287,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=True)
            log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Reason", value=reason, inline=False)
            log_embed.set_thumbnail(url=member.display_avatar.url)
            
            await log_moderation(interaction.guild, log_embed)
            await interaction.response.send_message(f"✅ Removed timeout from {member.mention}", ephemeral=True)
        
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to remove timeout.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to remove timeout: {e}", ephemeral=True)
    
    
    @bot.tree.command(name="warn", description="Warn a member")
    @app_commands.describe(member="Member to warn", reason="Reason for warning")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warn_command(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        add_warning(interaction.guild_id, member.id, reason, str(interaction.user))
        warnings = get_warnings(interaction.guild_id, member.id)
        
        # DM user
        try:
            dm_embed = discord.Embed(
                title=f"⚠️ Warning in {interaction.guild.name}",
                description=f"**Reason:** {reason}\n**Total Warnings:** {len(warnings)}",
                color=0xFEE75C,
                timestamp=datetime.utcnow()
            )
            dm_embed.set_footer(text=f"Warned by {interaction.user.name}")
            await member.send(embed=dm_embed)
        except:
            pass
        
        # Log action
        log_embed = discord.Embed(
            title="⚠️ Member Warned",
            color=0xFEE75C,
            timestamp=datetime.utcnow()
        )
        log_embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=True)
        log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        log_embed.add_field(name="Total Warnings", value=str(len(warnings)), inline=True)
        log_embed.add_field(name="Reason", value=reason, inline=False)
        log_embed.set_thumbnail(url=member.display_avatar.url)
        
        await log_moderation(interaction.guild, log_embed)
        await interaction.response.send_message(
            f"✅ Warned {member.mention} - {reason}\nTotal warnings: {len(warnings)}",
            ephemeral=True
        )
    
    
    @bot.tree.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="Member to check warnings for")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def warnings_command(interaction: discord.Interaction, member: discord.Member):
        warnings = get_warnings(interaction.guild_id, member.id)
        
        if not warnings:
            await interaction.response.send_message(f"{member.mention} has no warnings.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title=f"Warnings for {member.name}",
            color=0xFEE75C
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        
        for idx, warning in enumerate(warnings, 1):
            timestamp = warning["timestamp"].strftime("%Y-%m-%d %H:%M UTC")
            embed.add_field(
                name=f"Warning #{idx}",
                value=f"**Reason:** {warning['reason']}\n**By:** {warning['moderator']}\n**Date:** {timestamp}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    
    @bot.tree.command(name="clearwarnings", description="Clear all warnings for a member")
    @app_commands.describe(member="Member to clear warnings for")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clearwarnings_command(interaction: discord.Interaction, member: discord.Member):
        clear_warnings(interaction.guild_id, member.id)
        
        # Log action
        log_embed = discord.Embed(
            title="🧹 Warnings Cleared",
            color=0x57F287,
            timestamp=datetime.utcnow()
        )
        log_embed.add_field(name="Member", value=f"{member.mention} ({member.id})", inline=True)
        log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
        log_embed.set_thumbnail(url=member.display_avatar.url)
        
        await log_moderation(interaction.guild, log_embed)
        await interaction.response.send_message(f"✅ Cleared all warnings for {member.mention}", ephemeral=True)
    
    
    @bot.tree.command(name="purge", description="Delete multiple messages")
    @app_commands.describe(amount="Number of messages to delete (1-100)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def purge_command(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]):
        await interaction.response.defer(ephemeral=True)
        
        try:
            deleted = await interaction.channel.purge(limit=amount)
            
            # Log action
            log_embed = discord.Embed(
                title="🧹 Messages Purged",
                color=0x57F287,
                timestamp=datetime.utcnow()
            )
            log_embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
            log_embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
            log_embed.add_field(name="Amount", value=str(len(deleted)), inline=True)
            
            await log_moderation(interaction.guild, log_embed)
            await interaction.followup.send(f"✅ Deleted {len(deleted)} messages.", ephemeral=True)
        
        except discord.Forbidden:
            await interaction.followup.send("❌ I don't have permission to delete messages.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"❌ Failed to purge: {e}", ephemeral=True)
    
    
    @bot.tree.command(name="modlog", description="Set the moderation log channel")
    @app_commands.describe(channel="Channel to send moderation logs to")
    @app_commands.checks.has_permissions(administrator=True)
    async def modlog_command(interaction: discord.Interaction, channel: discord.TextChannel):
        MOD_LOG_CHANNELS[interaction.guild_id] = channel.id
        await interaction.response.send_message(f"✅ Moderation logs will be sent to {channel.mention}", ephemeral=True)
    
    
    @bot.tree.command(name="slowmode", description="Set slowmode for a channel")
    @app_commands.describe(seconds="Slowmode delay in seconds (0 to disable)", channel="Channel (defaults to current)")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode_command(
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, 21600],
        channel: Optional[discord.TextChannel] = None
    ):
        target_channel = channel or interaction.channel
        
        try:
            await target_channel.edit(slowmode_delay=seconds)
            
            if seconds == 0:
                await interaction.response.send_message(f"✅ Disabled slowmode in {target_channel.mention}", ephemeral=True)
            else:
                await interaction.response.send_message(
                    f"✅ Set slowmode to {seconds} seconds in {target_channel.mention}",
                    ephemeral=True
                )
        
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to edit this channel.", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"❌ Failed to set slowmode: {e}", ephemeral=True)
