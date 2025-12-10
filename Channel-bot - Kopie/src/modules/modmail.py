"""
Modmail system for private user-to-moderator communication.
Users can DM the bot to create modmail threads that staff can respond to.
"""
import discord
from discord import app_commands
from typing import Dict, Optional
import asyncio


# Store active modmail threads: {user_id: {"channel_id": int, "guild_id": int}}
MODMAIL_THREADS: Dict[int, dict] = {}


def init_modmail(bot):
    """Initialize modmail system"""
    @bot.listen("on_message")
    async def on_message(message: discord.Message):
        # Skip if bot message or in a guild
        if message.author.bot:
            return
        
        # Handle DM messages for modmail
        if isinstance(message.channel, discord.DMChannel):
            await handle_modmail_message(bot, message)


async def handle_modmail_message(bot, message: discord.Message):
    """Handle incoming DM messages for modmail"""
    user_id = message.author.id
    
    # Check if user has an active thread
    if user_id in MODMAIL_THREADS:
        thread_info = MODMAIL_THREADS[user_id]
        guild = bot.get_guild(thread_info["guild_id"])
        if guild:
            channel = guild.get_channel(thread_info["channel_id"])
            if channel:
                # Forward message to modmail channel
                embed = discord.Embed(
                    description=message.content,
                    color=0x5865F2,
                    timestamp=message.created_at
                )
                embed.set_author(
                    name=f"{message.author.name} ({message.author.id})",
                    icon_url=message.author.display_avatar.url
                )
                
                # Handle attachments
                files = []
                if message.attachments:
                    for attachment in message.attachments:
                        embed.add_field(name="Attachment", value=f"[{attachment.filename}]({attachment.url})", inline=False)
                
                await channel.send(embed=embed)
                await message.add_reaction("✅")
                return
    
    # New modmail - ask which server
    mutual_guilds = [g for g in bot.guilds if g.get_member(user_id)]
    
    if not mutual_guilds:
        await message.channel.send("You don't share any servers with this bot.")
        return
    
    if len(mutual_guilds) == 1:
        # Auto-create thread for single shared guild
        await create_modmail_thread(bot, message.author, mutual_guilds[0], message.content)
    else:
        # Let user select guild
        embed = discord.Embed(
            title="Select Server for Modmail",
            description="React with the number of the server you want to contact:",
            color=0x5865F2
        )
        
        for idx, guild in enumerate(mutual_guilds[:10], 1):
            embed.add_field(name=f"{idx}. {guild.name}", value=f"ID: {guild.id}", inline=False)
        
        msg = await message.channel.send(embed=embed)
        
        # Store pending modmail
        if not hasattr(bot, '_pending_modmail'):
            bot._pending_modmail = {}
        bot._pending_modmail[user_id] = {
            "guilds": mutual_guilds,
            "initial_message": message.content
        }


async def create_modmail_thread(bot, user: discord.User, guild: discord.Guild, initial_message: str):
    """Create a new modmail thread in the guild"""
    # Find or create modmail category
    modmail_category = discord.utils.get(guild.categories, name="Modmail")
    
    if not modmail_category:
        modmail_category = await guild.create_category("Modmail", reason="Modmail system setup")
    
    # Create thread channel
    thread_channel = await guild.create_text_channel(
        name=f"modmail-{user.name}-{user.discriminator}",
        category=modmail_category,
        reason=f"Modmail from {user.name}",
        topic=f"Modmail thread for {user.name} ({user.id})"
    )
    
    # Store thread info
    MODMAIL_THREADS[user.id] = {
        "channel_id": thread_channel.id,
        "guild_id": guild.id
    }
    
    # Send initial message to thread
    embed = discord.Embed(
        title=f"New Modmail from {user.name}",
        description=initial_message,
        color=0x5865F2,
        timestamp=discord.utils.utcnow()
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="User ID", value=str(user.id), inline=True)
    embed.add_field(name="Account Created", value=discord.utils.format_dt(user.created_at, "R"), inline=True)
    
    # Add user info
    member = guild.get_member(user.id)
    if member:
        embed.add_field(name="Joined Server", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)
        embed.add_field(name="Roles", value=", ".join([r.mention for r in member.roles[1:]]) or "None", inline=False)
    
    await thread_channel.send(embed=embed)
    
    # Notify user
    confirm_embed = discord.Embed(
        title="✅ Modmail Thread Created",
        description=f"Your message has been sent to the staff of **{guild.name}**.\n\nReply here to continue the conversation. Staff will see your messages.",
        color=0x57F287
    )
    await user.send(embed=confirm_embed)


async def close_modmail_thread(bot, channel: discord.TextChannel, closer: discord.Member, reason: str = None):
    """Close a modmail thread"""
    # Find user ID from thread
    user_id = None
    for uid, info in MODMAIL_THREADS.items():
        if info["channel_id"] == channel.id:
            user_id = uid
            break
    
    if user_id:
        # Remove from active threads
        del MODMAIL_THREADS[user_id]
        
        # Notify user
        try:
            user = await bot.fetch_user(user_id)
            close_embed = discord.Embed(
                title="Modmail Thread Closed",
                description=f"Your modmail thread in **{channel.guild.name}** has been closed by {closer.mention}.",
                color=0xED4245
            )
            if reason:
                close_embed.add_field(name="Reason", value=reason, inline=False)
            close_embed.add_field(name="Need Help?", value="Send a new DM to reopen modmail.", inline=False)
            await user.send(embed=close_embed)
        except:
            pass
    
    # Archive by moving to closed category or deleting
    closed_category = discord.utils.get(channel.guild.categories, name="Modmail - Closed")
    if not closed_category:
        closed_category = await channel.guild.create_category("Modmail - Closed", reason="Archive closed modmail")
    
    await channel.edit(
        category=closed_category,
        name=f"closed-{channel.name}",
        reason=f"Closed by {closer.name}"
    )
    
    # Send closure message
    close_log = discord.Embed(
        title="Thread Closed",
        description=f"Closed by {closer.mention}",
        color=0xED4245,
        timestamp=discord.utils.utcnow()
    )
    if reason:
        close_log.add_field(name="Reason", value=reason, inline=False)
    await channel.send(embed=close_log)


async def send_modmail_reply(bot, channel: discord.TextChannel, staff_member: discord.Member, content: str):
    """Send a reply from staff to user via modmail"""
    # Find user ID from thread
    user_id = None
    for uid, info in MODMAIL_THREADS.items():
        if info["channel_id"] == channel.id:
            user_id = uid
            break
    
    if not user_id:
        return False
    
    try:
        user = await bot.fetch_user(user_id)
        
        # Send to user
        reply_embed = discord.Embed(
            description=content,
            color=0x57F287,
            timestamp=discord.utils.utcnow()
        )
        reply_embed.set_author(
            name=f"{staff_member.name} (Staff)",
            icon_url=staff_member.display_avatar.url
        )
        reply_embed.set_footer(text=f"From {channel.guild.name}")
        
        await user.send(embed=reply_embed)
        
        # Confirm in channel
        confirm_embed = discord.Embed(
            description=content,
            color=0x57F287,
            timestamp=discord.utils.utcnow()
        )
        confirm_embed.set_author(
            name=f"{staff_member.name} (Staff Reply)",
            icon_url=staff_member.display_avatar.url
        )
        await channel.send(embed=confirm_embed)
        
        return True
    except:
        return False


def setup_modmail_commands(bot):
    """Setup modmail slash commands"""
    
    @bot.tree.command(name="modmail_reply", description="Reply to a modmail thread")
    @app_commands.describe(message="Your reply to the user")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def modmail_reply(interaction: discord.Interaction, message: str):
        if not interaction.channel.name.startswith("modmail-"):
            await interaction.response.send_message("This command only works in modmail threads.", ephemeral=True)
            return
        
        success = await send_modmail_reply(bot, interaction.channel, interaction.user, message)
        if success:
            await interaction.response.send_message("✅ Reply sent!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Failed to send reply. Thread may be closed.", ephemeral=True)
    
    
    @bot.tree.command(name="modmail_close", description="Close a modmail thread")
    @app_commands.describe(reason="Reason for closing (optional)")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def modmail_close(interaction: discord.Interaction, reason: str = None):
        if not interaction.channel.name.startswith("modmail-"):
            await interaction.response.send_message("This command only works in modmail threads.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await close_modmail_thread(bot, interaction.channel, interaction.user, reason)
        await interaction.followup.send("✅ Modmail thread closed.", ephemeral=True)
    
    
    @bot.tree.command(name="modmail_contact", description="Contact a user via modmail")
    @app_commands.describe(user="The user to contact", message="Your initial message")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def modmail_contact(interaction: discord.Interaction, user: discord.User, message: str):
        await interaction.response.defer(ephemeral=True)
        await create_modmail_thread(bot, user, interaction.guild, f"[Staff contacted you]\n\n{message}")
        await interaction.followup.send(f"✅ Modmail thread created with {user.mention}", ephemeral=True)
