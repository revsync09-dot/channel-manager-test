"""
Reaction roles system - assign roles when users react to messages.
"""
import discord
from discord import app_commands
from typing import Dict, List


# Store reaction role configs: {guild_id: {message_id: [{emoji: str, role_id: int}]}}
REACTION_ROLES: Dict[int, Dict[int, List[dict]]] = {}


def init_reaction_roles(bot):
    """Initialize reaction role system"""
    
    @bot.listen("on_raw_reaction_add")
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
        await handle_reaction_role(bot, payload, add=True)
    
    @bot.listen("on_raw_reaction_remove")
    async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
        await handle_reaction_role(bot, payload, add=False)


async def handle_reaction_role(bot, payload: discord.RawReactionActionEvent, add: bool):
    """Handle reaction role assignment/removal"""
    # Skip if bot reaction
    if payload.user_id == bot.user.id:
        return
    
    guild_id = payload.guild_id
    if not guild_id or guild_id not in REACTION_ROLES:
        return
    
    message_id = payload.message_id
    if message_id not in REACTION_ROLES[guild_id]:
        return
    
    # Find matching role for this emoji
    emoji_str = str(payload.emoji)
    role_id = None
    
    for rr in REACTION_ROLES[guild_id][message_id]:
        if rr["emoji"] == emoji_str:
            role_id = rr["role_id"]
            break
    
    if not role_id:
        return
    
    # Get guild and member
    guild = bot.get_guild(guild_id)
    if not guild:
        return
    
    member = guild.get_member(payload.user_id)
    if not member:
        return
    
    role = guild.get_role(role_id)
    if not role:
        return
    
    # Add or remove role
    try:
        if add:
            if role not in member.roles:
                await member.add_roles(role, reason="Reaction role assignment")
        else:
            if role in member.roles:
                await member.remove_roles(role, reason="Reaction role removal")
    except discord.Forbidden:
        pass
    except discord.HTTPException:
        pass


def add_reaction_role(guild_id: int, message_id: int, emoji: str, role_id: int):
    """Add a reaction role configuration"""
    if guild_id not in REACTION_ROLES:
        REACTION_ROLES[guild_id] = {}
    
    if message_id not in REACTION_ROLES[guild_id]:
        REACTION_ROLES[guild_id][message_id] = []
    
    # Check if already exists
    for rr in REACTION_ROLES[guild_id][message_id]:
        if rr["emoji"] == emoji:
            rr["role_id"] = role_id
            return
    
    REACTION_ROLES[guild_id][message_id].append({
        "emoji": emoji,
        "role_id": role_id
    })


def remove_reaction_role(guild_id: int, message_id: int, emoji: str):
    """Remove a reaction role configuration"""
    if guild_id not in REACTION_ROLES:
        return
    
    if message_id not in REACTION_ROLES[guild_id]:
        return
    
    REACTION_ROLES[guild_id][message_id] = [
        rr for rr in REACTION_ROLES[guild_id][message_id] if rr["emoji"] != emoji
    ]
    
    # Clean up if empty
    if not REACTION_ROLES[guild_id][message_id]:
        del REACTION_ROLES[guild_id][message_id]
    
    if not REACTION_ROLES[guild_id]:
        del REACTION_ROLES[guild_id]


def get_reaction_roles(guild_id: int, message_id: int) -> List[dict]:
    """Get all reaction roles for a message"""
    if guild_id not in REACTION_ROLES:
        return []
    
    if message_id not in REACTION_ROLES[guild_id]:
        return []
    
    return REACTION_ROLES[guild_id][message_id]


def setup_reaction_role_commands(bot):
    """Setup reaction role slash commands"""
    
    @bot.tree.command(name="reactionrole_create", description="Create a reaction role panel")
    @app_commands.describe(
        channel="Channel to send the panel to",
        title="Title for the reaction role panel",
        description="Description for the panel"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_create(
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        description: str = "React below to get roles!"
    ):
        embed = discord.Embed(
            title=title,
            description=description,
            color=0x5865F2
        )
        embed.set_footer(text="React to get your roles!")
        
        message = await channel.send(embed=embed)
        
        await interaction.response.send_message(
            f"✅ Reaction role panel created! Message ID: `{message.id}`\n"
            f"Use `/reactionrole_add {message.id}` to add role reactions.",
            ephemeral=True
        )
    
    
    @bot.tree.command(name="reactionrole_add", description="Add a reaction role to a message")
    @app_commands.describe(
        message_id="Message ID to add the reaction role to",
        emoji="Emoji to react with",
        role="Role to assign"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_add(
        interaction: discord.Interaction,
        message_id: str,
        emoji: str,
        role: discord.Role
    ):
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return
        
        # Try to fetch message
        message = None
        for channel in interaction.guild.text_channels:
            try:
                message = await channel.fetch_message(msg_id)
                break
            except:
                continue
        
        if not message:
            await interaction.response.send_message("Message not found.", ephemeral=True)
            return
        
        # Add reaction to message
        try:
            await message.add_reaction(emoji)
        except discord.HTTPException:
            await interaction.response.send_message("Invalid emoji or couldn't add reaction.", ephemeral=True)
            return
        
        # Store configuration
        add_reaction_role(interaction.guild_id, msg_id, emoji, role.id)
        
        # Update embed if it's an embed message
        if message.embeds:
            embed = message.embeds[0]
            current_desc = embed.description or ""
            new_line = f"\n{emoji} - {role.mention}"
            
            # Check if role already in description
            if str(role.id) not in current_desc:
                embed.description = current_desc + new_line
                await message.edit(embed=embed)
        
        await interaction.response.send_message(
            f"✅ Added {emoji} → {role.mention} to message `{msg_id}`",
            ephemeral=True
        )
    
    
    @bot.tree.command(name="reactionrole_remove", description="Remove a reaction role from a message")
    @app_commands.describe(
        message_id="Message ID to remove the reaction role from",
        emoji="Emoji to remove"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_remove(
        interaction: discord.Interaction,
        message_id: str,
        emoji: str
    ):
        try:
            msg_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid message ID.", ephemeral=True)
            return
        
        # Try to fetch message
        message = None
        for channel in interaction.guild.text_channels:
            try:
                message = await channel.fetch_message(msg_id)
                break
            except:
                continue
        
        if not message:
            await interaction.response.send_message("Message not found.", ephemeral=True)
            return
        
        # Remove reaction from message
        try:
            await message.clear_reaction(emoji)
        except discord.HTTPException:
            pass
        
        # Remove configuration
        remove_reaction_role(interaction.guild_id, msg_id, emoji)
        
        await interaction.response.send_message(
            f"✅ Removed {emoji} from message `{msg_id}`",
            ephemeral=True
        )
    
    
    @bot.tree.command(name="reactionrole_list", description="List all reaction roles in this server")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reactionrole_list(interaction: discord.Interaction):
        guild_id = interaction.guild_id
        
        if guild_id not in REACTION_ROLES or not REACTION_ROLES[guild_id]:
            await interaction.response.send_message("No reaction roles configured.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="Reaction Roles Configuration",
            color=0x5865F2
        )
        
        for message_id, roles in REACTION_ROLES[guild_id].items():
            role_list = []
            for rr in roles:
                role = interaction.guild.get_role(rr["role_id"])
                role_name = role.mention if role else f"Unknown Role ({rr['role_id']})"
                role_list.append(f"{rr['emoji']} → {role_name}")
            
            embed.add_field(
                name=f"Message ID: {message_id}",
                value="\n".join(role_list),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
